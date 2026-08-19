"""DuMate 积分余额 API 服务。

从百度云 console 拉取 DuMate 积分余额，暴露为本地 REST API 供其他 agent 调用。

启动:
    python points_api.py
    # 或指定端口 / token
    python points_api.py --port 8765 --token my-secret-token
"""
import argparse
import base64
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import uuid

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from dumate_client import DumateClient, discover_user_id

APP_DATA = os.path.join(os.environ.get("APPDATA", ""), "qianfan-desktop-app")
KEY_FILE = os.path.join(APP_DATA, ".cookie-key")
AUTH_FILE = os.path.join(APP_DATA, "auth.json")
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "points_api.pid")

CONSOLE_BASE = "https://console.bce.baidu.com"
QUOTA_PATH = "/api/dumate/points/quota_overview"

# 绕过环境代理(127.0.0.1:8888 未运行)，直连百度云
SESSION = requests.Session()
SESSION.trust_env = False
SESSION.proxies = {"http": None, "https": None}
SESSION.headers.update({
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": CONSOLE_BASE,
    "Referer": CONSOLE_BASE + "/",
})

_cache = {"data": None, "ts": 0.0}
_cache_lock = threading.Lock()
CACHE_TTL = 60  # 秒


def decrypt(encoded: str, key: bytes) -> str:
    buf = base64.b64decode(encoded)
    iv, tag, ct = buf[:12], buf[12:28], buf[28:]
    return AESGCM(key).decrypt(iv, ct + tag, None).decode("utf-8")


def _cookie_header() -> str:
    with open(KEY_FILE, "rb") as f:
        key = f.read()
    with open(AUTH_FILE, "r", encoding="utf-8") as f:
        auth = json.load(f)
    cookies = json.loads(decrypt(auth["cookies"], key))
    parts = []
    for c in cookies:
        name = c.get("name", "")
        value = c.get("value", "")
        if not name or value in (None, "undefined", ""):
            continue
        val = value.strip('"')
        if any(ch in val for ch in ":|;= "):
            val = f'"{val}"'
        parts.append(f"{name}={val}")
    return "; ".join(parts)


def fetch_quota() -> dict:
    """调用百度云 quota_overview 接口，返回原始 result。"""
    tz = urllib.parse.quote("Asia/Shanghai")
    url = f"{CONSOLE_BASE}{QUOTA_PATH}?timezone={tz}&clientType=desktop&ignoreLoginBonus=true"
    resp = SESSION.get(url, headers={"Cookie": _cookie_header()}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0 or not data.get("success"):
        raise RuntimeError(f"cloud api error: {data.get('message') or data.get('code')}")
    return data["result"]


def get_balance(force: bool = False) -> dict:
    """获取积分余额（带 60s 缓存）。"""
    now = time.time()
    with _cache_lock:
        if not force and _cache["data"] and now - _cache["ts"] < CACHE_TTL:
            return _cache["data"]
    result = fetch_quota()
    total = float(result["totalPoints"])
    used = float(result["usedPoints"])
    available = round(total - used, 2)
    payload = {
        "totalPoints": total,
        "usedPoints": used,
        "availablePoints": available,
        "isSubscribed": result.get("isSubscribed", False),
        "subscriptionCount": len(result.get("subscription") or []),
        "incrementalCount": len(result.get("incremental") or []),
        "updatedAt": int(now),
    }
    with _cache_lock:
        _cache["data"] = payload
        _cache["ts"] = now
    return payload


app = FastAPI(title="DuMate Points API", version="1.1.0", docs_url=None, redoc_url=None)
API_TOKEN = os.environ.get("DUMATE_API_TOKEN", "")


def _auth(x_api_key: str = Header(default=""), authorization: str = Header(default="")):
    """同时支持 X-API-Key 与 Authorization: Bearer <token>。"""
    token = x_api_key
    if not token and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if API_TOKEN and token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid api token")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/points/balance")
def points_balance(_: None = Depends(_auth)):
    try:
        return get_balance()
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": str(e)})


@app.get("/api/points/balance/refresh")
def points_balance_refresh(_: None = Depends(_auth)):
    try:
        return get_balance(force=True)
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": str(e)})


# ---------- OpenAI 兼容接口 ----------

MODEL_NAME = "dumate-points"

# DuMate 三种模型模式：lite / turbo / ultra（对应请求头 X-Dumate-AutoModel-Level 的 L0/L1/L2）
MODEL_LEVELS = {
    "dumate-lite": "lite",
    "dumate-turbo": "turbo",
    "dumate-ultra": "ultra",
}
ALL_MODELS = ["dumate-points", "dumate-lite", "dumate-turbo", "dumate-ultra"]

# Claude 客户端（如 Claude Code）默认模型名 -> DuMate 模式映射
LEVEL_HINTS = (
    ("haiku", "lite"), ("lite", "lite"),
    ("sonnet", "turbo"), ("turbo", "turbo"),
    ("opus", "ultra"), ("ultra", "ultra"),
)


def _resolve_level(model: str):
    """把模型名解析为 lite/turbo/ultra。

    dumate-lite/turbo/ultra 直接映射；claude-haiku/sonnet/opus 等客户端默认
    模型名按档位映射；其他返回 None（DuMate 默认模式）。
    """
    m = (model or "").strip().lower()
    if m in MODEL_LEVELS:
        return MODEL_LEVELS[m]
    for hint, level in LEVEL_HINTS:
        if hint in m:
            return level
    return None

POINTS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_points_balance",
        "description": "查询百度搭子(DuMate)的积分余额，返回总积分、已用积分和可用积分",
        "parameters": {"type": "object", "properties": {}},
    },
}

POINTS_KEYWORDS = ("积分", "余额", "点数", "额度", "points", "balance", "quota", "dumate", "搭子")

# ---------- 任务执行工具（OpenAI 兼容） ----------

TASK_CREATE_KEYWORDS = ("创建任务", "新建任务", "新建会话", "新开任务", "create task", "create_task")
TASK_READ_KEYWORDS = ("读取结果", "查看结果", "任务结果", "读取消息", "消息列表", "get_task_messages", "get messages")
TASK_EXEC_KEYWORDS = ("执行任务", "帮我", "请写", "写一个", "写文件", "生成", "修改", "创建文件", "对话", "回答", "task", "任务", "工作")

TASK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "创建一个 DuMate 任务会话，返回 task_id（后续发送消息用）",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务标题"},
                    "directory": {"type": "string", "description": "工作目录，省略时用默认目录"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_task_message",
            "description": "向指定任务发送消息并执行（对话、内容生成、修改文件等），返回任务回复",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "任务 ID（由 create_task 返回）"},
                    "message": {"type": "string", "description": "要执行的任务描述"},
                },
                "required": ["task_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_messages",
            "description": "读取指定任务的全部消息与结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "任务 ID"},
                },
                "required": ["task_id"],
            },
        },
    },
]

ALL_TOOLS = [POINTS_TOOL] + TASK_TOOLS


def _declared_tools(body) -> set:
    names = set()
    for t in body.get("tools") or []:
        if not isinstance(t, dict) or t.get("type") != "function":
            continue
        fn = t.get("function") or {}
        name = fn.get("name") or t.get("name")
        if name:
            names.add(name)
    return names


def _route_tool(text: str, declared: set):
    tl = text.lower()
    if _mentions_points(tl) and "get_points_balance" in declared:
        return "get_points_balance"
    if any(k in tl for k in TASK_CREATE_KEYWORDS) and "create_task" in declared:
        return "create_task"
    if any(k in tl for k in TASK_READ_KEYWORDS) and "get_task_messages" in declared:
        return "get_task_messages"
    if any(k in tl for k in TASK_EXEC_KEYWORDS) and "send_task_message" in declared:
        return "send_task_message"
    return None


def _suggest_args(name: str, text: str) -> dict:
    if name == "create_task":
        return {"title": text.strip()[:30] or "新任务"}
    if name == "send_task_message":
        return {"message": text}
    return {}


def _make_tool_call(name: str, args: dict) -> dict:
    return {
        "id": "call_" + uuid.uuid4().hex[:24],
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
    }


def _find_tool_call(messages):
    """从 chat 消息中提取最近一轮的工具调用（name, arguments），遇到 user 消息即停止。"""
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") == "assistant" and m.get("tool_calls"):
            tc = m["tool_calls"][0]
            fn = tc.get("function", {})
            return fn.get("name"), fn.get("arguments", "{}")
        if m.get("role") == "user":
            break
    return None, "{}"


def _find_responses_tool_call(inp):
    """从 responses input 中提取最近一轮的工具调用（name, arguments），遇到 user 消息即停止。"""
    if not isinstance(inp, list):
        return None, "{}"
    for item in reversed(inp):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call":
            return item.get("name"), item.get("arguments", "{}")
        if item.get("role") == "user":
            break
    return None, "{}"


def _execute_tool(name, args_str, level: str = None) -> str:
    """执行工具并返回 JSON 字符串结果（服务端真正调用 DuMate）。level: lite/turbo/ultra。"""
    try:
        args = json.loads(args_str or "{}")
    except Exception:
        args = {}
    try:
        if name == "get_points_balance":
            return json.dumps(get_balance(), ensure_ascii=False)
        if name == "create_task":
            title = (args.get("title") or "新任务").strip()
            directory = (args.get("directory") or _default_dir()).strip()
            client = DumateClient()
            sess = client.create_session(title, directory)
            return json.dumps({
                "task_id": sess["id"],
                "title": sess.get("title", title),
                "directory": sess.get("directory", directory),
            }, ensure_ascii=False)
        if name == "send_task_message":
            task_id = (args.get("task_id") or "").strip()
            message = (args.get("message") or "").strip()
            if not task_id or not message:
                return json.dumps({"error": "task_id and message are required"}, ensure_ascii=False)
            client = DumateClient()
            client.send_message(task_id, message, model_level=level, timeout=300)
            msgs = client.get_messages(task_id)
            return json.dumps({"task_id": task_id, "reply": _extract_reply(msgs)}, ensure_ascii=False)
        if name == "get_task_messages":
            task_id = (args.get("task_id") or "").strip()
            if not task_id:
                return json.dumps({"error": "task_id is required"}, ensure_ascii=False)
            client = DumateClient()
            msgs = client.get_messages(task_id)
            return json.dumps({"task_id": task_id, "messages": _simplify_messages(msgs)}, ensure_ascii=False)
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"{name} failed: {e}"}, ensure_ascii=False)


def _fallback_text(json_mode: bool) -> str:
    msg = "我是 DuMate 助手，可以查询积分余额，或让我执行任务（对话、内容生成、修改文件等）。"
    if json_mode:
        return json.dumps({"message": msg}, ensure_ascii=False)
    return msg


_default_session = {"id": None, "lock": threading.Lock()}


def _default_session_id() -> str:
    """懒创建并复用默认会话，让连续消息保持对话上下文。"""
    with _default_session["lock"]:
        if _default_session["id"]:
            return _default_session["id"]
        client = DumateClient()
        sess = client.create_session("默认会话", _default_dir())
        _default_session["id"] = sess["id"]
        return sess["id"]


def _chat_with_dumate(text: str, level: str = None) -> str:
    """把消息转发给 DuMate 执行（消耗积分），只返回回复文本。level: lite/turbo/ultra。"""
    client = DumateClient()
    sid = _default_session_id()
    client.send_message(sid, text, model_level=level, timeout=300)
    msgs = client.get_messages(sid)
    reply = _extract_reply(msgs)
    if isinstance(reply, dict):
        return reply.get("content") or ""
    return str(reply)


def _text_of(msg) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") in ("text", "input_text"):
                parts.append(c.get("text", ""))
        return " ".join(parts)
    return ""


def _mentions_points(text: str) -> bool:
    tl = text.lower()
    return any(k in tl for k in POINTS_KEYWORDS)


def _balance_text(b: dict) -> str:
    return (
        f"当前 DuMate 积分余额：可用 {b['availablePoints']} 积分"
        f"（总 {b['totalPoints']}，已用 {b['usedPoints']}）。"
        f"订阅状态：{'已订阅' if b['isSubscribed'] else '未订阅'}，"
        f"含 {b['subscriptionCount']} 个订阅包、{b['incrementalCount']} 个增量包。"
    )


def _balance_content(b: dict, json_mode: bool, schema: dict | None = None) -> str:
    """根据 response_format 生成最终答复：JSON 模式返回结构化数据，否则返回自然语言。"""
    if not json_mode:
        return _balance_text(b)
    data = b
    props = (schema or {}).get("properties") if isinstance(schema, dict) else None
    if isinstance(props, dict):
        data = {k: b[k] for k in props if k in b}
    return json.dumps(data, ensure_ascii=False)


def _chat_base(model: str = MODEL_NAME) -> dict:
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex[:24],
        "created": int(time.time()),
        "model": model,
    }


def _chat_json(content, tool_calls, finish, model: str = MODEL_NAME) -> dict:
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    resp = _chat_base(model)
    resp["object"] = "chat.completion"
    resp["choices"] = [{"index": 0, "message": msg, "finish_reason": finish}]
    resp["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return resp


def _chat_stream(content, tool_calls, finish, model: str = MODEL_NAME):
    def gen():
        def chunk(payload):
            resp = _chat_base(model)
            resp["object"] = "chat.completion.chunk"
            resp["choices"] = payload
            return "data: " + json.dumps(resp, ensure_ascii=False) + "\n\n"

        if tool_calls:
            tc = tool_calls[0]
            yield chunk([{"index": 0, "delta": {
                "role": "assistant",
                "tool_calls": [{"index": 0, "id": tc["id"], "type": "function",
                                "function": {"name": tc["function"]["name"], "arguments": ""}}],
            }, "finish_reason": None}])
            yield chunk([{"index": 0, "delta": {
                "tool_calls": [{"index": 0, "function": {"arguments": tc["function"]["arguments"]}}],
            }, "finish_reason": None}])
            yield chunk([{"index": 0, "delta": {}, "finish_reason": finish}])
        else:
            yield chunk([{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}])
            yield chunk([{"index": 0, "delta": {"content": content}, "finish_reason": None}])
            yield chunk([{"index": 0, "delta": {}, "finish_reason": finish}])
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/v1/models")
def list_models(_: None = Depends(_auth)):
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "created": 0, "owned_by": "dumate"} for m in ALL_MODELS],
    }


@app.post("/v1/chat/completions")
def chat_completions(body: dict, _: None = Depends(_auth)):
    messages = body.get("messages", []) or []
    stream = bool(body.get("stream", False))
    has_tools = bool(body.get("tools"))
    declared = _declared_tools(body)
    level = _resolve_level(body.get("model") or "")
    # 仅当最后一条是 tool 消息时才视为第二轮（避免历史工具结果导致后续请求误判）
    has_tool_result = bool(messages) and isinstance(messages[-1], dict) and messages[-1].get("role") == "tool"

    response_format = body.get("response_format") or {}
    fmt_type = response_format.get("type") if isinstance(response_format, dict) else None
    json_mode = fmt_type in ("json_object", "json_schema")
    schema = response_format.get("json_schema") if isinstance(response_format, dict) else None

    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = _text_of(m)
            break

    content, tool_calls, finish = None, None, "stop"
    try:
        if has_tool_result:
            # 第二轮：执行工具并返回真实结果
            tool_name, tool_args = _find_tool_call(messages)
            content = _execute_tool(tool_name, tool_args, level)
        elif has_tools:
            tool_name = _route_tool(last_user, declared)
            if tool_name:
                tool_calls = [_make_tool_call(tool_name, _suggest_args(tool_name, last_user))]
                finish = "tool_calls"
            elif last_user:
                content = _chat_with_dumate(last_user, level)
            else:
                content = _fallback_text(json_mode)
        elif _mentions_points(last_user):
            content = _balance_content(get_balance(), json_mode, schema)
        elif last_user:
            content = _chat_with_dumate(last_user, level)
        else:
            content = _fallback_text(json_mode)
    except Exception as e:
        content = f"执行失败：{e}"
        if json_mode:
            content = json.dumps({"error": str(e)}, ensure_ascii=False)

    if stream:
        return _chat_stream(content, tool_calls, finish, (body.get("model") or MODEL_NAME).strip())
    return _chat_json(content, tool_calls, finish, (body.get("model") or MODEL_NAME).strip())


# ---------- OpenAI Responses API 兼容接口 ----------

def _parse_responses_input(inp):
    """解析 /v1/responses 的 input，返回 (用户文本, 是否含工具结果)。

    仅当最后一条是 function_call_output 时才视为第二轮，避免历史工具结果误判。
    """
    user_text = ""
    if isinstance(inp, str):
        user_text = inp
    elif isinstance(inp, list):
        for item in inp:
            if not isinstance(item, dict):
                continue
            if item.get("role") == "user":
                content = item.get("content")
                if isinstance(content, str):
                    user_text = content
                elif isinstance(content, list):
                    parts = []
                    for c in content:
                        if isinstance(c, dict) and c.get("type") in ("input_text", "text"):
                            parts.append(c.get("text", ""))
                    user_text = " ".join(parts)
    has_tool_output = (
        isinstance(inp, list) and bool(inp) and isinstance(inp[-1], dict)
        and inp[-1].get("type") == "function_call_output"
    )
    return user_text, has_tool_output


def _resp_base(model: str = MODEL_NAME) -> dict:
    return {
        "id": "resp_" + uuid.uuid4().hex[:24],
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
    }


def _resp_message(text: str) -> dict:
    return {
        "type": "message",
        "id": "msg_" + uuid.uuid4().hex[:24],
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }


def _resp_function_call_for(name: str, args: dict) -> dict:
    return {
        "type": "function_call",
        "id": "fc_" + uuid.uuid4().hex[:24],
        "call_id": "call_" + uuid.uuid4().hex[:24],
        "name": name,
        "arguments": json.dumps(args, ensure_ascii=False),
        "status": "completed",
    }


def _resp_function_call() -> dict:
    return _resp_function_call_for("get_points_balance", {})


def _resp_stream(output):
    def gen():
        def ev(event, data):
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        base = _resp_base()
        yield ev("response.created", {"type": "response.created", "response": {**base, "output": [], "status": "in_progress"}})
        for item in output:
            yield ev("response.output_item.added", {"type": "response.output_item.added", "output_index": 0, "item": item})
            if item["type"] == "message":
                text = item["content"][0]["text"]
                yield ev("response.content_part.added", {"type": "response.content_part.added", "item_id": item["id"], "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}})
                yield ev("response.output_text.delta", {"type": "response.output_text.delta", "item_id": item["id"], "output_index": 0, "content_index": 0, "delta": text})
                yield ev("response.output_text.done", {"type": "response.output_text.done", "item_id": item["id"], "output_index": 0, "content_index": 0, "text": text})
                yield ev("response.content_part.done", {"type": "response.content_part.done", "item_id": item["id"], "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": text}})
            yield ev("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": item})
        yield ev("response.completed", {"type": "response.completed", "response": {**base, "output": output, "status": "completed"}})
        yield ev("response.done", {"type": "response.done", "response": {**base, "output": output, "status": "completed"}})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/v1/responses")
def responses_api(body: dict, _: None = Depends(_auth)):
    inp = body.get("input", "")
    stream = bool(body.get("stream", False))
    has_tools = bool(body.get("tools"))
    declared = _declared_tools(body)
    level = _resolve_level(body.get("model") or "")
    user_text, has_tool_output = _parse_responses_input(inp)

    # text.format 对应 response_format
    text_cfg = body.get("text") or {}
    fmt = text_cfg.get("format") if isinstance(text_cfg, dict) else None
    fmt_type = fmt.get("type") if isinstance(fmt, dict) else None
    json_mode = fmt_type in ("json_object", "json_schema")
    schema = fmt.get("schema") if isinstance(fmt, dict) and fmt_type == "json_schema" else None

    try:
        if has_tool_output:
            # 第二轮：执行工具并返回真实结果
            tool_name, tool_args = _find_responses_tool_call(inp)
            output = [_resp_message(_execute_tool(tool_name, tool_args, level))]
        elif has_tools:
            tool_name = _route_tool(user_text, declared)
            if tool_name:
                output = [_resp_function_call_for(tool_name, _suggest_args(tool_name, user_text))]
            elif user_text:
                output = [_resp_message(_chat_with_dumate(user_text, level))]
            else:
                output = [_resp_message(_fallback_text(json_mode))]
        elif _mentions_points(user_text):
            output = [_resp_message(_balance_content(get_balance(), json_mode, schema))]
        elif user_text:
            output = [_resp_message(_chat_with_dumate(user_text, level))]
        else:
            output = [_resp_message(_fallback_text(json_mode))]
    except Exception as e:
        msg = f"执行失败：{e}"
        if json_mode:
            msg = json.dumps({"error": str(e)}, ensure_ascii=False)
        output = [_resp_message(msg)]

    if stream:
        return _resp_stream(output)
    resp = _resp_base((body.get("model") or MODEL_NAME).strip())
    resp["status"] = "completed"
    resp["output"] = output
    resp["usage"] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    return resp


# ---------- 任务执行 API（消耗积分） ----------

def _default_dir() -> str:
    home = os.environ.get("USERPROFILE", "")
    uid = discover_user_id()
    if uid:
        return os.path.join(home, ".qianfan", "workspace", uid)
    return os.path.join(home, ".qianfan", "workspace")


def _simplify_messages(messages: list) -> list:
    out = []
    for m in messages:
        info = m.get("info", {})
        texts = [p.get("text", "") for p in m.get("parts", []) if p.get("type") == "text"]
        out.append({
            "role": info.get("role"),
            "content": "\n".join(texts),
            "id": info.get("id"),
            "error": info.get("error"),
            "created_at": (info.get("time") or {}).get("created"),
        })
    return out


def _extract_reply(messages: list):
    """从消息列表提取最后一条 assistant 文本回复。"""
    for m in reversed(messages):
        info = m.get("info", {})
        if info.get("role") != "assistant":
            continue
        texts = [p.get("text", "") for p in m.get("parts", []) if p.get("type") == "text"]
        if texts or info.get("error"):
            return {"role": "assistant", "content": "\n".join(texts), "error": info.get("error")}
    return None


@app.post("/api/tasks")
def create_task(body: dict, _: None = Depends(_auth)):
    title = (body.get("title") or "新任务").strip()
    directory = (body.get("directory") or _default_dir()).strip()
    if not directory:
        raise HTTPException(status_code=400, detail="directory is required")
    client = DumateClient()
    try:
        sess = client.create_session(title, directory)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"create session failed: {e}")
    return {
        "task_id": sess["id"],
        "session_id": sess["id"],
        "title": sess.get("title", title),
        "directory": sess.get("directory", directory),
        "created_at": (sess.get("time") or {}).get("created"),
    }


@app.get("/api/tasks")
def list_tasks(_: None = Depends(_auth)):
    client = DumateClient()
    try:
        sessions = client.list_sessions()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"list sessions failed: {e}")
    tasks = []
    for s in sessions:
        tasks.append({
            "task_id": s.get("id"),
            "title": s.get("title", ""),
            "directory": s.get("directory", ""),
            "created_at": (s.get("time") or {}).get("created"),
            "updated_at": (s.get("time") or {}).get("updated"),
        })
    return {"tasks": tasks}


@app.post("/api/tasks/{task_id}/messages")
def send_task_message(task_id: str, body: dict, _: None = Depends(_auth)):
    message = (body.get("message") or body.get("text") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    sync = bool(body.get("sync", True))
    level = _resolve_level(body.get("model") or body.get("model_level") or "")
    client = DumateClient()
    if sync:
        try:
            client.send_message(task_id, message, model_level=level, timeout=300)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"send message failed: {e}")
        try:
            msgs = client.get_messages(task_id)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"read messages failed: {e}")
        return {"task_id": task_id, "reply": _extract_reply(msgs), "messages": _simplify_messages(msgs)}
    # 异步：后台线程发送，立即返回
    def worker():
        try:
            client.send_message(task_id, message, model_level=level, timeout=300)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()
    return {"task_id": task_id, "accepted": True, "poll": f"/api/tasks/{task_id}/messages"}


@app.get("/api/tasks/{task_id}/messages")
def get_task_messages(task_id: str, _: None = Depends(_auth)):
    client = DumateClient()
    try:
        msgs = client.get_messages(task_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"read messages failed: {e}")
    return {"task_id": task_id, "messages": _simplify_messages(msgs)}


# ---------- Anthropic Claude 兼容接口 ----------

def _claude_text_of(msg) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
        return " ".join(parts)
    return ""


def _claude_last_tool_result(messages):
    """最后一条 user 消息里含 tool_result 时返回它，视为工具第二轮。"""
    if not messages or not isinstance(messages[-1], dict):
        return None
    m = messages[-1]
    if m.get("role") != "user":
        return None
    content = m.get("content")
    if not isinstance(content, list):
        return None
    for c in content:
        if isinstance(c, dict) and c.get("type") == "tool_result":
            return c
    return None


def _find_claude_tool_call(messages):
    """提取最近一条 assistant 消息中的 tool_use（name, input JSON）。

    Claude 格式中 tool_result 挂在 user 消息的 content 里，遇到 user 不能停，
    需继续向上找最近的 assistant tool_use。
    """
    for m in reversed(messages):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        content = m.get("content")
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    return c.get("name"), json.dumps(c.get("input") or {}, ensure_ascii=False)
    return None, "{}"


def _declared_claude_tools(body) -> set:
    names = set()
    for t in body.get("tools") or []:
        if isinstance(t, dict) and t.get("name"):
            names.add(t["name"])
    return names


def _claude_message(blocks: list, model: str, stop_reason: str) -> dict:
    return {
        "id": "msg_" + uuid.uuid4().hex[:24],
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def _claude_stream(blocks: list, model: str, stop_reason: str):
    def gen():
        def ev(event, data):
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        msg_base = {
            "id": "msg_" + uuid.uuid4().hex[:24],
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
        yield ev("message_start", {"type": "message_start", "message": msg_base})
        for i, b in enumerate(blocks):
            if b["type"] == "text":
                yield ev("content_block_start", {"type": "content_block_start", "index": i,
                                                 "content_block": {"type": "text", "text": ""}})
                yield ev("content_block_delta", {"type": "content_block_delta", "index": i,
                                                 "delta": {"type": "text_delta", "text": b["text"]}})
            else:
                yield ev("content_block_start", {"type": "content_block_start", "index": i,
                                                 "content_block": {"type": "tool_use", "id": b["id"],
                                                                   "name": b["name"], "input": {}}})
                yield ev("content_block_delta", {"type": "content_block_delta", "index": i,
                                                 "delta": {"type": "input_json_delta",
                                                           "partial_json": json.dumps(b.get("input") or {}, ensure_ascii=False)}})
            yield ev("content_block_stop", {"type": "content_block_stop", "index": i})
        yield ev("message_delta", {"type": "message_delta",
                                   "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                                   "usage": {"output_tokens": 0}})
        yield ev("message_stop", {"type": "message_stop"})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/v1/messages")
def claude_messages(body: dict, _: None = Depends(_auth)):
    messages = body.get("messages", []) or []
    stream = bool(body.get("stream", False))
    model = (body.get("model") or "dumate-turbo").strip()
    level = _resolve_level(model)
    has_tools = bool(body.get("tools"))
    declared = _declared_claude_tools(body)

    last_user = ""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user = _claude_text_of(m)
            break

    stop_reason = "end_turn"
    blocks = []
    try:
        tool_result = _claude_last_tool_result(messages)
        if tool_result is not None:
            # 第二轮：执行工具并返回真实结果
            tool_name, tool_args = _find_claude_tool_call(messages)
            blocks = [{"type": "text", "text": _execute_tool(tool_name, tool_args, level)}]
        elif has_tools:
            tool_name = _route_tool(last_user, declared)
            if tool_name:
                blocks = [{"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:24],
                           "name": tool_name, "input": _suggest_args(tool_name, last_user)}]
                stop_reason = "tool_use"
            elif last_user:
                blocks = [{"type": "text", "text": _chat_with_dumate(last_user, level)}]
            else:
                blocks = [{"type": "text", "text": _fallback_text(False)}]
        elif _mentions_points(last_user):
            blocks = [{"type": "text", "text": _balance_content(get_balance(), False, None)}]
        elif last_user:
            blocks = [{"type": "text", "text": _chat_with_dumate(last_user, level)}]
        else:
            blocks = [{"type": "text", "text": _fallback_text(False)}]
    except Exception as e:
        blocks = [{"type": "text", "text": f"执行失败：{e}"}]

    if stream:
        return _claude_stream(blocks, model, stop_reason)
    return _claude_message(blocks, model, stop_reason)


@app.post("/v1/messages/count_tokens")
def claude_count_tokens(body: dict, _: None = Depends(_auth)):
    total = 0
    for m in body.get("messages") or []:
        if isinstance(m, dict):
            total += len(_claude_text_of(m)) // 4 + 1
    return {"input_tokens": total}


def main():
    parser = argparse.ArgumentParser(description="DuMate points balance API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="", help="API token; 为空则不鉴权")
    args = parser.parse_args()
    global API_TOKEN
    if args.token:
        API_TOKEN = args.token
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    import uvicorn
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


if __name__ == "__main__":
    main()

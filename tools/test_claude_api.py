"""Claude 兼容接口端到端测试：/v1/messages 非流式 / 流式 / 工具调用 / count_tokens。"""
import json
import sys
import os

import requests

BASE = "http://127.0.0.1:8765"
TOKEN = open(os.path.join(os.path.dirname(__file__), "..", "token.txt")).read().strip()
H = {"x-api-key": TOKEN, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}

PASSED = []
FAILED = []


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name} {detail}")


def main():
    # 1. 非流式：积分查询（Claude 格式，不消耗积分）
    print("== 1. Claude 非流式 - 积分查询 ==")
    r = requests.post(f"{BASE}/v1/messages", headers=H, json={
        "model": "dumate-turbo", "max_tokens": 1024,
        "messages": [{"role": "user", "content": "查询积分余额"}],
    }, timeout=60)
    data = r.json()
    check("http 200", r.status_code == 200, str(data)[:200])
    check("type=message", data.get("type") == "message")
    check("content 有 text 块", isinstance(data.get("content"), list)
          and any(b.get("type") == "text" for b in data["content"]))
    text = data["content"][0]["text"]
    check("返回余额文本", "积分" in text, text[:120])
    check("stop_reason=end_turn", data.get("stop_reason") == "end_turn")
    print(f"    -> {text[:100]}")

    # 2. 非流式：Claude 默认模型名映射（sonnet -> turbo）
    print("== 2. Claude 默认模型名（claude-sonnet-4-5）对话 ==")
    r = requests.post(f"{BASE}/v1/messages", headers=H, json={
        "model": "claude-sonnet-4-5-20250929", "max_tokens": 1024,
        "messages": [{"role": "user", "content": "用一句话介绍你自己"}],
    }, timeout=300)
    data = r.json()
    text = (data.get("content") or [{}])[0].get("text", "")
    check("sonnet 模型可对话", r.status_code == 200 and len(text) > 5, text[:150])
    print(f"    -> {text[:100]}")

    # 3. 流式
    print("== 3. Claude 流式 ==")
    r = requests.post(f"{BASE}/v1/messages", headers=H, stream=True, json={
        "model": "dumate-lite", "max_tokens": 1024, "stream": True,
        "messages": [{"role": "user", "content": "回复：流式测试通过"}],
    }, timeout=300)
    events = []
    text_parts = []
    for line in r.iter_lines(decode_unicode=True):
        if line.startswith("event: "):
            events.append(line[7:])
        elif line.startswith("data: "):
            d = json.loads(line[6:])
            if d.get("type") == "content_block_delta":
                text_parts.append(d["delta"].get("text", ""))
    check("流式事件序列",
          events[:1] == ["message_start"] and "content_block_stop" in events
          and events[-1] == "message_stop", str(events))
    check("流式有文本", len("".join(text_parts)) > 0)
    print(f"    -> {''.join(text_parts)[:100]}")

    # 4. 工具调用两轮
    print("== 4. Claude 工具调用（第一轮 -> tool_use）==")
    tools = [{
        "name": "get_points_balance",
        "description": "查询百度搭子(DuMate)的积分余额，返回总积分、已用积分和可用积分",
        "input_schema": {"type": "object", "properties": {}},
    }]
    r = requests.post(f"{BASE}/v1/messages", headers=H, json={
        "model": "dumate-turbo", "max_tokens": 1024, "tools": tools,
        "messages": [{"role": "user", "content": "帮我查一下积分余额还有多少"}],
    }, timeout=60)
    data = r.json()
    blocks = data.get("content") or []
    tu = next((b for b in blocks if b.get("type") == "tool_use"), None)
    check("返回 tool_use 块", tu is not None, str(data)[:200])
    check("stop_reason=tool_use", data.get("stop_reason") == "tool_use")
    check("工具名正确", tu and tu.get("name") == "get_points_balance")

    print("== 4b. Claude 工具调用（第二轮 -> 真实结果）==")
    if tu:
        r2 = requests.post(f"{BASE}/v1/messages", headers=H, json={
            "model": "dumate-turbo", "max_tokens": 1024, "tools": tools,
            "messages": [
                {"role": "user", "content": "帮我查一下积分余额还有多少"},
                {"role": "assistant", "content": [tu]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tu["id"], "content": "..."}]},
            ],
        }, timeout=60)
        d2 = r2.json()
        t2 = (d2.get("content") or [{}])[0].get("text", "")
        check("第二轮返回余额 JSON", "availablePoints" in t2 or "积分" in t2, t2[:150])
        print(f"    -> {t2[:120]}")

    # 5. count_tokens
    print("== 5. Claude count_tokens ==")
    r = requests.post(f"{BASE}/v1/messages/count_tokens", headers=H, json={
        "model": "dumate-turbo",
        "messages": [{"role": "user", "content": "你好世界" * 10}],
    }, timeout=30)
    check("count_tokens 返回", r.status_code == 200 and "input_tokens" in r.json(), r.text[:100])

    # 6. Bearer 鉴权（Claude Code 用 ANTHROPIC_AUTH_TOKEN 时发 Bearer）
    print("== 6. Bearer 鉴权 ==")
    r = requests.post(f"{BASE}/v1/messages",
                      headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                      json={"model": "dumate-turbo", "max_tokens": 16,
                            "messages": [{"role": "user", "content": "查询积分余额"}]},
                      timeout=60)
    check("Bearer 可用", r.status_code == 200, r.text[:100])

    # 7. 无鉴权 401
    print("== 7. 无鉴权 401 ==")
    r = requests.post(f"{BASE}/v1/messages", json={
        "model": "dumate-turbo", "max_tokens": 16,
        "messages": [{"role": "user", "content": "hi"}],
    }, timeout=10)
    check("无鉴权 401", r.status_code == 401)

    # 8. 回归：OpenAI chat 接口
    print("== 8. 回归 OpenAI chat/completions ==")
    r = requests.post(f"{BASE}/v1/chat/completions",
                      headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                      json={"model": "dumate-points", "messages": [{"role": "user", "content": "查询积分余额"}]},
                      timeout=60)
    d = r.json()
    check("OpenAI 回归", r.status_code == 200 and "积分" in (d.get("choices") or [{}])[0].get("message", {}).get("content", ""),
          r.text[:200])

    print()
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        print("失败项:", FAILED)
        sys.exit(1)


if __name__ == "__main__":
    main()

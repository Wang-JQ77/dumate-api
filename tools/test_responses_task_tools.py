"""Responses API 任务工具测试：create_task / send_task_message 两轮调用。"""
import json
import os

import requests

token = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "token.txt")).read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}

TASK_TOOLS = [
    {"type": "function", "name": "create_task", "description": "创建任务会话", "parameters": {"type": "object", "properties": {"title": {"type": "string"}}}},
    {"type": "function", "name": "send_task_message", "description": "发送任务消息", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "message": {"type": "string"}}, "required": ["task_id", "message"]}},
]


def resp(body):
    r = requests.post(base + "/v1/responses", headers=h, json=body, timeout=320)
    return r.status_code, r.json()


print("=== responses: create_task round1 ===")
s, r = resp({"model": "dumate-points", "input": "创建任务，标题为 Responses 任务测试", "tools": TASK_TOOLS})
print("status:", s)
fc = r["output"][0]
print("output:", json.dumps(fc, ensure_ascii=False))

print("\n=== responses: create_task round2 (服务端执行) ===")
s, r = resp({"model": "dumate-points", "input": [
    {"role": "user", "content": "创建任务，标题为 Responses 任务测试"},
    {"type": "function_call", "call_id": fc["call_id"], "name": fc["name"], "arguments": fc["arguments"]},
    {"type": "function_call_output", "call_id": fc["call_id"], "output": "{}"},
]})
print("status:", s)
text = r["output"][0]["content"][0]["text"]
result = json.loads(text)
print("result:", json.dumps(result, ensure_ascii=False))
task_id = result["task_id"]

print("\n=== responses: send_task_message round1 ===")
s, r = resp({"model": "dumate-points", "input": "帮我执行任务：请只回复三个字：已收到。", "tools": TASK_TOOLS})
fc2 = r["output"][0]
print("output:", json.dumps(fc2, ensure_ascii=False))

print("\n=== responses: send_task_message round2 (服务端执行) ===")
args2 = json.loads(fc2["arguments"])
args2["task_id"] = task_id
s, r = resp({"model": "dumate-points", "input": [
    {"role": "user", "content": "帮我执行任务：请只回复三个字：已收到。"},
    {"type": "function_call", "call_id": fc2["call_id"], "name": fc2["name"], "arguments": json.dumps(args2, ensure_ascii=False)},
    {"type": "function_call_output", "call_id": fc2["call_id"], "output": "{}"},
]})
print("status:", s)
print("result:", r["output"][0]["content"][0]["text"])

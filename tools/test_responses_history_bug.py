"""Responses API 历史 bug 复现：历史含 function_call_output 时，新消息不应再返回余额。"""
import json
import os

import requests

token = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "token.txt")).read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}

POINTS_TOOL = [{"type": "function", "name": "get_points_balance", "description": "查询积分余额", "parameters": {"type": "object", "properties": {}}}]


def resp(body):
    r = requests.post(base + "/v1/responses", headers=h, json=body, timeout=60)
    return r.status_code, r.json()


# 第一轮
s, r = resp({"model": "dumate-points", "input": "还剩多少积分", "tools": POINTS_TOOL})
fc = r["output"][0]
print("round1:", fc["type"], fc["name"])

# 第二轮
s, r = resp({"model": "dumate-points", "input": [
    {"role": "user", "content": "还剩多少积分"},
    {"type": "function_call", "call_id": fc["call_id"], "name": fc["name"], "arguments": fc["arguments"]},
    {"type": "function_call_output", "call_id": fc["call_id"], "output": "{}"},
]})
print("round2:", r["output"][0]["content"][0]["text"][:50], "...")

# 第三轮：历史含 function_call_output，发新消息
s, r = resp({"model": "dumate-points", "input": [
    {"role": "user", "content": "还剩多少积分"},
    {"type": "function_call", "call_id": fc["call_id"], "name": fc["name"], "arguments": fc["arguments"]},
    {"type": "function_call_output", "call_id": fc["call_id"], "output": "{}"},
    {"role": "assistant", "content": [{"type": "output_text", "text": "余额 21884.71"}]},
    {"role": "user", "content": "你好"},
]})
text = r["output"][0]["content"][0]["text"]
print("\nnew message reply:", text[:60])
print("is balance JSON:", text.startswith("{") and "totalPoints" in text)

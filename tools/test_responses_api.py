import json
import os

import requests

token = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "token.txt")).read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}


def resp(body):
    r = requests.post(base + "/v1/responses", headers=h, json=body, timeout=10)
    return r.status_code, r.json()


print("=== direct (string input) ===")
s, r = resp({"model": "dumate-points", "input": "查询积分余额"})
print("status:", s, "| object:", r.get("object"), "| status:", r.get("status"))
print("output:", json.dumps(r.get("output"), ensure_ascii=False))

print()
print("=== tool round1 (function_call) ===")
s, r = resp({
    "model": "dumate-points",
    "input": "还剩多少积分",
    "tools": [{"type": "function", "name": "get_points_balance", "description": "查询积分余额", "parameters": {"type": "object", "properties": {}}}],
})
print("status:", s)
print("output:", json.dumps(r.get("output"), ensure_ascii=False))

print()
print("=== tool round2 (function_call_output) ===")
fc = r["output"][0]
s, r = resp({
    "model": "dumate-points",
    "input": [
        {"role": "user", "content": "还剩多少积分"},
        {"type": "function_call", "call_id": fc["call_id"], "name": fc["name"], "arguments": fc["arguments"]},
        {"type": "function_call_output", "call_id": fc["call_id"], "output": json.dumps({"availablePoints": 21906.99})},
    ],
})
print("status:", s)
print("output:", json.dumps(r.get("output"), ensure_ascii=False))

print()
print("=== text.format json_object ===")
s, r = resp({
    "model": "dumate-points",
    "input": "积分余额",
    "text": {"format": {"type": "json_object"}},
})
text = r["output"][0]["content"][0]["text"]
print("status:", s, "| text:", text)
print("parsed:", json.loads(text))

print()
print("=== streaming ===")
body = {"model": "dumate-points", "stream": True, "input": "积分余额"}
r = requests.post(base + "/v1/responses", headers=h, json=body, timeout=10, stream=True)
for line in r.iter_lines():
    if line:
        print(line.decode())

import json
import requests

token = open(r"C:\Users\Wangjq\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a84802e6239e8c35d40dc58\dumate-api\token.txt").read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}

print("=== chat round2 (tool result) ===")
body = {
    "model": "dumate-points",
    "messages": [
        {"role": "user", "content": "还剩多少积分"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "get_points_balance", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "call_1", "content": json.dumps({"availablePoints": 21906.99})},
    ],
}
r = requests.post(base + "/v1/chat/completions", headers=h, json=body, timeout=10)
print(r.status_code, json.dumps(r.json(), ensure_ascii=False))

print()
print("=== chat streaming ===")
body = {"model": "dumate-points", "stream": True, "messages": [{"role": "user", "content": "积分余额"}]}
r = requests.post(base + "/v1/chat/completions", headers=h, json=body, timeout=10, stream=True)
for line in r.iter_lines():
    if line:
        print(line.decode())

print()
print("=== chat unrelated question ===")
body = {"model": "dumate-points", "messages": [{"role": "user", "content": "你好"}]}
r = requests.post(base + "/v1/chat/completions", headers=h, json=body, timeout=10)
print(r.status_code, json.dumps(r.json(), ensure_ascii=False))

print()
print("=== auth: no token ===")
r = requests.post(base + "/v1/chat/completions", json={"messages": [{"role": "user", "content": "积分"}]}, timeout=10)
print(r.status_code)

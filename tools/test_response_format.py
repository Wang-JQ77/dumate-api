import json
import requests

token = open(r"C:\Users\Wangjq\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a84802e6239e8c35d40dc58\dumate-api\token.txt").read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}


def chat(messages, **extra):
    body = {"model": "dumate-points", "messages": messages, **extra}
    r = requests.post(base + "/v1/chat/completions", headers=h, json=body, timeout=10)
    return r.status_code, r.json()


print("=== json_object (direct) ===")
s, r = chat([{"role": "user", "content": "查询积分余额"}], response_format={"type": "json_object"})
content = r["choices"][0]["message"]["content"]
print("status:", s, "| content:", content)
print("parsed:", json.loads(content))

print()
print("=== json_schema with field filter ===")
schema = {
    "type": "object",
    "properties": {"availablePoints": {}, "totalPoints": {}, "isSubscribed": {}},
}
s, r = chat([{"role": "user", "content": "积分余额"}], response_format={"type": "json_schema", "json_schema": schema})
content = r["choices"][0]["message"]["content"]
print("status:", s, "| content:", content)
print("parsed:", json.loads(content))

print()
print("=== tool round2 + json_object ===")
messages = [
    {"role": "user", "content": "还剩多少积分"},
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "get_points_balance", "arguments": "{}"}}
    ]},
    {"role": "tool", "tool_call_id": "call_1", "content": json.dumps({"availablePoints": 21906.99})},
]
s, r = chat(messages, response_format={"type": "json_object"})
content = r["choices"][0]["message"]["content"]
print("status:", s, "| content:", content)
print("parsed:", json.loads(content))

print()
print("=== streaming + json_object ===")
body = {
    "model": "dumate-points",
    "stream": True,
    "messages": [{"role": "user", "content": "积分余额"}],
    "response_format": {"type": "json_object"},
}
r = requests.post(base + "/v1/chat/completions", headers=h, json=body, timeout=10, stream=True)
full = ""
for line in r.iter_lines():
    if not line:
        continue
    text = line.decode()
    if text.startswith("data: ") and text != "data: [DONE]":
        payload = json.loads(text[6:])
        delta = payload["choices"][0]["delta"]
        if delta.get("content"):
            full += delta["content"]
print("streamed content:", full)
print("parsed:", json.loads(full))

"""OpenAI 兼容任务工具测试：create_task / send_task_message / get_task_messages 两轮调用。"""
import json
import time
import requests

token = open(r"C:\Users\Wangjq\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a84802e6239e8c35d40dc58\dumate-api\token.txt").read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}

TASK_TOOLS = [
    {"type": "function", "function": {"name": "create_task", "description": "创建任务会话", "parameters": {"type": "object", "properties": {"title": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "send_task_message", "description": "发送任务消息", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "message": {"type": "string"}}, "required": ["task_id", "message"]}}},
    {"type": "function", "function": {"name": "get_task_messages", "description": "读取任务结果", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}}},
]


def chat(body):
    r = requests.post(base + "/v1/chat/completions", headers=h, json=body, timeout=320)
    return r.status_code, r.json()


print("=== chat: create_task round1 ===")
s, r = chat({"model": "dumate-points", "messages": [{"role": "user", "content": "创建任务，标题为 OpenAI 任务测试"}], "tools": TASK_TOOLS})
print("status:", s, "| finish:", r["choices"][0]["finish_reason"])
tc = r["choices"][0]["message"]["tool_calls"][0]
print("tool:", tc["function"]["name"], "| args:", tc["function"]["arguments"])

print("\n=== chat: create_task round2 (服务端执行) ===")
s, r = chat({"model": "dumate-points", "messages": [
    {"role": "user", "content": "创建任务，标题为 OpenAI 任务测试"},
    {"role": "assistant", "content": None, "tool_calls": [tc]},
    {"role": "tool", "tool_call_id": tc["id"], "content": "{}"},
]})
print("status:", s)
result = json.loads(r["choices"][0]["message"]["content"])
print("result:", json.dumps(result, ensure_ascii=False))
task_id = result["task_id"]

print("\n=== chat: send_task_message round1 ===")
s, r = chat({"model": "dumate-points", "messages": [{"role": "user", "content": "帮我执行任务：请只回复两个字：收到。"}], "tools": TASK_TOOLS})
print("status:", s, "| finish:", r["choices"][0]["finish_reason"])
tc2 = r["choices"][0]["message"]["tool_calls"][0]
print("tool:", tc2["function"]["name"], "| args:", tc2["function"]["arguments"])

print("\n=== chat: send_task_message round2 (服务端执行) ===")
args2 = json.loads(tc2["function"]["arguments"])
args2["task_id"] = task_id  # 调用方 LLM 补全 task_id
tc2["function"]["arguments"] = json.dumps(args2, ensure_ascii=False)
s, r = chat({"model": "dumate-points", "messages": [
    {"role": "user", "content": "帮我执行任务：请只回复两个字：收到。"},
    {"role": "assistant", "content": None, "tool_calls": [tc2]},
    {"role": "tool", "tool_call_id": tc2["id"], "content": "{}"},
]})
print("status:", s)
print("result:", r["choices"][0]["message"]["content"])

print("\n=== chat: get_task_messages round1 ===")
s, r = chat({"model": "dumate-points", "messages": [{"role": "user", "content": "读取任务结果"}], "tools": TASK_TOOLS})
tc3 = r["choices"][0]["message"]["tool_calls"][0]
print("tool:", tc3["function"]["name"], "| args:", tc3["function"]["arguments"])

print("\n=== chat: get_task_messages round2 ===")
args3 = json.loads(tc3["function"]["arguments"])
args3["task_id"] = task_id
tc3["function"]["arguments"] = json.dumps(args3, ensure_ascii=False)
s, r = chat({"model": "dumate-points", "messages": [
    {"role": "user", "content": "读取任务结果"},
    {"role": "assistant", "content": None, "tool_calls": [tc3]},
    {"role": "tool", "tool_call_id": tc3["id"], "content": "{}"},
]})
print("status:", s)
data = json.loads(r["choices"][0]["message"]["content"])
print("messages:", len(data.get("messages", [])))
for m in data.get("messages", [])[-2:]:
    print(f"- {m['role']}: {m['content'][:40]}")

print("\n=== chat: points tool 仍正常 ===")
s, r = chat({"model": "dumate-points", "messages": [{"role": "user", "content": "还剩多少积分"}], "tools": TASK_TOOLS + [{"type": "function", "function": {"name": "get_points_balance", "description": "查询积分余额", "parameters": {"type": "object", "properties": {}}}}]})
print("finish:", r["choices"][0]["finish_reason"], "| tool:", r["choices"][0]["message"]["tool_calls"][0]["function"]["name"])

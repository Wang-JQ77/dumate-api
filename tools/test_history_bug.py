"""复现 bug：历史含工具结果时，后续任意消息不应再返回余额 JSON。"""
import json
import requests

token = open(r"C:\Users\Wangjq\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a84802e6239e8c35d40dc58\dumate-api\token.txt").read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}

POINTS_TOOL = [{"type": "function", "function": {"name": "get_points_balance", "description": "查询积分余额", "parameters": {"type": "object", "properties": {}}}}]


def chat(messages, tools=None):
    body = {"model": "dumate-points", "messages": messages}
    if tools:
        body["tools"] = tools
    r = requests.post(base + "/v1/chat/completions", headers=h, json=body, timeout=60)
    return r.status_code, r.json()


# 模拟 agent 的多轮对话历史
history = [{"role": "user", "content": "还剩多少积分"}]

# 第一轮：返回 tool_call
s, r = chat(history, POINTS_TOOL)
tc = r["choices"][0]["message"]["tool_calls"][0]
print("round1 finish:", r["choices"][0]["finish_reason"], "| tool:", tc["function"]["name"])

# 第二轮：回传工具结果
history += [
    {"role": "assistant", "content": None, "tool_calls": [tc]},
    {"role": "tool", "tool_call_id": tc["id"], "content": "{}"},
]
s, r = chat(history)
print("round2:", r["choices"][0]["message"]["content"][:60], "...")

# 第三轮：agent 把历史带上，发一条新消息（不含积分关键词）
history += [{"role": "assistant", "content": "当前积分余额为 21884.71"}]
history += [{"role": "user", "content": "你好，帮我介绍一下你自己"}]
s, r = chat(history)
content = r["choices"][0]["message"]["content"]
print("\nnew message reply:", content[:80])
print("is balance JSON:", content.startswith("{") and "totalPoints" in content)

# 第四轮：不带工具，直接发新消息（历史仍含 tool 消息）
s, r = chat([{"role": "user", "content": "还剩多少积分"},
             {"role": "assistant", "content": None, "tool_calls": [tc]},
             {"role": "tool", "tool_call_id": tc["id"], "content": "{}"},
             {"role": "assistant", "content": "余额 21884.71"},
             {"role": "user", "content": "写一首关于秋天的诗"}])
content = r["choices"][0]["message"]["content"]
print("\npoem request reply:", content[:80])
print("is balance JSON:", content.startswith("{") and "totalPoints" in content)

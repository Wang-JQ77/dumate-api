import json
import os

from openai import OpenAI

token = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "token.txt")).read().strip()
client = OpenAI(base_url="http://127.0.0.1:8765/v1", api_key=token)

print("=== models.list ===")
models = client.models.list()
print([m.id for m in models.data])

print()
print("=== chat (direct) ===")
r = client.chat.completions.create(
    model="dumate-points",
    messages=[{"role": "user", "content": "查询积分余额"}],
)
print(r.choices[0].message.content)

print()
print("=== tool calling round1 ===")
r1 = client.chat.completions.create(
    model="dumate-points",
    messages=[{"role": "user", "content": "还剩多少积分"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_points_balance",
            "description": "查询DuMate积分余额",
            "parameters": {"type": "object", "properties": {}},
        },
    }],
)
msg = r1.choices[0].message
print("finish_reason:", r1.choices[0].finish_reason)
print("tool_calls:", json.dumps([tc.model_dump() for tc in msg.tool_calls], ensure_ascii=False))

print()
print("=== tool calling round2 ===")
tool_call = msg.tool_calls[0]
r2 = client.chat.completions.create(
    model="dumate-points",
    messages=[
        {"role": "user", "content": "还剩多少积分"},
        {"role": "assistant", "content": None, "tool_calls": [tc.model_dump() for tc in msg.tool_calls]},
        {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps({"availablePoints": 21906.99})},
    ],
)
print(r2.choices[0].message.content)

print()
print("=== streaming ===")
stream = client.chat.completions.create(
    model="dumate-points",
    messages=[{"role": "user", "content": "积分余额"}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="")
    if chunk.choices[0].finish_reason:
        print(f"\n[finish_reason={chunk.choices[0].finish_reason}]")

"""用官方 Anthropic SDK 验证 Claude 兼容接口。"""
import os

from anthropic import Anthropic

TOKEN = open(os.path.join(os.path.dirname(__file__), "..", "token.txt")).read().strip()
client = Anthropic(base_url="http://127.0.0.1:8765", api_key=TOKEN)

print("=== 1. 非流式对话（ultra）===")
r = client.messages.create(
    model="dumate-ultra",
    max_tokens=1024,
    messages=[{"role": "user", "content": "用一句话介绍你能做什么"}],
)
print("stop_reason:", r.stop_reason)
print("reply:", r.content[0].text[:120])

print()
print("=== 2. 流式对话（lite）===")
with client.messages.stream(
    model="dumate-lite",
    max_tokens=1024,
    messages=[{"role": "user", "content": "回复四个字：流式正常"}],
) as stream:
    text = stream.get_final_text()
print("reply:", text[:100])

print()
print("=== 3. 工具调用两轮（turbo）===")
tools = [{
    "name": "get_points_balance",
    "description": "查询百度搭子(DuMate)的积分余额，返回总积分、已用积分和可用积分",
    "input_schema": {"type": "object", "properties": {}},
}]
r = client.messages.create(
    model="dumate-turbo",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "查一下积分余额"}],
)
tool_use = next((b for b in r.content if b.type == "tool_use"), None)
print("stop_reason:", r.stop_reason, "| tool:", tool_use.name if tool_use else None)

if tool_use:
    r2 = client.messages.create(
        model="dumate-turbo",
        max_tokens=1024,
        tools=tools,
        messages=[
            {"role": "user", "content": "查一下积分余额"},
            {"role": "assistant", "content": [b.model_dump() for b in r.content]},
            {"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": "tool executed",
            }]},
        ],
    )
    print("round2 reply:", r2.content[0].text[:150])

print()
print("=== 4. count_tokens ===")
n = client.messages.count_tokens(
    model="dumate-turbo",
    messages=[{"role": "user", "content": "你好" * 20}],
)
print("input_tokens:", n.input_tokens)

print()
print("SDK 验证全部通过")

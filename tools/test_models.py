"""验证三模型支持：/v1/models 列表 + 各模型实际调用。"""
import os

import requests

token = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "token.txt")).read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}

# 1. 模型列表
r = requests.get(base + "/v1/models", headers=h, timeout=10)
print("=== /v1/models ===")
print([m["id"] for m in r.json()["data"]])

# 2. 各模型调用（转发给 DuMate）
for model in ["dumate-lite", "dumate-turbo", "dumate-ultra"]:
    r = requests.post(base + "/v1/chat/completions", headers=h,
                      json={"model": model, "messages": [{"role": "user", "content": "用一句话介绍你自己"}]},
                      timeout=300)
    j = r.json()
    c = j["choices"][0]
    print(f"\n=== {model} ===")
    print("resp model:", j.get("model"))
    print("reply:", (c["message"].get("content") or "")[:100])

# 3. 积分查询仍正常
r = requests.post(base + "/v1/chat/completions", headers=h,
                  json={"model": "dumate-points", "messages": [{"role": "user", "content": "查询积分余额"}]},
                  timeout=60)
print("\n=== dumate-points ===")
print("reply:", r.json()["choices"][0]["message"]["content"][:80])

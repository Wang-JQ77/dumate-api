import json
import time
import requests

token = open(r"C:\Users\Wangjq\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a84802e6239e8c35d40dc58\dumate-api\token.txt").read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}

print("=== 1. create task ===")
r = requests.post(base + "/api/tasks", headers=h, json={"title": "API 任务测试", "directory": r"C:\Users\Wangjq\.qianfan\workspace\e268d0e57d52419fb005572030fae56d"}, timeout=20)
print(r.status_code, json.dumps(r.json(), ensure_ascii=False, indent=2))
task_id = r.json()["task_id"]

print("\n=== 2. send message (sync, simple) ===")
r = requests.post(base + f"/api/tasks/{task_id}/messages", headers=h,
                  json={"message": "请只回复两个字：收到。不要执行任何其他操作。"}, timeout=320)
print(r.status_code)
data = r.json()
print("reply:", json.dumps(data.get("reply"), ensure_ascii=False))
print("messages count:", len(data.get("messages", [])))

print("\n=== 3. get messages ===")
r = requests.get(base + f"/api/tasks/{task_id}/messages", headers=h, timeout=20)
print(r.status_code)
for m in r.json()["messages"]:
    print(f"- {m['role']}: {m['content'][:80]}")

print("\n=== 4. list tasks ===")
r = requests.get(base + "/api/tasks", headers=h, timeout=20)
print(r.status_code)
tasks = r.json()["tasks"]
print("total tasks:", len(tasks))
for t in tasks[:3]:
    print(f"- {t['task_id'][:20]}... title={t['title']}")

print("\n=== 5. async mode ===")
r = requests.post(base + f"/api/tasks/{task_id}/messages", headers=h,
                  json={"message": "请只回复三个字：已收到。", "sync": False}, timeout=20)
print(r.status_code, json.dumps(r.json(), ensure_ascii=False))
print("polling...")
for i in range(6):
    time.sleep(10)
    r = requests.get(base + f"/api/tasks/{task_id}/messages", headers=h, timeout=20)
    msgs = r.json()["messages"]
    last = msgs[-1] if msgs else {}
    if last.get("role") == "assistant" and last.get("content"):
        print(f"[{i*10}s] assistant: {last['content'][:80]}")
        break
    print(f"[{i*10}s] last role={last.get('role')} content={last.get('content','')[:40]}")

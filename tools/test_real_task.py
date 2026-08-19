"""真实任务执行测试：让 DuMate 生成一个 Python 文件并验证内容。"""
import json
import time
import requests

token = open(r"C:\Users\Wangjq\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a84802e6239e8c35d40dc58\dumate-api\token.txt").read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}
workdir = r"C:\Users\Wangjq\.qianfan\workspace\e268d0e57d52419fb005572030fae56d"

print("=== 1. balance before ===")
r = requests.get(base + "/api/points/balance", headers=h, timeout=20)
print("available:", r.json()["availablePoints"])

print("\n=== 2. create task ===")
r = requests.post(base + "/api/tasks", headers=h, json={"title": "真实任务测试", "directory": workdir}, timeout=20)
print(r.status_code, r.json()["task_id"])
task_id = r.json()["task_id"]

print("\n=== 3. send real task (write a python file) ===")
msg = (
    "请在当前工作目录创建一个名为 hello_api.py 的 Python 文件，"
    "内容为：print('hello from dumate api')。创建完成后回复文件已创建。"
)
r = requests.post(base + f"/api/tasks/{task_id}/messages", headers=h, json={"message": msg}, timeout=320)
print(r.status_code)
data = r.json()
print("reply:", json.dumps(data.get("reply"), ensure_ascii=False))

print("\n=== 4. verify file exists ===")
import os
fp = os.path.join(workdir, "hello_api.py")
print("file exists:", os.path.exists(fp))
if os.path.exists(fp):
    print("content:", open(fp, encoding="utf-8").read().strip())

print("\n=== 5. balance after ===")
r = requests.get(base + "/api/points/balance/refresh", headers=h, timeout=20)
print("available:", r.json()["availablePoints"])

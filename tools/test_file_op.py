import json
import os
import tempfile

import requests

token = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "token.txt")).read().strip()
base = "http://127.0.0.1:8765"
h = {"Authorization": "Bearer " + token}
workdir = tempfile.mkdtemp(prefix="dumate_test_")

print("=== create task for file op ===")
r = requests.post(base + "/api/tasks", headers=h, json={"title": "文件操作测试", "directory": workdir}, timeout=20)
task_id = r.json()["task_id"]
print("task_id:", task_id)

print("\n=== send file-creation message (sync) ===")
r = requests.post(base + f"/api/tasks/{task_id}/messages", headers=h,
                  json={"message": "请在当前工作目录下创建一个名为 api_test.txt 的文件，文件内容为 hello-from-dumate-api。创建完成后只回复：文件已创建。"},
                  timeout=320)
print(r.status_code)
data = r.json()
print("reply:", json.dumps(data.get("reply"), ensure_ascii=False))

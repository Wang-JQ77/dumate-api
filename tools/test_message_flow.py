import json
import os
import sys
import tempfile
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dumate_client import discover_inapp_key, discover_opencode_url

KEY = discover_inapp_key()
BASE = discover_opencode_url()

# 创建独立测试会话，避免污染已有会话
_req = urllib.request.Request(BASE + "/session", method="POST")
_req.add_header("X-Dumate-Inapp-Key", KEY)
_req.add_header("Content-Type", "application/json")
_data = json.dumps({"title": "message flow test", "directory": tempfile.mkdtemp(prefix="dumate_test_")}).encode()
with urllib.request.urlopen(_req, _data, timeout=15) as resp:
    SID = json.loads(resp.read().decode())["id"]
print("session:", SID)

def post_message(text):
    req = urllib.request.Request(BASE + f"/session/{SID}/message", method="POST")
    req.add_header("X-Dumate-Inapp-Key", KEY)
    req.add_header("Content-Type", "application/json")
    data = json.dumps({"parts": [{"type": "text", "text": text}]}).encode()
    try:
        with urllib.request.urlopen(req, data, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return "ERR", str(e)[:200]

def get_messages():
    req = urllib.request.Request(BASE + f"/session/{SID}/message")
    req.add_header("X-Dumate-Inapp-Key", KEY)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

print("=== sending message ===")
s, b = post_message("请只回复两个字：收到。不要执行任何其他操作。")
print("post:", s, b[:300])

print("=== polling for assistant reply ===")
for i in range(12):
    time.sleep(10)
    msgs = get_messages()
    last = msgs[-1]
    info = last.get("info", {})
    role = info.get("role")
    texts = [p.get("text", "") for p in last.get("parts", []) if p.get("type") == "text"]
    err = info.get("error")
    print(f"[{i*10}s] last={role} texts={texts} error={'YES' if err else 'no'}")
    if role == "assistant" and (texts or err):
        break

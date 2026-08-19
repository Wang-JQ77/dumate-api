import json
import time
import urllib.request
import urllib.error

KEY = "a4851ca1d5b880779f3b1317511c777639a67d07596fcc79ef3fdcbfd2e24e86"
BASE = "http://127.0.0.1:52972"
SID = "ses_gffe5fea0d3443ffeEHSgGFFPqyMGPe"  # api-probe 会话

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

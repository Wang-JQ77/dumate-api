import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:52972"
KEY = sys.argv[1] if len(sys.argv) > 1 else ""

def req(method, path, body=None, timeout=10):
    url = BASE + path
    r = urllib.request.Request(url, method=method)
    r.add_header("X-Dumate-Inapp-Key", KEY)
    r.add_header("Content-Type", "application/json")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(r, data, timeout=timeout) as resp:
            b = resp.read().decode("utf-8", errors="replace")
            return resp.status, b
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", errors="replace")
        return e.code, b
    except Exception as e:
        return "ERR", str(e)[:300]

# Test creating a session
print("=== POST /session ===")
status, body = req("POST", "/session", {
    "directory": "C:\\Users\\Wangjq\\.qianfan\\workspace\\e268d0e57d52419fb005572030fae56d",
    "title": "API 测试会话",
})
print("status:", status)
print(body[:1500])

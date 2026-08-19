import json
import os
import sys
import tempfile
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dumate_client import discover_inapp_key, discover_opencode_url

BASE = discover_opencode_url()
KEY = discover_inapp_key()

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
    "directory": tempfile.mkdtemp(prefix="dumate_test_"),
    "title": "API 测试会话",
})
print("status:", status)
print(body[:1500])

"""REST 任务 API 三模式选择测试。"""
import os
import sys

import requests

BASE = "http://127.0.0.1:8765"
TOKEN = open(os.path.join(os.path.dirname(__file__), "..", "token.txt")).read().strip()
H = {"X-API-Key": TOKEN, "Content-Type": "application/json"}


def main():
    r = requests.post(f"{BASE}/api/tasks", headers=H, json={"title": "三模式测试"}, timeout=30)
    task_id = r.json()["task_id"]
    print("task:", task_id)

    for model in ("dumate-lite", "dumate-turbo", "dumate-ultra"):
        r = requests.post(f"{BASE}/api/tasks/{task_id}/messages", headers=H,
                          json={"message": f"（模式自检）请只回复一个词：你好。当前选择的是 {model} 模式。",
                                "model": model, "sync": True}, timeout=300)
        d = r.json()
        reply = (d.get("reply") or {}).get("content", "")
        ok = r.status_code == 200 and bool(reply)
        print(f"  [{'PASS' if ok else 'FAIL'}] {model} -> {reply[:60]}")
        if not ok:
            sys.exit(1)

    print("全部通过")


if __name__ == "__main__":
    main()

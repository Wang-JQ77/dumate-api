"""等待 DuMate 桌面版的 opencode 服务就绪。

轮询 dumate_client 的端口自动发现逻辑，直到发现地址且端口可连接。
就绪时打印 opencode 服务地址并以退出码 0 结束；超时打印 TIMEOUT 并以 1 结束。

用法:
    python wait_opencode.py [超时秒数]     # 默认 90 秒
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dumate_client import discover_opencode_url  # noqa: E402


def _reachable(url: str) -> bool:
    try:
        port = int(url.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        return False
    s = socket.socket()
    s.settimeout(1)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def main(timeout: int) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = discover_opencode_url()
            if _reachable(url):
                print(url)
                return 0
        except Exception:
            pass  # DuMate 尚未运行或端口尚未监听，继续等待
        time.sleep(2)
    print("TIMEOUT")
    return 1


if __name__ == "__main__":
    t = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    sys.exit(main(t))

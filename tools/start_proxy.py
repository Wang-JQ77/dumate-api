"""智能代理启动器：自动发现 DuMate 期望的代理端口并按需启动透传代理。

DuMate 的模型调用链路会使用其进程环境中的 HTTP_PROXY/HTTPS_PROXY。
该地址并非固定（继承自 DuMate 启动时的环境，每台机器可能不同），因此：
1. 读取 DuMate 进程环境，解析它期望的本地代理端口
2. 若该端口已有服务在监听（真实代理），无需处理
3. 若无服务监听（陈旧的代理配置），在该端口启动透明转发代理
4. 若 DuMate 未配置代理，则直接连接，无需任何代理
"""
import os
import re
import socket
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dumate_client import _find_pid, _read_process_env  # noqa: E402

DUMATE_PROCS = ("dumate-main-server.exe", "dumate-opencode.exe", "DuMate.exe")


def discover_proxy_port():
    """从 DuMate 进程环境解析期望的本地代理端口。"""
    for proc in DUMATE_PROCS:
        pid = _find_pid(proc)
        if not pid:
            continue
        envs = _read_process_env(pid)
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            val = envs.get(var, "")
            m = re.search(r"(?:127\.0\.0\.1|localhost):(\d+)", val)
            if m:
                return int(m.group(1)), val
    return None, ""


def port_in_use(port):
    s = socket.socket()
    s.settimeout(1)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def main():
    port, raw = discover_proxy_port()
    if port is None:
        print("[Proxy] DuMate 未配置代理（直连模式），无需透传代理")
        return 0
    if port_in_use(port):
        print(f"[Proxy] DuMate 期望代理 {raw}，端口 {port} 已有服务在监听，无需处理")
        return 0
    proxy_script = os.path.join(ROOT, "tools", "transparent_proxy.py")
    subprocess.Popen(
        [sys.executable, proxy_script, str(port)],
        creationflags=0x08000000,  # CREATE_NO_WINDOW：后台运行
        cwd=ROOT,
    )
    print(f"[Proxy] DuMate 期望代理 {raw}，但端口 {port} 无服务，已启动透传代理")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""DuMate opencode 客户端：封装会话 / 消息接口，自动发现本地鉴权 key。"""
import ctypes
import os
import re
import socket
import subprocess
import sys
import time

import requests

DEFAULT_BASE = "http://127.0.0.1:52795"

# DuMate 模型模式 -> 请求头 X-Dumate-AutoModel-Level 的值
MODEL_LEVEL_HEADER = "X-Dumate-AutoModel-Level"
MODEL_LEVELS = {"lite": "L0", "turbo": "L1", "ultra": "L2"}

DUMATE_PROCS = ("dumate-main-server.exe", "dumate-opencode.exe", "DuMate.exe")

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

_PROXY_ENSURE = {"done": False, "last_check": 0.0}


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]


_ntdll = ctypes.WinDLL("ntdll")
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def _read_mem(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t(0)
    if not _kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)):
        return None
    return buf.raw[:read.value]


def _read_ptr(h, addr):
    data = _read_mem(h, addr, 8)
    if data is None:
        return None
    return int.from_bytes(data, "little")


def _read_process_env(pid):
    h = _kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return {}
    try:
        pbi = PROCESS_BASIC_INFORMATION()
        if _ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None) != 0:
            return {}
        peb = pbi.PebBaseAddress
        pp = _read_ptr(h, peb + 0x20)
        if not pp:
            return {}
        env_ptr = _read_ptr(h, pp + 0x80)
        if not env_ptr:
            return {}
        buf = b""
        offset = 0
        while True:
            chunk = _read_mem(h, env_ptr + offset, 4096)
            if not chunk:
                break
            buf += chunk
            offset += len(chunk)
            if b"\x00\x00\x00\x00" in buf[-8:]:
                break
            if len(buf) > 2_000_000:
                break
        text = buf.decode("utf-16-le", errors="replace")
        envs = {}
        for line in text.split("\x00"):
            if "=" in line:
                k, v = line.split("=", 1)
                envs[k] = v
        return envs
    finally:
        _kernel32.CloseHandle(h)


def _find_pid(name):
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = [p.strip().strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == name.lower():
            try:
                return int(parts[1])
            except ValueError:
                return None
    return None


def discover_inapp_key():
    """从环境变量或 DuMate 进程环境读取 DUMATE_INAPP_KEY。"""
    key = os.environ.get("DUMATE_INAPP_KEY", "")
    if key:
        return key
    for proc in ("dumate-main-server.exe", "dumate-opencode.exe"):
        pid = _find_pid(proc)
        if pid:
            key = _read_process_env(pid).get("DUMATE_INAPP_KEY", "")
            if key:
                return key
    return ""


def discover_user_id():
    """读取 DUMATE_USER_ID，用于构造默认工作目录。"""
    uid = os.environ.get("DUMATE_USER_ID", "")
    if uid:
        return uid
    for proc in ("dumate-main-server.exe", "dumate-opencode.exe"):
        pid = _find_pid(proc)
        if pid:
            envs = _read_process_env(pid)
            uid = envs.get("DUMATE_USER_ID", "") or envs.get("DUMATE_ACCOUNT_ID", "")
            if uid:
                return uid
    return ""


def discover_opencode_url():
    """从 DuMate 进程环境读取 opencode 服务地址（端口可能随版本变化）。"""
    url = os.environ.get("DUMATE_HOST_URL", "")
    if url:
        return url
    for proc in ("dumate-main-server.exe", "dumate-opencode.exe"):
        pid = _find_pid(proc)
        if pid:
            envs = _read_process_env(pid)
            url = envs.get("DUMATE_HOST_URL", "")
            if url:
                return url
            port = envs.get("OPENCODE_SERVER_PORT", "")
            if port:
                return f"http://127.0.0.1:{port}"
    fallback_port = int(DEFAULT_BASE.rsplit(":", 1)[1])
    if _port_in_use(fallback_port):
        return DEFAULT_BASE
    raise RuntimeError(
        f"未检测到 DuMate 桌面版进程（dumate-main-server / dumate-opencode），"
        f"且默认端口 {fallback_port} 上没有服务监听。"
        f"请先启动 DuMate 桌面版并等待其完全就绪后重试；"
        f"或通过环境变量 DUMATE_OPENCODE_URL 手动指定 opencode 服务地址。"
    )


def _port_in_use(port):
    s = socket.socket()
    s.settimeout(1)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def ensure_dumate_proxy():
    """确保 DuMate 期望的本地代理端口有服务监听，无则启动透传代理兜底。

    DuMate 的模型调用走其进程环境中的 HTTP_PROXY，该地址可能是陈旧配置
    （指向已不存在的代理端口）。本服务可能在 DuMate 启动前就运行，启动时
    无法发现代理配置，因此在每次创建客户端时惰性检查（带节流）。
    """
    st = _PROXY_ENSURE
    now = time.time()
    if st["done"] or now - st["last_check"] < 30:
        return
    st["last_check"] = now
    port = None
    for proc in DUMATE_PROCS:
        pid = _find_pid(proc)
        if not pid:
            continue
        envs = _read_process_env(pid)
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            m = re.search(r"(?:127\.0\.0\.1|localhost):(\d+)", envs.get(var, ""))
            if m:
                port = int(m.group(1))
                break
        if port:
            break
    if port is None:
        return  # DuMate 未运行或未配置代理，稍后重试
    if _port_in_use(port):
        st["done"] = True  # 端口已有服务（真实代理或先前启动的透传代理）
        return
    proxy_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "transparent_proxy.py")
    if os.path.exists(proxy_script):
        subprocess.Popen(
            [sys.executable, proxy_script, str(port)],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    st["done"] = True


class DumateClient:
    def __init__(self, base=None, key=None):
        self.base = base or os.environ.get("DUMATE_OPENCODE_URL") or discover_opencode_url()
        self.key = key or discover_inapp_key()
        self.headers = {"X-Dumate-Inapp-Key": self.key, "Content-Type": "application/json"}
        ensure_dumate_proxy()

    def create_session(self, title, directory):
        r = requests.post(f"{self.base}/session", headers=self.headers,
                          json={"title": title, "directory": directory}, timeout=20)
        r.raise_for_status()
        return r.json()

    def send_message(self, session_id, text, model_level=None, timeout=300):
        body = {"parts": [{"type": "text", "text": text}]}
        if model_level and model_level in MODEL_LEVELS:
            body["headers"] = {MODEL_LEVEL_HEADER: MODEL_LEVELS[model_level]}
        r = requests.post(f"{self.base}/session/{session_id}/message", headers=self.headers,
                          json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def get_messages(self, session_id):
        r = requests.get(f"{self.base}/session/{session_id}/message", headers=self.headers, timeout=20)
        r.raise_for_status()
        return r.json()

    def list_sessions(self):
        r = requests.get(f"{self.base}/session", headers=self.headers, timeout=20)
        r.raise_for_status()
        return r.json()

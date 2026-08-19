import socket
import threading
import select
import sys
import os

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "proxy.pid")

def pipe(a, b):
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 60)
            if not r:
                break
            for s in r:
                other = b if s is a else a
                data = s.recv(65536)
                if not data:
                    raise ConnectionError
                other.sendall(data)
    except Exception:
        pass
    finally:
        for s in (a, b):
            try:
                s.close()
            except Exception:
                pass

def handle(client):
    try:
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = client.recv(4096)
            if not chunk:
                return
            buf += chunk
            if len(buf) > 1_000_000:
                return
        head, _, rest = buf.partition(b"\r\n\r\n")
        first_line = head.split(b"\r\n")[0].decode("latin-1", errors="replace")
        parts = first_line.split(" ")
        if len(parts) < 2:
            return
        method, target = parts[0], parts[1]

        if method.upper() == "CONNECT":
            host, _, port = target.partition(":")
            try:
                remote = socket.create_connection((host, int(port)), timeout=15)
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            except Exception:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                return
            if rest:
                remote.sendall(rest)
            pipe(client, remote)
        else:
            # 普通 HTTP 转发
            if target.startswith("http://"):
                from urllib.parse import urlparse
                u = urlparse(target)
                host, port = u.hostname, u.port or 80
                path = u.path or "/"
                if u.query:
                    path += "?" + u.query
                new_head = head.replace(target, path, 1)
                try:
                    remote = socket.create_connection((host, int(port)), timeout=15)
                    remote.sendall(new_head + b"\r\n\r\n" + rest)
                    pipe(client, remote)
                except Exception:
                    client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            else:
                client.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
    except Exception:
        pass
    finally:
        try:
            client.close()
        except Exception:
            pass

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    listen = ("127.0.0.1", port)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(listen)
    srv.listen(128)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    print(f"transparent proxy listening on {listen[0]}:{listen[1]}", flush=True)
    try:
        while True:
            c, _ = srv.accept()
            threading.Thread(target=handle, args=(c,), daemon=True).start()
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

if __name__ == "__main__":
    main()

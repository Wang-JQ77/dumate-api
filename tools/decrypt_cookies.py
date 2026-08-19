import base64
import json
import os
import sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

APP_DATA = os.environ.get("DUMATE_APP_DATA") or os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~/.config")), "qianfan-desktop-app"
)
KEY_FILE = os.path.join(APP_DATA, ".cookie-key")
AUTH_FILE = os.path.join(APP_DATA, "auth.json")

def decrypt(encoded: str, key: bytes) -> str:
    buf = base64.b64decode(encoded)
    iv = buf[:12]
    tag = buf[12:28]
    ct = buf[28:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ct + tag, None).decode("utf-8")

def main():
    with open(KEY_FILE, "rb") as f:
        key = f.read()
    with open(AUTH_FILE, "r", encoding="utf-8") as f:
        auth = json.load(f)
    cookies = json.loads(decrypt(auth["cookies"], key))
    print(f"total cookies: {len(cookies)}")
    for c in cookies:
        name = c.get("name", "")
        domain = c.get("domain", "")
        value = c.get("value", "")
        if len(value) > 60:
            value = value[:60] + "..."
        print(f"  {name} @ {domain} = {value}")

if __name__ == "__main__":
    main()

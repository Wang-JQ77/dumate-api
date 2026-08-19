"""首次运行时生成随机 API token 到项目根目录 token.txt（已存在则跳过）。"""
import os
import secrets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "token.txt")

if not os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "w") as f:
        f.write(secrets.token_hex(16))

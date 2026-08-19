@echo off
rem Start DuMate API service (+ transparent proxy when needed) in background.
rem On first run, generates a random token saved to token.txt.
setlocal
cd /d "%~dp0"

rem --- 检查 Python（直接验证可执行，兼容 PATH 无 where.exe 的环境） ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 无法运行 python 命令。
    echo 请安装 Python 3.10+，安装时务必勾选 "Add Python to PATH":
    echo   https://www.python.org/downloads/
    echo 若弹出 Microsoft Store 页面，说明装的是商店占位符，请改用官网安装包。
    pause
    exit /b 1
)

rem --- 检查依赖 ---
python -c "import fastapi, uvicorn, requests, cryptography" >nul 2>&1
if errorlevel 1 (
    echo [错误] 缺少 Python 依赖，请在本项目目录执行:
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

set "TOKEN_FILE=%~dp0token.txt"
if not exist "%TOKEN_FILE%" (
    python -c "import secrets; open(r'%TOKEN_FILE%','w').write(secrets.token_hex(16))"
)
set /p API_TOKEN=<"%TOKEN_FILE%"

rem --- DuMate 透传代理（按需启动，自动适配 DuMate 期望的代理端口） ---
python "%~dp0tools\start_proxy.py"

rem --- API 服务 ---
python -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',8765)); s.close(); raise SystemExit(0 if r==0 else 1)" >nul 2>&1
if %errorlevel%==0 (
    echo [DuMate API] 服务已在运行: http://127.0.0.1:8765
    goto :showtoken
)

start "DuMateAPI" /min python "%~dp0points_api.py" --port 8765 --token "%API_TOKEN%"

rem --- 等待服务就绪，启动失败时给出排查提示 ---
timeout /t 2 /nobreak >nul
python -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',8765)); s.close(); raise SystemExit(0 if r==0 else 1)" >nul 2>&1
if errorlevel 1 (
    echo [警告] 服务可能启动失败。请手动运行以下命令查看具体报错:
    echo   python points_api.py --port 8765 --token "%API_TOKEN%"
    echo 常见原因: 端口 8765 被占用、依赖未安装、DuMate 未运行。
) else (
    echo [DuMate API] 服务已启动: http://127.0.0.1:8765
)

:showtoken
echo.
echo API Token: %API_TOKEN%
echo 调用示例:
echo   curl -H "X-API-Key: %API_TOKEN%" http://127.0.0.1:8765/api/points/balance
echo.
echo 按任意键关闭本窗口（服务在后台继续运行，停止请运行 stop_points_api.bat）...
pause >nul
endlocal

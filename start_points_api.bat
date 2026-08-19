@echo off
rem Start DuMate API service – 三步骤自动启动流程
rem   [1/3] 检查 DuMate 桌面版 → 自动启动 → 等待 opencode 就绪
rem   [2/3] 启动 8888 透传代理
rem   [3/3] 启动 DuMate API 服务 (8765)
setlocal
cd /d "%~dp0"

rem --- 检查 Python ---
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

rem --- 检查 Python 版本（需 3.10+） ---
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 版本过低，本项目需要 Python 3.10+，当前版本:
    python --version
    echo 请从 https://www.python.org/downloads/ 升级后重试。
    pause
    exit /b 1
)

rem --- 首次运行自动生成随机 token ---
python "%~dp0tools\ensure_token.py"
set /p API_TOKEN=<"%~dp0token.txt"
if "%API_TOKEN%"=="" (
    echo [错误] 无法读取 API Token（token.txt 为空或生成失败）。
    pause
    exit /b 1
)

echo.
echo === [1/3] 检查 DuMate 桌面版 ===

rem 检查 DuMate 进程是否已在运行（dumate-main-server 或 dumate-opencode）
python -c "import subprocess; out=subprocess.run(['tasklist','/FI','IMAGENAME eq dumate-main-server.exe','/FO','CSV','/NH'],capture_output=True,text=True).stdout; exit(0 if 'dumate-main-server' in out else 1)" >nul 2>&1
if errorlevel 1 (
    echo [1/3] DuMate 未运行，正在启动 D:\DuMate\DuMate.exe ...
    if exist "D:\DuMate\DuMate.exe" (
        start "" "D:\DuMate\DuMate.exe"
    ) else (
        echo [警告] 未找到 D:\DuMate\DuMate.exe，请手动启动 DuMate 桌面版。
    )
) else (
    echo [1/3] DuMate 桌面版已在运行
)

rem 等待 opencode 服务就绪（最多 90 秒）
python "%~dp0tools\wait_opencode.py" 90
if %errorlevel%==0 (
    for /f %%i in ('python "%~dp0tools\wait_opencode.py" 0') do set OPENCODE_URL=%%i
    rem 取最后一次成功输出
    python -c "import subprocess, sys; r=subprocess.run([sys.executable,r'%~dp0tools\wait_opencode.py','0'],capture_output=True,text=True); print(r.stdout.strip())" > "%TEMP%\opencode_url.txt" 2>&1
    set /p OPENCODE_URL=<"%TEMP%\opencode_url.txt"
    if defined OPENCODE_URL (
        echo [OK] opencode 已就绪: %OPENCODE_URL%
    ) else (
        echo [OK] opencode 已就绪
    )
) else (
    echo [1/3] DuMate 尚未就绪（首次登录可能需要手动操作），API 会先启动。
    echo        DuMate 就绪后，后续调用会自动恢复，无需重启本服务。
)

echo.
echo === [2/3] 启动 8888 透传代理 ===
python "%~dp0tools\start_proxy.py"

echo.
echo === [3/3] 启动 DuMate API 服务 ===
python -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',8765)); s.close(); raise SystemExit(0 if r==0 else 1)" >nul 2>&1
if %errorlevel%==0 (
    echo [3/3] DuMate API 已在运行: http://127.0.0.1:8765
    goto :showtoken
)

start "DuMateAPI" /min python "%~dp0points_api.py" --port 8765 --token "%API_TOKEN%"

timeout /t 2 /nobreak >nul
python -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',8765)); s.close(); raise SystemExit(0 if r==0 else 1)" >nul 2>&1
if errorlevel 1 (
    echo [3/3] 服务启动失败。请手动运行以下命令查看具体报错:
    echo   python points_api.py --port 8765 --token "%API_TOKEN%"
    echo 常见原因: 端口 8765 被占用、依赖未安装、DuMate 未运行。
) else (
    echo [3/3] DuMate API 已启动: http://127.0.0.1:8765
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
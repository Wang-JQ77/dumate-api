@echo off
rem Start DuMate Points API service + 8888 transparent proxy in background.
rem On first run, generates a random token saved to token.txt.
setlocal
cd /d "%~dp0"

set "TOKEN_FILE=%~dp0token.txt"
if not exist "%TOKEN_FILE%" (
    python -c "import secrets; open(r'%TOKEN_FILE%','w').write(secrets.token_hex(16))"
)
set /p API_TOKEN=<"%TOKEN_FILE%"

rem --- 8888 transparent proxy (needed for DuMate model calls) ---
python -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',8888)); s.close(); raise SystemExit(0 if r==0 else 1)" >nul 2>&1
if %errorlevel%==0 (
    echo [Proxy] 8888 already running.
) else (
    start "DuMateProxy8888" /min python "%~dp0tools\transparent_proxy.py"
    echo [Proxy] 8888 transparent proxy started.
)

rem --- Points API service ---
python -c "import socket; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',8765)); s.close(); raise SystemExit(0 if r==0 else 1)" >nul 2>&1
if %errorlevel%==0 (
    echo [DuMate Points API] Service already running.
    goto :showtoken
)

start "DuMatePointsAPI" /min python "%~dp0points_api.py" --port 8765 --token "%API_TOKEN%"
echo [DuMate Points API] Service started: http://127.0.0.1:8765

:showtoken
echo.
echo API Token: %API_TOKEN%
echo Example:
echo   curl -H "X-API-Key: %API_TOKEN%" http://127.0.0.1:8765/api/points/balance
endlocal

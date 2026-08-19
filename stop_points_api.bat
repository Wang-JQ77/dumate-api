@echo off
rem Stop DuMate API service and transparent proxy.
python -c "import os, ctypes, sys; pid_file=os.path.join(os.path.dirname(os.path.abspath(r'%~dp0points_api.py')),'points_api.pid'); pid=int(open(pid_file).read().strip()) if os.path.exists(pid_file) else None; (print('no pid file, nothing to stop'), sys.exit(0)) if pid is None else None; h=ctypes.windll.kernel32.OpenProcess(1, False, pid); (print('process not running'), sys.exit(0)) if not h else None; ctypes.windll.kernel32.TerminateProcess(h, 0); ctypes.windll.kernel32.CloseHandle(h); os.remove(pid_file); print('stopped api pid', pid)"
python -c "import os, ctypes, sys; pid_file=os.path.join(os.path.dirname(os.path.abspath(r'%~dp0points_api.py')),'proxy.pid'); pid=int(open(pid_file).read().strip()) if os.path.exists(pid_file) else None; (print('no proxy pid file'), sys.exit(0)) if pid is None else None; h=ctypes.windll.kernel32.OpenProcess(1, False, pid); (print('proxy not running'), sys.exit(0)) if not h else None; ctypes.windll.kernel32.TerminateProcess(h, 0); ctypes.windll.kernel32.CloseHandle(h); os.remove(pid_file); print('stopped proxy pid', pid)"
echo.
echo 已尝试停止 API 服务与透传代理。按任意键关闭...
pause >nul

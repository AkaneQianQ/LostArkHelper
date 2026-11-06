@echo off
chcp 936 >nul
cd /d "%~dp0"
echo 正在启动命运方舟助手（调试模式）...
where py >nul 2>nul
if errorlevel 1 (
  echo 未找到 Python 启动器，请安装 Python 3.11 或更新版本。
  pause
  exit /b 1
)
py -3 launcher.py
echo 服务已退出，退出码 %errorlevel%。
pause

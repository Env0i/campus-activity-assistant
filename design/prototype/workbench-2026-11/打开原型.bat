@echo off
chcp 65001 >nul
rem 用本机 Python 起一个只监听本机的静态服务器，再用默认浏览器打开原型查看器；关掉服务器窗口就停止
cd /d "%~dp0"
if not exist support.js (
  echo 缺少画布运行时 support.js，见 README 的“运行时文件”一节。
  pause
  exit /b 1
)
start "workbench-prototype" python -m http.server 8790 --bind 127.0.0.1
timeout /t 2 >nul
start "" http://127.0.0.1:8790/

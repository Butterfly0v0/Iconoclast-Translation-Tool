@echo off
chcp 65001 >nul
cd /d "%~dp0tools"
echo 正在启动 Iconoclasts 字符表编辑器...
echo 浏览器将自动打开 http://127.0.0.1:8765/rosetta_editor.html
echo 若端口被占用，程序会自动尝试 8766、8767… 或请先关闭先前启动的编辑器窗口。
echo 关闭本窗口即可停止服务。
python rosetta_server.py
if errorlevel 1 pause

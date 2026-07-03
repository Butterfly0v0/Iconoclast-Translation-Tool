@echo off
chcp 65001 >nul
cd /d "%~dp0tools"
echo 正在启动 Iconoclasts 译文编辑器...
echo 浏览器将自动打开 http://127.0.0.1:8765/translation_editor.html
echo 关闭本窗口即可停止服务。
python rosetta_server.py --page translation_editor.html
if errorlevel 1 pause

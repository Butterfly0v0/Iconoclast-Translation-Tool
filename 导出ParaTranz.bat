@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在导出 ParaTranz JSON（台词 + 说话人）...
python tools\paratranz_convert.py export
if errorlevel 1 pause

@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ParaTranz 导入：将 tools\paratranz\ 下的 JSON 写回 diachn
echo 默认先写入工具目录 diachn（--target working），确认无误后再写入游戏。
echo.
set /p CONFIRM=继续导入到 working 副本？[Y/N]:
if /i not "%CONFIRM%"=="Y" (
    echo 已取消。
    pause
    exit /b 0
)
python tools\paratranz_convert.py import --target working
if errorlevel 1 (
    echo 导入失败，请查看上方错误（缺字等）。
    pause
    exit /b 1
)
echo.
echo 导入完成。若要写入游戏 data\diachn，请运行：
echo   python tools\paratranz_convert.py import --target game
echo 或先启动游戏验证 working 副本后再执行上述命令。
pause

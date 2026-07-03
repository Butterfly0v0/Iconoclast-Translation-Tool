@echo off
chcp 65001 >nul
cd /d "%~dp0Iconoclast-Translation-Tool"
echo 正在重建字形映射（含 OCR，约需数分钟）...
python tools\build_font_mapping.py
if errorlevel 1 exit /b 1
echo.
echo 正在导出字形 PNG...
python tools\export_glyphs.py
if errorlevel 1 exit /b 1
echo.
echo 完成。请刷新字符表编辑器页面（Ctrl+F5）。
pause

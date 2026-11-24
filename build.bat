@echo off
cd /d "%~dp0"
echo Installing PySide6 and PyInstaller...
python -m pip install PySide6 pyinstaller
echo.
echo Building Sakura.exe, this takes a few minutes...
python -m PyInstaller --noconsole --onefile --name Sakura falling.pyw
echo.
echo DONE. Your file is in the dist folder: Sakura.exe
pause

@echo off
setlocal

REM Build OpenPixMod as a single Windows EXE with app icon.
pyinstaller --noconfirm --windowed --onefile --name OpenPixMod --icon assets\Logo.png app.py

echo Build complete. Check dist\OpenPixMod.exe


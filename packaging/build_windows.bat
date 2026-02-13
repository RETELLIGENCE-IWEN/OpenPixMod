@echo off
setlocal

REM Build OpenPixMod as a single Windows EXE with app icon.
set "ROOT_DIR=%~dp0.."
set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ERROR: venv Python not found at "%PYTHON_EXE%"
    echo Create it first: python -m venv .venv
    exit /b 1
)

pushd "%ROOT_DIR%"
"%PYTHON_EXE%" -m PyInstaller --noconfirm OpenPixMod.spec
set "BUILD_RC=%ERRORLEVEL%"
popd

if not "%BUILD_RC%"=="0" (
    exit /b %BUILD_RC%
)

echo Build complete. Check dist\OpenPixMod.exe

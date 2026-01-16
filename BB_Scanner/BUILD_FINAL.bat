@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   BUILD BB_SCANNER.EXE
echo ========================================
echo.

echo [STEP 1] Running bootstrap (installs Python and dependencies)...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "tools\bootstrap_windows.ps1"

if errorlevel 1 (
    echo.
    echo ERROR: Bootstrap failed!
    pause
    exit /b 1
)

echo.
echo [STEP 2] Building EXE...
echo This may take 3-5 minutes...
echo.

set VENV_PYTHON=%~dp0.venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" (
    echo ERROR: Python not found in .venv
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install pyinstaller --quiet

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

"%VENV_PYTHON%" -m PyInstaller --name=BB_Scanner --onefile --windowed --add-data=app;app --hidden-import=playwright --hidden-import=playwright.async_api --hidden-import=winotify --hidden-import=pyperclip --collect-all=playwright run_scanner.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

if exist dist\BB_Scanner.exe (
    echo.
    echo ========================================
    echo   BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo EXE file: dist\BB_Scanner.exe
    echo.
) else (
    echo.
    echo ERROR: EXE not found!
)

pause







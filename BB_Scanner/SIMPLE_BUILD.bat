@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   BUILD BB_SCANNER.EXE
echo ========================================
echo.

REM Check if .venv exists
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
    echo Found Python in .venv
    goto :build
)

REM Check Python314
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe" (
    set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe
    echo Found Python 3.14
    goto :build
)

REM Check Python313
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe" (
    set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe
    echo Found Python 3.13
    goto :build
)

REM Check Python312
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe" (
    set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe
    echo Found Python 3.12
    goto :build
)

echo ERROR: Python not found!
echo Please install Python from https://www.python.org/downloads/
pause
exit /b 1

:build
"%PYTHON%" --version
echo.

echo [1/3] Installing dependencies...
"%PYTHON%" -m pip install --upgrade pip --quiet
"%PYTHON%" -m pip install pyinstaller playwright winotify pyperclip --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo OK
echo.

echo [2/3] Installing Chromium...
"%PYTHON%" -m playwright install chromium
echo OK
echo.

echo [3/3] Building EXE...
echo This may take 3-5 minutes...
echo.

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

"%PYTHON%" -m PyInstaller --name=BB_Scanner --onefile --windowed --add-data=app;app --hidden-import=playwright --hidden-import=playwright.async_api --hidden-import=winotify --hidden-import=pyperclip --collect-all=playwright run_scanner.py

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







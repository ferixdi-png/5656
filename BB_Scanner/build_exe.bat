@echo off
chcp 65001 >nul
echo ========================================
echo   Сборка EXE-файла BetBoom Scanner
echo ========================================
echo.

cd /d "%~dp0"

REM Проверяем Python (пробуем разные варианты)
set "PYTHON_CMD="

REM Вариант 1: python в PATH
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto python_found
)

REM Вариант 2: py launcher (обычно работает даже без PATH)
"C:\Users\%USERNAME%\AppData\Local\Programs\Python\Launcher\py.exe" --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Launcher\py.exe"
    goto python_found
)

REM Вариант 3: прямой путь к python.exe
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe" (
    set "PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe"
    goto python_found
)

REM Вариант 4: через py без полного пути
py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto python_found
)

echo ОШИБКА: Python не найден!
echo.
echo Python установлен, но не доступен в командной строке.
echo.
echo РЕШЕНИЕ: Перезагрузите компьютер или откройте НОВОЕ окно cmd.
echo Python был установлен, но PATH обновится после перезагрузки.
echo.
pause
exit /b 1

:python_found
echo Найден Python: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

echo [1/4] Установка PyInstaller...
%PYTHON_CMD% -m pip install pyinstaller

echo.
echo [2/4] Установка зависимостей...
%PYTHON_CMD% -m pip install playwright winotify pyperclip

echo.
echo [3/4] Установка браузера Chromium...
%PYTHON_CMD% -m playwright install chromium

echo.
echo [4/4] Сборка EXE-файла...
echo Это может занять 3-5 минут...
echo.

REM Удаляем старые build файлы
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Собираем exe
%PYTHON_CMD% -m PyInstaller --name="BB_Scanner" ^
    --onefile ^
    --windowed ^
    --icon=NONE ^
    --add-data "app;app" ^
    --hidden-import=playwright ^
    --hidden-import=playwright.async_api ^
    --hidden-import=winotify ^
    --hidden-import=pyperclip ^
    --collect-all playwright ^
    run_scanner.py

if errorlevel 1 (
    echo.
    echo ОШИБКА при сборке!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Сборка завершена!
echo ========================================
echo.
echo EXE-файл находится в папке: dist\BB_Scanner.exe
echo.
echo Вы можете скопировать dist\BB_Scanner.exe на рабочий стол
echo и запускать его напрямую - Python не нужен!
echo.
pause

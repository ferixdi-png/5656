@echo off
chcp 65001 >nul
echo ========================================
echo   АВТОМАТИЧЕСКАЯ СБОРКА EXE
echo ========================================
echo.

cd /d "%~dp0"

REM Ищем Python в разных местах
set "PYTHON_EXE="

echo Поиск Python...

REM Вариант 1: Стандартное место установки
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe" (
    set "PYTHON_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe"
    echo Найден: %PYTHON_EXE%
    goto found
)

REM Вариант 2: Python 3.13
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe"
    echo Найден: %PYTHON_EXE%
    goto found
)

REM Вариант 3: Python 3.12
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
    echo Найден: %PYTHON_EXE%
    goto found
)

REM Вариант 4: Python 3.11
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe"
    echo Найден: %PYTHON_EXE%
    goto found
)

REM Вариант 5: Python 3.10
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe"
    echo Найден: %PYTHON_EXE%
    goto found
)

REM Вариант 6: Program Files
if exist "C:\Program Files\Python314\python.exe" (
    set "PYTHON_EXE=C:\Program Files\Python314\python.exe"
    echo Найден: %PYTHON_EXE%
    goto found
)

echo.
echo ❌ Python не найден автоматически!
echo.
echo Пожалуйста:
echo 1. Перезагрузите компьютер (самый простой способ)
echo 2. Или откройте файл РЕШЕНИЕ_ПРОБЛЕМЫ.txt
echo.
pause
exit /b 1

:found
echo.
%PYTHON_EXE% --version
echo.

echo [1/4] Установка PyInstaller...
%PYTHON_EXE% -m pip install --upgrade pip
%PYTHON_EXE% -m pip install pyinstaller

echo.
echo [2/4] Установка зависимостей...
%PYTHON_EXE% -m pip install playwright winotify pyperclip

echo.
echo [3/4] Установка браузера Chromium...
%PYTHON_EXE% -m playwright install chromium

echo.
echo [4/4] Сборка EXE-файла...
echo Это может занять 3-5 минут...
echo.

REM Удаляем старые build файлы
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Собираем exe
%PYTHON_EXE% -m PyInstaller --name="BB_Scanner" ^
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
    echo ❌ ОШИБКА при сборке!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   ✅ Сборка завершена успешно!
echo ========================================
echo.
echo 📁 EXE-файл: dist\BB_Scanner.exe
echo.
echo Теперь вы можете:
echo - Запустить dist\BB_Scanner.exe напрямую
echo - Скопировать его куда угодно
echo - Python больше не нужен!
echo.
pause







@echo off
chcp 65001 >nul
echo ========================================
echo   BetBoom Live Scanner
echo   Запуск приложения...
echo ========================================
echo.

REM Переходим в папку скрипта
cd /d "%~dp0"

REM Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден!
    echo.
    echo Установите Python 3.10+ с python.org
    echo Или используйте python из PATH
    echo.
    pause
    exit /b 1
)

REM Создаем виртуальное окружение если его нет
if not exist "venv" (
    echo Создание виртуального окружения...
    python -m venv venv
    echo.
)

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

REM Устанавливаем зависимости если их нет
if not exist "venv\Lib\site-packages\playwright" (
    echo Установка зависимостей...
    echo Это может занять несколько минут...
    echo.
    pip install --upgrade pip
    pip install playwright winotify pyperclip
    echo.
    echo Установка браузера Chromium...
    python -m playwright install chromium
    echo.
)

REM Запускаем приложение
echo Запуск сканера...
echo.
python run_scanner.py

if errorlevel 1 (
    echo.
    echo ОШИБКА: Приложение завершилось с ошибкой
    pause
)








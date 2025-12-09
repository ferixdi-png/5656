@echo off
chcp 65001 >nul

REM ВАЖНО: Переходим в директорию, где находится этот скрипт
cd /d "%~dp0"

REM Проверяем, что мы в правильной директории
if not exist "run_bot.py" (
    echo [ОШИБКА] Файл run_bot.py не найден!
    echo Текущая директория: %CD%
    echo Ожидаемая директория: %~dp0
    echo.
    echo Убедитесь, что вы запускаете скрипт из папки с ботом.
    pause
    exit /b 1
)

echo ========================================
echo   Запуск KIE Telegram Bot
echo ========================================
echo.
echo Директория: %CD%
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не установлен!
    echo Установите Python 3.8+ с python.org
    pause
    exit /b 1
)

REM Установка зависимостей (если нужно)
echo Проверка зависимостей...
python -c "import telegram" >nul 2>&1
if errorlevel 1 (
    echo Установка зависимостей...
    pip install python-telegram-bot python-dotenv aiohttp
)

echo.
echo ========================================
echo   Очистка кэша Python...
echo ========================================
echo.

REM Очистка кэша Python для принудительной перезагрузки модулей
echo Очистка кэша Python...
if exist "__pycache__" (
    echo   - Удаление __pycache__...
    rmdir /s /q "__pycache__" 2>nul
)
REM Удаляем все .pyc файлы в корне
del /q *.pyc 2>nul
REM Удаляем кэш для всех модулей
for /d %%d in (*) do (
    if exist "%%d\__pycache__" (
        echo   - Удаление %%d\__pycache__...
        rmdir /s /q "%%d\__pycache__" 2>nul
    )
)

echo Кэш полностью очищен!
echo.
echo ========================================
echo   Бот запускается...
echo   Нажмите Ctrl+C для остановки
echo ========================================
echo.

REM Запуск бота с явным указанием пути
python "%~dp0run_bot.py"

pause


@echo off
chcp 65001 >nul
cls
echo.
echo ═══════════════════════════════════════════════════════════
echo   ЗАПУСК KIE TELEGRAM BOT
echo ═══════════════════════════════════════════════════════════
echo.

echo Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo Установите Python с https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python найден
python --version
echo.

echo Проверка основных модулей...
python -c "import telegram; import dotenv; import aiohttp" 2>nul
if errorlevel 1 (
    echo [ОШИБКА] Не все зависимости установлены!
    echo Установите их: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo [OK] Все зависимости установлены
echo.

echo Проверка файла .env...
if not exist .env (
    echo [ПРЕДУПРЕЖДЕНИЕ] Файл .env не найден!
    echo Создайте файл .env с настройками бота
    echo Или запустите setup.bat для создания .env
    echo.
    set /p CONTINUE="Продолжить запуск? (y/n): "
    if /i not "%CONTINUE%"=="y" exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════
echo   ЗАПУСК БОТА...
echo ═══════════════════════════════════════════════════════════
echo.
echo Для остановки нажмите Ctrl+C
echo.

python run_bot.py

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Бот завершился с ошибкой!
    echo Проверьте логи выше для диагностики
    pause
)





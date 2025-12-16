@echo off
chcp 65001 >nul
cls
echo.
echo ═══════════════════════════════════════════════════════════
echo   УСТАНОВКА ВСЕХ ЗАВИСИМОСТЕЙ
echo ═══════════════════════════════════════════════════════════
echo.

python --version
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    pause
    exit /b 1
)

echo.
echo Обновление pip...
python -m pip install --upgrade pip --quiet

echo.
echo Установка всех зависимостей из requirements.txt...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось установить некоторые зависимости!
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════
echo   ПРОВЕРКА УСТАНОВЛЕННЫХ ПАКЕТОВ
echo ═══════════════════════════════════════════════════════════
echo.

echo Основные пакеты:
python -m pip list | findstr /i "telegram dotenv aiohttp aiofiles Pillow pytesseract"

echo.
echo ═══════════════════════════════════════════════════════════
echo   [УСПЕХ] Все зависимости установлены!
echo ═══════════════════════════════════════════════════════════
echo.
echo Следующие шаги:
echo 1. ЗАКРОЙТЕ VS Code полностью
echo 2. Откройте VS Code заново
echo 3. Ошибки импорта должны исчезнуть!
echo.
pause



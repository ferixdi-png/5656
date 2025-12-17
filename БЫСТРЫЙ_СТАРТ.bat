@echo off
chcp 65001 >nul
cls
echo.
echo ═══════════════════════════════════════════════════════════
echo   БЫСТРЫЙ СТАРТ - УСТАНОВКА ЗАВИСИМОСТЕЙ
echo ═══════════════════════════════════════════════════════════
echo.

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo.
    echo Сначала установите Python:
    echo 1. Скачайте с https://www.python.org/downloads/
    echo 2. При установке отметьте "Add Python to PATH"
    echo 3. Перезапустите этот скрипт
    echo.
    echo Подробная инструкция в файле: ПРОСТАЯ_УСТАНОВКА.txt
    echo.
    pause
    exit /b 1
)

echo [OK] Python найден
python --version
echo.

echo ═══════════════════════════════════════════════════════════
echo   УСТАНОВКА ЗАВИСИМОСТЕЙ
echo ═══════════════════════════════════════════════════════════
echo.

echo Обновление pip...
python -m pip install --upgrade pip --quiet
echo.

echo Установка пакетов из requirements.txt...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось установить зависимости!
    echo Проверьте подключение к интернету.
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════
echo   [УСПЕХ] Все зависимости установлены!
echo ═══════════════════════════════════════════════════════════
echo.
echo Следующие шаги:
echo 1. Перезапустите VS Code (Ctrl+Shift+P → Reload Window)
echo 2. Ошибки импорта должны исчезнуть!
echo.
pause








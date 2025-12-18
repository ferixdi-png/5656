@echo off
REM Скрипт запуска тестов для Windows

echo 🧪 Запуск тестов...

REM Устанавливаем тестовые переменные окружения
set TEST_MODE=1
set DRY_RUN=1
set ALLOW_REAL_GENERATION=0
set TELEGRAM_BOT_TOKEN=test_token_12345
set KIE_API_KEY=test_api_key
set ADMIN_ID=12345

REM Запускаем pytest
pytest -q tests/

REM Проверяем результат
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Все тесты прошли успешно!
    exit /b 0
) else (
    echo.
    echo ❌ Некоторые тесты не прошли
    exit /b 1
)


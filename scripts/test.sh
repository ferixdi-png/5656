#!/bin/bash
# Скрипт запуска тестов с правильными env переменными

set -e

echo "🧪 Запуск тестов..."

# Устанавливаем тестовые переменные окружения
export TEST_MODE=1
export DRY_RUN=1
export ALLOW_REAL_GENERATION=0
export TELEGRAM_BOT_TOKEN=test_token_12345
export KIE_API_KEY=test_api_key
export ADMIN_ID=12345

# Запускаем pytest
pytest -q tests/

# Выводим результат
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Все тесты прошли успешно!"
    exit 0
else
    echo ""
    echo "❌ Некоторые тесты не прошли"
    exit 1
fi


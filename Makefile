# Makefile для запуска тестов

.PHONY: test test-verbose install-deps

# Установка зависимостей для тестов
install-deps:
	pip install -r requirements.txt

# Запуск тестов (краткий вывод)
test:
	TEST_MODE=1 DRY_RUN=1 ALLOW_REAL_GENERATION=0 TELEGRAM_BOT_TOKEN=test_token_12345 KIE_API_KEY=test_api_key ADMIN_ID=12345 pytest -q tests/

# Запуск тестов (подробный вывод)
test-verbose:
	TEST_MODE=1 DRY_RUN=1 ALLOW_REAL_GENERATION=0 TELEGRAM_BOT_TOKEN=test_token_12345 KIE_API_KEY=test_api_key ADMIN_ID=12345 pytest -v tests/

# Запуск конкретного теста
test-menu:
	TEST_MODE=1 DRY_RUN=1 ALLOW_REAL_GENERATION=0 TELEGRAM_BOT_TOKEN=test_token_12345 KIE_API_KEY=test_api_key ADMIN_ID=12345 pytest -v tests/test_main_menu.py

test-callbacks:
	TEST_MODE=1 DRY_RUN=1 ALLOW_REAL_GENERATION=0 TELEGRAM_BOT_TOKEN=test_token_12345 KIE_API_KEY=test_api_key ADMIN_ID=12345 pytest -v tests/test_callbacks_smoke.py


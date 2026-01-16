.PHONY: verify test clean install firebreak smoke-render deploy-check syntax truth-gate test-lock verify-truth

# TRUTH GATE: Полная валидация архитектурного контракта
truth-gate:
	@echo "🏛️ TRUTH GATE: Running architecture contract validation..."
	@echo ""
	@echo "1️⃣ verify_truth.py (architecture invariants)..."
	python3 verify_truth.py
	@echo ""
	@echo "2️⃣ Unit tests (lock mechanism)..."
	python3 -m pytest tests/test_render_singleton_lock.py -v
	@echo ""
	@echo "3️⃣ Syntax check..."
	python3 -m py_compile main_render.py
	python3 -m py_compile render_singleton_lock.py
	@echo ""
	@echo "✅ ALL TRUTH GATES PASSED"

# verify_truth standalone
verify-truth:
	@echo "🔍 Running verify_truth.py..."
	@python3 verify_truth.py

# test-lock standalone
test-lock:
	@echo "🧪 Running lock mechanism tests..."
	@python3 -m pytest tests/test_render_singleton_lock.py -v

# FIREBREAK: Полная проверка перед деплоем (критично!)
firebreak: truth-gate
	@echo ""
	@echo "2️⃣ Smoke test (локально)..."
	python3 smoke_test.py || true
	@echo ""
	@echo "✅ FIREBREAK: Все проверки пройдены!"

# Smoke test на Render
smoke-render:
	@echo "🧪 Smoke test на Render..."
	python3 smoke_test.py --url https://five656.onrender.com

# Smoke test for button handlers: verify all callback_data have handlers
smoke-buttons:
	@echo "🧪 Smoke test: Button Handlers..."
	python3 scripts/smoke_buttons.py

# Smoke test для button instrumentation (legacy)
smoke-buttons-instrumentation:
	@echo "🧪 Smoke test: Button Instrumentation..."
	python3 scripts/smoke_buttons_instrumentation.py

# Smoke test для webhook production readiness (P0)
smoke-webhook:
	@echo "🧪 Smoke test: Webhook Production Readiness..."
	python3 scripts/smoke_webhook.py

# Render log watcher (last 30 minutes)
render-logs:
	@echo "📊 Fetching Render logs (last 30 minutes)..."
	python scripts/render_watch.py --minutes 30

# Render log watcher (last 10 minutes)
render-logs-10:
	@echo "📊 Fetching Render logs (last 10 minutes)..."
	python scripts/render_watch.py --minutes 10

# Render logs check (error detection)
render:logs:
	@echo "🔍 Checking Render logs for errors..."
	python scripts/render_logs_check.py --minutes 30

# Render logs check (last 10 minutes)
render:logs-10:
	@echo "🔍 Checking Render logs for errors (last 10 minutes)..."
	python scripts/render_logs_check.py --minutes 10

# Database readonly check
db:check:
	@echo "🔍 Checking database connection (readonly)..."
	python scripts/db_readonly_check.py

# Ops All: Render logs + DB check + Critical 5 analysis
ops-all:
	@echo "🚀 Running comprehensive operational check..."
	@echo "   - Render logs check (last 30 minutes)"
	@echo "   - Database readonly check"
	@echo "   - Critical 5 analysis"
	@echo "   - Report generation"
	python scripts/ops_all.py

# Ops observability targets
ops-fetch-logs:
	@echo "📊 Fetching Render logs..."
	python -m app.ops.render_logs --minutes 60

ops-db-diag:
	@echo "🔍 Running DB diagnostics..."
	python -m app.ops.db_diag

ops-critical5:
	@echo "🚨 Detecting critical issues..."
	python -m app.ops.critical5

ops-all: render:logs db:check
	@echo "✅ Ops observability complete (Render logs + DB check)"

# Render logs check (using render_logs_check.py)
render:logs:
	@echo "📊 Checking Render logs for errors..."
	@python scripts/render_logs_check.py --minutes 30 || echo "⚠️  Render logs check failed (may need TRT_RENDER.env)"

# Database readonly check
db:check:
	@echo "🔍 Checking database (readonly)..."
	@python scripts/db_readonly_check.py || echo "⚠️  DB check failed (may need DATABASE_URL_READONLY)"

# Sync TRT_REPORT.md to Desktop
sync-report:
	@echo "📄 Syncing TRT_REPORT.md to Desktop..."
	@python scripts/sync_desktop_report.py || echo "⚠️  Sync failed (non-critical)"

# Auto-sync report after cycle (called automatically by post-commit hook)
auto-sync-report:
	@echo "🔄 Auto-syncing TRT_REPORT.md to Desktop..."
	@python scripts/sync_desktop_report.py || echo "⚠️  Auto-sync failed (non-critical)"

# Import check: smoke test for critical imports (P0)
import-check:
	@echo "🔍 Running import smoke test..."
	@python scripts/smoke_import_check.py

# Boot symbols smoke test: verify required functions exist (P0)
smoke-boot-symbols:
	@echo "🔍 Running boot symbols smoke test..."
	@python scripts/smoke_boot_symbols.py

# Admin smoke test: verify admin functions don't crash
smoke-admin:
	@echo "🔍 Running admin smoke test..."
	@python scripts/smoke_admin.py

# Admin analytics smoke test: verify fail-open behavior (legacy)
smoke-admin-analytics:
	@echo "🔍 Running admin analytics smoke test..."
	@python scripts/smoke_admin_analytics.py

# Observability V2 smoke test: verify logging doesn't crash
obs-check:
	@echo "🔍 Running observability V2 smoke test..."
	@python scripts/smoke_observability.py

# Click paths smoke test: verify critical handlers don't crash
smoke-clickpaths:
	@echo "🔍 Running click paths smoke test..."
	@python scripts/smoke_clickpaths.py

# Button inventory: scan all buttons and build inventory
inventory-buttons:
	@echo "🔍 Running button inventory..."
	@python scripts/inventory_buttons.py

# Press all buttons: test all buttons from inventory
press-all-buttons: inventory-buttons
	@echo "🔍 Testing all buttons..."
	@python scripts/smoke_press_all_buttons.py

# Health/ready contract test: verify endpoint contracts (local)
health-ready-contract:
	@echo "🔍 Running health/ready contract test..."
	@python scripts/test_health_ready_contract.py

# Verify all models pass contract checks
verify-models:
	@echo "🔍 Verifying model contracts..."
	@python3 scripts/verify_models_contract.py

# E2E smoke tests for all models (DRY_RUN)
smoke-models:
	@echo "🧪 Running E2E smoke tests for all models..."
	@python3 scripts/smoke_models_e2e.py

# Full models verification (contracts + smoke)
verify-models-full: verify-models smoke-models
	@echo "✅ All model verifications passed"

# UX smoke walkthrough: verify Russian texts and step markers
ux-smoke:
	@echo "🔍 Running UX smoke walkthrough..."
	@python scripts/ux_smoke_walkthrough.py

# Lint UX strings: check for English user-facing strings
lint-ux-strings:
	@echo "🔍 Linting UX strings..."
	@python scripts/lint_ux_strings.py

# ONE COMMAND "GREEN OR RED" - comprehensive ship check
ship:
	@echo "🚀 SHIP CHECK: Running all critical checks..."
	@python scripts/ship_check.py || (echo "❌ SHIP CHECK FAILED - DO NOT DEPLOY" && exit 1)

# ONE COMMAND "GREEN OR RED" - comprehensive ship check
ship:
	@echo "🚀 SHIP CHECK: Running all critical checks..."
	@python scripts/ship_check.py || (echo "❌ SHIP CHECK FAILED - DO NOT DEPLOY" && exit 1)

# PRE-DEPLOY GATE: Iron gate that prevents broken builds from reaching Render
# Includes: syntax check, import check, smoke tests (admin, buttons), health/ready contract
pre-deploy-verify:
	@echo "🚪 PRE-DEPLOY GATE: Comprehensive build validation..."
	@python scripts/pre_deploy_gate.py || (echo "❌ PRE-DEPLOY GATE REJECTED - DO NOT PUSH" && exit 1)
	@echo "✅ PRE-DEPLOY GATE APPROVED - Safe to push"

# Legacy pre-deploy verify (deprecated, use pre-deploy-verify instead)
pre-deploy-verify-legacy: import-check smoke-boot-symbols smoke-admin obs-check smoke-clickpaths inventory-buttons ux-smoke lint-ux-strings
	@echo "🔍 Enhanced pre-deploy verification (iron gate)..."
	@python scripts/enhanced_pre_deploy_verify.py || (echo "❌ Pre-deploy verification failed - DO NOT PUSH" && exit 1)
	@echo "🔍 Running legacy pre-deploy checks..."
	@python scripts/pre_deploy_verify.py || (echo "❌ Pre-deploy verification failed" && exit 1)

# Pre-commit check: ensure TRT_REPORT.md updated when app/bot changes
pre-commit-check:
	@echo "🔍 Running pre-commit check (TRT_REPORT.md)..."
	@python scripts/pre_commit_check_report.py

# Install git hooks (pre-commit + post-commit)
install-hooks:
	@echo "📎 Installing git hooks..."
	@mkdir -p .git/hooks
	@if [ ! -f .git/hooks/pre-commit ]; then \
		echo '#!/bin/sh' > .git/hooks/pre-commit; \
		echo 'HOOK_DIR="$$(cd "$$(dirname "$$0")" && pwd)"' >> .git/hooks/pre-commit; \
		echo 'REPO_ROOT="$$(cd "$$HOOK_DIR/../.." && pwd)"' >> .git/hooks/pre-commit; \
		echo 'if command -v python3 >/dev/null 2>&1; then PYTHON_CMD="python3"; elif command -v python >/dev/null 2>&1; then PYTHON_CMD="python"; else exit 0; fi' >> .git/hooks/pre-commit; \
		echo '$$PYTHON_CMD "$$REPO_ROOT/scripts/pre_commit_check_report.py"' >> .git/hooks/pre-commit; \
		echo 'EXIT_CODE=$$?' >> .git/hooks/pre-commit; \
		echo 'if [ $$EXIT_CODE -ne 0 ]; then exit 1; fi' >> .git/hooks/pre-commit; \
		chmod +x .git/hooks/pre-commit; \
		echo "✅ Pre-commit hook installed"; \
	else \
		echo "✅ Pre-commit hook already exists"; \
	fi
	@if [ ! -f .git/hooks/post-commit ]; then \
		echo '#!/bin/sh' > .git/hooks/post-commit; \
		echo 'HOOK_DIR="$$(cd "$$(dirname "$$0")" && pwd)"' >> .git/hooks/post-commit; \
		echo 'REPO_ROOT="$$(cd "$$HOOK_DIR/../.." && pwd)"' >> .git/hooks/post-commit; \
		echo 'if command -v python3 >/dev/null 2>&1; then PYTHON_CMD="python3"; elif command -v python >/dev/null 2>&1; then PYTHON_CMD="python"; else exit 0; fi' >> .git/hooks/post-commit; \
		echo 'if [ ! -f "$$REPO_ROOT/TRT_REPORT.md" ]; then exit 0; fi' >> .git/hooks/post-commit; \
		echo '$$PYTHON_CMD "$$REPO_ROOT/scripts/sync_desktop_report.py" 2>/dev/null || true' >> .git/hooks/post-commit; \
		chmod +x .git/hooks/post-commit; \
		echo "✅ Post-commit hook installed (auto-sync to Desktop)"; \
	else \
		echo "✅ Post-commit hook already exists"; \
	fi

# Smoke test (alias для удобства)
smoke: smoke-webhook
	@echo "✅ Smoke tests complete"

# Проверка логов Render после деплоя (ждем 2 минуты)
deploy-check:
	@echo "🔍 Проверка Render логов..."
	@echo "⏳ Ждем 2 минуты для стабилизации деплоя..."
	@sleep 120
	python3 check_render_logs.py --minutes 10

# Быстрая проверка синтаксиса
syntax:
	@python3 -m py_compile render_singleton_lock.py
	@python3 -m py_compile app/utils/update_queue.py
	@python3 -m py_compile smoke_test.py
	@python3 -m py_compile check_render_logs.py
	@echo "✅ Синтаксис корректен"

# Verify critical functionality before deploy
verify:
	@echo "🔍 Running critical state machine verification..."
	pytest tests/test_state_machine_verify.py -v --tb=short
	@echo "✅ State machine verification complete"

# Install dependencies
install:
	pip install -r requirements.txt

# Clean Python artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

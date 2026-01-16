# План очистки репозитория

## ✅ Безопасно удалить (не используются в основном коде)

### 1. Старые entry points (заменены на main_render.py)
- `bot_kie.py` - старый entry point, не используется
- `run_bot.py` - если есть, старый entry point

### 2. Старые клиенты (заменены на app/kie/client_v4.py)
- `kie_client.py` - старый клиент в корне
- `kie_gateway.py` - старый gateway
- `kie_universal_handler.py` - старый handler
- `kie_input_adapter.py` - старый adapter
- `kie_validator.py` - если есть в корне (есть в app/kie/validator.py)
- `kie_models.py` - старый файл
- `kie_schema.py` - старый файл

### 3. Тестовые validate_*.py файлы (не используются в основном коде)
- Все `validate_*.py` в корне (70+ файлов)

### 4. Временные скрипты
- Все `.bat` файлы (auto_*.bat, check_*.bat, fix_*.bat, setup_*.bat, etc.)
- Все `.ps1` файлы (auto_*.ps1, setup_*.ps1, etc.)
- Все `.sh` файлы (кроме критичных)

### 5. Старые отчеты и документация
- Все `*_REPORT*.md` кроме TRT_REPORT.md
- Все `*_SUMMARY*.md`
- Все `*_FIXES*.md`
- Все `*_STATUS*.md`
- Все `*_FINAL*.md`
- `TRT_REPORT_OLD.md`, `TRT_REPORT_v2.md`, `TRT_REPORT.md.old`

### 6. Папки с архивными файлами
- `quarantine/` - старые файлы
- `archive/` - архивные отчеты
- `legacy/` - старые скрипты
- `artifacts/` - можно очистить (генерируются автоматически)

### 7. Временные файлы
- `*.zip` файлы (5656-main-ideal-self.zip)
- `*.json` результаты тестов (all_models_test_results.json, etc.)
- `*.txt` логи и результаты (audit_output.txt, validation_output.txt, etc.)

### 8. Дубликаты конфигов
- `Dockerfile.optimized` - если есть основной Dockerfile
- `config.json.example` - если есть другой example
- `render.yaml.example` - если есть основной render.yaml

### 9. Старые бизнес-логика файлы (если есть в app/)
- `business_layer.py` - проверить, используется ли
- `database.py` - проверить, используется ли (есть app/database/)

### 10. Неиспользуемые папки
- `betboom_scanner/` - если не используется
- `bb_tt_scanner/` - если не используется
- `scanner_app/` - если не используется
- `scanner_min/` - если не используется
- `kie_sync/` - если не используется
- `5656/` - если не используется

## ⚠️ ОСТОРОЖНО (проверить перед удалением)

### Файлы, которые могут использоваться
- `helpers.py` - проверить импорты
- `config.py` - проверить, используется ли
- `database.py` - проверить, используется ли
- Все файлы в `app/` и `bot/` - НЕ ТРОГАТЬ без проверки

## ✅ Оставить (критичные файлы)

- `main_render.py` - основной entry point
- `requirements.txt`, `requirements-prod.txt`
- `Dockerfile`
- `README.md`
- `TRT_REPORT.md`
- `KIE_AI_INTEGRATION_AUDIT.md`
- Все файлы в `app/`, `bot/`, `models/`, `migrations/`
- `.gitignore`
- `pyproject.toml`, `pytest.ini`


# KIE Market Synchronizer

Автоматическая синхронизация моделей и цен с https://kie.ai/market

## Быстрый старт

### Локальная синхронизация

1. **Логин (один раз)**:
   ```bash
   python tools/kie_sync/login_kie.py
   ```
   Браузер откроется, войдите вручную. Сохранится `.cache/kie_storage_state.json`.

2. **Синхронизация**:
   ```bash
   # Тест (dry-run)
   python tools/kie_sync/export_market.py --dry-run --limit 5
   
   # Полная синхронизация
   python tools/kie_sync/export_market.py --sync
   ```

### CI/CD (GitHub Actions)

Workflow автоматически запускается раз в день и синхронизирует модели.

#### Настройка GitHub Secrets

1. **Откройте https://kie.ai/market в браузере и войдите**

2. **Откройте DevTools (F12) → Network → найдите любой запрос к kie.ai**

3. **Скопируйте Cookie header:**
   - В DevTools выберите запрос
   - Найдите заголовок `Cookie:`
   - Скопируйте всё значение (например: `session=abc123; token=xyz789`)

4. **Добавьте в GitHub Secrets:**
   - Репозиторий → Settings → Secrets and variables → Actions
   - New repository secret
   - Name: `KIE_COOKIE_HEADER`
   - Value: вставьте скопированный Cookie header (весь, включая все куки через `;`)

5. **Проверка:**
   - Actions → KIE Market Sync → Run workflow (manual trigger)
   - Проверьте что синхронизация прошла успешно

#### Формат Cookie Header

```
session=abc123def456; token=xyz789; _ga=GA1.2.1234567890
```

⚠️ **Важно:** Не логируйте cookie header в коде или логах!

## Файлы

- `login_kie.py` - локальный логин, сохраняет storage state
- `export_market.py` - экспорт моделей (использует storage state)
- `run_all.py` - экспорт для CI (использует cookie header из env)

## Выходные файлы

- `models/catalog.yaml` - схемы input параметров всех моделей
- `models/catalog.json` - то же в JSON (автоматически)
- `pricing/config.yaml` - цены моделей (USD, матрицы или unsupported)

## Параметры

```bash
--dry-run          # Показать что изменится, не писать файлы
--sync             # Записать изменения в файлы
--only "wan/"      # Только модели с префиксом
--limit 5          # Ограничить количество моделей (для теста)
```

## Структура catalog.yaml

```yaml
meta:
  source: "kie.ai/market"
  synced_at: 1234567890000
models:
  wan/2-6-text-to-video:
    title: "WAN 2.6 Text-to-Video"
    source_url: "https://kie.ai/market/wan-2-6-text-to-video"
    endpoint:
      create_task: "/api/v1/jobs/createTask"
      query_task: "/api/v1/jobs/recordInfo"
    input_schema:
      prompt:
        type: string
        required: true
        max_len: 800
      duration:
        type: string
        required: false
        values: ["5", "10", "15"]
```

## Структура pricing/config.yaml

```yaml
models:
  wan/2-6-text-to-video:
    type: matrix
    axes: ["duration", "resolution"]
    table:
      "5":
        "720p": 0.35
        "1080p": 0.53
```

Или для моделей без извлечённого pricing:

```yaml
  model-name:
    unsupported: true
    reason: "pricing_not_extracted"
```




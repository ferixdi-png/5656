# KIE (Knowledge Is Everything) Telegram Bot

Production-grade Telegram bot for AI model generation via Kie.ai API.

**📚 Документация:**
- [🚀 Quick Start для разработчиков](./QUICK_START_DEV.md)
- [🤝 Contributing Guidelines](./CONTRIBUTING.md)
- [🌐 Deployment на Render](./DEPLOYMENT.md)

**📊 Статус:** Production Ready | 72 модели | PostgreSQL + SQLite

---

## 🚀 БЫСТРЫЙ СТАРТ

### Codespaces Quickstart

Запуск в GitHub Codespaces занимает 1-2 минуты:

```bash
# 1) Открой репозиторий в Codespaces (Use this template → Create Codespace)
# 2) Проверь Python и окружение
python3 --version
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) Базовая проверка проекта
make verify

# 4) Локальный запуск (webhook/polling по необходимости)
source .env.test && python main_render.py
```

Devcontainer (.devcontainer/devcontainer.json) настроен: venv + зависимости устанавливаются автоматически; при необходимости запусти команды выше вручную.

### Локальная разработка:

```bash
# 1. Установи зависимости
pip install -r requirements.txt

# 2. Установи переменные окружения (см. ниже)

# 3. Запусти бота
BOT_MODE=polling python bot_kie.py
```

### Deploy to Render (за 3 минуты):

1. **PostgreSQL база:** New → PostgreSQL → Free tier
2. **Web Service:** New → Web Service → Python 3
3. **ENV переменные:**
   ```bash
   TELEGRAM_BOT_TOKEN=7...     # от @BotFather
   KIE_API_KEY=kie_...         # от Kie.ai
   DATABASE_URL=postgresql://  # Internal URL
   ADMIN_ID=123456789          # ваш Telegram ID
   BOT_MODE=webhook            # ОБЯЗАТЕЛЬНО для Render
   ```
4. **Deploy!** → Бот работает

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
python main_render.py
```

### Render Deploy Checklist

- ENV (обязательные):
   - `TELEGRAM_BOT_TOKEN`, `KIE_API_KEY`, `DATABASE_URL`, `ADMIN_ID`, `BOT_MODE=webhook`, `PORT`
- ENV (рекомендуемые):
   - `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET_PATH`, `WEBHOOK_SECRET_TOKEN`, `DB_MAXCONN`
- Build: `pip install -r requirements.txt`
- Start: `python main_render.py`
- Health URL: `/health` (GET) — ожидается 200
- Webhook URL: `${WEBHOOK_BASE_URL}/webhook/${TELEGRAM_BOT_TOKEN}` — секрет-токен проверяется, если задан

**FINAL RENDER REQUIREMENTS (источник правды):**

| Переменная | Обязательно | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен от @BotFather |
| `KIE_API_KEY` | ✅ | API ключ от kie.ai |
| `DATABASE_URL` | ✅ | PostgreSQL DSN (Internal URL из Render) |
| `ADMIN_ID` | ✅ | Ваш Telegram ID (целое число) |
| `BOT_MODE` | ✅ | Должен быть `webhook` для Render |
| `PORT` | ✅ | По умолчанию 8000 (Render устанавливает автоматически) |
| `WEBHOOK_BASE_URL` | ✅ для webhook | Полный URL вашего сервиса (https://yourservice.onrender.com) |
| `WEBHOOK_SECRET_PATH` | ⭐ рекомендуется | Скрытая часть пути webhook (для безопасности, например `secret123`) |
| `WEBHOOK_SECRET_TOKEN` | ⭐ рекомендуется | Дополнительный токен валидации для Telegram webhook (генерируй с `openssl rand -hex 32`) |
| `KIE_CALLBACK_PATH` | ⭐ рекомендуется | Путь для KIE callback (по умолчанию `callbacks/kie`) |
| `KIE_CALLBACK_TOKEN` | ⭐ рекомендуется | Токен валидации для KIE callback (генерируй с `openssl rand -hex 32`) |
| `DB_MAXCONN` | Опционально | Макс. connections к БД (по умолчанию 5) |
| `PAYMENT_BANK`, `PAYMENT_CARD_HOLDER`, `PAYMENT_PHONE` | Опционально | Для платежных систем (если используются) |
| `SUPPORT_TELEGRAM`, `SUPPORT_TEXT` | Опционально | Контакты поддержки для пользователей |

**Webhook URLs (как их найти):**

1. **Telegram webhook** → Render URL будет: `https://yourservice.onrender.com/webhook/{WEBHOOK_SECRET_PATH}`
   - Telegram отправляет POST с header `X-Telegram-Bot-Api-Secret-Token: {WEBHOOK_SECRET_TOKEN}`
   
2. **KIE callback** → URL будет: `https://yourservice.onrender.com/{KIE_CALLBACK_PATH}`
   - KIE отправляет POST с header `X-KIE-Callback-Token: {KIE_CALLBACK_TOKEN}`

**Health check:** `curl https://yourservice.onrender.com/health`  
→ Ожидается: `{"status": "ok", "storage": "postgres", "kie_mode": "real"}`

**⚠️ РИСК: Кредиты KIE.ai** — В PRODUCTION 402 ошибка вернёт **честный FAIL** (не мок). Убедись, что:
- Ключ `KIE_API_KEY` актуален  
- На аккаунте Kie.ai достаточно кредитов  
- Режим тестирования отключен (`DRY_RUN` и `TEST_MODE` = 0 или не установлены)

### Автоматический деплой через GitHub Actions:

1. **Добавь GitHub Secrets** (один раз):
   - `RENDER_DEPLOY_HOOK` (предпочтительно) ИЛИ `RENDER_API_KEY` + `RENDER_SERVICE_ID`
   - `RENDER_HEALTH_URL` (опционально, для health check)

2. **Push в main** → CI запускается автоматически
3. **После CI PASS** → Deploy на Render автоматически

**Подробнее:** см. `GITHUB_ACTIONS_SETUP.md`

**GitHub Secrets (один раз):**
- Перейди: Repository → Settings → Secrets and variables → Actions
- Добавь: `RENDER_DEPLOY_HOOK` = `https://api.render.com/deploy/srv-XXXXX?key=XXXXX`
  - Получи из: Render Dashboard → Service → Settings → Deploy Hook

---

## ✅ Проверка перед деплоем

### Локальная разработка (с .env.test):

```bash
# Активируй тестовое окружение
source .env.test

# Запусти полную верификацию (тесты + smoke + lint)
make verify
```

`.env.test` содержит:
- Valid Telegram bot token (формат: `1234567890:ABC...`)
- Test Kie.ai credentials
- Localhost PostgreSQL (или JSON storage fallback)
- Webhook secrets для локального тестирования

**Результаты проверки:**
- ✅ Runtime validation (ENV vars, API connectivity)
- ✅ Lint checks (ruff)
- ✅ Unit tests (pytest, 211+ tests)
- ✅ E2E smoke tests (webhook, callback, generation)
- ✅ Health endpoint check (`/health`)

### Перед деплоем на Render:

```bash
# Проверить что все ENV переменные установлены и работают
make verify-runtime
```

Скрипт проверит:
1. ✅ Все обязательные ENV переменные заданы
2. ✅ Telegram Bot API доступен (валидирует токен)
3. ✅ KIE API доступен (валидирует ключ)
4. ✅ PostgreSQL база доступна (валидирует соединение)
5. ❌ Падает с понятным сообщением об ошибке если что-то не так

**Все чувствительные данные маскируются в логах** (выводит только `****abcd`).

**В CI:**
```bash
make verify  # Запускает verify-runtime + все тесты + smoke + integrity
```

---

## 🔐 ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ

### Обязательные:
- `TELEGRAM_BOT_TOKEN` - токен бота от @BotFather
- `KIE_API_KEY` - API ключ от Kie.ai
- `DATABASE_URL` - PostgreSQL connection string (для production)
- `ADMIN_ID` - Telegram ID админов (CSV: `111,222,333`)
- `BOT_MODE` - `webhook` (для Render) или `polling` (для локальной разработки)

### Опциональные:
- `APP_ENV` - `prod` (default), `dev`, или `test`
- `FAKE_KIE_MODE` - `1` для тестов (обязательно в CI)
- `RENDER_API_KEY` - для чтения логов Render
- `RENDER_SERVICE_ID` - для чтения логов Render
- `INSTANCE_NAME` - имя инстанса для мониторинга
- `LOG_LEVEL` - `DEBUG`/`INFO`/`WARNING` (default: `INFO`)
- `PAYMENT_BANK` - банк для оплаты
- `PAYMENT_CARD_HOLDER` - владелец карты
- `PAYMENT_PHONE` - телефон для оплаты
- `SUPPORT_TELEGRAM` - Telegram поддержки
- `SUPPORT_TEXT` - текст поддержки
- `PRICING_MARKUP` - множитель цены (default: 2.0)
- `WELCOME_BALANCE_RUB` - стартовый баланс новых пользователей (default: 0)

**Все секреты ТОЛЬКО через ENV, никаких .env файлов в репо!**

---

## ✅ Production Safety

### 🔐 Pricing Protection (P0)

- ✅ **72 модели** в SOURCE_OF_TRUTH
- ✅ **Pricing:** точные цены из Kie.ai
- ✅ **Формула:** `USER_PRICE_RUB = KIE_PRICE_USD × FX_RATE × 2.0`
- ✅ **FX auto-update** из ЦБР (78.43 RUB/USD актуальный)
- ⚠️ **Input schemas:** требуют обновления (см. QUICK_START_DEV.md)

### 🔒 Singleton Lock

- ✅ PostgreSQL advisory lock
- ✅ TTL = 60 секунд
- ✅ Heartbeat каждые 20 секунд
- ✅ Автоочистка stale locks
- ✅ Graceful shutdown (SIGTERM/SIGINT)

### 🌐 Multi-Tenant

- ✅ Один репозиторий → много Render services
- ✅ ENV-based конфигурация
- ✅ `ADMIN_ID` CSV поддержка: `111,222,333`
- ✅ `INSTANCE_NAME` для мониторинга

---

## 🧪 ТЕСТИРОВАНИЕ

```bash
# Установи тестовое окружение
export APP_ENV=test
export FAKE_KIE_MODE=1

# Запусти проверки
python scripts/verify_project.py
python scripts/behavioral_e2e.py
```

### Все тесты:
```bash
python -m pytest tests/ -v
```

**59 тестов проходят** ✅

---

## 📊 КОМАНДЫ

### Проверка проекта:
```bash
# Все гейты (lint, test, smoke, integrity, e2e)
make verify

# Только проверка проекта
python scripts/verify_project.py
```

### Comprehensive Smoke Test (DoD point 4):
```bash
# Запустить полный smoke test продукта
make smoke-product
# или
python scripts/smoke_product.py

# Проверяет:
# - Health endpoint (200 OK)
# - Webhook/callback configuration
# - Button audit (нет мертвых callbacks)
# - Flow type validation (70/72 models)
# - image_edit input order (image FIRST)
# - Payment idempotency
# - Partnership section presence
# - No mock success in production
```

### Sync KIE.ai Truth (DoD point 11):
```bash
# Попытаться синхронизировать модели с KIE.ai API
make sync-kie
# или
python scripts/sync_kie_truth.py

# Процесс:
# 1. Пытается получить JSON от KIE.ai (модели/цены)
# 2. Валидирует структуру данных
# 3. Обновляет models/KIE_SOURCE_OF_TRUTH.json
# 4. Пишет отчет об изменениях в TRT_REPORT.md
# 5. Если API недоступен: возвращает SYNC_UNAVAILABLE (не ошибка)
#
# Примечание: KIE.ai не предоставляет публичный JSON API для моделей.
# Обновления производятся вручную через SOURCE_OF_TRUTH.json
```

### Поведенческое тестирование:
```bash
python scripts/behavioral_e2e.py
```

### Полный цикл автопилота:
```bash
python scripts/autopilot_one_command.py
```

### Чтение логов Render:
```bash
python scripts/read_logs.py --since 60m --grep "ERROR|Traceback"
```

---

## 📁 СТРУКТУРА ПРОЕКТА

```
├── bot_kie.py              # Главный файл бота
├── main_render.py          # Точка входа для Render
├── kie_models.py           # Список моделей KIE.ai
├── app/                    # Модули приложения
│   ├── config.py          # Конфигурация из ENV
│   ├── singleton_lock.py  # Singleton lock (409 fix)
│   └── bot_mode.py        # Управление режимами
├── scripts/                # Скрипты автопилота
│   ├── verify_project.py  # Единственная команда правды
│   ├── behavioral_e2e.py  # Поведенческое тестирование
│   ├── preflight_checks.py # Критические проверки
│   └── autopilot_one_command.py # Полный цикл
├── tests/                  # Тесты
│   ├── fakes/             # Fake API для тестов
│   └── test_*.py          # Unit/E2E тесты
├── .github/workflows/      # GitHub Actions
│   ├── ci.yml             # CI pipeline
│   └── deploy_render.yml  # Deploy на Render
└── artifacts/              # Артефакты проверок
```

---

## 📦 Возможности

- ✅ **AI генерация:** изображения (Flux, DALL-E), видео (Kling, Luma), аудио
- ✅ **Платежи:** предоплата через Telegram Stars, автоматические возвраты
- ✅ **Pricing safety:** NO fallback prices, только проверенные цены
- ✅ **Singleton lock:** предотвращение дубликатов при blue-green deployment
- ✅ **Graceful shutdown:** корректная остановка при deployment
- ✅ **Multi-tenant:** несколько ботов из одного кода
- ✅ **Health check:** `/health` endpoint для мониторинга

---

## 📝 Лицензия

MIT

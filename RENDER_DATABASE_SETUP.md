# 🚀 НАСТРОЙКА RENDER SHARED DATABASE

## ✅ ФАЙЛ `.cursorrules` СОЗДАН

Файл `.cursorrules` содержит все правила для работы с Render shared PostgreSQL database.

---

## 📋 БЫСТРЫЙ СТАРТ

### 1. Подключение к Render Database

1. Открой Render Dashboard → Database → `telegrambot_j6cd`
2. Перейди в раздел "Connections"
3. Скопируй `Internal Database URL` (формат: `postgresql://user:password@host:port/database`)

### 2. Локальная разработка

Создай файл `.env` в корне проекта:
```env
DATABASE_URL=postgresql://telegrambot_j6cd_user:password@dpg-d50f1hvgi27c73ajfos0-a:5432/telegrambot_j6cd
```

**ВАЖНО:** Замени `password` на реальный пароль из Render Dashboard!

### 3. Деплой на Render

1. В Render Dashboard → Service → Environment
2. Нажми "Connect to Database"
3. Выбери `telegrambot_j6cd`
4. Render автоматически добавит `DATABASE_URL` в Environment Variables
5. Deploy - готово!

---

## 🔧 ТЕКУЩАЯ РЕАЛИЗАЦИЯ

### Текущий код использует:
- ✅ `psycopg2-binary` для синхронных операций
- ✅ `SimpleConnectionPool` для connection pooling
- ✅ `DATABASE_URL` из environment variables
- ✅ Parameterized queries (`%s`)

### Рекомендации для async операций:

Если нужно перейти на async операции (для Telegram бота это рекомендуется):

1. **Добавь `asyncpg` в requirements.txt** (уже добавлено)
2. **Создай async версию database.py:**

```python
import os
import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        DATABASE_URL = os.getenv('DATABASE_URL')
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL не установлен")
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10
        )
    return _pool

async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            user_id
        )
        return dict(row) if row else None
```

---

## 📊 ИНФОРМАЦИЯ О БД

**Render PostgreSQL:**
- **Hostname:** `dpg-d50f1hvgi27c73ajfos0-a`
- **Port:** `5432`
- **Database:** `telegrambot_j6cd`
- **Username:** `telegrambot_j6cd_user`
- **Connection URL:** Получи из Render Dashboard → Database → Connections

---

## ✅ ПРОВЕРКА

### Проверка подключения локально:

```python
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def test_connection():
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL не установлен")
        return
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        version = await conn.fetchval('SELECT version()')
        print(f"✅ Подключение успешно!")
        print(f"PostgreSQL version: {version[:50]}...")
        await conn.close()
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

# Запуск: asyncio.run(test_connection())
```

---

## 🔴 КРИТИЧЕСКИЕ ПРАВИЛА

1. ✅ **ВСЕГДА используй `DATABASE_URL` из environment**
2. ✅ **Используй connection pooling**
3. ✅ **Parameterized queries для безопасности**
4. ✅ **НЕ создавай локальные БД**
5. ✅ **НЕ хардкодь значения подключения**

---

**Статус:** ✅ `.cursorrules` создан, `asyncpg` добавлен в requirements.txt



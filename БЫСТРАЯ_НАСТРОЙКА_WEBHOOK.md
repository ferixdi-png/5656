# ⚡ БЫСТРАЯ НАСТРОЙКА WEBHOOK

## Информация
- **URL:** https://five656.onrender.com
- **Токен:** `8524869517:AAEqLyZ3guOUoNsAnmkkKTTX56MoKW2f30Y`

---

## ⚠️ ВАЖНО: ТЕКУЩИЙ РЕЖИМ

**Бот сейчас использует POLLING, а не webhook.**

Health check работает: https://five656.onrender.com → `{"status":"ok"}`

---

## 🔧 УСТАНОВКА WEBHOOK (ЕСЛИ НУЖНО)

### Команда для установки webhook:

```bash
curl -F "url=https://five656.onrender.com/webhook" \
  https://api.telegram.org/bot8524869517:AAEqLyZ3guOUoNsAnmkkKTTX56MoKW2f30Y/setWebhook
```

### Или через браузер:

```
https://api.telegram.org/bot8524869517:AAEqLyZ3guOUoNsAnmkkKTTX56MoKW2f30Y/setWebhook?url=https://five656.onrender.com/webhook
```

### Проверка webhook:

```bash
curl https://api.telegram.org/bot8524869517:AAEqLyZ3guOUoNsAnmkkKTTX56MoKW2f30Y/getWebhookInfo
```

### Удаление webhook (вернуться к polling):

```bash
curl https://api.telegram.org/bot8524869517:AAEqLyZ3guOUoNsAnmkkKTTX56MoKW2f30Y/deleteWebhook
```

---

## ⚠️ ПРОБЛЕМА: RENDER FREE TIER

**На Render Free tier webhook НЕ РЕКОМЕНДУЕТСЯ:**

- ❌ Инстанс засыпает после 15 минут неактивности
- ❌ Webhook перестаёт работать когда инстанс спит
- ❌ Первый запрос после пробуждения занимает 50+ секунд
- ❌ Telegram может отключить webhook из-за таймаутов

**Рекомендация:** Оставить POLLING (текущий режим работает отлично!)

---

## ✅ РЕКОМЕНДАЦИЯ

**ОСТАВИТЬ POLLING** - он работает стабильно на Render Free tier!

Если нужен webhook:
1. Upgrade до Paid tier на Render
2. Изменить код бота на `run_webhook()`
3. Настроить endpoint `/webhook`

---

**Готово! 🚀**


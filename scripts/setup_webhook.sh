#!/bin/bash
# Скрипт для настройки webhook для Telegram бота

BOT_TOKEN="8524869517:AAEqLyZ3guOUoNsAnmkkKTTX56MoKW2f30Y"
WEBHOOK_URL="https://five656.onrender.com/webhook"

echo "🔧 Настройка webhook для Telegram бота..."
echo ""

# Проверка текущего webhook
echo "📋 Проверка текущего webhook:"
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
echo ""

# Установка webhook
echo "🔧 Установка webhook..."
RESPONSE=$(curl -s -F "url=${WEBHOOK_URL}" "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook")

echo "$RESPONSE" | python3 -m json.tool

# Проверка результата
if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo ""
    echo "✅ Webhook успешно установлен!"
    echo "📍 URL: ${WEBHOOK_URL}"
else
    echo ""
    echo "❌ Ошибка при установке webhook!"
    exit 1
fi

echo ""
echo "📋 Финальная проверка:"
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool


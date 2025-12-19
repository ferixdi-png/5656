#!/bin/bash
# Скрипт для экстренной разблокировки токена Telegram бота
# Удаляет webhook и очищает очередь апдейтов

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "🔓 Разблокировка токена Telegram бота"
echo "=========================================="
echo ""

# Проверка наличия токена
if [ -z "$BOT_TOKEN" ]; then
    echo -e "${RED}❌ Ошибка: BOT_TOKEN не установлен${NC}"
    echo ""
    echo "Использование:"
    echo "  export BOT_TOKEN='your_bot_token_here'"
    echo "  ./unlock_bot_token.sh"
    echo ""
    echo "Или:"
    echo "  BOT_TOKEN='your_bot_token' ./unlock_bot_token.sh"
    exit 1
fi

# Маскируем токен для вывода (первые 4 и последние 4 символа)
TOKEN_MASKED="${BOT_TOKEN:0:4}...${BOT_TOKEN: -4}"
echo -e "${YELLOW}📋 Токен: ${TOKEN_MASKED}${NC}"
echo ""

# URL API Telegram
API_URL="https://api.telegram.org/bot${BOT_TOKEN}"

echo "🔍 Шаг 1: Проверка текущего состояния webhook..."
WEBHOOK_INFO=$(curl -s "${API_URL}/getWebhookInfo")
echo "$WEBHOOK_INFO" | python3 -m json.tool 2>/dev/null || echo "$WEBHOOK_INFO"
echo ""

# Проверяем, есть ли webhook
HAS_WEBHOOK=$(echo "$WEBHOOK_INFO" | grep -o '"url":"[^"]*"' | head -1)

if [ -n "$HAS_WEBHOOK" ]; then
    WEBHOOK_URL=$(echo "$HAS_WEBHOOK" | cut -d'"' -f4)
    echo -e "${YELLOW}⚠️  Обнаружен webhook: ${WEBHOOK_URL}${NC}"
    echo ""
else
    echo -e "${GREEN}✅ Webhook не установлен${NC}"
    echo ""
fi

echo "🗑️  Шаг 2: Удаление webhook и очистка очереди апдейтов..."
DELETE_RESULT=$(curl -s "${API_URL}/deleteWebhook?drop_pending_updates=true")
echo "$DELETE_RESULT" | python3 -m json.tool 2>/dev/null || echo "$DELETE_RESULT"
echo ""

# Проверяем результат
SUCCESS=$(echo "$DELETE_RESULT" | grep -o '"ok":true')

if [ -n "$SUCCESS" ]; then
    echo -e "${GREEN}✅ Webhook успешно удалён!${NC}"
    echo ""
    
    echo "🔍 Шаг 3: Проверка результата..."
    sleep 2
    FINAL_CHECK=$(curl -s "${API_URL}/getWebhookInfo")
    echo "$FINAL_CHECK" | python3 -m json.tool 2>/dev/null || echo "$FINAL_CHECK"
    echo ""
    
    # Проверяем, что webhook действительно удалён
    FINAL_HAS_WEBHOOK=$(echo "$FINAL_CHECK" | grep -o '"url":"[^"]*"' | head -1)
    if [ -z "$FINAL_HAS_WEBHOOK" ]; then
        echo -e "${GREEN}✅✅✅ Токен разблокирован! Webhook удалён, очередь очищена.${NC}"
        echo ""
        echo "Теперь можно:"
        echo "  1. Остановить все локальные экземпляры бота"
        echo "  2. Проверить Render Dashboard на дубликаты сервисов"
        echo "  3. Перезапустить Render worker"
    else
        echo -e "${RED}❌ Webhook всё ещё установлен. Возможно, другой экземпляр бота активен.${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Ошибка при удалении webhook${NC}"
    echo "$DELETE_RESULT"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Готово!"
echo "=========================================="


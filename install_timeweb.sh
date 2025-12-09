#!/bin/bash

echo "========================================"
echo "  УСТАНОВКА KIE BOT НА TIMEWEB"
echo "========================================"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "Запустите с sudo: sudo bash install_timeweb.sh"
    exit 1
fi

# Обновление системы
echo "[1/6] Обновление системы..."
apt-get update -y
apt-get upgrade -y

# Установка Python и зависимостей
echo ""
echo "[2/6] Установка Python 3 и pip..."
apt-get install python3 python3-pip -y

# Установка screen для фонового запуска
echo ""
echo "[3/6] Установка screen..."
apt-get install screen -y

# Переход в папку бота (предполагается что скрипт запущен из папки бота)
BOT_DIR=$(pwd)
echo ""
echo "[4/6] Папка бота: $BOT_DIR"

# Установка Python зависимостей
echo ""
echo "[5/6] Установка зависимостей Python..."
pip3 install -r requirements.txt

# Проверка .env файла
echo ""
echo "[6/6] Проверка .env файла..."
if [ ! -f .env ]; then
    echo "[!] Файл .env не найден!"
    echo "Создайте файл .env с необходимыми данными:"
    echo "  TELEGRAM_BOT_TOKEN=ваш_токен"
    echo "  KIE_API_KEY=ваш_ключ"
    echo "  KIE_API_URL=https://api.kie.ai"
    echo "  ADMIN_ID=ваш_id"
    echo ""
    echo "Используйте: nano .env"
    exit 1
fi

echo ""
echo "========================================"
echo "  УСТАНОВКА ЗАВЕРШЕНА!"
echo "========================================"
echo ""
echo "Для запуска бота используйте:"
echo ""
echo "1. Через screen (рекомендуется):"
echo "   screen -S kie_bot"
echo "   python3 run_bot.py"
echo "   (Отключитесь: Ctrl+A, затем D)"
echo ""
echo "2. Через nohup:"
echo "   nohup python3 run_bot.py > bot.log 2>&1 &"
echo ""
echo "3. Через systemd (как служба):"
echo "   См. инструкцию в ИНСТРУКЦИЯ_ПРОСТАЯ.txt"
echo ""



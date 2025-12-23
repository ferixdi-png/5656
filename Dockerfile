# Простой Dockerfile для Render (если требуется)
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем скрипт
COPY kie_api_scraper.py .

# Не запускаем парсинг автоматически при деплое
# Парсинг должен быть выполнен один раз локально
# Результаты сохраняются в kie_full_api.json
CMD ["python", "-c", "print('✅ Сервис готов. Используйте данные из kie_full_api.json')"]


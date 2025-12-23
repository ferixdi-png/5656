# Простой Dockerfile для Render (если требуется)
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем скрипт
COPY kie_api_scraper.py .

# Запускаем скрипт
CMD ["python", "kie_api_scraper.py"]


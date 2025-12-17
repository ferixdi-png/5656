# 🔴 ОБЯЗАТЕЛЬНОЕ ПРАВИЛО: FILE UPLOAD API

## ГЛАВНОЕ ПРАВИЛО ДЛЯ ЗАГРУЗКИ ФАЙЛОВ

**ВСЕ файлы (изображения, видео, аудио) ДОЛЖНЫ загружаться через KIE AI File Upload API!**

**НИКАКИХ внешних хостингов (0x0.st, catbox.moe, transfer.sh и т.д.)!**

---

## 📚 ИСТОЧНИК ДОКУМЕНТАЦИИ:

**https://docs.kie.ai/file-upload-api** - File Upload API Quickstart

---

## 🔧 API CONFIGURATION

### Base URL:
```
https://kieai.redpandaai.co
```

### Authentication:
```http
Authorization: Bearer YOUR_API_KEY
```

Получить API ключ: https://kie.ai/api-key

---

## 📤 ENDPOINTS

### 1. URL File Upload
**Для загрузки файлов с удаленных URL**

- **Endpoint:** `POST https://kieai.redpandaai.co/api/file-url-upload`
- **Content-Type:** `application/json`
- **Параметры:**
  - `fileUrl` (required, string) - URL файла для загрузки
  - `uploadPath` (optional, string) - путь для сохранения
  - `fileName` (optional, string) - имя файла (если не указано, генерируется случайное)

**Подходит для:**
- Миграция файлов
- Пакетная обработка
- Удаленные ресурсы

**Ограничения:**
- Требуется публично доступный URL
- Таймаут загрузки: 30 секунд
- Рекомендуется ≤100MB

### 2. File Stream Upload
**Для загрузки локальных файлов (РЕКОМЕНДУЕТСЯ для больших файлов)**

- **Endpoint:** `POST https://kieai.redpandaai.co/api/file-stream-upload`
- **Content-Type:** `multipart/form-data`
- **Параметры:**
  - `file` (required, file) - файл для загрузки
  - `uploadPath` (optional, string) - путь для сохранения
  - `fileName` (optional, string) - имя файла (если не указано, генерируется случайное)

**Подходит для:**
- Большие файлы
- Локальные файлы
- Высокая эффективность передачи

**Преимущества:**
- Высокая эффективность передачи
- Поддержка больших файлов
- Бинарная передача

### 3. Base64 Upload
**Для загрузки файлов в формате Base64**

- **Endpoint:** `POST https://kieai.redpandaai.co/api/file-base64-upload`
- **Content-Type:** `application/json`
- **Параметры:**
  - `base64Data` (required, string) - данные файла в формате Base64 (может быть Data URL: `data:image/png;base64,...`)
  - `uploadPath` (optional, string) - путь для сохранения
  - `fileName` (optional, string) - имя файла (если не указано, генерируется случайное)

**Подходит для:**
- Маленькие файлы (≤10MB)
- Интеграция через JSON
- Data URL формат

**Ограничения:**
- Размер данных увеличивается на 33%
- Не подходит для больших файлов
- Рекомендуется ≤10MB

---

## 📋 ВЫБОР МЕТОДА ЗАГРУЗКИ

| Размер файла | Рекомендуемый метод |
|-------------|---------------------|
| ≤1MB | Base64 Upload |
| 1MB-10MB | File Stream Upload |
| >10MB | File Stream Upload (обязательно) |
| Удаленные файлы | URL File Upload (≤100MB) |

---

## ✅ RESPONSE FORMAT

При успешной загрузке возвращается:

```json
{
  "success": true,
  "code": 200,
  "msg": "File uploaded successfully",
  "data": {
    "fileId": "file_abc123456",
    "fileName": "my-image.jpg",
    "originalName": "sample-image.jpg",
    "fileSize": 245760,
    "mimeType": "image/jpeg",
    "uploadPath": "images",
    "fileUrl": "https://kieai.redpandaai.co/files/images/my-image.jpg",
    "downloadUrl": "https://kieai.redpandaai.co/download/file_abc123456",
    "uploadTime": "2025-01-15T10:30:00Z",
    "expiresAt": "2025-01-18T10:30:00Z"
  }
}
```

**Важно:** Использовать `fileUrl` из ответа для передачи в модели KIE AI!

---

## ⚠️ КРИТИЧЕСКИЕ ПРАВИЛА

1. ✅ **ОБЯЗАТЕЛЬНО использовать KIE AI File Upload API** для всех загрузок файлов
2. ❌ **НЕ использовать внешние хостинги** (0x0.st, catbox.moe, transfer.sh и т.д.)
3. ⚠️ **Файлы автоматически удаляются через 3 дня** - важно скачать или мигрировать важные файлы
4. ✅ Использовать `fileUrl` из ответа API для передачи в модели KIE AI
5. ✅ Параметр `fileName` опционален - если не указан, генерируется случайное имя
6. ✅ При повторной загрузке с тем же `fileName` старый файл перезаписывается (с учетом кэширования)

---

## 📝 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Python - File Stream Upload

```python
import requests

url = "https://kieai.redpandaai.co/api/file-stream-upload"
headers = {
    "Authorization": "Bearer YOUR_API_KEY"
}

files = {
    'file': ('your-file.jpg', open('/path/to/your-file.jpg', 'rb')),
    'uploadPath': (None, 'images/user-uploads'),
    'fileName': (None, 'custom-name.jpg')
}

response = requests.post(url, headers=headers, files=files)
result = response.json()

if result.get('success'):
    file_url = result['data']['fileUrl']
    print(f"File uploaded: {file_url}")
    # Использовать file_url в параметрах модели KIE AI
```

### Python - Base64 Upload

```python
import requests
import base64

# Read file and convert to base64
with open('/path/to/your-file.jpg', 'rb') as f:
    file_data = base64.b64encode(f.read()).decode('utf-8')
    base64_data = f'data:image/jpeg;base64,{file_data}'

url = "https://kieai.redpandaai.co/api/file-base64-upload"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

payload = {
    "base64Data": base64_data,
    "uploadPath": "images",
    "fileName": "base64-image.jpg"
}

response = requests.post(url, json=payload, headers=headers)
result = response.json()

if result.get('success'):
    file_url = result['data']['fileUrl']
    print(f"File uploaded: {file_url}")
```

### Python - URL File Upload

```python
import requests

url = "https://kieai.redpandaai.co/api/file-url-upload"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

payload = {
    "fileUrl": "https://example.com/sample-image.jpg",
    "uploadPath": "images",
    "fileName": "my-image.jpg"
}

response = requests.post(url, json=payload, headers=headers)
result = response.json()

if result.get('success'):
    file_url = result['data']['fileUrl']
    print(f"File uploaded: {file_url}")
```

---

## 🔍 STATUS CODES

- **200** - Успешная загрузка
- **400** - Неверные параметры запроса или отсутствуют обязательные параметры
- **401** - Отсутствуют или неверны учетные данные аутентификации
- **405** - Метод запроса не поддерживается
- **500** - Произошла неожиданная ошибка при обработке запроса

---

## 📖 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ

- **Документация:** https://docs.kie.ai/file-upload-api
- **API Key Management:** https://kie.ai/api-key
- **Support:** support@kie.ai

---

**Дата фиксации правила:** 2025-12-16  
**Статус:** ✅ ОБЯЗАТЕЛЬНО ДЛЯ ВСЕХ ЗАГРУЗОК ФАЙЛОВ  
**Источник:** https://docs.kie.ai/file-upload-api

# KIE AI Models Catalog - Source of Truth

## 📋 Описание

`models_pricing.yaml` — единый источник правды (Source of Truth) для всех моделей KIE AI, их режимов генерации и цен.

## 📊 Источник данных

Данные взяты из официальной таблицы цен KIE AI (Models Pricing):
- URL: https://kie.ai (раздел Models Pricing)
- Дата обновления: 2025-12-21
- Все модели и режимы из таблицы "Our Price"

## 💰 Формула ценообразования

```
Цена в рублях = official_usd × USD_TO_RUB × PRICE_MULTIPLIER
```

Где:
- `official_usd` — "Our Price" из таблицы KIE AI (в USD)
- `USD_TO_RUB` — курс доллара к рублю (по умолчанию 100.0, настраивается через `USD_TO_RUB` env)
- `PRICE_MULTIPLIER` — множитель цены (по умолчанию 2.0, настраивается через `PRICE_MULTIPLIER` env)

**Важно:** Множитель ×2 применяется **всегда** для отображения пользователю и для списания.

## 📁 Структура файла

```yaml
version: '1.0'
source: KIE AI Models Pricing Table
last_updated: '2025-12-21'
models:
  - id: model_id              # ID модели для KIE API
    title_ru: Название модели  # Как показывать пользователю
    type: t2i                  # Тип: t2i, i2i, t2v, i2v, v2v, tts, stt, sfx, audio_isolation, upscale, bg_remove, watermark_remove, music, lip_sync
    modes:
      - unit: image            # Единица: image, video, second, minute, 1000_chars, request, megapixel, removal, upscale
        credits: 14.0          # Кредиты за генерацию
        official_usd: 0.07      # Our Price в USD
        notes: "1.0s-1K"        # Опционально: дополнительные параметры режима
```

## 🔄 Обновление каталога

Для обновления каталога:

1. Обновите данные в `data/kie_models_complete_pricing.json`
2. Запустите генератор:
   ```bash
   python scripts/generate_kie_catalog_yaml.py
   ```

## 📝 Использование в коде

```python
from app.kie_catalog import load_catalog, get_model
from app.services.pricing_service import price_for_model_rub
from app.config import get_settings

# Загрузить каталог
catalog = load_catalog()

# Получить модель
model = get_model("flux-2/pro-text-to-image")

# Рассчитать цену
settings = get_settings()
price_rub = price_for_model_rub("flux-2/pro-text-to-image", 0, settings)
```

## ⚠️ Важно

- Этот файл — **единственный источник правды** для моделей и цен
- Все цены должны рассчитываться через `pricing_service.py`
- Не используйте хардкод цен в коде
- Все изменения цен должны вноситься в этот файл

## 📊 Статистика

- **Всего моделей:** 70
- **Всего режимов:** 214
- **Типы моделей:** t2i, i2i, t2v, i2v, v2v, tts, stt, sfx, audio_isolation, upscale, bg_remove, watermark_remove, music, lip_sync


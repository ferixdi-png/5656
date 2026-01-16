"""
Построение меню моделей из KIE Registry (единый источник правды).

Использует ТОЛЬКО модели из registry, построенного из документации.
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.kie.spec_registry import get_registry, ModelSpecFromRegistry
from app.services.pricing_service import price_for_model_rub, get_settings

logger = logging.getLogger(__name__)


def build_models_menu_from_registry(user_lang: str = 'ru') -> InlineKeyboardMarkup:
    """
    Строит меню моделей из registry.
    
    Returns:
        InlineKeyboardMarkup с кнопками моделей
    """
    registry = get_registry()
    settings = get_settings()
    
    models = registry.get_all_models()
    
    if not models:
        # Пустое меню если нет моделей
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("Нет доступных моделей", callback_data="no_models")
        ]])
    
    keyboard = []
    
    # Простой плоский список с пагинацией (если моделей много)
    # Группируем по провайдеру для удобства
    models_by_provider: Dict[str, List[ModelSpecFromRegistry]] = defaultdict(list)
    
    for model_id, model_spec in models.items():
        provider = model_id.split('/')[0] if '/' in model_id else 'other'
        models_by_provider[provider].append(model_spec)
    
    # Сортируем провайдеров
    provider_order = [
        'google', 'kling', 'wan', 'bytedance', 'ideogram', 'flux-2',
        'qwen', 'elevenlabs', 'hailuo', 'recraft', 'grok-imagine',
        'sora', 'seedream', 'infinitalk', 'topaz', 'z-image', 'nano-banana'
    ]
    
    for provider in provider_order:
        if provider not in models_by_provider:
            continue
        
        provider_models = models_by_provider[provider]
        if not provider_models:
            continue
        
        # Заголовок провайдера
        keyboard.append([InlineKeyboardButton(
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            callback_data="provider_header:ignore"
        )])
        
        keyboard.append([InlineKeyboardButton(
            f"📦 {provider.upper()} ({len(provider_models)})",
            callback_data="provider_header:ignore"
        )])
        
        # Кнопки моделей с metadata (title, subtitle, badge)
        for model_spec in sorted(provider_models, key=lambda m: m.model_id):
            price_rub = price_for_model_rub(model_spec.model_id, settings)
            
            # Get menu metadata with defaults
            menu_title = model_spec.menu_title or model_spec.title_ru or model_spec.model_id
            menu_badge = model_spec.menu_badge
            
            # Build button text with badge if present
            parts = [menu_title]
            if menu_badge:
                parts.append(menu_badge)
            
            # Price tag
            if price_rub == 0:
                price_tag = "🆓"
            elif price_rub < 1.0:
                price_tag = f"{price_rub:.2f}₽"
            elif price_rub < 10.0:
                price_tag = f"{price_rub:.1f}₽"
            else:
                price_tag = f"{price_rub:.0f}₽"
            
            parts.append(price_tag)
            button_text = " • ".join(parts)
            
            # Truncate if too long (max 60 chars for Telegram button)
            if len(button_text) > 60:
                # Try to keep title and price, truncate badge if needed
                if menu_badge and len(menu_badge) > 10:
                    short_badge = menu_badge[:8] + ".."
                    button_text = f"{menu_title} • {short_badge} • {price_tag}"
                if len(button_text) > 60:
                    # Truncate title
                    title_max = 60 - len(f" • {menu_badge if menu_badge else ''} • {price_tag}")
                    if title_max > 10:
                        menu_title = menu_title[:title_max-3] + "..."
                        button_text = f"{menu_title} • {menu_badge if menu_badge else ''} • {price_tag}".replace(" •  • ", " • ")
                    else:
                        # Fallback: just title and price
                        button_text = f"{menu_title[:50]}... • {price_tag}"
            
            # Используем короткий callback если model_id длинный
            if len(model_spec.model_id) > 50:
                # Хешируем для короткого callback
                import hashlib
                hash_id = hashlib.md5(model_spec.model_id.encode()).hexdigest()[:8]
                callback_data = f"modelk:{hash_id}"
                # Сохраняем маппинг (в реальности нужен глобальный кеш)
            else:
                callback_data = f"model:{model_spec.model_id}"
            
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=callback_data
            )])
    
    # Остальные провайдеры
    for provider, provider_models in models_by_provider.items():
        if provider in provider_order:
            continue
        
        keyboard.append([InlineKeyboardButton(
            f"📦 {provider.upper()} ({len(provider_models)})",
            callback_data="provider_header:ignore"
        )])
        
        for model_spec in sorted(provider_models, key=lambda m: m.model_id):
            price_rub = price_for_model_rub(model_spec.model_id, settings)
            
            # Get menu metadata with defaults
            menu_title = model_spec.menu_title or model_spec.title_ru or model_spec.model_id
            menu_badge = model_spec.menu_badge
            
            # Build button text with badge if present
            parts = [menu_title]
            if menu_badge:
                parts.append(menu_badge)
            
            # Price tag
            if price_rub == 0:
                price_tag = "🆓"
            elif price_rub < 1.0:
                price_tag = f"{price_rub:.2f}₽"
            elif price_rub < 10.0:
                price_tag = f"{price_rub:.1f}₽"
            else:
                price_tag = f"{price_rub:.0f}₽"
            
            parts.append(price_tag)
            button_text = " • ".join(parts)
            
            # Truncate if too long
            if len(button_text) > 60:
                if menu_badge and len(menu_badge) > 10:
                    short_badge = menu_badge[:8] + ".."
                    button_text = f"{menu_title} • {short_badge} • {price_tag}"
                if len(button_text) > 60:
                    title_max = 60 - len(f" • {menu_badge if menu_badge else ''} • {price_tag}")
                    if title_max > 10:
                        menu_title = menu_title[:title_max-3] + "..."
                        button_text = f"{menu_title} • {menu_badge if menu_badge else ''} • {price_tag}".replace(" •  • ", " • ")
                    else:
                        button_text = f"{menu_title[:50]}... • {price_tag}"
            callback_data = f"model:{model_spec.model_id}"
            
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=callback_data
            )])
    
    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(
        "🔙 Назад",
        callback_data="back_to_main"
    )])
    
    return InlineKeyboardMarkup(keyboard)


def build_model_card_from_registry(model_id: str, user_lang: str = 'ru') -> tuple[str, InlineKeyboardMarkup]:
    """
    Строит карточку модели из registry.
    
    Args:
        model_id: ID модели
        user_lang: Язык пользователя
    
    Returns:
        (text, keyboard) или (None, None) если модель не найдена
    """
    registry = get_registry()
    settings = get_settings()
    
    model_spec = registry.get_model(model_id)
    if not model_spec:
        return None, None
    
    price_rub = price_for_model_rub(model_id, settings)
    title = model_spec.title_ru or model_id
    
    # Формируем текст карточки
    text = f"╔═══ {title} ═══╗\n\n"
    
    if model_spec.description:
        text += f"{model_spec.description[:200]}...\n\n"
    
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"💰 Цена: <b>₽{price_rub}</b>\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Параметры
    required_fields = [f for f in model_spec.input_schema.values() if f.required]
    optional_fields = [f for f in model_spec.input_schema.values() if not f.required]
    
    if required_fields:
        text += "📋 <b>Обязательные параметры:</b>\n"
        for field in required_fields:
            text += f"  • {field.name} ({field.type})"
            if field.max_length:
                text += f" [max {field.max_length}]"
            text += "\n"
        text += "\n"
    
    if optional_fields:
        text += "📋 <b>Опциональные параметры:</b>\n"
        for field in optional_fields[:5]:  # Показываем первые 5
            text += f"  • {field.name} ({field.type})"
            if field.default is not None:
                text += f" [default: {field.default}]"
            text += "\n"
        if len(optional_fields) > 5:
            text += f"  ... и еще {len(optional_fields) - 5}\n"
        text += "\n"
    
    # Кнопки
    keyboard = [
        [InlineKeyboardButton("🚀 Сгенерировать", callback_data=f"generate:{model_id}")],
        [InlineKeyboardButton("📖 Пример", callback_data=f"example:{model_id}")],
        [InlineKeyboardButton("🔙 Назад к моделям", callback_data="show_all_models_list")]
    ]
    
    return text, InlineKeyboardMarkup(keyboard)


def resolve_model_id_from_callback(callback_data: str) -> Optional[str]:
    """
    Разрешает model_id из callback_data.
    
    Args:
        callback_data: callback_data из кнопки
    
    Returns:
        model_id или None
    """
    if callback_data.startswith("model:"):
        return callback_data[6:]  # Убираем "model:"
    
    if callback_data.startswith("modelk:"):
        # Для хешированных ID нужен маппинг (упрощенная версия)
        # В реальности нужен глобальный кеш hash -> model_id
        logger.warning(f"Hash-based model ID not fully implemented: {callback_data}")
        return None
    
    return None












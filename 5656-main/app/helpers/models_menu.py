"""
Построение меню моделей из каталога KIE AI.
Группировка по типам и брендам, отображение цен в рублях.
"""

import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.kie_catalog import load_catalog, get_model, ModelSpec
from app.services.pricing_service import price_for_model_rub
from app.config import get_settings

logger = logging.getLogger(__name__)

# Кеш маппинга коротких callback_data
_callback_mapping: Dict[str, str] = {}
_reverse_mapping: Dict[str, str] = {}


def _get_model_brand(model_id: str, title: str) -> str:
    """Определяет бренд модели по ID или названию."""
    model_lower = model_id.lower()
    title_lower = title.lower()
    
    # Проверяем по префиксам ID
    if model_id.startswith("flux"):
        return "Flux"
    elif model_id.startswith("kling"):
        return "Kling"
    elif model_id.startswith("wan"):
        return "Wan"
    elif model_id.startswith("google"):
        return "Google"
    elif model_id.startswith("ideogram"):
        return "Ideogram"
    elif model_id.startswith("bytedance") or "seedance" in model_lower or "seedream" in model_lower:
        return "ByteDance"
    elif model_id.startswith("sora") or "openai" in model_lower:
        return "OpenAI"
    elif model_id.startswith("qwen") or model_id.startswith("z-image"):
        return "Qwen"
    elif model_id.startswith("elevenlabs"):
        return "ElevenLabs"
    elif model_id.startswith("hailuo"):
        return "Hailuo"
    elif model_id.startswith("topaz"):
        return "Topaz"
    elif model_id.startswith("recraft"):
        return "Recraft"
    elif model_id.startswith("suno"):
        return "Suno"
    elif model_id.startswith("midjourney"):
        return "Midjourney"
    elif model_id.startswith("runway"):
        return "Runway"
    elif model_id.startswith("grok"):
        return "Grok"
    elif "infinitalk" in model_lower or "meigen" in model_lower:
        return "MeiGen-AI"
    
    # Проверяем по названию
    if "flux" in title_lower:
        return "Flux"
    elif "kling" in title_lower:
        return "Kling"
    elif "google" in title_lower:
        return "Google"
    elif "openai" in title_lower or "sora" in title_lower:
        return "OpenAI"
    
    return "Other"


def _get_type_emoji(model_type: str) -> str:
    """Возвращает эмодзи для типа модели."""
    emoji_map = {
        't2i': '🖼️',
        'i2i': '🎨',
        't2v': '🎬',
        'i2v': '📹',
        'v2v': '🎞️',
        'tts': '🔊',
        'stt': '🎤',
        'sfx': '🎵',
        'audio_isolation': '🎧',
        'upscale': '⬆️',
        'bg_remove': '✂️',
        'watermark_remove': '💧',
        'music': '🎼',
        'lip_sync': '👄'
    }
    return emoji_map.get(model_type, '🤖')


def _get_type_name_ru(model_type: str) -> str:
    """Возвращает название типа на русском."""
    name_map = {
        't2i': 'Текст → Изображение',
        'i2i': 'Изображение → Изображение',
        't2v': 'Текст → Видео',
        'i2v': 'Изображение → Видео',
        'v2v': 'Видео → Видео',
        'tts': 'Текст → Речь',
        'stt': 'Речь → Текст',
        'sfx': 'Звуковые эффекты',
        'audio_isolation': 'Изоляция аудио',
        'upscale': 'Увеличение качества',
        'bg_remove': 'Удаление фона',
        'watermark_remove': 'Удаление водяного знака',
        'music': 'Музыка',
        'lip_sync': 'Синхронизация губ'
    }
    return name_map.get(model_type, model_type)


def _create_callback_data(model_id: str) -> str:
    """
    Создаёт callback_data для модели.
    Если model_id слишком длинный, использует короткий формат с маппингом.
    """
    callback_data = f"model:{model_id}"
    callback_bytes = callback_data.encode('utf-8')
    
    # Telegram ограничение: 64 байта
    if len(callback_bytes) <= 64:
        return callback_data
    
    # Используем короткий формат с хешем
    model_hash = hashlib.md5(model_id.encode()).hexdigest()[:12]
    short_callback = f"modelk:{model_hash}"
    
    # Сохраняем маппинг
    _callback_mapping[short_callback] = model_id
    _reverse_mapping[model_id] = short_callback
    
    return short_callback


def _resolve_model_id(callback_data: str) -> Optional[str]:
    """Разрешает callback_data в model_id (поддерживает короткий формат)."""
    if callback_data.startswith("model:"):
        return callback_data[6:]  # Убираем "model:"
    elif callback_data.startswith("modelk:"):
        hash_part = callback_data[7:]  # Убираем "modelk:"
        # Ищем в маппинге
        for short, model_id in _callback_mapping.items():
            if short.endswith(hash_part):
                return model_id
        # Если не нашли, пробуем найти по хешу
        for model_id in _reverse_mapping.keys():
            model_hash = hashlib.md5(model_id.encode()).hexdigest()[:12]
            if model_hash == hash_part:
                return model_id
    return None


def build_models_menu_by_type(user_lang: str = 'ru') -> InlineKeyboardMarkup:
    """
    Строит меню моделей, сгруппированных по типам.
    
    Returns:
        InlineKeyboardMarkup с кнопками моделей, сгруппированных по типам
    """
    catalog = load_catalog()
    settings = get_settings()
    
    # Группируем по типам
    models_by_type: Dict[str, List[ModelSpec]] = defaultdict(list)
    for model in catalog:
        models_by_type[model.type].append(model)
    
    keyboard = []
    
    # Сортируем типы для отображения
    type_order = ['t2i', 'i2i', 't2v', 'i2v', 'v2v', 'tts', 'stt', 'sfx', 'audio_isolation', 
                  'upscale', 'bg_remove', 'watermark_remove', 'music', 'lip_sync']
    
    for model_type in type_order:
        if model_type not in models_by_type:
            continue
        
        models = models_by_type[model_type]
        if not models:
            continue
        
        # Заголовок типа (неактивная кнопка для визуального разделения)
        emoji = _get_type_emoji(model_type)
        type_name = _get_type_name_ru(model_type) if user_lang == 'ru' else model_type
        # Используем callback_data который не обрабатывается (для визуального разделения)
        keyboard.append([
            InlineKeyboardButton(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                callback_data="type_header:ignore"  # Неактивная кнопка
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} <b>{type_name}</b> ({len(models)})",
                callback_data="type_header:ignore"  # Неактивная кнопка
            )
        ])
        
        # Группируем модели по брендам
        models_by_brand: Dict[str, List[ModelSpec]] = defaultdict(list)
        for model in models:
            brand = _get_model_brand(model.id, model.title_ru)
            models_by_brand[brand].append(model)
        
        # Сортируем бренды
        brand_order = ['Flux', 'Kling', 'Wan', 'Google', 'OpenAI', 'Ideogram', 'ByteDance', 
                      'Qwen', 'ElevenLabs', 'Hailuo', 'Topaz', 'Recraft', 'Suno', 
                      'Midjourney', 'Runway', 'Grok', 'MeiGen-AI', 'Other']
        
        for brand in brand_order:
            if brand not in models_by_brand:
                continue
            
            brand_models = models_by_brand[brand]
            if not brand_models:
                continue
            
            # Кнопки моделей (по 1 в ряд, так как могут быть длинными)
            for model in sorted(brand_models, key=lambda m: m.title_ru):
                # Получаем цену для первого режима
                price_rub = price_for_model_rub(model.id, 0, settings)
                if price_rub is None:
                    price_rub = 0
                
                # Получаем эмодзи для типа модели
                type_emoji = _get_type_emoji(model.type)
                
                # Формируем текст кнопки с эмодзи и ценой
                button_text = f"{type_emoji} {model.title_ru} • ₽{price_rub}"
                
                # Ограничение Telegram: ~64 символа для текста кнопки
                if len(button_text.encode('utf-8')) > 60:
                    max_len = 60 - len(f" • ₽{price_rub}".encode('utf-8')) - 2  # -2 для эмодзи и пробела
                    button_text = f"{type_emoji} {model.title_ru[:max_len]}... • ₽{price_rub}"
                
                callback_data = _create_callback_data(model.id)
                
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=callback_data
                    )
                ])
    
    # Кнопка "Назад"
    keyboard.append([])  # Пустая строка для разделения
    if user_lang == 'ru':
        keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    else:
        keyboard.append([InlineKeyboardButton("🔙 Back to menu", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def build_model_card_text(model: ModelSpec, mode_index: int = 0, user_lang: str = 'ru') -> Tuple[str, InlineKeyboardMarkup]:
    """
    Строит текст карточки модели и клавиатуру.
    
    Args:
        model: ModelSpec модели
        mode_index: Индекс режима (по умолчанию 0)
        user_lang: Язык пользователя
    
    Returns:
        Tuple (текст карточки, клавиатура)
    """
    settings = get_settings()
    
    if mode_index < 0 or mode_index >= len(model.modes):
        mode_index = 0
    
    mode = model.modes[mode_index]
    price_rub = price_for_model_rub(model.id, mode_index, settings)
    if price_rub is None:
        price_rub = 0
    
    # Формируем текст карточки
    type_emoji = _get_type_emoji(model.type)
    
    if user_lang == 'ru':
        type_name = _get_type_name_ru(model.type)
        
        card_text = (
            f"╔═══════════════════════════════════════════╗\n"
            f"║  {type_emoji} <b>{model.title_ru}</b> {type_emoji}          ║\n"
            f"╚═══════════════════════════════════════════╝\n\n"
            f"╔═══════════════════════════════════════════╗\n"
            f"║  📋 ТИП ГЕНЕРАЦИИ: {type_name} 📋        ║\n"
            f"╚═══════════════════════════════════════════╝\n"
        )
        
        if mode.notes:
            card_text += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚙️ <b>Режим:</b> <code>{mode.notes}</code>\n"
            )
        
        card_text += (
            f"\n╔═══════════════════════════════════════════╗\n"
            f"║  💰 ЦЕНА: <b>₽{price_rub}</b> 💰              ║\n"
            f"╚═══════════════════════════════════════════╝\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Официально: <code>${mode.official_usd:.4f}</code>\n"
            f"🎫 Кредиты: <code>{mode.credits}</code>\n"
            f"📦 Единица: <code>{mode.unit}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        
        if len(model.modes) > 1:
            card_text += (
                f"\n╔═══════════════════════════════════════════╗\n"
                f"║  📌 ДОСТУПНО РЕЖИМОВ: {len(model.modes)} 📌    ║\n"
                f"╚═══════════════════════════════════════════╝\n"
            )
    else:
        card_text = (
            f"╔═══════════════════════════════════╗\n"
            f"║  {type_emoji} <b>{model.title_ru}</b>  ║\n"
            f"╚═══════════════════════════════════╝\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Generation Type:</b> {model.type}\n"
        )
        
        if mode.notes:
            card_text += f"⚙️ <b>Mode:</b> <code>{mode.notes}</code>\n"
        
        card_text += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>PRICE:</b> <b>₽{price_rub}</b>\n"
            f"💵 Official: ${mode.official_usd:.4f}\n"
            f"🎫 Credits: {mode.credits}\n"
            f"📦 Unit: {mode.unit}\n"
        )
        
        if len(model.modes) > 1:
            card_text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            card_text += f"📌 <b>Available modes:</b> {len(model.modes)}\n"
    
    # Формируем клавиатуру
    keyboard = []
    
    if user_lang == 'ru':
        keyboard.append([
            InlineKeyboardButton("🚀 Сгенерировать", callback_data=f"select_model:{model.id}")
        ])
        keyboard.append([
            InlineKeyboardButton("📸 Пример", callback_data=f"example:{model.id}"),
            InlineKeyboardButton("ℹ️ Инфо", callback_data=f"info:{model.id}")
        ])
        keyboard.append([
            InlineKeyboardButton("🔙 Назад к моделям", callback_data="show_models")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("🚀 Generate", callback_data=f"select_model:{model.id}")
        ])
        keyboard.append([
            InlineKeyboardButton("📸 Example", callback_data=f"example:{model.id}"),
            InlineKeyboardButton("ℹ️ Info", callback_data=f"info:{model.id}")
        ])
        keyboard.append([
            InlineKeyboardButton("🔙 Back to models", callback_data="show_models")
        ])
    
    return card_text, InlineKeyboardMarkup(keyboard)


def resolve_model_id_from_callback(callback_data: str) -> Optional[str]:
    """
    Разрешает callback_data в model_id.
    Используется в обработчиках для получения model_id из callback.
    """
    return _resolve_model_id(callback_data)


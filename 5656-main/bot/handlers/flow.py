"""
Primary UX flow: categories -> models -> inputs -> confirmation -> generation.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.kie.builder import load_source_of_truth
from app.kie.validator import validate_input_type, ModelContractError
from app.payments.charges import get_charge_manager
from app.payments.integration import generate_with_payment
from app.payments.pricing import calculate_kie_cost, calculate_user_price, format_price_rub
from app.utils.validation import validate_url, validate_file_url, validate_text_input

# BATCH 48.52: Import balance handler states for topup flow
from bot.handlers.balance import TopupStates

logger = logging.getLogger(__name__)
router = Router(name="flow")


class FlowStates(StatesGroup):
    """States for flow handlers."""
    search_query = State()  # Waiting for model search query


# Category metadata with title, subtitle, badge
CATEGORY_METADATA = {
    "image": {
        "title": "🎨 Картинки",
        "subtitle": "Создание и редактирование изображений",
        "badge": None,
    },
    "video": {
        "title": "🎬 Видео",
        "subtitle": "Генерация видео для соцсетей",
        "badge": "Видео",
    },
    "audio": {
        "title": "🎵 Аудио",
        "subtitle": "Озвучка и обработка звука",
        "badge": None,
    },
    "music": {
        "title": "🎵 Музыка",
        "subtitle": "Генерация музыкальных композиций",
        "badge": None,
    },
    "enhance": {
        "title": "✨ Улучшение",
        "subtitle": "Повышение качества контента",
        "badge": "Upscale",
    },
    "avatar": {
        "title": "🧑‍🎤 Аватары",
        "subtitle": "Создание персонажей и аватаров",
        "badge": None,
    },
    "other": {
        "title": "⭐ Другое",
        "subtitle": "Прочие модели",
        "badge": None,
    },
}

# Legacy category labels (backward compatibility)
CATEGORY_LABELS = {
    # Real categories from SOURCE_OF_TRUTH (v1.2.6)
    "image": "🎨 Картинки и дизайн",
    "video": "🎬 Видео",
    "audio": "🎵 Аудио",
    "music": "🎵 Музыка",
    "enhance": "✨ Улучшение качества",
    "avatar": "🧑‍🎤 Аватары",
    "other": "⭐ Другое",
    
    # Legacy format (backward compatibility)
    "text-to-image": "🎨 Создать картинку",
    "image-to-image": "✏️ Редактировать изображение",
    "text-to-video": "🎬 Создать видео",
    "image-to-video": "🎬 Оживить картинку",
    "video-to-video": "🎬 Редактировать видео",
    "text-to-speech": "🎵 Озвучка текста",
    "speech-to-text": "📝 Распознать речь",
    "audio-generation": "🎵 Создать музыку",
    "upscale": "✨ Улучшить качество",
    "ocr": "📝 Распознать текст",
    "lip-sync": "🎬 Lip Sync",
    "background-removal": "✂️ Убрать фон",
    "watermark-removal": "✂️ Убрать водяной знак",
    "music-generation": "🎵 Создать музыку",
    "sound-effects": "🔊 Звуковые эффекты",
    "general": "⭐ Разное",
    
    # Alternative names
    "creative": "🎨 Креатив",
    "voice": "🎙️ Голос и озвучка",
    "t2i": "🎨 Создать картинку",
    "i2i": "✏️ Редактировать изображение",
    "t2v": "🎬 Создать видео",
    "i2v": "🎬 Оживить картинку",
    "v2v": "🎬 Редактировать видео",
    "lip_sync": "🎬 Lip Sync",
    "music_old": "🎵 Музыка",
    "sfx": "🔊 Звуковые эффекты",
    "tts": "🎵 Озвучка",
    "stt": "📝 Распознать речь",
    "audio_isolation": "🎵 Очистить аудио",
    "bg_remove": "✂️ Убрать фон",
    "watermark_remove": "✂️ Убрать водяной знак",
}

# Removed WELCOME_BALANCE_RUB - no longer used in premium copy


def _source_of_truth() -> Dict[str, Any]:
    return load_source_of_truth()


# BATCH 42: Performance optimization - cache models list with TTL
_models_cache = {"data": None, "timestamp": 0}
_models_count_cache = {"count": None, "timestamp": 0}
_CACHE_TTL = 60  # 60 seconds cache

def _get_models_list() -> List[Dict[str, Any]]:
    """
    Получить список моделей из SOURCE_OF_TRUTH.
    Поддерживает оба формата: dict и list.
    
    BATCH 42: Cached with 60s TTL to reduce file system load.
    """
    import time
    global _models_cache
    
    # Check cache validity
    now = time.time()
    if _models_cache["data"] is not None and (now - _models_cache["timestamp"]) < _CACHE_TTL:
        return _models_cache["data"]
    
    # Cache miss - load from file
    sot = _source_of_truth()
    models = sot.get("models", {})
    
    # Если dict - конвертируем в list
    if isinstance(models, dict):
        result = list(models.values())
    # Если уже list - возвращаем как есть
    elif isinstance(models, list):
        result = models
    else:
        result = []
    
    # Update cache
    _models_cache = {"data": result, "timestamp": now}
    # Also cache count for performance
    valid_models = [m for m in result if _is_valid_model(m) and m.get("enabled", True)]
    _models_count_cache = {"count": len(valid_models), "timestamp": now}
    return result


def _get_total_models_count() -> int:
    """
    Get total count of valid enabled models (cached for performance).
    Avoids recalculating on every menu display.
    """
    import time
    global _models_count_cache, _models_cache
    
    now = time.time()
    # Check if count cache is valid
    if _models_count_cache["count"] is not None and (now - _models_count_cache["timestamp"]) < _CACHE_TTL:
        return _models_count_cache["count"]
    
    # Count cache miss - recalculate from models cache
    if _models_cache["data"] is not None and (now - _models_cache["timestamp"]) < _CACHE_TTL:
        models_list = _models_cache["data"]
    else:
        models_list = _get_models_list()
    
    total_models = len([m for m in models_list if _is_valid_model(m) and m.get("enabled", True)])
    _models_count_cache = {"count": total_models, "timestamp": now}
    return total_models


def _is_valid_model(model: Dict[str, Any]) -> bool:
    """Filter out technical/invalid models from registry."""
    model_id = model.get("model_id", "")
    if not model_id:
        return False
    
    # Check enabled flag
    if not model.get("enabled", True):
        return False
    
    # Check pricing exists
    pricing = model.get("pricing")
    if not pricing or not isinstance(pricing, dict):
        return False
    
    # Skip models with zero price AND no explicit free flag
    # (processors/technical entries have all zeros)
    rub_price = pricing.get("rub_per_use", 0)
    usd_price = pricing.get("usd_per_use", 0)
    
    if rub_price == 0 and usd_price == 0:
        # Allow if it's a known cheap model (will be free)
        # But skip if it's a technical entry
        if model_id.isupper() or "_processor" in model_id.lower():
            return False
    
    # Valid model must have either:
    # - vendor/name format (google/veo, flux/dev, etc.) OR
    # - simple name without uppercase/processor (z-image, grok-imagine, etc.)
    return True


def _models_by_category() -> Dict[str, List[Dict[str, Any]]]:
    models = [model for model in _get_models_list() if _is_valid_model(model)]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for model in models:
        category = model.get("category", "other") or "other"
        grouped.setdefault(category, []).append(model)
    # Sort by price (cheapest first), then by name
    for model_list in grouped.values():
        model_list.sort(key=lambda item: (
            item.get("pricing", {}).get("rub_per_gen", 999999),
            (item.get("name") or item.get("model_id") or "").lower()
        ))
    return grouped


def _category_label(category: str) -> str:
    """Get category label (backward compatibility)."""
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def _category_metadata(category: str) -> Dict[str, Optional[str]]:
    """Get category metadata (title, subtitle, badge) with defaults."""
    metadata = CATEGORY_METADATA.get(category, {})
    return {
        "title": metadata.get("title") or _category_label(category),
        "subtitle": metadata.get("subtitle"),
        "badge": metadata.get("badge"),
    }


def _categories_from_registry() -> List[Tuple[str, str]]:
    grouped = _models_by_category()
    categories = sorted(grouped.keys(), key=lambda value: _category_label(value).lower())
    return [(category, _category_label(category)) for category in categories]


def _category_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"cat:{category}")]
        for category, label in _categories_from_registry()
    ]
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _models_by_io_type() -> Dict[str, List[Dict[str, Any]]]:
    """
    Group models by input/output type (BATCH 48.43: Simplified menu).
    
    Categories:
    - text-to-image: Models that generate images from text (prompt only)
    - image-to-image: Models that transform images (input_url/image_url required)
    - text-to-video: Models that generate videos from text (prompt only, category=video)
    - image-to-video: Models that generate videos from images (input_url required, category=video)
    - image-editor: Models that edit/enhance/upscale images (upscale, enhance, edit in name)
    """
    models = [model for model in _get_models_list() if _is_valid_model(model)]
    grouped: Dict[str, List[Dict[str, Any]]] = {
        "text-to-image": [],
        "image-to-image": [],
        "text-to-video": [],
        "image-to-video": [],
        "image-editor": []
    }
    
    for model in models:
        model_id = model.get("model_id", "").lower()
        category = model.get("category", "").lower()
        input_schema = model.get("input_schema", {})
        
        # Get properties from input_schema (BATCH 48.43: Use same logic as builder.py)
        # Support multiple formats:
        # 1. input_schema.input.properties (nested with properties)
        # 2. input_schema.input.examples[0] (nested with examples - most common)
        # 3. input_schema.properties (flat with properties)
        # 4. input_schema itself (flat)
        properties = {}
        if isinstance(input_schema, dict):
            # Check if input_schema has "input" key (nested structure)
            if "input" in input_schema and isinstance(input_schema["input"], dict):
                input_obj = input_schema["input"]
                # Check for properties first
                if "properties" in input_obj and isinstance(input_obj["properties"], dict):
                    properties = input_obj["properties"]
                # Check for examples (most common format in KIE_SOURCE_OF_TRUTH.json)
                elif "examples" in input_obj and isinstance(input_obj["examples"], list):
                    examples = input_obj["examples"]
                    if examples and isinstance(examples[0], dict):
                        # Extract fields from first example
                        properties = {key: {} for key in examples[0].keys()}
                else:
                    # input_obj itself might be properties
                    properties = input_obj
            elif "properties" in input_schema:
                properties = input_schema.get("properties", {})
            else:
                # input_schema itself is properties
                properties = input_schema
        
        # Check what inputs are required/available
        has_prompt = "prompt" in properties or "text" in properties
        has_image_input = any(
            key in properties 
            for key in ["input_url", "input_urls", "image_url", "image", "input_image", "base_image", "image_urls"]
        )
        is_video = category == "video" or "video" in model_id
        is_editor = any(
            keyword in model_id 
            for keyword in ["upscale", "enhance", "edit", "restore", "remove", "replace"]
        ) or category == "enhance"
        
        # Determine IO type
        if is_editor:
            grouped["image-editor"].append(model)
        elif is_video:
            if has_image_input:
                grouped["image-to-video"].append(model)
            elif has_prompt:
                grouped["text-to-video"].append(model)
            # Skip video models without clear input type
        elif has_image_input:
            # Has image input = image-to-image
            grouped["image-to-image"].append(model)
        elif has_prompt:
            # Has prompt only = text-to-image (default for image category)
            grouped["text-to-image"].append(model)
        # Skip models without clear input type (audio, avatar, music, etc.)
    
    # Sort by price (cheapest first)
    for model_list in grouped.values():
        model_list.sort(key=lambda item: (
            item.get("pricing", {}).get("rub_per_gen", 999999),
            (item.get("name") or item.get("model_id") or "").lower()
        ))
    
    return grouped


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Main menu keyboard - simplified (BATCH 48.43).
    
    Shows only:
    - Free models button
    - IO type categories (text-to-image, image-to-image, text-to-video, image-to-video, image-editor)
    - Balance
    - Referral (partnership)
    """
    # Get models grouped by IO type
    grouped = _models_by_io_type()
    
    # Build simplified menu
    buttons = []
    
    # BATCH 48.43: 🆓 FREE MODELS - FIRST BUTTON!
    buttons.append([
        InlineKeyboardButton(
            text="🆓 БЕСПЛАТНЫЕ МОДЕЛИ - Попробуй прямо сейчас!",
            callback_data="gallery:free"
        )
    ])
    
    # BATCH 48.43: IO type categories in order
    io_categories = [
        ("text-to-image", "📝 Из текста в фото"),
        ("image-to-image", "🖼 Из фото в фото"),
        ("text-to-video", "🎬 Из текста в видео"),
        ("image-to-video", "🎥 Из фото в видео"),
        ("image-editor", "✨ Фото редактор"),
    ]
    
    for io_type, label in io_categories:
        if io_type in grouped and len(grouped[io_type]) > 0:
            buttons.append([
                InlineKeyboardButton(text=label, callback_data=f"io:{io_type}")
            ])
    
    # BATCH 48.43: Bottom row - Balance and Referral only
    buttons.append([
        InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance"),
        InlineKeyboardButton(text="👥 Партнерка", callback_data="menu:referral")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _help_menu_keyboard() -> InlineKeyboardMarkup:
    """Help menu with FAQ."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆓 Как получить бесплатные генерации?", callback_data="help:free")],
            [InlineKeyboardButton(text="💳 Как пополнить баланс?", callback_data="help:topup")],
            [InlineKeyboardButton(text="📊 Как работает ценообразование?", callback_data="help:pricing")],
            [InlineKeyboardButton(text="🔧 Что делать при ошибке?", callback_data="help:errors")],
            [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
        ]
    )


def _main_menu_keyboard_OLD() -> InlineKeyboardMarkup:
    """
    Main menu keyboard with category shortcuts.
    
    ARCHITECTURE:
    - Quick access to most popular categories
    - All models accessible via category browser
    - Cheap/Free models highlighted
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            # Popular categories (auto-detect from registry)
            [InlineKeyboardButton(text="🎬 Видео (Reels/TikTok/Ads)", callback_data="cat:text-to-video")],
            [InlineKeyboardButton(text="🖼️ Картинка (баннер/пост/креатив)", callback_data="cat:text-to-image")],
            [InlineKeyboardButton(text="✨ Улучшить (апскейл/редакт)", callback_data="cat:upscale")],
            [InlineKeyboardButton(text="🎙️ Аудио (озвучка/музыка)", callback_data="cat:text-to-speech")],
            
            # Browse all
            [InlineKeyboardButton(text="🔎 Все модели (по категориям)", callback_data="menu:categories")],
            [InlineKeyboardButton(text="⭐ Дешёвые / Бесплатные", callback_data="menu:free")],
            
            # User actions
            [InlineKeyboardButton(text="🧾 История генераций", callback_data="menu:history")],
            [InlineKeyboardButton(text="💳 Баланс и пополнение", callback_data="menu:balance")],
        ]
    )


def _model_keyboard(models: List[Dict[str, Any]], back_cb: str, page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """Create paginated model keyboard with prices."""
    rows: List[List[InlineKeyboardButton]] = []
    
    # Calculate pagination
    start = page * per_page
    end = start + per_page
    page_models = models[start:end]
    total_pages = (len(models) + per_page - 1) // per_page
    
    # Model buttons with PRICE indicators and metadata (title, subtitle, badge)
    for model in page_models:
        model_id = model.get("model_id", "unknown")
        
        # Get menu metadata with defaults
        menu_title = model.get("menu_title") or model.get("display_name") or model.get("name") or model_id
        menu_subtitle = model.get("menu_subtitle")
        menu_badge = model.get("menu_badge")
        
        price_rub = model.get("pricing", {}).get("rub_per_gen", 0)
        
        # Price tag
        if price_rub == 0:
            price_tag = "🆓"
        elif price_rub < 1.0:
            price_tag = f"{price_rub:.2f}₽"
        elif price_rub < 10.0:
            price_tag = f"{price_rub:.1f}₽"
        else:
            price_tag = f"{price_rub:.0f}₽"
        
        # Build button text with badge if present
        # Format: "Title • Badge • Price" or "Title • Price"
        parts = [menu_title]
        if menu_badge:
            parts.append(menu_badge)
        parts.append(price_tag)
        
        button_text = " • ".join(parts)
        
        # Truncate if too long (max 64 chars for Telegram button)
        max_len = 60
        if len(button_text) > max_len:
            # Try to keep title and price, truncate badge if needed
            if menu_badge and len(menu_badge) > 10:
                # Shorten badge
                short_badge = menu_badge[:8] + ".."
                button_text = f"{menu_title} • {short_badge} • {price_tag}"
            if len(button_text) > max_len:
                # Truncate title
                title_max = max_len - len(f" • {menu_badge if menu_badge else ''} • {price_tag}")
                if title_max > 10:
                    menu_title = menu_title[:title_max-3] + "..."
                    button_text = f"{menu_title} • {menu_badge if menu_badge else ''} • {price_tag}".replace(" •  • ", " • ")
                else:
                    # Fallback: just title and price
                    button_text = f"{menu_title[:max_len-10]}... • {price_tag}"
        
        rows.append([InlineKeyboardButton(text=button_text, callback_data=f"model:{model_id}")])
    
    # Pagination buttons
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Пред", callback_data=f"page:{back_cb}:{page-1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="След ▶️", callback_data=f"page:{back_cb}:{page+1}"))
        rows.append(nav_buttons)
    
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _model_detail_text(model: Dict[str, Any]) -> str:
    """
    Create human-friendly model card.
    
    PRODUCTION-READY:
    - Clear value proposition (what user gets)
    - Honest pricing (exact formula)
    - No technical jargon
    - Examples when available
    """
    name = model.get("display_name") or model.get("name") or model.get("model_id")
    model_id = model.get("model_id", "")
    vendor = model.get("vendor", "")
    
    # Description - human-friendly (v6.3.0 enrichment)
    # CRITICAL: Always use Russian text
    description = model.get("description", "")
    
    # Check if description is in English (contains common English words)
    def is_english_text(text: str) -> bool:
        """Check if text appears to be in English."""
        if not text:
            return False
        english_indicators = ['the', 'and', 'for', 'with', 'this', 'that', 'from', 'power', 'api', 'model', 'generate', 'create']
        text_lower = text.lower()
        # If text contains many English words, it's likely English
        english_word_count = sum(1 for word in english_indicators if word in text_lower)
        return english_word_count >= 2 or (len(text) > 50 and english_word_count >= 1)
    
    # If description is empty or in English, use Russian fallback
    if not description or is_english_text(description):
        # Enhanced fallback descriptions based on category
        category = model.get("category", "")
        fallback_descriptions = {
            "text-to-image": "Создаёт изображения по вашему описанию",
            "image": "Создаёт изображения по вашему описанию",
            "text-to-video": "Создаёт видео из текста",
            "video": "Создаёт и редактирует видео",
            "audio": "Работа с аудио: озвучка, музыка, обработка",
            "music": "Генерация музыки и звуковых эффектов",
            "upscale": "Улучшает качество изображений",
            "enhance": "Улучшает качество и редактирует медиа",
            "image-to-image": "Редактирует и улучшает изображения",
            "image-to-video": "Превращает картинку в видео",
            "avatar": "Создание анимированных аватаров и персонажей",
            "other": "AI генерация и обработка контента",
        }
        description = fallback_descriptions.get(category, "AI генерация контента")
    
    # Use-case from v6.3.0 enrichment - CRITICAL: Always use Russian
    use_case = model.get("use_case", "")
    if use_case and is_english_text(use_case):
        # Translate common use cases to Russian
        use_case_translations = {
            "brand canvas": "Маркетинговые материалы",
            "design dreamscape": "Прототипирование продуктов",
            "content creation": "Создание контента",
            "social media": "Социальные сети",
            "marketing": "Маркетинг",
            "advertising": "Реклама",
        }
        # Try to find translation
        use_case_lower = use_case.lower()
        for eng_key, rus_value in use_case_translations.items():
            if eng_key in use_case_lower:
                use_case = rus_value
                break
        else:
            # If no translation found, use category-based fallback
            category = model.get("category", "")
            if "video" in category:
                use_case = "Создание видео для соцсетей и YouTube"
            elif "image" in category:
                use_case = "Создание изображений для маркетинга и дизайна"
            elif "audio" in category or "music" in category:
                use_case = "Озвучка и генерация музыки"
            else:
                use_case = "Генерация контента"
    
    # Example from v6.3.0 enrichment
    example = model.get("example", "")
    
    # Pricing - EXACT FORMULA
    from app.pricing.free_models import is_free_model
    
    if is_free_model(model_id):
        price_line = "💰 <b>Цена:</b> 🆓 БЕСПЛАТНО (FREE tier)"
    else:
        pricing = model.get("pricing", {})
        rub_per_use = pricing.get("rub_per_use")
        if rub_per_use:
            price_line = f"💰 <b>Цена:</b> {format_price_rub(rub_per_use)}"
        else:
            # Fallback calculation
            from app.payments.pricing import calculate_kie_cost, calculate_user_price
            kie_cost = calculate_kie_cost(model, {}, None)
            user_price = calculate_user_price(kie_cost)
            price_line = f"💰 <b>Цена:</b> {format_price_rub(user_price)}"
    
    # Parameters
    input_schema = model.get("input_schema", {})
    if 'properties' in input_schema:
        # Nested format
        required = input_schema.get("required", [])
        optional = input_schema.get("optional", [])
    else:
        # Flat format (source_of_truth.json)
        properties = input_schema
        required = [k for k, v in properties.items() if v.get('required', False)]
        optional = [k for k in properties.keys() if k not in required]
    
    params_total = len(required) + len(optional)
    if params_total == 0:
        params_line = "⚙️ <b>Параметры:</b> Не требуются"
    elif len(required) == 0:
        params_line = f"⚙️ <b>Параметры:</b> {params_total} опциональных"
    else:
        params_line = f"⚙️ <b>Параметры:</b> {len(required)} обязательных"
        if optional:
            params_line += f", {len(optional)} опциональных"
    
    # Vendor info
    if vendor:
        vendor_line = f"🏢 <b>Модель:</b> {vendor}"
    else:
        vendor_line = ""
    
    # Build card
    lines = [
        f"✨ <b>{name}</b>",
        "",
        f"📝 {description}",
    ]
    
    # Add use-case if available
    if use_case:
        lines.append("")
        lines.append(f"🎯 <b>Для чего:</b> {use_case[:200]}")  # Truncate to 200 chars
    
    lines.extend([
        "",
        price_line,
        params_line,
    ])
    
    if vendor_line:
        lines.append(vendor_line)
    
    # Add example from v6.3.0 enrichment
    if example:
        lines.append("")
        lines.append(f"💡 <b>Пример:</b> {example[:150]}")  # Truncate to 150 chars
    
    # Add tags if available
    tags = model.get("tags")
    if tags and isinstance(tags, list):
        lines.append("")
        tags_str = " • ".join(f"#{tag}" for tag in tags[:5])
        lines.append(f"🏷 {tags_str}")
    
    return "\n".join(lines)


def _model_detail_text_OLD(model: Dict[str, Any]) -> str:
    """Create human-friendly model card."""
    name = model.get("name") or model.get("model_id")
    model_id = model.get("model_id", "")
    
    # Check if price is preliminary (disabled_reason exists)
    price_warning = ""
    if model.get("disabled_reason"):
        price_warning = "\n\n⚠️ <i>Цена предварительная, актуализируется автоматически</i>"
    
    # Human-friendly description
    best_for = model.get("best_for") or model.get("description")
    if not best_for:
        # Generate description from model_id
        if "video" in model_id.lower():
            best_for = "Создание видео из текста или изображений"
        elif "image" in model_id.lower() or "flux" in model_id.lower():
            best_for = "Генерация изображений по описанию"
        elif "upscale" in model_id.lower():
            best_for = "Улучшение качества и разрешения изображений"
        elif "audio" in model_id.lower() or "tts" in model_id.lower():
            best_for = "Генерация голоса и озвучка текста"
        else:
            best_for = "Обработка и генерация контента"
    
    # Price formatting - CORRECT FORMULA: price_usd × 78 (USD→RUB) × 2 (markup)
    price_raw = model.get("price")
    if price_raw:
        try:
            price_usd = float(price_raw)
            if price_usd == 0:
                price_str = "Бесплатно"
            else:
                # Step 1: Convert USD to RUB (using calculate_kie_cost)
                kie_cost_rub = calculate_kie_cost(model, {}, None)
                # Step 2: Apply 2x markup for user price
                user_price_rub = calculate_user_price(kie_cost_rub)
                price_str = format_price_rub(user_price_rub)
        except (TypeError, ValueError):
            price_str = str(price_raw)
    else:
        price_str = "Уточняется"
    
    # ETA
    eta = model.get("eta")
    if eta:
        eta_str = f"~{eta} сек"
    else:
        # Estimate by category
        category = model.get("category", "")
        if "video" in category or "v2v" in category:
            eta_str = "~30-60 сек"
        elif "upscale" in category:
            eta_str = "~15-30 сек"
        else:
            eta_str = "~10-20 сек"
    
    # Example result
    input_schema = model.get("input_schema", {})
    required_fields = input_schema.get("required", [])
    if not required_fields:
        example = "Результат придет автоматически"
    elif len(required_fields) == 1:
        example = "Нужен 1 параметр"
    else:
        example = f"Нужно {len(required_fields)} параметра"
    
    return (
        f"✨ <b>{name}</b>\n\n"
        f"<b>Для чего:</b> {best_for}\n\n"
        f"<b>Что получите:</b> {example}\n"
        f"<b>Цена:</b> {price_str}\n"
        f"<b>Время:</b> {eta_str}"
        f"{price_warning}"
    )


def _model_detail_keyboard(model_id: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сгенерировать", callback_data=f"gen:{model_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb)],
        ]
    )


class InputFlow(StatesGroup):
    waiting_input = State()
    confirm = State()


@dataclass
class InputContext:
    model_id: str
    required_fields: List[str]
    optional_fields: List[str]  # MASTER PROMPT: "Ввод ВСЕХ параметров (без автоподстановок)"
    properties: Dict[str, Any]
    collected: Dict[str, Any]
    index: int = 0
    collecting_optional: bool = False  # Track if collecting optional params


def _field_prompt(field_name: str, field_spec: Dict[str, Any], step_current: int = 1, step_total: int = 3) -> str:
    """Generate human-friendly prompt with examples, errors, and clear instructions (UX improvement)."""
    from app.ux.copy_ru import t
    from app.ux.russian_ux import get_russian_param_name, get_russian_enum_value, get_param_description
    
    field_type = field_spec.get("type", "string")
    enum = field_spec.get("enum")
    max_length = field_spec.get("max_length", 500)
    description = field_spec.get("description", "")
    
    # BATCH 44: Russian name for parameter
    field_display = get_russian_param_name(field_name)
    param_description = get_param_description(field_name, field_spec)
    
    if enum:
        # BATCH 44: Russian enum values
        enum_list = "\n".join([f"• {get_russian_enum_value(field_name, val)}" for val in enum])
        return (
            f"{t('step_prompt_title', current=step_current, total=step_total)}\n\n"
            f"<b>Что нужно:</b> Выберите значение для <b>{field_display}</b>\n\n"
            f"<b>Доступные варианты:</b>\n{enum_list}\n\n"
            f"<i>Просто нажмите на нужный вариант ниже ⬇️</i>"
        )
    
    # CRITICAL UX FIX: Special handling for image/video URL fields - clear Russian instructions
    if field_name in ["image_url", "image", "input_image", "base_image", "image_urls", "input_url"]:
        return (
            f"{t('step_prompt_title', current=step_current, total=step_total)}\n\n"
            f"<b>Что нужно:</b> Отправьте <b>изображение</b> для обработки\n\n"
            f"📷 <b>Как отправить:</b>\n"
            f"• Отправьте фото прямо в чат (нажмите 📎 и выберите изображение)\n"
            f"• Или отправьте ссылку на изображение (начинается с http:// или https://)\n\n"
            f"💡 <b>Примеры ссылок:</b>\n"
            f"• https://example.com/photo.jpg\n"
            f"• http://site.com/image.png\n\n"
            f"📋 <b>Поддерживаемые форматы:</b> JPG, PNG, WEBP\n\n"
            f"⚠️ <b>Ограничения:</b>\n"
            f"• Размер файла: до 10 МБ\n"
            f"• Ссылка должна быть доступна и начинаться с http:// или https://"
        )
    
    if field_name in ["video_url", "video", "input_video"]:
        return (
            f"{t('step_prompt_title', current=step_current, total=step_total)}\n\n"
            f"<b>Что нужно:</b> Отправьте <b>видео</b> для обработки\n\n"
            f"🎬 <b>Как отправить:</b>\n"
            f"• Отправьте видео прямо в чат (нажмите 📎 и выберите видео)\n"
            f"• Или отправьте ссылку на видео (начинается с http:// или https://)\n\n"
            f"💡 <b>Примеры ссылок:</b>\n"
            f"• https://example.com/video.mp4\n"
            f"• http://site.com/clip.mov\n\n"
            f"📋 <b>Поддерживаемые форматы:</b> MP4, MOV, AVI\n\n"
            f"⚠️ <b>Ограничения:</b>\n"
            f"• Размер файла: до 50 МБ\n"
            f"• Ссылка должна быть доступна и начинаться с http:// или https://"
        )
    
    if field_type in {"file", "file_id", "file_url"}:
        return (
            f"{t('step_prompt_title', current=step_current, total=step_total)}\n\n"
            f"<b>Что нужно:</b> Загрузите файл для параметра <b>{field_display}</b>\n\n"
            f"📎 <b>Что отправить:</b>\n"
            f"• Изображение (JPG, PNG, WEBP)\n"
            f"• Видео (MP4, MOV)\n"
            f"• Аудио (MP3, WAV)\n\n"
            f"💡 <b>Пример:</b> Отправьте фото, видео или аудиофайл прямо в чат\n\n"
            f"⚠️ <b>Ограничения:</b>\n"
            f"• Изображения: до 10 МБ\n"
            f"• Видео: до 50 МБ\n"
            f"• Аудио: до 20 МБ"
        )
    
    if field_type in {"url", "link", "source_url"}:
        return (
            f"{t('step_prompt_title', current=step_current, total=step_total)}\n\n"
            f"<b>Что нужно:</b> Отправьте ссылку для параметра <b>{field_display}</b>\n\n"
            f"🔗 <b>Формат:</b> Ссылка должна начинаться с http:// или https://\n\n"
            f"💡 <b>Примеры:</b>\n"
            f"• https://example.com/image.jpg\n"
            f"• http://site.com/video.mp4\n\n"
            f"⚠️ <b>Частые ошибки:</b>\n"
            f"• Ссылка без http:// или https://\n"
            f"• Неполная ссылка (без домена)\n"
            f"• Файл недоступен по ссылке"
        )
    
    # Text/prompt fields - master input style with full UX
    if field_name in {"prompt", "text", "description", "input"}:
        return (
            f"{t('step_prompt_title', current=step_current, total=step_total)}\n\n"
            f"{t('step_prompt_what_needed')}\n\n"
            f"{t('step_prompt_examples')}\n\n"
            f"<b>Ограничения:</b> {t('step_prompt_limits', max=max_length)}\n\n"
            f"{t('step_prompt_errors', max=max_length)}\n\n"
            f"<i>{t('step_prompt_next')}</i>"
        )
    
    # Generic text field with description
    prompt_text = (
        f"{t('step_prompt_title', current=step_current, total=step_total)}\n\n"
        f"<b>Что нужно:</b> Введите значение для <b>{field_display}</b>\n\n"
    )
    
    if description:
        prompt_text += f"<i>{description}</i>\n\n"
    
    if max_length:
        prompt_text += (
            f"<b>Ограничения:</b> максимум {max_length} символов\n\n"
        )
    
    prompt_text += (
        f"💡 <b>Совет:</b> Будьте конкретны и кратко опишите, что нужно\n\n"
        f"⚠️ <b>Частые ошибки:</b>\n"
        f"• Слишком длинный текст (максимум {max_length} символов)\n"
        f"• Пустое значение (не оставляйте поле пустым)"
    )
    
    return prompt_text


def _enum_keyboard(field_name: str, field_spec: Dict[str, Any]) -> Optional[InlineKeyboardMarkup]:
    """Create keyboard with Russian enum values - BATCH 44."""
    from app.ux.russian_ux import get_russian_enum_value
    
    enum = field_spec.get("enum")
    if not enum:
        return None
    
    # BATCH 44: Show Russian text, but callback_data keeps English value for KIE AI
    rows = [[
        InlineKeyboardButton(
            text=get_russian_enum_value(field_name, val),  # Russian display
            callback_data=f"enum:{val}"  # English value for API
        )
    ] for val in enum]
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _input_navigation_keyboard(back_callback: str = "main_menu") -> InlineKeyboardMarkup:
    """Generate keyboard with Back/Cancel buttons for input steps (UX improvement)."""
    from app.ux.copy_ru import t
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t('button_back'), callback_data=back_callback),
            InlineKeyboardButton(text=t('button_cancel'), callback_data="main_menu")
        ]
    ])


def _coerce_value(value: Any, field_spec: Dict[str, Any]) -> Any:
    field_type = field_spec.get("type", "string")
    if field_type in {"integer", "int"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if field_type in {"number", "float"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if field_type in {"boolean", "bool"}:
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes", "on"}
        return bool(value)
    return value


def _validate_field_value(value: Any, field_spec: Dict[str, Any], field_name: str) -> None:
    field_type = field_spec.get("type", "string")
    validate_input_type(value, field_type, field_name)
    if "enum" in field_spec:
        enum_values = field_spec.get("enum", [])
        # CRITICAL FIX: For text fields (prompt, text, input, message), enum values are suggestions/examples,
        # NOT strict constraints. Users should be able to enter arbitrary text.
        is_text_field = field_name in ['prompt', 'text', 'input', 'message', 'negative_prompt'] or field_type in ['text', 'string', 'prompt']
        
        if not is_text_field and value not in enum_values:
            # For non-text fields, enum is strict
            raise ModelContractError(
                f"Поле '{field_name}' должно быть одним из {enum_values}"
            )
        elif is_text_field and value not in enum_values:
            # For text fields, enum is just a suggestion - allow arbitrary text
            logger.debug(
                f"Field '{field_name}' has enum suggestions {enum_values}, but user provided '{value[:50]}...' - "
                f"allowing arbitrary text for text fields"
            )
            # Don't raise error - allow arbitrary text
    if field_type in {"string", "text", "prompt", "input", "message"}:
        max_length = field_spec.get("max_length")
        if max_length and isinstance(value, str) and len(value) > max_length:
            raise ModelContractError(
                f"Поле '{field_name}' должно быть не длиннее {max_length} символов"
            )
    minimum = field_spec.get("minimum")
    maximum = field_spec.get("maximum")
    if minimum is not None or maximum is not None:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return
        if minimum is not None and numeric_value < minimum:
            raise ModelContractError(
                f"Поле '{field_name}' должно быть >= {minimum}"
            )
        if maximum is not None and numeric_value > maximum:
            raise ModelContractError(
                f"Поле '{field_name}' должно быть <= {maximum}"
            )


@router.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext) -> None:
    """Start command - personalized welcome with version and changelog."""
    from app.ux.copy_ru import t
    from app.utils.version import get_app_version, get_version_info
    from app.utils.changelog import get_latest_version, format_changelog_for_user
    
    await state.clear()
    
    # BATCH 48.44: Process referral link (/start?ref=USER_ID or /start ref_USER_ID)
    # Validate message.from_user
    if not message.from_user:
        logger.error("[FLOW] message.from_user is None in start_cmd")
        await message.answer("❌ Ошибка: не удалось определить пользователя. Попробуйте позже.")
        return
    
    user_id = message.from_user.id
    referral_set = False
    if message.text:
        referrer_id = None
        # Try format: /start?ref=USER_ID (Telegram sends as "/start ref_USER_ID" or "/start?ref=USER_ID")
        if "?ref=" in message.text:
            try:
                ref_part = message.text.split("?ref=")[1].split()[0]  # Get ref value before space
                referrer_id = int(ref_part)
            except (ValueError, IndexError) as e:
                # P1-2: Log instead of silent pass
                logger.debug(f"[FLOW] Failed to parse ref from URL: {e}")
                pass
        # Try format: /start ref_USER_ID
        elif " " in message.text:
            parts = message.text.split()
            if len(parts) >= 2:
                ref_code = parts[1]
                if ref_code.startswith("ref_"):
                    try:
                        referrer_id = int(ref_code.replace("ref_", ""))
                    except ValueError as e:
                        # P1-2: Log instead of silent pass
                        logger.debug(f"[FLOW] Failed to parse ref from code: {e}")
                        pass
        
        # Process referral if found
        if referrer_id and referrer_id != user_id:
            try:
                from app.storage import get_storage
                from app.referrals.manager import ReferralManager
                storage = get_storage()
                referral_manager = ReferralManager(storage)
                referral_set = await referral_manager.set_referrer(user_id, referrer_id)
                if referral_set:
                    logger.info(f"[REFERRAL] User {user_id} registered via referral from {referrer_id}")
            except (ValueError, Exception) as e:
                logger.warning(f"[REFERRAL] Failed to process referral code: {e}")
    
    # Get user info for personalization (already validated above)
    first_name = message.from_user.first_name or "друг"
    
    # Count available models (cached for performance)
    total_models = _get_total_models_count()
    
    # Get version and changelog
    app_version = get_app_version()
    version_info = get_version_info()
    changelog_info = get_latest_version()
    changelog_text = format_changelog_for_user(changelog_info)
    
    # BATCH 48.42: Show referral success message if applicable
    referral_msg = ""
    if referral_set:
        referral_msg = "\n\n🎉 <b>Отлично! Вы зарегистрированы по реферальной ссылке!</b>\n"
        referral_msg += "Ваш друг получит +5 генераций в час за вашу регистрацию!"
    
    # Professional welcome message - final product ready
    welcome_text = (
        f"👋 Добро пожаловать, {first_name}!\n\n"
        f"🚀 <b>Лучший аналог Syntx с бесплатными моделями!</b>\n"
        f"Профессиональная AI-платформа для генерации контента.\n\n"
        f"🎁 <b>Специальное предложение:</b>\n"
        f"Попробуй БЕСПЛАТНЫЕ модели прямо сейчас!\n"
        f"Никаких ограничений, никакой оплаты — просто жми на кнопку! 🚀\n\n"
        f"💰 Низкие цены на премиум-модели — дешевле чем у конкурентов!\n\n"
        f"✨ {total_models}+ AI-моделей от ведущих разработчиков\n"
        f"🆓 Бесплатные модели для старта\n"
        f"💰 Низкие цены на премиум-модели\n"
        f"⚡️ Мгновенная генерация • 🎯 Высокое качество\n\n"
        f"👇 Начни с бесплатных моделей и оцени качество!\n\n"
        f"{referral_msg}"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=_main_menu_keyboard(),
    )


@router.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    
    # Get user info (with None check)
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in main_menu_cb")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    first_name = callback.from_user.first_name or "друг"
    
    # Count models (cached for performance)
    total_models = _get_total_models_count()
    
    # Professional main menu - final product ready
    first_name = callback.from_user.first_name or "друг"
    
    # CRITICAL: None check for callback.message
    if not callback.message:
        logger.error("[FLOW] callback.message is None in main_menu_cb")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"👋 Добро пожаловать, {first_name}!\n\n"
        f"🚀 <b>Лучший аналог Syntx с бесплатными моделями!</b>\n"
        f"Профессиональная AI-платформа для генерации контента.\n\n"
        f"🎁 <b>Специальное предложение:</b>\n"
        f"Попробуй БЕСПЛАТНЫЕ модели прямо сейчас!\n"
        f"Никаких ограничений, никакой оплаты — просто жми на кнопку! 🚀\n\n"
        f"💰 Низкие цены на премиум-модели — дешевле чем у конкурентов!\n\n"
        f"✨ {total_models}+ AI-моделей от ведущих разработчиков\n"
        f"🆓 Бесплатные модели для старта\n"
        f"💰 Низкие цены на премиум-модели\n"
        f"⚡️ Мгновенная генерация • 🎯 Высокое качество\n\n"
        f"👇 Начни с бесплатных моделей и оцени качество!",
        reply_markup=_main_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu:about")
async def about_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show bot information: version, date, changelog."""
    await callback.answer()
    await state.clear()
    
    from app.ux.copy_ru import t
    from app.utils.version import get_app_version, get_version_info
    from app.utils.changelog import get_latest_version, format_changelog_for_user
    
    # Get version and changelog
    app_version = get_app_version()
    version_info = get_version_info()
    changelog_info = get_latest_version()
    changelog_text = format_changelog_for_user(changelog_info)
    
    about_text = (
        f"ℹ️ <b>О боте</b>\n\n"
        f"{changelog_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Техническая информация:</b>\n"
        f"• Версия сборки: <code>{app_version}</code>\n"
        f"• Источник версии: {version_info.get('source', 'unknown')}\n\n"
        f"💡 <i>Бот постоянно улучшается. Следите за обновлениями!</i>"
    )
    
    await callback.message.edit_text(
        about_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
        ]),
    )


@router.callback_query(F.data == "menu:help")
async def help_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show help menu."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in help_menu_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in help_menu_cb")
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "❓ Помощь и FAQ\n\nВыберите вопрос:",
        reply_markup=_help_menu_keyboard(),
    )


@router.callback_query(F.data == "help:free")
async def help_free_cb(callback: CallbackQuery) -> None:
    """Explain free tier."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in help_free_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in help_free_cb")
        return
    
    await callback.answer()
    from app.pricing.free_models import get_free_models
    
    free_models = get_free_models()
    await callback.message.edit_text(
        f"🆓 **Бесплатные генерации**\n\n"
        f"У нас есть {len(free_models)} бесплатных моделей (TOP-{len(free_models)} самые дешёвые):\n\n"
        f"Эти модели доступны ВСЕМ пользователям без списания баланса.\n\n"
        f"📍 Найти их: Главное меню → Все категории → выбрать любую категорию\n"
        f"💡 Модели с ценой 0.16₽ - 0.39₽ - это FREE tier",
        reply_markup=_help_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "help:topup")
async def help_topup_cb(callback: CallbackQuery) -> None:
    """Explain how to top up balance."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in help_topup_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in help_topup_cb")
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "💳 **Пополнение баланса**\n\n"
        "1. Нажмите 'Баланс' в главном меню\n"
        "2. Выберите сумму пополнения\n"
        "3. Оплатите по реквизитам\n"
        "4. Отправьте скриншот оплаты боту\n"
        "5. Баланс пополнится автоматически (OCR проверка)\n\n"
        "⚡️ Обычно обработка занимает 1-2 минуты\n\n"
        "❗️ Если баланс не пополнился - напишите в поддержку",
        reply_markup=_help_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "help:pricing")
async def help_pricing_cb(callback: CallbackQuery) -> None:
    """Explain pricing model."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in help_pricing_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in help_pricing_cb")
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "📊 **Ценообразование**\n\n"
        "Цена каждой генерации зависит от модели:\n\n"
        "• 🆓 FREE: 0₽ (топ-5 самых дешёвых)\n"
        "• 💚 Cheap: 0.40₽ - 10₽\n"
        "• 💛 Mid: 10₽ - 50₽\n"
        "• 🔴 Expensive: 50₽+\n\n"
        "Цена показывается ПЕРЕД запуском генерации.\n"
        "Списание происходит только после подтверждения.\n\n"
        "Формула: price_usd × 78.59 (курс) × 2.0 (наценка)\n\n"
        "💡 Начните с бесплатных моделей!",
        reply_markup=_help_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "help:errors")
async def help_errors_cb(callback: CallbackQuery) -> None:
    """Explain error handling."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in help_errors_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in help_errors_cb")
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "🔧 **Что делать при ошибке?**\n\n"
        "**Ошибка генерации:**\n"
        "• Деньги вернутся автоматически (auto-refund)\n"
        "• Проверьте баланс через 'История'\n\n"
        "**Ошибка оплаты:**\n"
        "• Убедитесь что сумма совпадает\n"
        "• Скриншот чёткий и читаемый\n"
        "• Попробуйте ещё раз\n\n"
        "**Модель не работает:**\n"
        "• Попробуйте другую модель\n"
        "• Проверьте параметры (формат, размер)\n\n"
        "❗️ Если проблема не решилась - напишите /support",
        reply_markup=_help_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "menu:best")
async def best_models_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Show curated list of best models (MASTER PROMPT requirement).
    
    CRITERIA:
    - TOP cheapest models first (best value)
    - Quality: Most reliable models from registry
    - Use case coverage: Different types (image, video, audio, enhance)
    - Price: Mix of FREE and paid
    """
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in best_models_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in best_models_cb")
        return
    
    await callback.answer()
    await state.clear()
    
    # Get all models sorted by price
    models = _get_models_list()
    valid_models = [m for m in models if _is_valid_model(m)]
    
    # Sort by price (cheapest first)
    valid_models.sort(key=lambda m: m.get("pricing", {}).get("rub_per_gen", 999999))
    
    # Take top 15 best value models
    best_models = valid_models[:15]
    
    # Build keyboard with price indicators
    buttons = []
    for model in best_models:
        model_id = model.get("model_id", "")
        name = model.get("display_name") or model.get("name") or model_id
        price_rub = model.get("pricing", {}).get("rub_per_gen", 0)
        category = model.get("category", "other")
        
        # Add price + category tags
        if price_rub == 0:
            price_tag = "🆓"
        elif price_rub < 1.0:
            price_tag = "💚"
        elif price_rub < 5.0:
            price_tag = "💛"
        else:
            price_tag = "💰"
        
        # Category emoji
        cat_emoji = {
            "image": "🎨",
            "video": "🎬",
            "audio": "🎵",
            "music": "🎵",
            "enhance": "✨",
            "avatar": "🧑‍🎤",
        }.get(category, "⭐")
        
        # Truncate long names
        if len(name) > 30:
            name = name[:27] + "..."
        
        button_text = f"{price_tag} {cat_emoji} {name}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"model:{model_id}"
        )])
    
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "⭐ <b>Лучшие модели</b>\n\n"
        "Топ-15 моделей с лучшим соотношением цена/качество:\n\n"
        "🆓 Бесплатно (0₽)\n"
        "💚 Очень дёшево (<1₽)\n"
        "💛 Дёшево (<5₽)\n"
        "💰 Доступно (5₽+)\n\n"
        "Выберите модель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data == "menu:search")
async def search_models_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Start model search flow (MASTER PROMPT requirement).
    
    FLOW:
    1. User enters search query
    2. Bot searches in: model_id, name, description, category
    3. Shows matching models (max 10)
    """
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in search_models_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in search_models_cb")
        return
    
    await callback.answer()
    await state.set_state(FlowStates.search_query)
    
    await callback.message.edit_text(
        "🔍 **Поиск модели**\n\n"
        "Введите название модели или описание (например: 'видео', 'музыка', 'flux', 'kling'):\n\n"
        "Или нажмите 'Отмена' чтобы вернуться.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
        ]),
        parse_mode="Markdown"
    )


@router.message(FlowStates.search_query)
async def process_search_query(message: Message, state: FSMContext) -> None:
    """Process model search query."""
    # P1-1: CRITICAL None checks
    if not message.from_user:
        logger.error("[FLOW] message.from_user is None in process_search_query")
        await message.answer("❌ Ошибка: не удалось определить пользователя.")
        await state.clear()
        return
    if not message.text:
        await message.answer("❌ Введите поисковый запрос (например: 'видео', 'flux')")
        return
    
    query = message.text.strip().lower()
    
    if len(query) < 2:
        await message.answer("Введите минимум 2 символа для поиска.")
        return
    
    # Get registry
    from app.kie.registry import get_model_registry
    registry = get_model_registry()
    
    # Search in all fields
    matches = []
    for model_id, model in registry.items():
        searchable_text = " ".join([
            model_id,
            model.get("name", ""),
            model.get("description", ""),
            model.get("category", ""),
        ]).lower()
        
        if query in searchable_text:
            matches.append((model_id, model))
    
    # Limit results
    matches = matches[:10]
    
    if not matches:
        await message.answer(
            f"❌ По запросу '{query}' ничего не найдено.\n\n"
            f"Попробуйте другой запрос или вернитесь в меню.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )
        await state.clear()
        return
    
    # Build results keyboard
    buttons = []
    for model_id, model in matches:
        name = model.get("name", model_id)
        price = model.get("pricing", {}).get("rub_per_use", 0)
        
        # Add price tag
        if price < 0.5:
            price_tag = "🆓"
        elif price < 10:
            price_tag = "💚"
        elif price < 50:
            price_tag = "💛"
        else:
            price_tag = "🔴"
        
        button_text = f"{price_tag} {name}"
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"model:{model_id}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔍 Новый поиск", callback_data="menu:search")])
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await message.answer(
        f"🔍 Найдено моделей: {len(matches)}\n\n"
        f"По запросу: '{query}'\n\n"
        f"Выберите модель:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.clear()


@router.callback_query(F.data == "menu:generate")
async def generate_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in generate_menu_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in generate_menu_cb")
        return
    
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🚀 Генерация\n\nВыберите категорию:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data == "menu:all_categories")
async def all_categories_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show all categories - DEPRECATED, use menu:categories instead."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in all_categories_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in all_categories_cb")
        return
    
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📂 Все категории\n\nВыберите категорию:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data == "menu:categories")
async def categories_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show all models grouped by category."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in categories_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in categories_cb")
        return
    
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📂 Все модели по категориям\n\nВыберите категорию:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data == "menu:free")
async def free_models_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show TOP-5 cheapest (free) models."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in free_models_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in free_models_cb")
        return
    
    await callback.answer()
    await state.clear()
    
    try:
        from app.pricing.free_models import get_free_models, get_model_price
        
        free_ids = get_free_models()
        
        if not free_ids:
            await callback.message.edit_text(
                "⚠️ Бесплатные модели временно недоступны",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
                ])
            )
            return
        
        # Get full model info
        all_models = _get_models_list()
        free_models = [m for m in all_models if m["model_id"] in free_ids]
        
        # Build message
        lines = ["⭐ **Дешёвые / Бесплатные модели**\n"]
        lines.append("Эти модели можно использовать бесплатно (TOP-5 самых дешёвых):\n")
        
        for i, model in enumerate(free_models, 1):
            display_name = model.get("display_name", model["model_id"])
            category = _category_label(model.get("category", "other"))
            lines.append(f"{i}. **{display_name}** ({category})")
        
        lines.append("\n💡 Выберите модель ниже для генерации:")
        
        # Build keyboard
        rows = []
        for model in free_models:
            display_name = model.get("display_name", model["model_id"])
            # Truncate long names
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."
            rows.append([
                InlineKeyboardButton(
                    text=f"🆓 {display_name}",
                    callback_data=f"model:{model['model_id']}"
                )
            ])
        
        rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
        
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Failed to show free models: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Ошибка при загрузке бесплатных моделей",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )


@router.callback_query(F.data == "menu:edit")
async def edit_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in edit_menu_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in edit_menu_cb")
        return
    
    await callback.answer()
    await state.clear()
    # Show editing categories
    edit_categories = ["i2i", "upscale", "bg_remove", "watermark_remove"]
    grouped = _models_by_category()
    rows = []
    for cat in edit_categories:
        if cat in grouped and grouped[cat]:
            label = _category_label(cat)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"cat:{cat}")])
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    await callback.message.edit_text(
        "✏️ Редактирование\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "menu:audio")
async def audio_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in audio_menu_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in audio_menu_cb")
        return
    
    await callback.answer()
    await state.clear()
    # Show audio categories
    audio_categories = ["tts", "stt", "music", "sfx", "audio_isolation"]
    grouped = _models_by_category()
    rows = []
    for cat in audio_categories:
        if cat in grouped and grouped[cat]:
            label = _category_label(cat)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"cat:{cat}")])
    if not rows:
        rows.append([InlineKeyboardButton(text="⚠️ Аудио модели скоро появятся", callback_data="noop")])
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    await callback.message.edit_text(
        "🎧 Аудио / Озвучка\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "menu:top")
async def top_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in top_menu_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in top_menu_cb")
        return
    
    await callback.answer()
    await state.clear()
    # Top models - based on popularity/price
    all_models = [m for m in _get_models_list() if _is_valid_model(m)]
    
    # Sort by: has price, then by category popularity
    popular_categories = ["t2i", "t2v", "i2i", "upscale"]
    top_models = []
    
    for cat in popular_categories:
        cat_models = [m for m in all_models if m.get("category") == cat]
        if cat_models:
            top_models.append(cat_models[0])  # First model from each popular category
    
    if not top_models:
        top_models = all_models[:5]  # Fallback to first 5
    
    await state.update_data(top_models=True)
    await callback.message.edit_text(
        "⭐ Лучшие модели\n\nПопулярные и проверенные нейросети:",
        reply_markup=_model_keyboard(top_models, "main_menu", page=0),
    )


class SearchFlow(StatesGroup):
    waiting_query = State()


@router.callback_query(F.data == "menu:search")
async def search_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in search_menu_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in search_menu_cb")
        return
    
    await callback.answer()
    await state.set_state(SearchFlow.waiting_query)
    await callback.message.edit_text(
        "🔎 Поиск модели\n\n"
        "Введите название модели или ключевые слова (например: flux, kling, video, upscale):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]]
        ),
    )


@router.message(SearchFlow.waiting_query, F.text)
async def search_query_handler(message: Message, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not message.from_user:
        logger.error("[FLOW] message.from_user is None in search_query_handler")
        await message.answer("❌ Ошибка: не удалось определить пользователя.")
        await state.clear()
        return
    if not message.text:
        await message.answer("❌ Введите поисковый запрос")
        return
    query = (message.text or "").lower().strip()
    if not query:
        await message.answer("⚠️ Введите поисковый запрос.")
        return
    
    await state.clear()
    
    # Search models
    all_models = [m for m in _get_models_list() if _is_valid_model(m)]
    matches = []
    for model in all_models:
        model_id = model.get("model_id", "").lower()
        name = (model.get("name") or "").lower()
        desc = (model.get("description") or "").lower()
        best_for = (model.get("best_for") or "").lower()
        
        if query in model_id or query in name or query in desc or query in best_for:
            matches.append(model)
    
    if not matches:
        await message.answer(
            f"❌ По запросу '{query}' ничего не найдено.\n\n"
            "Попробуйте другие ключевые слова.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔎 Новый поиск", callback_data="menu:search")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ]
            ),
        )
        return
    
    # Show results
    await state.update_data(category_models=matches)
    await message.answer(
        f"🔎 Найдено моделей: {len(matches)}\n\nВыберите модель:",
        reply_markup=_model_keyboard(matches, "menu:search", page=0),
    )


@router.callback_query(F.data.in_({"support", "menu:support"}))
async def support_cb(callback: CallbackQuery, data: dict = None) -> None:
    """Handle support button click - uses keys from Render ENV."""
    from app.utils.correlation import ensure_correlation_id
    from app.utils.enhanced_logging import log_operation, log_error
    import time
    import os
    
    start_time = time.time()
    cid = ensure_correlation_id(str(callback.id))
    user_id = callback.from_user.id if callback.from_user else None
    chat_id = callback.message.chat.id if callback.message else None
    
    log_operation(
        "SUPPORT_BUTTON_CLICKED",
        status="START",
        user_id=user_id,
        chat_id=chat_id,
        callback_data=callback.data,
        callback_id=callback.id,
        cid=cid
    )
    
    try:
        await callback.answer()
        
        # BATCH 48.52: Get support info from ENV (Render keys)
        support_email = os.getenv("SUPPORT_EMAIL", "support@example.com")
        support_telegram = os.getenv("SUPPORT_TELEGRAM", "@support_bot")
        support_chat_id = os.getenv("SUPPORT_CHAT_ID")  # Optional: direct chat link
        
        # Build support message
        support_text = "ℹ️ <b>Поддержка</b>\n\n"
        support_text += "Если у вас возникли вопросы или проблемы:\n\n"
        
        if support_email:
            support_text += f"📧 Email: {support_email}\n"
        
        if support_telegram:
            # If it's a username (starts with @), make it a link
            if support_telegram.startswith("@"):
                support_text += f"💬 Telegram: <a href=\"https://t.me/{support_telegram[1:]}\">{support_telegram}</a>\n"
            else:
                support_text += f"💬 Telegram: {support_telegram}\n"
        
        if support_chat_id:
            # Direct chat link if chat_id is provided
            try:
                chat_id_int = int(support_chat_id)
                support_text += f"\n💬 <a href=\"https://t.me/{callback.message.bot.username}?start=support\">Написать в поддержку</a>\n"
            except ValueError:
                pass
        
        support_text += "\nМы отвечаем в течение 24 часов."
        
        await callback.message.edit_text(
            support_text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ]
            ),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        duration_ms = (time.time() - start_time) * 1000
        log_operation(
            "SUPPORT_BUTTON_CLICKED",
            status="OK",
            duration_ms=duration_ms,
            user_id=user_id,
            chat_id=chat_id,
            callback_data=callback.data,
            support_email=support_email,
            support_telegram=support_telegram,
            cid=cid
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            "SUPPORT_BUTTON_CLICKED",
            e,
            error_code="SUPPORT_HANDLER_ERROR",
            fix_hint="Check callback.message availability and edit_text permissions",
            check_list="callback.message | edit_text permissions | message not deleted",
            duration_ms=duration_ms,
            user_id=user_id,
            chat_id=chat_id,
            callback_data=callback.data,
            cid=cid
        )
        raise


@router.callback_query(F.data.in_({"balance", "menu:balance"}))
async def balance_cb(callback: CallbackQuery, state: FSMContext, data: dict = None) -> None:
    """Handle balance button click - full balance and topup functionality."""
    from app.utils.correlation import ensure_correlation_id
    from app.utils.enhanced_logging import log_operation, log_error
    import time
    
    start_time = time.time()
    cid = ensure_correlation_id(str(callback.id))
    user_id = callback.from_user.id if callback.from_user else None
    chat_id = callback.message.chat.id if callback.message else None
    
    log_operation(
        "BALANCE_BUTTON_CLICKED",
        status="START",
        user_id=user_id,
        chat_id=chat_id,
        callback_data=callback.data,
        callback_id=callback.id,
        cid=cid
    )
    
    try:
        await callback.answer()
        # CRITICAL FIX: Use state parameter instead of bot.get_current()
        await state.clear()
        
        # Get balance with detailed logging
        log_operation(
            "BALANCE_FETCH_START",
            status="START",
            user_id=user_id,
            cid=cid
        )
        
        balance_start = time.time()
        charge_manager = get_charge_manager()
        balance = await charge_manager.get_user_balance(user_id)
        balance_duration_ms = (time.time() - balance_start) * 1000
        
        log_operation(
            "BALANCE_FETCH_COMPLETE",
            status="OK",
            duration_ms=balance_duration_ms,
            user_id=user_id,
            balance=balance,
            balance_formatted=format_price_rub(balance),
            cid=cid
        )
        
        # BATCH 48.52: Show balance with full topup functionality
        text = (
            f"💳 <b>Ваш баланс</b>\n\n"
            f"💰 Доступно: {format_price_rub(balance)}\n\n"
            f"<b>Пополнение баланса:</b>\n"
            f"Выберите сумму или введите свою (от 50 до 50 000 руб.)"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💵 Пополнить баланс", callback_data="balance:topup")],
                [
                    InlineKeyboardButton(text="100₽", callback_data="topup:amount:100"),
                    InlineKeyboardButton(text="500₽", callback_data="topup:amount:500")
                ],
                [
                    InlineKeyboardButton(text="1000₽", callback_data="topup:amount:1000"),
                    InlineKeyboardButton(text="5000₽", callback_data="topup:amount:5000")
                ],
                [InlineKeyboardButton(text="📜 История", callback_data="menu:history")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
        duration_ms = (time.time() - start_time) * 1000
        log_operation(
            "BALANCE_BUTTON_CLICKED",
            status="OK",
            duration_ms=duration_ms,
            user_id=user_id,
            chat_id=chat_id,
            balance=balance,
            balance_formatted=format_price_rub(balance),
            callback_data=callback.data,
            cid=cid
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_error(
            "BALANCE_BUTTON_CLICKED",
            e,
            error_code="BALANCE_HANDLER_ERROR",
            fix_hint="Check ChargeManager.get_user_balance | callback.message availability | FileStorage",
            check_list="get_charge_manager() | get_user_balance() | callback.message | FileStorage | NO_DATABASE_MODE",
            duration_ms=duration_ms,
            user_id=user_id,
            chat_id=chat_id,
            callback_data=callback.data,
            cid=cid
        )
        raise


@router.callback_query(F.data.startswith("topup:amount:"))
async def cb_topup_preset_flow(callback: CallbackQuery, state: FSMContext) -> None:
    """Quick topup with preset amount."""
    await callback.answer()
    from decimal import Decimal
    amount = int(callback.data.split(":", 2)[2])
    await _show_payment_instructions_flow(callback, state, Decimal(amount))


@router.message(TopupStates.enter_amount)
async def process_topup_amount_flow(message: Message, state: FSMContext) -> None:
    """Process custom topup amount."""
    # CRITICAL: None checks
    if not message.from_user:
        logger.error("[FLOW] message.from_user is None in process_topup_amount_flow")
        await message.answer("❌ Ошибка: не удалось определить пользователя. Попробуйте позже.")
        return
    if not message.text:
        await message.answer("❌ Введите корректную сумму (например: 500)")
        return
    
    import decimal
    from decimal import Decimal
    
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля")
            return
        if amount > 100000:
            await message.answer("❌ Максимальная сумма: 100 000 руб.")
            return
    except (ValueError, decimal.InvalidOperation) as e:
        logger.error(f"Failed to parse amount from '{message.text}': {e}")
        await message.answer("❌ Введите корректную сумму (например: 500)")
        return
    
    await _show_payment_instructions_flow_message(message, state, amount)


async def _show_payment_instructions_flow_message(message: Message, state: FSMContext, amount: Decimal) -> None:
    """Show payment instructions (message version)."""
    # CRITICAL: None checks
    if not message.from_user:
        logger.error("[FLOW] message.from_user is None in _show_payment_instructions_flow_message")
        await message.answer("❌ Ошибка: не удалось определить пользователя. Попробуйте позже.")
        return
    
    import os
    
    # Validate amount range: 50-50000 RUB (payment safety)
    if amount < 50 or amount > 50000:
        await message.answer("❌ Сумма должна быть от 50 до 50 000 руб.")
        return
    
    # BATCH 48.52: Payment credentials from ENV (Render keys)
    bank = os.getenv("PAYMENT_BANK", "Сбербанк")
    card = os.getenv("PAYMENT_CARD", "2202 2000 0000 0000")
    holder = os.getenv("PAYMENT_CARD_HOLDER", "IVAN IVANOV")
    phone = os.getenv("PAYMENT_PHONE", "+7 900 000 00 00")
    
    text = (
        f"💳 <b>Пополнение на {format_price_rub(amount)}</b>\n\n"
        f"<b>Реквизиты для оплаты:</b>\n"
        f"🏦 Банк: {bank}\n"
        f"💳 Карта: <code>{card}</code>\n"
        f"👤 Получатель: {holder}\n"
        f"📱 Телефон: <code>{phone}</code>\n\n"
        f"<b>Важно:</b>\n"
        f"• Переводите точную сумму: {format_price_rub(amount)}\n"
        f"• После оплаты нажмите кнопку ниже\n"
        f"• Пришлите скриншот чека для проверки\n\n"
        f"<i>Обработка занимает до 5 минут</i>"
    )
    
    await state.update_data(topup_amount=float(amount))
    await state.set_state(TopupStates.confirm_payment)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="topup:paid")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu:balance")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "topup:paid")
async def cb_topup_paid_flow(callback: CallbackQuery, state: FSMContext) -> None:
    """User claims they paid - ask for receipt."""
    text = (
        f"📸 <b>Подтверждение платежа</b>\n\n"
        f"Пришлите скриншот чека или квитанции.\n\n"
        f"<i>После проверки средства будут зачислены автоматически</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu:balance")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(TopupStates.confirm_payment, F.photo)
async def process_receipt_flow(message: Message, state: FSMContext) -> None:
    """Process receipt photo for topup."""
    # CRITICAL: None checks
    if not message.from_user:
        logger.error("[FLOW] message.from_user is None in process_receipt_flow")
        await message.answer("❌ Ошибка: не удалось определить пользователя. Попробуйте позже.")
        return
    if not message.photo:
        await message.answer("❌ Пожалуйста, пришлите фото чека.")
        return
    
    from decimal import Decimal
    import uuid
    
    data = await state.get_data()
    amount = Decimal(str(data.get("topup_amount", 0)))
    
    await state.clear()
    
    # BATCH 48.52: Support both DB and NO DATABASE MODE
    from app.storage import get_storage
    from app.database.services import DatabaseService, WalletService
    
    db_service = None
    try:
        from app.services.wiring import get_db_service
        db_service = get_db_service()
    except Exception as e:
        logger.debug(f"[FLOW] Database service not available (NO DATABASE MODE): {e}")
    
    if db_service:
        # Use WalletService for DB mode
        wallet_service = WalletService(db_service)
        ref = f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}"
        success = await wallet_service.topup(
            message.from_user.id,
            amount,
            ref,
            meta={"photo_id": message.photo[-1].file_id, "status": "manual_review"}
        )
    else:
        # Use FileStorage for NO DATABASE MODE
        storage = get_storage()
        ref = f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}"
        # Add balance in FileStorage
        current_balance = await storage.get_user_balance(message.from_user.id)
        await storage.set_balance(message.from_user.id, float(current_balance) + float(amount))
        success = True
    
    if success:
        text = (
            f"✅ <b>Заявка принята!</b>\n\n"
            f"Сумма: {format_price_rub(amount)}\n"
            f"Номер заявки: <code>{ref}</code>\n\n"
            f"Средства будут зачислены после проверки (обычно до 5 минут)"
        )
    else:
        text = (
            f"⚠️ <b>Заявка уже обработана</b>\n\n"
            f"Эта заявка уже была принята ранее."
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Мой баланс", callback_data="menu:balance")],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


async def _show_payment_instructions_flow(callback: CallbackQuery, state: FSMContext, amount: Decimal) -> None:
    """Show payment instructions with ENV keys from Render."""
    import os
    
    # Validate amount range: 50-50000 RUB (payment safety)
    if amount < 50 or amount > 50000:
        await callback.answer("❌ Сумма должна быть от 50 до 50 000 руб.", show_alert=True)
        return
    
    # BATCH 48.52: Payment credentials from ENV (Render keys)
    bank = os.getenv("PAYMENT_BANK", "Сбербанк")
    card = os.getenv("PAYMENT_CARD", "2202 2000 0000 0000")
    holder = os.getenv("PAYMENT_CARD_HOLDER", "IVAN IVANOV")
    phone = os.getenv("PAYMENT_PHONE", "+7 900 000 00 00")
    
    text = (
        f"💳 <b>Пополнение на {format_price_rub(amount)}</b>\n\n"
        f"<b>Реквизиты для оплаты:</b>\n"
        f"🏦 Банк: {bank}\n"
        f"💳 Карта: <code>{card}</code>\n"
        f"👤 Получатель: {holder}\n"
        f"📱 Телефон: <code>{phone}</code>\n\n"
        f"<b>Важно:</b>\n"
        f"• Переводите точную сумму: {format_price_rub(amount)}\n"
        f"• После оплаты нажмите кнопку ниже\n"
        f"• Пришлите скриншот чека для проверки\n\n"
        f"<i>Обработка занимает до 5 минут</i>"
    )
    
    await state.update_data(topup_amount=float(amount))
    await state.set_state(TopupStates.confirm_payment)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="topup:paid")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu:balance")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu:referral")
async def referral_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle referral/partnership button click - show referral info and link."""
    # CRITICAL: None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in referral_cb")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in referral_cb")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    await state.clear()
    
    user_id = callback.from_user.id
    
    try:
        # BATCH 48.52: Get ReferralManager from global services
        from app.storage import get_storage
        from app.referrals.manager import ReferralManager
        
        storage = get_storage()
        referral_manager = ReferralManager(storage)
        
        # Get referral info
        referral_info = await referral_manager.get_referral_info(user_id)
        
        # Get bot username for referral link
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username or "your_bot"
        
        # Generate referral link
        referral_link = referral_manager.generate_referral_link(user_id, bot_username)
        
        # Build message
        text = (
            "👥 <b>Партнерская программа</b>\n\n"
            f"<b>Ваш лимит бесплатных генераций:</b>\n"
            f"⚡️ Базовый: {referral_info['base_limit']} генераций в час\n"
        )
        
        if referral_info['bonus_limit'] > 0:
            text += (
                f"🎁 Бонусный: +{referral_info['bonus_limit']} генераций в час "
                f"({referral_info['referrals_count']} приглашенных друзей)\n"
            )
        
        text += (
            f"📊 <b>Всего:</b> {referral_info['total_limit']} генераций в час\n\n"
            f"<b>Как получить больше генераций?</b>\n"
            f"Пригласите друга по реферальной ссылке и получите +5 генераций в час!\n\n"
            f"<b>Ваша реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"<i>Поделитесь ссылкой с друзьями. За каждого приглашенного друга вы получите +5 генераций в час!</i>"
        )
        
        # Build keyboard
        keyboard_buttons = []
        
        # Share button (Telegram share)
        share_text = f"🎁 Получи бесплатные генерации! Используй мою реферальную ссылку: {referral_link}"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="📤 Поделиться ссылкой",
                url=f"https://t.me/share/url?url={referral_link}&text={share_text}"
            )
        ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"[REFERRAL] Failed to show referral info: {e}", exc_info=True)
        await callback.message.edit_text(
            "⚠️ <b>Ошибка загрузки информации о партнерке</b>\n\n"
            "Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
                ]
            ),
        )


@router.callback_query(F.data == "menu:history")
async def history_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # CRITICAL: None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in history_cb")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in history_cb")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    await state.clear()
    history = get_charge_manager().get_user_history(callback.from_user.id, limit=10)
    
    if not history:
        await callback.message.edit_text(
            "🕘 История генераций пуста.\n\n"
            "Создайте свою первую генерацию!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]]
            ),
        )
        return
    
    # Show history
    text_lines = ["🕘 <b>Последние генерации:</b>\n"]
    rows = []
    for idx, record in enumerate(history[:5]):
        model_id = record.get('model_id', 'unknown')
        success = record.get('success', False)
        timestamp = record.get('timestamp', '')[:16]  # YYYY-MM-DDTHH:MM
        status_icon = "✅" if success else "❌"
        text_lines.append(f"{status_icon} {model_id} - {timestamp}")
        # Add repeat button
        if success and idx < 3:  # Only first 3
            rows.append([InlineKeyboardButton(text=f"🔁 {model_id}", callback_data=f"repeat:{idx}")])
    
    text_lines.append("\nНажмите 🔁 чтобы повторить генерацию.")
    rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("repeat:"))
async def repeat_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # CRITICAL: None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in repeat_cb")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in repeat_cb")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    idx_str = callback.data.split(":", 1)[1]
    try:
        idx = int(idx_str)
    except ValueError:
        await callback.message.edit_text("⚠️ Ошибка.")
        return
    
    history = get_charge_manager().get_user_history(callback.from_user.id, limit=10)
    if idx >= len(history):
        await callback.message.edit_text("⚠️ Генерация не найдена.")
        return
    
    record = history[idx]
    model_id = record.get('model_id')
    inputs = record.get('inputs', {})
    
    # Re-run generation with same inputs
    model = next((m for m in _get_models_list() if m.get("model_id") == model_id), None)
    if not model:
        logger.error(f"[FLOW] Model not found: {model_id}")
        await callback.message.edit_text("⚠️ Модель не найдена.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
        ]))
        return
    
    price_raw = model.get("price") or 0
    try:
        amount = float(price_raw)
    except (TypeError, ValueError):
        amount = 0.0
    
    charge_manager = get_charge_manager()
    balance = await charge_manager.get_user_balance(callback.from_user.id)
    if amount > 0 and balance < amount:
        await callback.message.edit_text(
            "❌ Недостаточно средств для повтора.\n\n"
            f"Стоимость: {format_price_rub(amount)}\n"
            f"Баланс: {format_price_rub(balance)}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Пополнить", callback_data="menu:balance")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ]
            ),
        )
        return
    
    await callback.message.edit_text("⏳ Повторная генерация запущена...")
    
    def heartbeat(text: str) -> None:
        asyncio.create_task(callback.message.answer(text))
    
    charge_task_id = f"repeat_{callback.from_user.id}_{callback.message.message_id}"
    result = await generate_with_payment(
        model_id=model_id,
        user_inputs=inputs,
        user_id=callback.from_user.id,
        amount=amount,
        progress_callback=heartbeat,
        task_id=charge_task_id,
        reserve_balance=True,
        chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
    )
    
    if result.get("success"):
        urls = result.get("result_urls") or []
        if urls:
            await callback.message.answer("\n".join(urls))
        else:
            await callback.message.answer("✅ Готово!")
        await callback.message.answer(
            "Что дальше?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Ещё раз", callback_data=f"repeat:{idx}")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )
    else:
        # CRITICAL: Clear FSM state on error to prevent user getting stuck
        await state.clear()
        
        # BATCH 38: Improved error handling with retry options
        from app.ux.error_handler import handle_generation_error
        
        # Get model_id from quick_models (assuming idx is valid)
        model_id = quick_models[idx] if idx < len(quick_models) else "unknown"
        
        # Get error message and keyboard from unified error handler
        error_msg, error_keyboard = handle_generation_error(result, model_id)
        
        # Send error with retry keyboard
        await callback.message.answer(
            error_msg,
            reply_markup=error_keyboard,
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("io:"))
async def io_type_cb(callback: CallbackQuery, state: FSMContext, data: dict = None) -> None:
    """Show models by input/output type (BATCH 48.43: Simplified menu)."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in io_type_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in io_type_cb")
        return
    
    await callback.answer()
    await state.clear()
    
    io_type = callback.data.split(":", 1)[1]
    await _show_io_type_models(callback.message, io_type, page=0)


async def _show_io_type_models(message: Message, io_type: str, page: int = 0) -> None:
    """Show models for IO type with pagination."""
    grouped = _models_by_io_type()
    models = grouped.get(io_type, [])
    
    if not models:
        await message.edit_text(
            "⚠️ Модели в этой категории временно недоступны.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )
        return
    
    # Pagination settings
    max_models_per_page = 10
    total_pages = (len(models) + max_models_per_page - 1) // max_models_per_page
    page = max(0, min(page, total_pages - 1))  # Clamp page to valid range
    
    # Calculate slice
    start_idx = page * max_models_per_page
    end_idx = start_idx + max_models_per_page
    page_models = models[start_idx:end_idx]
    
    # Build model list text
    io_labels = {
        "text-to-image": "📝 Из текста в фото",
        "image-to-image": "🖼 Из фото в фото",
        "text-to-video": "🎬 Из текста в видео",
        "image-to-video": "🎥 Из фото в видео",
        "image-editor": "✨ Фото редактор",
    }
    
    title = io_labels.get(io_type, io_type.replace("-", " ").title())
    lines = [
        f"<b>{title}</b>\n",
        f"Страница {page + 1}/{total_pages}",
        f"Всего моделей: {len(models)}\n",
        "Выберите модель для генерации:"
    ]
    
    # Build keyboard with pagination
    keyboard_rows = []
    
    for model in page_models:
        model_id = model.get("model_id")
        display_name = model.get("display_name") or model.get("name") or model_id
        price = model.get("pricing", {}).get("rub_per_gen", 0)
        
        # Truncate long names (max 50 chars for button)
        if len(display_name) > 50:
            display_name = display_name[:47] + "..."
        
        # Add price to button text if not free
        if price == 0:
            button_text = f"🆓 {display_name}"
        else:
            price_str = f"{price:.2f}₽" if price < 1 else f"{price:.0f}₽"
            button_text = f"{display_name} • {price_str}"
        
        keyboard_rows.append([
            InlineKeyboardButton(text=button_text, callback_data=f"model:{model_id}")
        ])
    
    # Pagination navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"io_page:{io_type}:{page-1}"
        ))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперёд ▶️",
            callback_data=f"io_page:{io_type}:{page+1}"
        ))
    
    if nav_buttons:
        keyboard_rows.append(nav_buttons)
    
    keyboard_rows.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("io_page:"))
async def io_page_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle pagination for IO type model lists."""
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("⚠️ Ошибка пагинации", show_alert=True)
        return
    
    io_type = parts[1]
    try:
        page = int(parts[2])
    except ValueError:
        page = 0
    
    await _show_io_type_models(callback.message, io_type, page)


@router.callback_query(F.data.startswith("cat:"))
async def category_cb(callback: CallbackQuery, state: FSMContext, data: dict = None) -> None:
    """Handle category selection callback (cat:image, cat:enhance, etc.)."""
    # Telemetry: log callback received
    from app.telemetry import (
        log_callback_received, log_callback_routed, log_callback_accepted, 
        log_ui_render, log_dispatch_ok, generate_cid,
        get_update_id, get_callback_id, get_user_id, get_message_id
    )
    
    cid = generate_cid()
    # Use safe helpers to extract context
    update_id = get_update_id(callback, data or {})
    callback_id = get_callback_id(callback)
    user_id = get_user_id(callback)
    message_id = get_message_id(callback)
    
    log_callback_received(
        callback_data=callback.data,
        query_id=callback_id,
        message_id=message_id,
        user_id=user_id,
        update_id=update_id,
        cid=cid
    )
    
    log_callback_routed(
        callback_data=callback.data,
        handler="category_cb",
        cid=cid
    )
    
    try:
        await callback.answer()
        category = callback.data.split(":", 1)[1]
        grouped = _models_by_category()
        models = grouped.get(category, [])

        if not models:
            category_label = _category_label(category)
            await callback.message.edit_text(
                f"⚠️ {category_label}\n\n"
                f"В этой категории пока нет доступных моделей.\n"
                f"Попробуйте другую категорию или вернитесь в меню.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📂 Все категории", callback_data="menu:categories")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
                ])
            )
            log_callback_accepted(callback_data=callback.data, handler="category_cb", cid=cid)
            log_ui_render(screen_id="category_empty", cid=cid)
            log_dispatch_ok(cid=cid)
            return

        await state.update_data(category=category, category_models=models)
        
        # Category benefit line
        from app.ux.copy_ru import get_category_benefit, t
        benefit = get_category_benefit(category)
        
        # Category micro-moment
        category_text = (
            f"Категория: <b>{_category_label(category)}</b>\n"
        )
        if benefit:
            category_text += f"<i>{benefit}</i>\n\n"
        category_text += f"{t('category_selected_message')}\n\n"
        category_text += "Выберите модель:"
        
        await callback.message.edit_text(
            category_text,
            reply_markup=_model_keyboard(models, f"cat:{category}", page=0),
        )
        log_callback_accepted(callback_data=callback.data, handler="category_cb", cid=cid)
        log_ui_render(screen_id=f"category_{category}", cid=cid)
        log_dispatch_ok(cid=cid)
    except Exception as e:
        from app.telemetry import log_callback_rejected
        log_callback_rejected(
            callback_data=callback.data,
            reason="EXCEPTION",
            reason_detail=str(e),
            cid=cid
        )
        logger.error(f"Error in category_cb: {e}", exc_info=True)
        # Re-raise to let exception middleware handle it
        raise


@router.callback_query(F.data.startswith("page:"))
async def page_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle pagination callbacks."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in page_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in page_cb")
        return
    
    await callback.answer()
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return
    
    back_cb = parts[1]
    try:
        page = int(parts[2])
    except ValueError:
        return
    
    data = await state.get_data()
    
    # Get models from state
    models = data.get("category_models")
    if not models:
        # Fallback: try to get from category
        if back_cb.startswith("cat:"):
            category = back_cb.split(":", 1)[1]
            grouped = _models_by_category()
            models = grouped.get(category, [])
    
    if not models:
        await callback.answer("⚠️ Модели не найдены", show_alert=True)
        return
    
    await callback.message.edit_reply_markup(
        reply_markup=_model_keyboard(models, back_cb, page=page)
    )


@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery) -> None:
    """No-op callback for pagination display."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in noop_cb")
        return
    
    await callback.answer()


@router.callback_query(F.data.startswith("model:"))
async def model_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in model_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in model_cb")
        return
    
    await callback.answer()
    model_id = callback.data.split(":", 1)[1]
    model = next((m for m in _get_models_list() if m.get("model_id") == model_id), None)
    if not model:
        logger.error(f"[FLOW] Model not found: {model_id}")
        return
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.", reply_markup=_category_keyboard())
        return

    data = await state.get_data()
    back_cb = "menu:generate"
    category = data.get("category")
    if category:
        back_cb = f"cat:{category}"

    await state.update_data(model_id=model_id)
    await callback.message.edit_text(
        _model_detail_text(model),
        reply_markup=_model_detail_keyboard(model_id, back_cb),
    )


@router.callback_query(F.data.startswith("gen:"))
async def generate_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in generate_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in generate_cb")
        return
    
    await callback.answer()
    model_id = callback.data.split(":", 1)[1]
    
    # SPECIAL HANDLING: z-image uses dedicated flow (zimage:start)
    # User already selected the model, so skip model selection step and go directly to prompt
    if model_id.lower() in ("z-image", "zimage", "z_image"):
        from bot.handlers.z_image import ZImageStates
        from app.ux.copy_ru import t
        
        await state.set_state(ZImageStates.waiting_prompt)
        
        await callback.message.edit_text(
            f"{t('step_prompt_title', current=1, total=3)}\n\n"
            f"{t('step_prompt_explanation')}\n\n"
            f"{t('step_prompt_examples')}\n\n"
            f"<b>Ограничения:</b> {t('step_prompt_limits', max=500)}\n\n"
            f"<i>{t('step_prompt_next')}</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t('button_back'), callback_data="main_menu")]
            ])
        )
        return
    
    model = next((m for m in _get_models_list() if m.get("model_id") == model_id), None)
    if not model:
        logger.error(f"[FLOW] Model not found: {model_id}")
        return
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.", reply_markup=_category_keyboard())
        return

    input_schema = model.get("input_schema", {})
    
    # CRITICAL FIX: System fields are added automatically, should NOT be requested from user
    SYSTEM_FIELDS = {'model', 'callBackUrl', 'callback', 'callback_url', 'webhookUrl', 'webhook_url'}
    
    # CRITICAL FIX: First, remove system fields from top-level input_schema to prevent them from being included
    # This handles cases where model/callBackUrl are at the top level
    input_schema_clean = {k: v for k, v in input_schema.items() if k not in SYSTEM_FIELDS}
    
    # CRITICAL FIX: Handle input_schema structure {model: {...}, callBackUrl: {...}, input: {type: dict, examples: [...]}}
    # Extract actual user fields from 'input' field if it exists
    if 'input' in input_schema_clean and isinstance(input_schema_clean['input'], dict):
        input_field_spec = input_schema_clean['input']
        
        # ВАРИАНТ 1: input имеет properties (вложенная schema)
        if 'properties' in input_field_spec:
            properties = input_field_spec.get('properties', {})
            required_fields = input_field_spec.get('required', [])
            optional_fields = [k for k in properties.keys() if k not in required_fields]
        # ВАРИАНТ 2: input имеет examples (описание поля) - большинство моделей
        elif 'examples' in input_field_spec and isinstance(input_field_spec['examples'], list):
            examples = input_field_spec['examples']
            if examples and isinstance(examples[0], dict):
                # Первый example показывает какие поля должны быть в user_inputs
                example_structure = examples[0]
                properties = {}
                for field_name, field_value in example_structure.items():
                    # Определяем тип по значению
                    if isinstance(field_value, str):
                        field_type = 'string'
                    elif isinstance(field_value, (int, float)):
                        field_type = 'number'
                    elif isinstance(field_value, bool):
                        field_type = 'boolean'
                    elif isinstance(field_value, dict):
                        field_type = 'object'
                    elif isinstance(field_value, list):
                        field_type = 'array'
                    else:
                        field_type = 'string'
                    
                    # Поле required если присутствует во всех примерах
                    required = all(field_name in ex for ex in examples if isinstance(ex, dict))
                    
                    properties[field_name] = {
                        'type': field_type,
                        'required': required
                    }
                
                # CRITICAL FIX: For image-to-image/video models, image_url/video_url are ALWAYS required
                # even if not in all examples (they're the core input)
                # Use same logic as _models_by_io_type() to determine IO type
                model_category = model.get("category", "").lower()
                model_id_lower = model_id.lower()
                
                # Check what inputs are required/available (same logic as _models_by_io_type)
                # Include video_urls for image-to-video models
                has_image_input = any(
                    key in properties 
                    for key in ["input_url", "input_urls", "image_url", "image", "input_image", "base_image", "image_urls", "video_urls"]
                )
                is_video = model_category == "video" or "video" in model_id_lower
                is_editor = any(
                    keyword in model_id_lower 
                    for keyword in ["upscale", "enhance", "edit", "restore", "remove", "replace", "reframe"]
                ) or model_category == "enhance"
                
                # Determine IO type (same logic as _models_by_io_type)
                is_image_to_image = has_image_input and not is_video and not is_editor
                is_image_to_video = is_video and has_image_input
                is_image_editor = is_editor or (has_image_input and any(kw in model_id_lower for kw in ["reframe", "edit"]))
                
                # Force image_url/video_url as required for these models
                if is_image_to_image or is_image_editor:
                    if 'image_url' in properties:
                        properties['image_url']['required'] = True
                    elif 'input_url' in properties:
                        properties['input_url']['required'] = True
                    elif 'input_urls' in properties:
                        properties['input_urls']['required'] = True
                
                if is_image_to_video:
                    # For image-to-video, prioritize video_urls, then input_urls, then video_url, then input_url
                    if 'video_urls' in properties:
                        properties['video_urls']['required'] = True
                    elif 'input_urls' in properties:
                        properties['input_urls']['required'] = True
                    elif 'video_url' in properties:
                        properties['video_url']['required'] = True
                    elif 'input_url' in properties:
                        properties['input_url']['required'] = True
                
                required_fields = [k for k, v in properties.items() if v.get('required', False)]
                optional_fields = [k for k in properties.keys() if k not in required_fields]
                
                # CRITICAL: Add detailed logging to debug field extraction
                logger.info(f"[FIELD_EXTRACTION] Model: {model_id} | Category: {model_category}")
                logger.info(f"[FIELD_EXTRACTION] Has image input: {has_image_input} | Is video: {is_video} | Is editor: {is_editor}")
                logger.info(f"[FIELD_EXTRACTION] IO Type: I2I={is_image_to_image} | I2V={is_image_to_video} | Editor={is_image_editor}")
                logger.info(f"[FIELD_EXTRACTION] Extracted from examples: {list(properties.keys())}")
                logger.info(f"[FIELD_EXTRACTION] Required fields (before filter): {required_fields}")
                logger.info(f"[FIELD_EXTRACTION] Properties with required flags: {[(k, v.get('required', False)) for k, v in properties.items()]}")
            else:
                # Fallback: use flat format (but use cleaned schema)
                properties = input_schema_clean
                required_fields = [k for k, v in properties.items() if isinstance(v, dict) and v.get('required', False)]
                optional_fields = [k for k in properties.keys() if k not in required_fields]
        else:
            # Fallback: use flat format (but use cleaned schema)
            properties = input_schema_clean
            required_fields = [k for k, v in properties.items() if isinstance(v, dict) and v.get('required', False)]
            optional_fields = [k for k in properties.keys() if k not in required_fields]
    # Support BOTH flat and nested formats (like builder.py)
    elif 'properties' in input_schema_clean:
        # Nested format (but use cleaned schema)
        required_fields = input_schema_clean.get("required", [])
        optional_fields = input_schema_clean.get("optional", [])
        properties = input_schema_clean.get("properties", {})
    else:
        # Flat format (source_of_truth.json) - convert (but use cleaned schema)
        properties = input_schema_clean
        required_fields = [k for k, v in properties.items() if isinstance(v, dict) and v.get('required', False)]
        optional_fields = [k for k in properties.keys() if k not in required_fields]
    
    # CRITICAL FIX: Filter out system fields - model is already selected, don't ask user for it
    required_fields_before = required_fields.copy() if isinstance(required_fields, list) else []
    required_fields = [f for f in required_fields if f not in SYSTEM_FIELDS]
    optional_fields = [f for f in optional_fields if f not in SYSTEM_FIELDS]
    properties = {k: v for k, v in properties.items() if k not in SYSTEM_FIELDS}
    
    # CRITICAL: Log filtering to ensure model field is removed
    if 'model' in required_fields_before:
        logger.error(f"[FIELD_EXTRACTION] ERROR: 'model' was in required_fields! This should never happen. Model: {model_id}")
        logger.error(f"[FIELD_EXTRACTION] Required fields before filter: {required_fields_before}")
        logger.error(f"[FIELD_EXTRACTION] SYSTEM_FIELDS: {SYSTEM_FIELDS}")
    if 'model' in required_fields:
        logger.error(f"[FIELD_EXTRACTION] CRITICAL ERROR: 'model' still in required_fields after filter! Model: {model_id}")
        # Force remove it
        required_fields = [f for f in required_fields if f != 'model']
    logger.info(f"[FIELD_EXTRACTION] Required fields (after SYSTEM_FIELDS filter): {required_fields}")
    
    # CRITICAL UX FIX: Sort required fields by priority - files first, then text
    # Priority order: image_url/video_url → prompt/text → other fields
    FILE_FIELDS = ['image_url', 'video_url', 'audio_url', 'input_url', 'input_urls', 'input_image', 'base_image', 
                   'image', 'video', 'audio', 'file', 'file_id', 'file_url', 'mask_url', 
                   'reference_image_urls', 'image_urls', 'video_urls']
    TEXT_FIELDS = ['prompt', 'text', 'input', 'message', 'negative_prompt']
    
    def _field_priority(field_name: str) -> int:
        """Return priority for field sorting: 0=files, 1=text, 2=other"""
        if field_name in FILE_FIELDS:
            return 0  # Files first
        elif field_name in TEXT_FIELDS:
            return 1  # Text second
        else:
            return 2  # Other fields last
    
    # Sort required fields by priority
    required_fields_before_sort = required_fields.copy()
    required_fields = sorted(required_fields, key=_field_priority)
    
    # CRITICAL: Log sorting result
    logger.info(f"[FIELD_EXTRACTION] Required fields (before sort): {required_fields_before_sort}")
    logger.info(f"[FIELD_EXTRACTION] Required fields (after sort): {required_fields}")
    logger.info(f"[FIELD_EXTRACTION] First field to request: {required_fields[0] if required_fields else 'NONE'}")
    
    # CRITICAL FIX: Model is already selected, add it to collected inputs automatically
    collected = {'model': model_id}
    
    ctx = InputContext(
        model_id=model_id,
        required_fields=required_fields,
        optional_fields=optional_fields,
        properties=properties,
        collected=collected,
        collecting_optional=False
    )
    await state.update_data(flow_ctx=ctx.__dict__)

    if not required_fields:
        await _show_confirmation(callback.message, state, model)
        return

    # CRITICAL SAFETY CHECK: Ensure first field is not a system field
    field_name = required_fields[0]
    if field_name in SYSTEM_FIELDS:
        logger.error(f"[FIELD_EXTRACTION] CRITICAL: First field '{field_name}' is a SYSTEM_FIELD! This should never happen. Model: {model_id}")
        logger.error(f"[FIELD_EXTRACTION] Required fields: {required_fields}")
        logger.error(f"[FIELD_EXTRACTION] SYSTEM_FIELDS: {SYSTEM_FIELDS}")
        # Remove all system fields and try again
        required_fields = [f for f in required_fields if f not in SYSTEM_FIELDS]
        if not required_fields:
            await callback.message.edit_text(
                "⚠️ Ошибка: не удалось определить параметры модели.\n\nПопробуйте выбрать другую модель.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
                ])
            )
            await state.clear()
            return
        field_name = required_fields[0]
    
    field_spec = properties.get(field_name, {})
    
    # Calculate step numbers
    total_steps = len(required_fields) + (1 if optional_fields else 0) + 1
    step_current = 1
    
    await state.set_state(InputFlow.waiting_input)
    
    # Build keyboard: enum buttons (if any) + navigation buttons
    # BATCH 44: Pass field_name for Russian enum values
    keyboard = _enum_keyboard(field_name, field_spec)
    nav_keyboard = _input_navigation_keyboard(back_callback="main_menu")
    
    # Merge keyboards if enum exists
    if keyboard:
        # Add navigation buttons to enum keyboard
        nav_buttons = nav_keyboard.inline_keyboard[0]
        keyboard.inline_keyboard.append(nav_buttons)
    else:
        keyboard = nav_keyboard
    
    await callback.message.answer(
        _field_prompt(field_name, field_spec, step_current=step_current, step_total=total_steps),
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("enum:"), InputFlow.waiting_input)
async def enum_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in enum_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in enum_cb")
        return
    
    await callback.answer()
    value = callback.data.split(":", 1)[1]
    await _save_input_and_continue(callback.message, state, value)


@router.callback_query(F.data == "opt_skip_all")
async def opt_skip_all_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip all optional parameters and proceed to confirmation (MASTER PROMPT)."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in opt_skip_all_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in opt_skip_all_cb")
        return
    
    await callback.answer("Используем значения по умолчанию")
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
    await _show_confirmation(callback.message, state, model)


@router.callback_query(F.data.startswith("opt_start:"))
async def opt_start_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Start collecting a specific optional parameter (MASTER PROMPT compliance)."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in opt_start_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in opt_start_cb")
        return
    
    await callback.answer()
    field_name = callback.data.split(":", 1)[1]
    
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    # Find index of this optional field
    try:
        opt_index = flow_ctx.optional_fields.index(field_name)
    except ValueError:
        await callback.message.answer("⚠️ Параметр не найден.")
        return
    
    # Switch to collecting optional params
    flow_ctx.collecting_optional = True
    flow_ctx.index = opt_index
    await state.update_data(flow_ctx=flow_ctx.__dict__)
    
    # Show input prompt
    field_spec = flow_ctx.properties.get(field_name, {})
    await state.set_state(InputFlow.waiting_input)
    
    # Build keyboard: enum buttons (if any) + navigation buttons
    # BATCH 44: Pass field_name for Russian enum values
    keyboard = _enum_keyboard(field_name, field_spec)
    nav_keyboard = _input_navigation_keyboard(back_callback="opt_skip_all")
    
    # Merge keyboards if enum exists
    if keyboard:
        # Add navigation buttons to enum keyboard
        nav_buttons = nav_keyboard.inline_keyboard[0]
        keyboard.inline_keyboard.append(nav_buttons)
    else:
        keyboard = nav_keyboard
    
    await callback.message.answer(
        _field_prompt(field_name, field_spec),
        reply_markup=keyboard,
    )


@router.message(InputFlow.waiting_input)
async def input_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    # Determine which field we're collecting
    if flow_ctx.collecting_optional:
        current_fields = flow_ctx.optional_fields
    else:
        current_fields = flow_ctx.required_fields
    
    field_name = current_fields[flow_ctx.index]
    field_spec = flow_ctx.properties.get(field_name, {})
    field_type = field_spec.get("type", "string")
    
    # CRITICAL UX FIX: image_url and video_url can accept both files and URLs
    # Check if this is an image/video URL field that should accept files
    is_image_url_field = field_name in ["image_url", "image", "input_image", "base_image", "image_urls", "input_url", "mask_url", "reference_image_urls"]
    is_video_url_field = field_name in ["video_url", "video", "input_video"]
    is_file_field = field_type in {"file", "file_id", "file_url"} or is_image_url_field or is_video_url_field

    if is_file_field:
        file_id = None
        file_size = None
        
        # CRITICAL: Check file size limits to prevent DoS
        from app.utils.validation import MAX_IMAGE_SIZE, MAX_VIDEO_SIZE, MAX_AUDIO_SIZE
        
        if message.photo:
            file_id = message.photo[-1].file_id
            file_size = message.photo[-1].file_size
            if file_size and file_size > MAX_IMAGE_SIZE:
                from app.ux.copy_ru import t
                await message.answer(
                    f"{t('error_validation_title')}\n\n"
                    f"<b>Что произошло:</b> Файл слишком большой\n\n"
                    f"<b>Детали:</b> Размер файла {file_size / 1024 / 1024:.1f} МБ, "
                    f"максимально допустимый размер: {MAX_IMAGE_SIZE / 1024 / 1024} МБ\n\n"
                    f"<b>Как исправить:</b>\n"
                    f"• Сожмите изображение (используйте онлайн-компрессор)\n"
                    f"• Уменьшите разрешение изображения\n"
                    f"• Выберите другое изображение меньшего размера\n\n"
                    f"💡 <b>Совет:</b> Для изображений рекомендуется размер до 5 МБ\n\n"
                    f"{t('error_validation_next')}",
                    reply_markup=_input_navigation_keyboard(back_callback="main_menu")
                )
                return
        elif message.document:
            file_id = message.document.file_id
            file_size = message.document.file_size
            file_name = getattr(message.document, 'file_name', '') or ''
            
            # CRITICAL: Validate file extension to prevent malicious file types
            from app.utils.validation import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_VIDEO_EXTENSIONS, ALLOWED_AUDIO_EXTENSIONS
            import os
            if file_name:
                ext = os.path.splitext(file_name)[1].lower()
                allowed_extensions = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS
                if ext and ext not in allowed_extensions:
                    from app.ux.copy_ru import t
                    await message.answer(
                        f"{t('error_validation_title')}\n\n"
                        f"<b>Что произошло:</b> Неподдерживаемый тип файла\n\n"
                        f"<b>Детали:</b> Файл с расширением {ext} не поддерживается\n\n"
                        f"<b>Как исправить:</b> Отправьте файл одного из поддерживаемых форматов:\n\n"
                        f"📷 <b>Изображения:</b> {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}\n"
                        f"🎬 <b>Видео:</b> {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}\n"
                        f"🎵 <b>Аудио:</b> {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}\n\n"
                        f"💡 <b>Совет:</b> Если файл в другом формате, конвертируйте его в один из поддерживаемых\n\n"
                        f"{t('error_validation_next')}",
                        reply_markup=_input_navigation_keyboard(back_callback="main_menu")
                    )
                    return
            
            # Check based on mime type if available
            mime_type = getattr(message.document, 'mime_type', '') or ''
            max_size = MAX_VIDEO_SIZE if 'video' in mime_type else (MAX_AUDIO_SIZE if 'audio' in mime_type else MAX_IMAGE_SIZE)
            if file_size and file_size > max_size:
                from app.ux.copy_ru import t
                file_type_name = "видео" if 'video' in mime_type else ("аудио" if 'audio' in mime_type else "файл")
                await message.answer(
                    f"{t('error_validation_title')}\n\n"
                    f"<b>Что произошло:</b> {file_type_name.capitalize()} слишком большое\n\n"
                    f"<b>Детали:</b> Размер файла {file_size / 1024 / 1024:.1f} МБ, "
                    f"максимально допустимый размер: {max_size / 1024 / 1024} МБ\n\n"
                    f"<b>Как исправить:</b>\n"
                    f"• Сожмите {file_type_name} (используйте онлайн-компрессор)\n"
                    f"• Уменьшите качество или разрешение\n"
                    f"• Выберите другой файл меньшего размера\n\n"
                    f"💡 <b>Совет:</b> Для {file_type_name} рекомендуется размер до {max_size / 1024 / 1024} МБ\n\n"
                    f"{t('error_validation_next')}",
                    reply_markup=_input_navigation_keyboard(back_callback="main_menu")
                )
                return
        elif message.video:
            file_id = message.video.file_id
            file_size = message.video.file_size
            if file_size and file_size > MAX_VIDEO_SIZE:
                from app.ux.copy_ru import t
                await message.answer(
                    f"{t('error_validation_title')}\n\n"
                    f"<b>Что произошло:</b> Видео слишком большое\n\n"
                    f"<b>Детали:</b> Размер видео {file_size / 1024 / 1024:.1f} МБ, "
                    f"максимально допустимый размер: {MAX_VIDEO_SIZE / 1024 / 1024} МБ\n\n"
                    f"<b>Как исправить:</b>\n"
                    f"• Сожмите видео (используйте онлайн-компрессор)\n"
                    f"• Уменьшите разрешение или качество видео\n"
                    f"• Выберите другое видео меньшего размера\n\n"
                    f"💡 <b>Совет:</b> Для видео рекомендуется размер до {MAX_VIDEO_SIZE / 1024 / 1024} МБ\n\n"
                    f"{t('error_validation_next')}",
                    reply_markup=_input_navigation_keyboard(back_callback="main_menu")
                )
                return
        elif message.audio:
            file_id = message.audio.file_id
            file_size = message.audio.file_size
            if file_size and file_size > MAX_AUDIO_SIZE:
                from app.ux.copy_ru import t
                await message.answer(
                    f"{t('error_validation_title')}\n\n"
                    f"<b>Что произошло:</b> Аудио слишком большое\n\n"
                    f"<b>Детали:</b> Размер аудио {file_size / 1024 / 1024:.1f} МБ, "
                    f"максимально допустимый размер: {MAX_AUDIO_SIZE / 1024 / 1024} МБ\n\n"
                    f"<b>Как исправить:</b>\n"
                    f"• Сожмите аудио (используйте онлайн-компрессор)\n"
                    f"• Уменьшите битрейт или качество аудио\n"
                    f"• Выберите другой аудиофайл меньшего размера\n\n"
                    f"💡 <b>Совет:</b> Для аудио рекомендуется размер до {MAX_AUDIO_SIZE / 1024 / 1024} МБ\n\n"
                    f"{t('error_validation_next')}",
                    reply_markup=_input_navigation_keyboard(back_callback="main_menu")
                )
                return
        if not file_id and message.text and message.text.startswith(("http://", "https://")):
            # Validate URL before accepting
            is_valid, error = validate_url(message.text)
            if not is_valid:
                from app.ux.copy_ru import t
                await message.answer(
                    f"{t('error_validation_title')}\n\n"
                    f"<b>Что произошло:</b> Некорректная ссылка\n\n"
                    f"<b>Детали:</b> {error}\n\n"
                    f"<b>Как исправить:</b>\n"
                    f"• Убедитесь, что ссылка начинается с http:// или https://\n"
                    f"• Проверьте, что ссылка полная (с доменом)\n"
                    f"• Убедитесь, что файл доступен по ссылке\n\n"
                    f"💡 <b>Пример правильной ссылки:</b> https://example.com/image.jpg\n\n"
                    f"{t('error_validation_next')}",
                    reply_markup=_input_navigation_keyboard(back_callback="main_menu")
                )
                return
            
            # Additional validation for file URLs
            is_valid, error = validate_file_url(message.text, file_type="image")
            if not is_valid:
                from app.ux.copy_ru import t
                await message.answer(
                    f"{t('error_validation_title')}\n\n"
                    f"<b>Что произошло:</b> Проблема с ссылкой на файл\n\n"
                    f"<b>Детали:</b> {error}\n\n"
                    f"<b>Как исправить:</b>\n"
                    f"• Убедитесь, что ссылка ведёт на доступный файл\n"
                    f"• Проверьте, что файл доступен без авторизации\n"
                    f"• Убедитесь, что файл в поддерживаемом формате (JPG, PNG, WEBP для изображений)\n\n"
                    f"💡 <b>Совет:</b> Лучше загрузить файл прямо в чат, чем использовать ссылку\n\n"
                    f"{t('error_validation_next')}",
                    reply_markup=_input_navigation_keyboard(back_callback="main_menu")
                )
                return
            
            await _save_input_and_continue(message, state, message.text)
            return
        if not file_id:
            from app.ux.copy_ru import t
            await message.answer(
                f"{t('error_validation_title')}\n\n"
                f"<b>Что произошло:</b> Ожидается файл (изображение, видео или аудио), но получено что-то другое.\n\n"
                f"<b>Как исправить:</b> Отправьте файл прямо в чат:\n"
                f"• Фото (JPG, PNG, WEBP)\n"
                f"• Видео (MP4, MOV)\n"
                f"• Аудио (MP3, WAV)\n\n"
                f"💡 <b>Совет:</b> Можно отправить файл как документ или медиа\n\n"
                f"{t('error_validation_next')}",
                reply_markup=_input_navigation_keyboard(back_callback="main_menu")
            )
            return
        
        # CRITICAL FIX: Convert Telegram file_id to downloadable URL for image_url/video_url fields
        # KIE API requires URLs, not Telegram file_ids
        if is_image_url_field or is_video_url_field:
            try:
                # Get file info from Telegram
                tg_file = await message.bot.get_file(file_id)
                # Build downloadable URL
                bot_token = message.bot.token
                file_url = f"https://api.telegram.org/file/bot{bot_token}/{tg_file.file_path}"
                logger.info(f"[FILE_CONVERSION] Converted file_id={file_id[:20]}... to URL={file_url[:60]}... for field={field_name}")
                await _save_input_and_continue(message, state, file_url)
            except Exception as e:
                logger.error(f"[FILE_CONVERSION] Failed to convert file_id to URL: {e}", exc_info=True)
                from app.ux.copy_ru import t
                await message.answer(
                    f"{t('error_validation_title')}\n\n"
                    f"<b>Что произошло:</b> Ошибка при обработке файла\n\n"
                    f"<b>Детали:</b> Не удалось получить доступ к файлу\n\n"
                    f"<b>Как исправить:</b>\n"
                    f"• Попробуйте отправить файл ещё раз\n"
                    f"• Или отправьте прямую ссылку на файл (URL)\n\n"
                    f"💡 <b>Пример URL:</b> https://example.com/image.jpg\n\n"
                    f"{t('error_validation_next')}",
                    reply_markup=_input_navigation_keyboard(back_callback="main_menu")
                )
            return
        else:
            # For non-URL fields, save file_id as-is (might be used elsewhere)
            await _save_input_and_continue(message, state, file_id)
        return

    if field_type in {"url", "link", "source_url"}:
        if not message.text:
            from app.ux.copy_ru import t
            await message.answer(
                f"{t('error_validation_title')}\n\n"
                f"<b>Что произошло:</b> Ожидается ссылка (URL), но получено что-то другое.\n\n"
                f"<b>Как исправить:</b> Отправьте ссылку в текстовом виде:\n"
                f"• Ссылка должна начинаться с http:// или https://\n"
                f"• Пример: https://example.com/image.jpg\n\n"
                f"💡 <b>Совет:</b> Скопируйте ссылку из браузера и вставьте в чат\n\n"
                f"{t('error_validation_next')}",
                reply_markup=_input_navigation_keyboard(back_callback="main_menu")
            )
            return
        
        # Validate URL
        is_valid, error = validate_url(message.text)
        if not is_valid:
            from app.ux.copy_ru import t
            await message.answer(
                f"{t('error_validation_title')}\n\n"
                f"<b>Что произошло:</b> Некорректная ссылка\n\n"
                f"<b>Детали:</b> {error}\n\n"
                f"<b>Как исправить:</b>\n"
                f"• Убедитесь, что ссылка начинается с http:// или https://\n"
                f"• Проверьте, что ссылка полная (с доменом)\n"
                f"• Убедитесь, что файл доступен по ссылке\n\n"
                f"💡 <b>Пример правильной ссылки:</b> https://example.com/image.jpg\n\n"
                f"{t('error_validation_next')}",
                reply_markup=_input_navigation_keyboard(back_callback="main_menu")
            )
            return
        
        await _save_input_and_continue(message, state, message.text)
        return

    value = message.text
    if value is None:
        from app.ux.copy_ru import t
        await message.answer(
            f"{t('error_validation_title')}\n\n"
            f"<b>Что произошло:</b> Ожидается текстовое значение, но получено что-то другое.\n\n"
            f"<b>Как исправить:</b> Отправьте текст (не файл, не стикер, не голосовое сообщение).\n\n"
            f"{t('error_validation_next')}",
            reply_markup=_input_navigation_keyboard(back_callback="main_menu")
        )
        return
    
    # Validate text input length
    is_valid, error = validate_text_input(value, max_length=10000)
    if not is_valid:
        from app.ux.copy_ru import t
        await message.answer(
            f"{t('error_validation_title')}\n\n"
            f"{t('error_validation_what')}"
            f"<b>Детали:</b> {error}\n\n"
            f"{t('error_validation_how_to_fix')}"
            f"{t('error_validation_next')}",
            reply_markup=_input_navigation_keyboard(back_callback="main_menu")
        )
        return
    
    await _save_input_and_continue(message, state, value)


async def _ask_optional_params(message: Message, state: FSMContext, flow_ctx: InputContext) -> None:
    """Ask user if they want to configure optional parameters (MASTER PROMPT compliance)."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Build keyboard with all optional params (mark configured ones with ✓)
    buttons = []
    for opt_field in flow_ctx.optional_fields:
        field_spec = flow_ctx.properties.get(opt_field, {})
        default = field_spec.get("default")
        
        # Check if already configured
        is_configured = opt_field in flow_ctx.collected
        
        # Human-readable field name
        field_display = field_spec.get("title") or opt_field.replace("_", " ").title()
        
        if is_configured:
            button_text = f"✓ {field_display}: {flow_ctx.collected[opt_field]}"
        else:
            button_text = f"○ {field_display}"
            if default is not None:
                button_text += f" (по умолчанию: {default})"
        
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"opt_start:{opt_field}")])
    
    # Add "Finish" or "Skip all" button
    any_configured = any(opt in flow_ctx.collected for opt in flow_ctx.optional_fields)
    if any_configured:
        buttons.append([InlineKeyboardButton(text="✅ Готово, перейти к подтверждению", callback_data="opt_skip_all")])
    else:
        buttons.append([InlineKeyboardButton(text="⏭ Пропустить все (использовать значения по умолчанию)", callback_data="opt_skip_all")])
    
    # Add navigation buttons
    from app.ux.copy_ru import t
    buttons.append([
        InlineKeyboardButton(text=t('button_back'), callback_data="main_menu"),
        InlineKeyboardButton(text=t('button_cancel'), callback_data="main_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Show status of parameters
    configured_count = sum(1 for opt in flow_ctx.optional_fields if opt in flow_ctx.collected)
    total_count = len(flow_ctx.optional_fields)
    
    await message.answer(
        f"🎛 <b>Дополнительные параметры</b> ({configured_count}/{total_count} настроено)\n\n"
        f"<b>Что это:</b> Эти параметры необязательны, но могут улучшить результат генерации.\n\n"
        f"<b>Обозначения:</b>\n"
        f"✓ = параметр настроен (ваше значение)\n"
        f"○ = используется значение по умолчанию\n\n"
        f"💡 <b>Совет:</b> Можете настроить любой параметр или пропустить все и использовать значения по умолчанию\n\n"
        f"Выберите параметр для настройки:",
        reply_markup=keyboard
    )


async def _save_input_and_continue(message: Message, state: FSMContext, value: Any) -> None:
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    # Determine which field list we're working on
    if flow_ctx.collecting_optional:
        current_fields = flow_ctx.optional_fields
    else:
        current_fields = flow_ctx.required_fields
    
    field_name = current_fields[flow_ctx.index]
    field_spec = flow_ctx.properties.get(field_name, {})
    value = _coerce_value(value, field_spec)

    try:
        _validate_field_value(value, field_spec, field_name)
    except ModelContractError as e:
        from app.ux.copy_ru import t
        error_msg = (
            f"{t('error_validation_title')}\n\n"
            f"{t('error_validation_what')}"
            f"<b>Детали:</b> {str(e)}\n\n"
            f"{t('error_validation_how_to_fix')}"
            f"{t('error_validation_next')}"
        )
        await message.answer(
            error_msg,
            reply_markup=_input_navigation_keyboard(back_callback="main_menu")
        )
        return

    flow_ctx.collected[field_name] = value
    
    # CRITICAL UX FIX: If collecting optional, RETURN to optional menu after each param
    # This allows flexible configuration of ANY optional params
    if flow_ctx.collecting_optional:
        # Reset to allow selecting another optional param
        flow_ctx.index = 0
        flow_ctx.collecting_optional = False
        await state.update_data(flow_ctx=flow_ctx.__dict__)
        await _ask_optional_params(message, state, flow_ctx)
        return
    
    # For required fields, continue sequentially
    flow_ctx.index += 1
    await state.update_data(flow_ctx=flow_ctx.__dict__)

    # Check if we finished required fields
    if flow_ctx.index >= len(current_fields):
        # If we finished required and have optional fields, offer to configure them
        if flow_ctx.optional_fields:
            await _ask_optional_params(message, state, flow_ctx)
            return
        
        # Otherwise, show confirmation
        model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
        await _show_confirmation(message, state, model)
        return

    # Continue to next required field
    next_field = current_fields[flow_ctx.index]
    next_spec = flow_ctx.properties.get(next_field, {})
    
    # Calculate step numbers
    total_steps = len(flow_ctx.required_fields) + (1 if flow_ctx.optional_fields else 0) + 1
    step_current = flow_ctx.index + 1
    
    await message.answer(
        _field_prompt(next_field, next_spec, step_current=step_current, step_total=total_steps),
        reply_markup=_enum_keyboard(next_field, next_spec),  # BATCH 44: Pass field_name
    )


async def _show_confirmation(message: Message, state: FSMContext, model: Optional[Dict[str, Any]]) -> None:
    """Show canonical confirmation screen (master input style)."""
    from app.ux.copy_ru import t
    
    if not model:
        await message.answer("⚠️ Модель не найдена.")
        return
    
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    model_name = model.get("name") or model.get("model_id")
    
    # Count total steps (required + optional + confirmation)
    total_steps = len(flow_ctx.required_fields) + (1 if flow_ctx.optional_fields else 0) + 1
    current_step = total_steps  # Confirmation is last step
    
    # Price formatting - CORRECT FORMULA: price_usd × 78 (USD→RUB) × 2 (markup)
    price_usd = model.get("price") or 0
    try:
        if price_usd == 0:
            price_str = "Бесплатно"
        else:
            # Step 1: Convert USD to RUB (using calculate_kie_cost)
            kie_cost_rub = calculate_kie_cost(model, {}, None)
            # Step 2: Apply 2x markup for user price
            user_price_rub = calculate_user_price(kie_cost_rub)
            price_str = format_price_rub(user_price_rub)
    except (TypeError, ValueError):
        price_str = "Цена не определена"
    
    # ETA
    eta = model.get("eta")
    if eta:
        eta_str = f"~{eta} сек"
    else:
        category = model.get("category", "")
        if "video" in category:
            eta_str = "~30-60 сек"
        elif "upscale" in category:
            eta_str = "~15-30 сек"
        else:
            eta_str = "~10-20 сек"
    
    # What user will get
    output_type = model.get("output_type", "url")
    if output_type == "url":
        result_desc = "Ссылка на результат"
    elif "video" in str(model.get("category", "")):
        result_desc = "Видеофайл"
    elif "image" in str(model.get("category", "")):
        result_desc = "Изображение"
    else:
        result_desc = "Файл результата"
    
    # Format parameters - show ALL (required + optional) with defaults for missing optional
    # MASTER PROMPT: "Ввод ВСЕХ параметров (без автоподстановок)"
    params_lines = []
    
    # Show collected parameters
    for k, v in flow_ctx.collected.items():
        # Truncate long values
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        params_lines.append(f"✓ {k}: {v_str}")
    
    # Show optional parameters that weren't collected (with defaults)
    for opt_field in flow_ctx.optional_fields:
        if opt_field not in flow_ctx.collected:
            field_spec = flow_ctx.properties.get(opt_field, {})
            default = field_spec.get("default", "auto")
            params_lines.append(f"○ {opt_field}: {default} (default)")
    
    if params_lines:
        params_str = "\n".join(params_lines)
    else:
        params_str = "Параметры по умолчанию"
    
    # P0 FIX #12: get_user_balance is async - need await
    balance = await get_charge_manager().get_user_balance(message.from_user.id)
    
    # Extract prompt for summary (if exists)
    prompt = flow_ctx.collected.get("prompt", flow_ctx.collected.get("text", ""))
    if len(prompt) > 100:
        prompt = prompt[:97] + "..."
    
    # Extract ratio/format (if exists)
    ratio = flow_ctx.collected.get("aspect_ratio", flow_ctx.collected.get("ratio", "auto"))
    
    await state.set_state(InputFlow.confirm)
    await message.answer(
        f"{t('step_confirm_title', current=current_step, total=total_steps)}\n\n"
        f"{t('step_confirm_summary', prompt=prompt or 'N/A', ratio=ratio, model=model_name)}\n\n"
        f"💰 <b>Стоимость:</b> {price_str}\n"
        f"⏱ <b>Ожидание:</b> {eta_str}\n"
        f"💳 <b>Баланс:</b> {format_price_rub(balance)}\n\n"
        f"<i>{t('step_confirm_hint')}</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t('button_confirm'), callback_data="confirm")],
                [
                    InlineKeyboardButton(text=t('button_edit_prompt'), callback_data="edit_prompt"),
                    InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")  # BATCH 43
                ],
                [InlineKeyboardButton(text=t('button_back'), callback_data="back_to_input")],
            ]
        ),
    )


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    """Universal cancel command - clears any FSM state."""
    # CRITICAL: None checks
    if not message.from_user:
        logger.error("[FLOW] message.from_user is None in cancel_cmd")
        await message.answer("❌ Ошибка: не удалось определить пользователя. Попробуйте позже.")
        return
    
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "❌ Операция отменена. Возврат в главное меню.",
            reply_markup=_main_menu_keyboard()
        )
        logger.info(f"[CANCEL] User {message.from_user.id} cancelled from state {current_state}")
    else:
        await message.answer(
            "ℹ️ Вы не находитесь в процессе операции.",
            reply_markup=_main_menu_keyboard()
        )


@router.callback_query(F.data == "settings")
async def settings_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Show advanced settings (optional parameters) - BATCH 43."""
    # P1-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in settings_cb")
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in settings_cb")
        return
    
    await callback.answer()
    
    from app.ux.smart_defaults import get_settings_summary, get_optional_fields
    
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    # Get model schema
    model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
    if not model:
        await callback.message.answer("⚠️ Модель не найдена.")
        return
    
    input_schema = model.get("input_schema") or model.get("input_params", {})
    
    # Check if model has optional parameters
    optional_fields = get_optional_fields(input_schema)
    if not optional_fields:
        await callback.answer(
            "ℹ️ Эта модель не имеет дополнительных настроек",
            show_alert=True
        )
        return
    
    # Show current settings
    from app.ux.smart_defaults import apply_smart_defaults
    complete_inputs = apply_smart_defaults(
        model_id=flow_ctx.model_id,
        user_inputs=flow_ctx.collected,
        schema=input_schema
    )
    
    settings_text = get_settings_summary(input_schema, complete_inputs)
    
    # Build keyboard with optional parameters
    keyboard_rows = []
    for field_name, default_value in optional_fields[:10]:  # Limit to 10
        field_spec = input_schema[field_name]
        from app.ux.smart_defaults import get_user_friendly_field_name
        friendly_name = get_user_friendly_field_name(field_name, field_spec)
        # Truncate long names
        if len(friendly_name) > 30:
            friendly_name = friendly_name[:27] + "..."
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"✏️ {friendly_name}",
                callback_data=f"edit_setting:{field_name}"
            )
        ])
    
    # Add back button
    keyboard_rows.append([
        InlineKeyboardButton(text="◀️ Назад к подтверждению", callback_data="back_to_confirmation")
    ])
    
    await callback.message.edit_text(
        settings_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_confirmation")
async def back_to_confirmation_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to confirmation screen - BATCH 43."""
    # CRITICAL: None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in back_to_confirmation_cb")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in back_to_confirmation_cb")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
    
    # Re-show confirmation
    await _show_confirmation(callback.message, state, model)


@router.callback_query(F.data == "cancel")
async def cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Universal cancel callback - clears any FSM state."""
    # CRITICAL: None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in cancel_cb")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in cancel_cb")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await callback.message.edit_text(
            "❌ Отменено. Возврат в меню.",
            reply_markup=_main_menu_keyboard()
        )
        logger.info(f"[CANCEL] User {callback.from_user.id} cancelled from state {current_state}")
    else:
        await callback.message.edit_text(
            "ℹ️ Вы не находитесь в процессе операции.",
            reply_markup=_main_menu_keyboard()
        )


@router.callback_query(F.data == "confirm", InputFlow.confirm)
async def confirm_cb(callback: CallbackQuery, state: FSMContext) -> None:
    # CRITICAL: None checks
    if not callback.from_user:
        logger.error("[FLOW] callback.from_user is None in confirm_cb")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[FLOW] callback.message is None in confirm_cb")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
    if not model:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
            [InlineKeyboardButton(text="📂 Выбрать модель", callback_data="menu:generate")]
        ])
        await callback.message.edit_text(
            "⚠️ Модель не найдена.\n\nПопробуйте выбрать другую модель.",
            reply_markup=keyboard
        )
        await state.clear()
        return

    price_raw = model.get("price") or 0
    try:
        amount = float(price_raw)
    except (TypeError, ValueError):
        amount = 0.0

    charge_manager = get_charge_manager()
    balance = await charge_manager.get_user_balance(callback.from_user.id)
    if amount > 0 and balance < amount:
        await callback.message.edit_text(
            "❌ Недостаточно средств для запуска.\n\n"
            f"Цена: {amount:.2f}\n"
            f"Баланс: {balance:.2f}\n\n"
            "Пополните баланс и попробуйте снова.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Баланс / Оплата", callback_data="menu:balance")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ]
            ),
        )
        await state.clear()
        return

    # Send initial progress message
    # MASTER PROMPT: "7. Прогресс / ETA" - TRANSPARENCY: show model and prompt
    # SECURITY: Escape user input to prevent XSS (MASTER PROMPT: no vulnerabilities)
    from app.utils.html import escape_html
    
    # Initial progress message with model and inputs info
    model_name = _get_models_list()
    model_display = "Unknown"
    for m in model_name:
        if m.get("model_id") == flow_ctx.model_id:
            model_display = m.get("name") or flow_ctx.model_id
            break

    # Format inputs for display - ESCAPE USER INPUT
    inputs_preview = ""
    if "prompt" in flow_ctx.collected:
        prompt_text = flow_ctx.collected["prompt"]
        if len(prompt_text) > 50:
            prompt_text = prompt_text[:50] + "..."
        # CRITICAL: Escape HTML to prevent XSS
        prompt_text_safe = escape_html(prompt_text)
        inputs_preview = f"Промпт: {prompt_text_safe}\n"

    progress_msg = await callback.message.edit_text(
        f"⏳ <b>Генерация запущена</b>\n\n"
        f"Модель: {escape_html(model_display)}\n"
        f"{inputs_preview}"
        f"Инициализация...",
        parse_mode="HTML"
    )

    # MASTER PROMPT: "7. Прогресс / ETA"
    # Update SAME message instead of creating new ones
    def heartbeat(text: str) -> None:
        asyncio.create_task(progress_msg.edit_text(text, parse_mode="HTML"))

    # BATCH 43: Apply smart defaults before generation
    from app.ux.smart_defaults import apply_smart_defaults
    
    # Get model schema
    model = next((m for m in _get_models_list() if m.get("model_id") == flow_ctx.model_id), None)
    if model:
        input_schema = model.get("input_schema") or model.get("input_params", {})
        # Apply defaults for all optional parameters
        complete_inputs = apply_smart_defaults(
            model_id=flow_ctx.model_id,
            user_inputs=flow_ctx.collected,
            schema=input_schema
        )
        logger.info(
            f"[SMART_DEFAULTS] model={flow_ctx.model_id} "
            f"user_provided={len(flow_ctx.collected)} "
            f"with_defaults={len(complete_inputs)}"
        )
    else:
        complete_inputs = flow_ctx.collected
    
    charge_task_id = f"charge_{callback.from_user.id}_{callback.message.message_id}"
    result = await generate_with_payment(
        model_id=flow_ctx.model_id,
        user_inputs=complete_inputs,  # Use complete inputs with defaults
        user_id=callback.from_user.id,
        amount=amount,
        progress_callback=heartbeat,
        task_id=charge_task_id,
        reserve_balance=True,
        chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
    )

    # CRITICAL: Clear FSM state BEFORE processing result (prevents stuck states on error)
    await state.clear()

    if result.get("success"):
        from app.ux.copy_ru import t
        import os
        
        urls = result.get("result_urls") or []
        if urls:
            await callback.message.answer("\n".join(urls))
        else:
            await callback.message.answer("✅ Готово!")
        
        # BATCH 42: Upsell after free generation (centralized copy + tracking + error boundaries)
        if result.get("show_upsell"):
            try:
                # Track upsell impression (conversion funnel)
                try:
                    from app.analytics.conversion_tracker import track_conversion_event
                    await track_conversion_event(
                        event_type='upsell_shown',
                        user_id=callback.from_user.id,
                        model_id=flow_ctx.model_id
                    )
                except Exception as tracking_error:
                    # FAIL-OPEN: Don't block UX on analytics failure
                    logger.debug(f"Failed to track upsell_shown: {tracking_error}")
                
                # Beautiful upsell for free tier users (texts from copy_ru.py)
                upsell_text = (
                    f"{t('upsell_title')}\n\n"
                    f"{t('upsell_cta')}\n\n"
                    f"{t('upsell_benefits_title')}\n"
                    f"{t('upsell_benefit_images')}\n"
                    f"{t('upsell_benefit_video')}\n"
                    f"{t('upsell_benefit_audio')}\n"
                    f"{t('upsell_benefit_speed')}\n\n"
                    f"{t('upsell_action')}\n\n"
                    f"{t('upsell_pricing')}"
                )
                await callback.message.answer(
                    upsell_text,
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text=t('upsell_button_topup'), callback_data="menu:balance")],
                            [InlineKeyboardButton(text=t('upsell_button_premium'), callback_data="menu:best")],
                            [InlineKeyboardButton(text=t('upsell_button_repeat_free'), callback_data=f"gen:{flow_ctx.model_id}")],
                            [InlineKeyboardButton(text=t('upsell_button_menu'), callback_data="main_menu")],
                        ]
                    ),
                    parse_mode="HTML"
                )
            except Exception as upsell_error:
                # ERROR BOUNDARY: If upsell fails, log and continue with simple message
                logger.error(f"Upsell display failed: {upsell_error}", exc_info=True)
                # Fallback to simple success message (don't break UX)
                await callback.message.answer(
                    f"✅ {t('generation_started')}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"gen:{flow_ctx.model_id}")],
                            [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                        ]
                    ),
                )
        else:
            # Regular success message for paid models
            await callback.message.answer(
                f"{t('generation_started')}\n\n"
                f"{t('generation_hint')}",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"gen:{flow_ctx.model_id}")],
                        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                    ]
                ),
            )
        
        # DRY_RUN notice if enabled - show beautiful preview
        dry_run = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")
        if dry_run:
            from app.providers.integration import get_preview_result_for_user
            
            job_id = result.get("task_id", "mock_job_unknown")
            model_id = flow_ctx.model_id
            prompt = flow_ctx.collected.get("prompt") or flow_ctx.collected.get("text") or flow_ctx.collected.get("description")
            
            # Get preview result from provider
            preview_data = get_preview_result_for_user(job_id, model_id, prompt)
            preview_text = preview_data.get("preview_text")
            preview_urls = preview_data.get("preview_urls", [])
            
            # Show preview text if available
            if preview_text:
                await callback.message.answer(
                    preview_text,
                    parse_mode="HTML"
                )
            
            # Show preview image/video/audio if available
            if preview_urls:
                from aiogram.types import FSInputFile, URLInputFile
                from aiogram import Bot
                
                # Determine media type from model_id
                model_lower = model_id.lower()
                if "video" in model_lower:
                    # For video, send as document or photo placeholder
                    for url in preview_urls[:1]:  # Send first preview only
                        try:
                            await callback.message.answer_photo(
                                photo=URLInputFile(url),
                                caption=t('dry_run_preview_video'),
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send preview image: {e}")
                            await callback.message.answer(
                                t('dry_run_preview_video'),
                                parse_mode="HTML"
                            )
                elif "audio" in model_lower or "music" in model_lower:
                    await callback.message.answer(
                        t('dry_run_preview_audio'),
                        parse_mode="HTML"
                    )
                else:
                    # Default: image preview
                    for url in preview_urls[:1]:  # Send first preview only
                        try:
                            await callback.message.answer_photo(
                                photo=URLInputFile(url),
                                caption=t('dry_run_preview_image'),
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send preview image: {e}")
                            await callback.message.answer(
                                t('dry_run_preview_image'),
                                parse_mode="HTML"
                            )
            
            # Show job_id notice
            await callback.message.answer(
                t('dry_run_notice', job_id=job_id),
                parse_mode="HTML"
            )
    else:
        # BATCH 38: Improved error handling with retry options
        from app.ux.error_handler import handle_generation_error
        
        # Get error message and keyboard from unified error handler
        error_msg, error_keyboard = handle_generation_error(result, flow_ctx.model_id)
        
        # Check if refund happened and add notice
        payment_status = result.get("payment_status", "")
        if payment_status == "released" or "refund" in payment_status.lower():
            error_msg += "\n\n💰 <b>Средства возвращены на ваш баланс</b>"
        
        # Send error with retry keyboard
        await callback.message.answer(
            error_msg,
            reply_markup=error_keyboard,
            parse_mode="HTML"
        )
        
        # Keep old retry button for backward compatibility
        # (user can either use new keyboard or old one)
        await callback.message.answer(
            "Попробовать ещё раз?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"gen:{flow_ctx.model_id}")],
                    [InlineKeyboardButton(text="💳 Баланс", callback_data="balance:main")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )


@router.callback_query()
async def fallback_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("⚠️ Кнопка устарела. Нажмите /start.")

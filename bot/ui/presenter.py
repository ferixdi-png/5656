"""Presenter helpers for marketing-first UI."""
from __future__ import annotations

from typing import Any, Dict


FRIENDLY_PARAM = {
    "prompt": "📝 Что рекламируем/о чём контент",
    "text": "📝 Что рекламируем/о чём контент",
    "input": "📝 Что рекламируем/о чём контент",
    "message": "📝 Что рекламируем/о чём контент",
    "product": "📦 Продукт/услуга",
    "audience": "👥 ЦА",
    "usp": "🎯 УТП",
    "tone": "🗣 Тон (дружелюбный/дерзкий/премиум)",
    "cta": "👉 Призыв к действию",
    "platform": "📍 Площадка",
    "duration": "🎬 Длительность",
    "aspect_ratio": "🎬 Формат (9:16, 1:1)",
    "negative_prompt": "🚫 Что исключить",
    "brand_colors": "🎨 Цвета бренда",
    "logo_url": "🔗 Лого (ссылка)",
    "reference_image": "📷 Референс",
    "url": "🔗 Ссылка",
    "link": "🔗 Ссылка",
    "source_url": "🔗 Ссылка",
    "file": "📎 Файл",
    "file_id": "📎 Файл",
    "file_url": "📎 Файл (ссылка)",
}

PARAM_HINTS = {
    "prompt": "Например: \"Кофейня для студентов в центре города\"",
    "product": "Укажите товар/услугу и главное преимущество.",
    "audience": "Например: \"молодые мамы 25-35\"",
    "usp": "Что отличает вас от конкурентов?",
    "tone": "Например: дружелюбный, уверенный, дерзкий.",
    "cta": "Например: \"Оставьте заявку\", \"Напишите в Direct\"",
    "platform": "Instagram, TikTok, Telegram и т.д.",
}

PLATFORM_LABELS = {
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube Shorts",
    "telegram": "Telegram",
    "vk": "VK",
    "other": "Другое",
}

GOAL_LABELS = {
    "reach": "Охват",
    "leads": "Лиды",
    "sales": "Продажи",
    "follows": "Подписки",
    "warmup": "Прогрев",
}


def display_name(model: Dict[str, Any]) -> str:
    return model.get("name") or model.get("model_id") or "Инструмент"


def friendly_param(param: str) -> str:
    return FRIENDLY_PARAM.get(param, param.replace("_", " ").title())


def output_summary(model: Dict[str, Any]) -> str:
    output_type = model.get("output_type")
    if output_type == "text":
        return "Текст/копирайт"
    if output_type == "video":
        return "Видео"
    if output_type == "audio":
        return "Аудио"
    if output_type == "url":
        return "Изображение/файл"
    return "Контент"


def input_summary(model: Dict[str, Any]) -> str:
    input_schema = model.get("input_schema", {})
    required = input_schema.get("required", [])
    if not required:
        return "Минимальный ввод"
    return ", ".join(friendly_param(field) for field in required)


def tool_card(model: Dict[str, Any], context: Dict[str, Any]) -> str:
    name = display_name(model)
    best_for = model.get("best_for") or model.get("description") or "Контент под рост и продажи"
    price = model.get("price") or "N/A"
    eta = model.get("eta") or "N/A"
    return (
        f"🛠 Инструмент: <b>{name}</b>\n\n"
        f"Лучше всего для: {best_for}\n"
        f"Что на выходе: {output_summary(model)}\n"
        f"Что нужно от вас: {input_summary(model)}\n"
        f"Цена: {price} ⭐ (спишем только при успехе)\n"
        f"ETA: {eta}"
    )


def price_info(model: Dict[str, Any]) -> str:
    price = model.get("price") or "N/A"
    return (
        f"⭐ Цена: {price}\n"
        "Списание только при успехе. Ошибка/таймаут → авто-рефанд."
    )


def param_hint(field_name: str, field_spec: Dict[str, Any]) -> str:
    return PARAM_HINTS.get(field_name, "Пример: кратко опишите задачу.")


def confirmation_text(
    model: Dict[str, Any],
    context: Dict[str, Any],
    inputs: Dict[str, Any],
    price: Any,
    balance: float,
) -> str:
    platform = PLATFORM_LABELS.get(context.get("platform"), "не указано")
    goal = GOAL_LABELS.get(context.get("goal"), "не указано")
    name = display_name(model)
    eta = model.get("eta") or "30–90 сек"
    return (
        "✅ Подтверждение генерации\n\n"
        f"Инструмент: {name}\n"
        f"Площадка: {platform} | Цель: {goal}\n"
        f"Результат: {output_summary(model)}\n\n"
        f"Параметры: {inputs}\n\n"
        f"Цена: {price} ⭐\n"
        f"ETA: {eta}\n"
        f"Баланс: {balance:.2f} ⭐\n\n"
        "Списание только при успехе. Ошибка/таймаут → авто-рефанд."
    )

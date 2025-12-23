"""
Primary UX flow: categories -> models -> inputs -> confirmation -> generation.
"""
from __future__ import annotations

import asyncio
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
from app.payments.pricing import calculate_user_price, format_price_rub

router = Router(name="flow")


CATEGORY_LABELS = {
    "t2i": "🎨 Text → Image",
    "i2i": "✏️ Image → Image",
    "t2v": "🎬 Text → Video",
    "i2v": "🎬 Image → Video",
    "v2v": "🎬 Video → Video",
    "lip_sync": "🎬 Lip Sync",
    "music": "🎵 Music",
    "sfx": "🎵 SFX",
    "tts": "🎵 Text → Speech",
    "stt": "🎵 Speech → Text",
    "audio_isolation": "🎵 Audio Isolation",
    "upscale": "✏️ Upscale",
    "bg_remove": "✏️ Background Remove",
    "watermark_remove": "✏️ Watermark Remove",
    "general": "⭐ General",
    "other": "⭐ Other",
}

WELCOME_BALANCE_RUB = float(os.getenv("WELCOME_BALANCE_RUB", "200"))


def _source_of_truth() -> Dict[str, Any]:
    return load_source_of_truth()


def _is_valid_model(model: Dict[str, Any]) -> bool:
    """Filter out technical/invalid models from registry."""
    model_id = model.get("model_id", "")
    if not model_id:
        return False
    # Skip uppercase technical entries
    if model_id.isupper():
        return False
    # Skip processor entries
    if model_id.endswith("_processor"):
        return False
    # CRITICAL: Skip models without confirmed pricing
    if not model.get("is_pricing_known", False):
        return False
    # Prefer vendor/name format
    return "/" in model_id


def _models_by_category() -> Dict[str, List[Dict[str, Any]]]:
    models = [model for model in _source_of_truth().get("models", []) if _is_valid_model(model)]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for model in models:
        category = model.get("category", "other") or "other"
        grouped.setdefault(category, []).append(model)
    for model_list in grouped.values():
        model_list.sort(key=lambda item: (item.get("name") or item.get("model_id") or "").lower())
    return grouped


def _category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


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


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Видео для Reels / TikTok", callback_data="cat:t2v")],
            [InlineKeyboardButton(text="🎨 Картинка / баннер / пост", callback_data="cat:t2i")],
            [InlineKeyboardButton(text="✏️ Улучшить / изменить / апскейл", callback_data="menu:edit")],
            [InlineKeyboardButton(text="🎧 Аудио / озвучка", callback_data="menu:audio")],
            [InlineKeyboardButton(text="⭐ Лучшие модели", callback_data="menu:top")],
            [InlineKeyboardButton(text="🔎 Поиск модели", callback_data="menu:search")],
            [InlineKeyboardButton(text="🕘 История", callback_data="menu:history")],
            [InlineKeyboardButton(text="💳 Баланс", callback_data="menu:balance")],
        ]
    )


def _model_keyboard(models: List[Dict[str, Any]], back_cb: str, page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """Create paginated model keyboard."""
    rows: List[List[InlineKeyboardButton]] = []
    
    # Calculate pagination
    start = page * per_page
    end = start + per_page
    page_models = models[start:end]
    total_pages = (len(models) + per_page - 1) // per_page
    
    # Model buttons
    for model in page_models:
        model_id = model.get("model_id", "unknown")
        title = model.get("name") or model_id
        # Truncate long names
        if len(title) > 40:
            title = title[:37] + "..."
        rows.append([InlineKeyboardButton(text=title, callback_data=f"model:{model_id}")])
    
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
    """Create human-friendly model card."""
    name = model.get("name") or model.get("model_id")
    model_id = model.get("model_id", "")
    
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
    
    # Price formatting - estimated user price (x2 from Kie.ai)
    price_raw = model.get("price")
    if price_raw:
        try:
            kie_cost = float(price_raw)
            if kie_cost == 0:
                price_str = "Бесплатно"
            else:
                user_price = calculate_user_price(kie_cost)
                price_str = format_price_rub(user_price)
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


def _field_prompt(field_name: str, field_spec: Dict[str, Any]) -> str:
    """Generate human-friendly prompt with examples."""
    field_type = field_spec.get("type", "string")
    enum = field_spec.get("enum")
    max_length = field_spec.get("max_length")
    
    if enum:
        return f"Выберите значение для <b>{field_name}</b>:"
    
    if field_type in {"file", "file_id", "file_url"}:
        return (
            f"📎 <b>Загрузите файл</b>\n\n"
            f"Отправьте изображение, видео или документ для параметра: {field_name}"
        )
    
    if field_type in {"url", "link", "source_url"}:
        return (
            f"🔗 <b>Отправьте ссылку</b>\n\n"
            f"Вставьте URL для параметра: {field_name}\n\n"
            f"<i>Пример: https://example.com/image.jpg</i>"
        )
    
    # Text/prompt fields - make them human-friendly
    if field_name in {"prompt", "text", "description", "input"}:
        return (
            f"✍️ <b>Опишите, что вы хотите создать</b>\n\n"
            f"<i>Пример:</i>\n"
            f"\"Неоновый баннер для Instagram, стиль киберпанк, тёмный фон\""
        )
    
    if max_length:
        return (
            f"✍️ <b>Введите {field_name}</b>\n\n"
            f"Максимум {max_length} символов"
        )
    
    return f"✍️ <b>Введите {field_name}</b>"


def _enum_keyboard(field_spec: Dict[str, Any]) -> Optional[InlineKeyboardMarkup]:
    enum = field_spec.get("enum")
    if not enum:
        return None
    rows = [[InlineKeyboardButton(text=str(val), callback_data=f"enum:{val}")] for val in enum]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        if value not in enum_values:
            raise ModelContractError(
                f"Поле '{field_name}' должно быть одним из {enum_values}"
            )
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
    await state.clear()
    charge_manager = get_charge_manager()
    charge_manager.ensure_welcome_credit(message.from_user.id, WELCOME_BALANCE_RUB)
    await message.answer(
        "� <b>Что вы хотите создать сегодня?</b>\n"
        "Я подберу лучшую нейросеть под вашу задачу",
        reply_markup=_main_menu_keyboard(),
    )


@router.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📋 Главное меню\n\nВыберите действие:",
        reply_markup=_main_menu_keyboard(),
    )


@router.callback_query(F.data == "menu:generate")
async def generate_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🚀 Генерация\n\nВыберите категорию:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data == "menu:all_categories")
async def all_categories_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📂 Все категории\n\nВыберите категорию:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data == "menu:edit")
async def edit_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
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
    await callback.answer()
    await state.clear()
    # Top models - based on popularity/price
    all_models = [m for m in _source_of_truth().get("models", []) if _is_valid_model(m)]
    
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
    query = (message.text or "").lower().strip()
    if not query:
        await message.answer("⚠️ Введите поисковый запрос.")
        return
    
    await state.clear()
    
    # Search models
    all_models = [m for m in _source_of_truth().get("models", []) if _is_valid_model(m)]
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
async def support_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "ℹ️ <b>Поддержка</b>\n\n"
        "Если у вас возникли вопросы или проблемы:\n\n"
        "📧 Email: support@example.com\n"
        "💬 Telegram: @support_bot\n\n"
        "Мы отвечаем в течение 24 часов.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
            ]
        ),
    )


@router.callback_query(F.data.in_({"balance", "menu:balance"}))
async def balance_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    balance = get_charge_manager().get_user_balance(callback.from_user.id)
    await callback.message.edit_text(
        f"💰 Баланс: {format_price_rub(balance)}\n\n"
        "Пополнение временно доступно через поддержку.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="ℹ️ Поддержка", callback_data="menu:support")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
            ]
        ),
    )


@router.callback_query(F.data == "menu:history")
async def history_cb(callback: CallbackQuery, state: FSMContext) -> None:
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
    model = next((m for m in _source_of_truth().get("models", []) if m.get("model_id") == model_id), None)
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.")
        return
    
    price_raw = model.get("price") or 0
    try:
        amount = float(price_raw)
    except (TypeError, ValueError):
        amount = 0.0
    
    charge_manager = get_charge_manager()
    balance = charge_manager.get_user_balance(callback.from_user.id)
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
        await callback.message.answer(result.get("message", "❌ Ошибка"))
        await callback.message.answer(
            "Попробовать ещё?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"repeat:{idx}")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )


@router.callback_query(F.data.startswith("cat:"))
async def category_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    category = callback.data.split(":", 1)[1]
    grouped = _models_by_category()
    models = grouped.get(category, [])

    if not models:
        await callback.message.edit_text("⚠️ В этой категории пока нет моделей.", reply_markup=_category_keyboard())
        return

    await state.update_data(category=category, category_models=models)
    await callback.message.edit_text(
        f"Категория: {_category_label(category)}\n\nВыберите модель:",
        reply_markup=_model_keyboard(models, f"cat:{category}", page=0),
    )


@router.callback_query(F.data.startswith("page:"))
async def page_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle pagination callbacks."""
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
    await callback.answer()


@router.callback_query(F.data.startswith("model:"))
async def model_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    model_id = callback.data.split(":", 1)[1]
    model = next((m for m in _source_of_truth().get("models", []) if m.get("model_id") == model_id), None)
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
    await callback.answer()
    model_id = callback.data.split(":", 1)[1]
    model = next((m for m in _source_of_truth().get("models", []) if m.get("model_id") == model_id), None)
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.", reply_markup=_category_keyboard())
        return

    input_schema = model.get("input_schema", {})
    required_fields = input_schema.get("required", [])
    optional_fields = input_schema.get("optional", [])  # MASTER PROMPT: "Ввод ВСЕХ параметров"
    properties = input_schema.get("properties", {})
    ctx = InputContext(
        model_id=model_id,
        required_fields=required_fields,
        optional_fields=optional_fields,
        properties=properties,
        collected={},
        collecting_optional=False
    )
    await state.update_data(flow_ctx=ctx.__dict__)

    if not required_fields:
        await _show_confirmation(callback.message, state, model)
        return

    field_name = required_fields[0]
    field_spec = properties.get(field_name, {})
    await state.set_state(InputFlow.waiting_input)
    await callback.message.answer(
        _field_prompt(field_name, field_spec),
        reply_markup=_enum_keyboard(field_spec),
    )


@router.callback_query(F.data.startswith("enum:"), InputFlow.waiting_input)
async def enum_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = callback.data.split(":", 1)[1]
    await _save_input_and_continue(callback.message, state, value)


@router.callback_query(F.data == "opt_skip_all")
async def opt_skip_all_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip all optional parameters and proceed to confirmation (MASTER PROMPT)."""
    await callback.answer("Используем значения по умолчанию")
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    model = next((m for m in _source_of_truth().get("models", []) if m.get("model_id") == flow_ctx.model_id), None)
    await _show_confirmation(callback.message, state, model)


@router.callback_query(F.data.startswith("opt_start:"))
async def opt_start_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Start collecting a specific optional parameter (MASTER PROMPT compliance)."""
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
    await callback.message.answer(
        _field_prompt(field_name, field_spec),
        reply_markup=_enum_keyboard(field_spec),
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

    if field_type in {"file", "file_id", "file_url"}:
        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id
        elif message.video:
            file_id = message.video.file_id
        elif message.audio:
            file_id = message.audio.file_id
        if not file_id and message.text and message.text.startswith(("http://", "https://")):
            await _save_input_and_continue(message, state, message.text)
            return
        if not file_id:
            await message.answer("⚠️ Нужен файл. Отправьте фото/документ/видео/аудио.")
            return
        await _save_input_and_continue(message, state, file_id)
        return

    if field_type in {"url", "link", "source_url"} and not message.text:
        await message.answer("⚠️ Ожидается ссылка (http/https).")
        return

    value = message.text
    if value is None:
        await message.answer("⚠️ Ожидается текстовое значение.")
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
        
        if is_configured:
            button_text = f"✓ {opt_field}: {flow_ctx.collected[opt_field]}"
        else:
            button_text = f"○ {opt_field}"
            if default is not None:
                button_text += f" (default: {default})"
        
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"opt_start:{opt_field}")])
    
    # Add "Finish" or "Skip all" button
    any_configured = any(opt in flow_ctx.collected for opt in flow_ctx.optional_fields)
    if any_configured:
        buttons.append([InlineKeyboardButton(text="✅ Готово, перейти к подтверждению", callback_data="opt_skip_all")])
    else:
        buttons.append([InlineKeyboardButton(text="⏭ Пропустить все (использовать defaults)", callback_data="opt_skip_all")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Show status of parameters
    configured_count = sum(1 for opt in flow_ctx.optional_fields if opt in flow_ctx.collected)
    total_count = len(flow_ctx.optional_fields)
    
    await message.answer(
        f"🎛 <b>Дополнительные параметры</b> ({configured_count}/{total_count} настроено)\n\n"
        f"✓ = настроено\n"
        f"○ = default значение\n\n"
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
        await message.answer(f"⚠️ {e}")
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
        model = next((m for m in _source_of_truth().get("models", []) if m.get("model_id") == flow_ctx.model_id), None)
        await _show_confirmation(message, state, model)
        return

    # Continue to next required field
    next_field = current_fields[flow_ctx.index]
    next_spec = flow_ctx.properties.get(next_field, {})
    await message.answer(
        _field_prompt(next_field, next_spec),
        reply_markup=_enum_keyboard(next_spec),
    )


async def _show_confirmation(message: Message, state: FSMContext, model: Optional[Dict[str, Any]]) -> None:
    """Show canonical confirmation screen."""
    if not model:
        await message.answer("⚠️ Модель не найдена.")
        return
    
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    
    model_name = model.get("name") or model.get("model_id")
    
    # Price formatting - estimated user price (x2 from Kie.ai)
    price_raw = model.get("price") or 0
    try:
        kie_cost_estimate = float(price_raw)
        if kie_cost_estimate == 0:
            price_str = "Бесплатно"
        else:
            user_price_estimate = calculate_user_price(kie_cost_estimate)
            price_str = format_price_rub(user_price_estimate)
    except (TypeError, ValueError):
        price_str = str(price_raw)
    
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
    
    balance = get_charge_manager().get_user_balance(message.from_user.id)
    
    await state.set_state(InputFlow.confirm)
    await message.answer(
        f"🔍 <b>Проверьте заказ</b>\n\n"
        f"<b>Модель:</b> {model_name}\n"
        f"<b>Задача:</b>\n{params_str}\n\n"
        f"💰 <b>Стоимость генерации:</b> {price_str}\n"
        f"📌 <b>Цена сформирована на основе тарифа модели</b>\n"
        f"⏱ <b>Ожидание:</b> {eta_str}\n"
        f"📦 <b>Получите:</b> {result_desc}\n\n"
        f"💳 <b>Ваш баланс:</b> {format_price_rub(balance)}\n\n"
        f"ℹ️ <i>Деньги спишутся ТОЛЬКО при успешной генерации</i>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Запустить", callback_data="confirm")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
            ]
        ),
    )


@router.callback_query(F.data == "cancel", InputFlow.confirm)
async def cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ Отменено. Возврат в меню.",
        reply_markup=_main_menu_keyboard()
    )


@router.callback_query(F.data == "confirm", InputFlow.confirm)
async def confirm_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    model = next((m for m in _source_of_truth().get("models", []) if m.get("model_id") == flow_ctx.model_id), None)
    if not model:
        await callback.message.edit_text("⚠️ Модель не найдена.")
        await state.clear()
        return

    price_raw = model.get("price") or 0
    try:
        amount = float(price_raw)
    except (TypeError, ValueError):
        amount = 0.0

    charge_manager = get_charge_manager()
    balance = charge_manager.get_user_balance(callback.from_user.id)
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

    await callback.message.edit_text("⏳ <b>Генерация запущена</b>\n\nЯ сообщу о результате. Пожалуйста, подождите...")

    def heartbeat(text: str) -> None:
        asyncio.create_task(callback.message.answer(text))

    charge_task_id = f"charge_{callback.from_user.id}_{callback.message.message_id}"
    result = await generate_with_payment(
        model_id=flow_ctx.model_id,
        user_inputs=flow_ctx.collected,
        user_id=callback.from_user.id,
        amount=amount,
        progress_callback=heartbeat,
        task_id=charge_task_id,
        reserve_balance=True,
    )

    await state.clear()

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
                    [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"gen:{flow_ctx.model_id}")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )
    else:
        await callback.message.answer(result.get("message", "❌ Ошибка"))
        await callback.message.answer(
            "Попробовать ещё раз?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Повторить", callback_data=f"gen:{flow_ctx.model_id}")],
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
                ]
            ),
        )


@router.callback_query()
async def fallback_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("⚠️ Кнопка устарела. Нажмите /start.")

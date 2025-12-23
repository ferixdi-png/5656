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

WELCOME_CREDITS = float(os.getenv("WELCOME_CREDITS", "10"))


def _source_of_truth() -> Dict[str, Any]:
    return load_source_of_truth()


def _models_by_category() -> Dict[str, List[Dict[str, Any]]]:
    models = [model for model in _source_of_truth().get("models", []) if model.get("model_id")]
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
            [InlineKeyboardButton(text="🚀 Генерация", callback_data="menu:generate")],
            [InlineKeyboardButton(text="💳 Баланс / Оплата", callback_data="menu:balance")],
            [InlineKeyboardButton(text="ℹ️ Поддержка", callback_data="menu:support")],
        ]
    )


def _model_keyboard(models: List[Dict[str, Any]], back_cb: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for model in models:
        model_id = model.get("model_id", "unknown")
        title = model.get("name") or model_id
        rows.append([InlineKeyboardButton(text=title, callback_data=f"model:{model_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _model_detail_text(model: Dict[str, Any]) -> str:
    name = model.get("name") or model.get("model_id")
    best_for = model.get("best_for") or model.get("description") or "Описание отсутствует"
    price = model.get("price") or "N/A"
    eta = model.get("eta") or "N/A"
    input_schema = model.get("input_schema", {})
    required_fields = input_schema.get("required", [])
    required_label = ", ".join(required_fields) if required_fields else "нет"
    return (
        f"<b>{name}</b>\n\n"
        f"Best for: {best_for}\n"
        f"Поля: {required_label}\n"
        f"Цена: {price}\n"
        f"ETA: {eta}\n"
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
    properties: Dict[str, Any]
    collected: Dict[str, Any]
    index: int = 0


def _field_prompt(field_name: str, field_spec: Dict[str, Any]) -> str:
    field_type = field_spec.get("type", "string")
    enum = field_spec.get("enum")
    max_length = field_spec.get("max_length")
    if enum:
        return f"Выберите значение для <b>{field_name}</b>:"
    if field_type in {"file", "file_id", "file_url"}:
        return f"Отправьте файл для <b>{field_name}</b>:"
    if field_type in {"url", "link", "source_url"}:
        return f"Отправьте ссылку для <b>{field_name}</b> (http/https):"
    if max_length:
        return f"Введите значение для <b>{field_name}</b> (до {max_length} символов):"
    return f"Введите значение для <b>{field_name}</b>:"


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
    charge_manager.ensure_welcome_credit(message.from_user.id, WELCOME_CREDITS)
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Выберите действие:",
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


@router.callback_query(F.data.in_({"support", "menu:support"}))
async def support_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "ℹ️ Поддержка\n\nНапишите в поддержку, если нужна помощь."
    )


@router.callback_query(F.data.in_({"balance", "menu:balance"}))
async def balance_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    balance = get_charge_manager().get_user_balance(callback.from_user.id)
    await callback.message.edit_text(
        f"💰 Баланс: {balance:.2f} кредитов\n\n"
        "Пополнение временно доступно через поддержку.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="ℹ️ Поддержка", callback_data="menu:support")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
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

    await state.update_data(category=category)
    await callback.message.edit_text(
        f"Категория: {_category_label(category)}\n\nВыберите модель:",
        reply_markup=_model_keyboard(models, "menu:generate"),
    )


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
    properties = input_schema.get("properties", {})
    ctx = InputContext(model_id=model_id, required_fields=required_fields, properties=properties, collected={})
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


@router.message(InputFlow.waiting_input)
async def input_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    field_name = flow_ctx.required_fields[flow_ctx.index]
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


async def _save_input_and_continue(message: Message, state: FSMContext, value: Any) -> None:
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    field_name = flow_ctx.required_fields[flow_ctx.index]
    field_spec = flow_ctx.properties.get(field_name, {})
    value = _coerce_value(value, field_spec)

    try:
        _validate_field_value(value, field_spec, field_name)
    except ModelContractError as e:
        await message.answer(f"⚠️ {e}")
        return

    flow_ctx.collected[field_name] = value
    flow_ctx.index += 1
    await state.update_data(flow_ctx=flow_ctx.__dict__)

    if flow_ctx.index >= len(flow_ctx.required_fields):
        model = next((m for m in _source_of_truth().get("models", []) if m.get("model_id") == flow_ctx.model_id), None)
        await _show_confirmation(message, state, model)
        return

    next_field = flow_ctx.required_fields[flow_ctx.index]
    next_spec = flow_ctx.properties.get(next_field, {})
    await message.answer(
        _field_prompt(next_field, next_spec),
        reply_markup=_enum_keyboard(next_spec),
    )


async def _show_confirmation(message: Message, state: FSMContext, model: Optional[Dict[str, Any]]) -> None:
    if not model:
        await message.answer("⚠️ Модель не найдена.")
        return
    data = await state.get_data()
    flow_ctx = InputContext(**data.get("flow_ctx"))
    price = model.get("price") or "N/A"
    balance = get_charge_manager().get_user_balance(message.from_user.id)
    await state.set_state(InputFlow.confirm)
    await message.answer(
        f"{_model_detail_text(model)}\n"
        f"Параметры: {flow_ctx.collected}\n\n"
        f"Цена: {price}\n"
        f"Баланс: {balance:.2f}\n"
        "Подтвердить генерацию?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Подтвердить", callback_data="confirm")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
            ]
        ),
    )


@router.callback_query(F.data == "cancel", InputFlow.confirm)
async def cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("❌ Отменено. Возврат в меню.", reply_markup=_category_keyboard())


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

    await callback.message.edit_text("⏳ Генерация запущена. Пожалуйста, подождите...")

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
        # Generation failed - payment was auto-refunded (see integration.py)
        payment_status = result.get("payment_status", "")
        payment_msg = result.get("payment_message", "")
        error_message = result.get("message", "❌ Ошибка")
        
        # Add refund info if payment was involved
        if payment_status == "released" or payment_status == "refunded":
            error_message += f"\n\n💰 {payment_msg}"
        
        await callback.message.answer(error_message)
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

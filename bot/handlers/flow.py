"""Marketing-first UX flow: jobs -> recommendations -> tools -> inputs -> confirmation."""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
import logging
import uuid
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.kie.builder import load_source_of_truth
from app.kie.validator import ModelContractError
from app.payments.charges import get_charge_manager
from app.payments.integration import generate_with_payment
from bot.flow.input_wizard import InputWizard, WizardStep
from bot.ui import marketing_taxonomy as mt
from bot.ui import presenter

router = Router(name="flow")
logger = logging.getLogger(__name__)

WELCOME_CREDITS = float(os.getenv("WELCOME_CREDITS", "10"))
CATALOG_PAGE_SIZE = 10
GENERATION_TIMEOUT_SEC = int(os.getenv("GENERATION_TIMEOUT_SEC", "300"))
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


class FlowState(StatesGroup):
    home = State()
    pick_template = State()
    pick_platform = State()
    pick_goal = State()
    pick_content_type = State()
    pick_tool = State()
    tool_card = State()
    input_step = State()
    confirm = State()
    generating = State()
    result = State()


@dataclass
class FlowContext:
    platform: Optional[str] = None
    goal: Optional[str] = None
    content_type: Optional[str] = None
    template_id: Optional[str] = None
    model_id: Optional[str] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    price_estimate: Optional[float] = None
    eta_estimate: Optional[str] = None
    pending_charge_id: Optional[str] = None
    task_id: Optional[str] = None
    progress_message_id: Optional[int] = None
    generation_started_at: Optional[str] = None


def _source_of_truth() -> Dict[str, Any]:
    return load_source_of_truth()


def _models() -> List[Dict[str, Any]]:
    return [model for model in _source_of_truth().get("models", []) if model.get("model_id")]


def _model_by_id(model_id: str) -> Optional[Dict[str, Any]]:
    return next((m for m in _models() if m.get("model_id") == model_id), None)


def _home_text(user_id: int) -> str:
    balance = get_charge_manager().get_user_balance(user_id)
    return (
        "📈 Контент-студия для роста соцсетей\n"
        "Выберите, что делаем прямо сейчас.\n\n"
        f"Баланс: {balance:.2f} ⭐"
    )


def _home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Быстрый старт (3 шага)", callback_data="home:quick")],
            [InlineKeyboardButton(text="🎬 Видео для соцсетей", callback_data="home:video")],
            [InlineKeyboardButton(text="🎨 Креативы/баннеры", callback_data="home:image")],
            [InlineKeyboardButton(text="✂️ Монтаж/редактирование", callback_data="home:edit")],
            [InlineKeyboardButton(text="🔥 Топ инструменты", callback_data="home:top")],
            [InlineKeyboardButton(text="⭐ Баланс / Оплата", callback_data="home:balance")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="home:support")],
        ]
    )


def _quick_templates_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=template.title, callback_data=f"tmpl:{template.template_id}")]
            for template in mt.TEMPLATES]
    rows.append([InlineKeyboardButton(text="📚 Все инструменты (по моделям)", callback_data="catalog:all:0")])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _platform_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="TikTok", callback_data="platform:tiktok")],
        [InlineKeyboardButton(text="Reels", callback_data="platform:instagram")],
        [InlineKeyboardButton(text="YouTube Shorts", callback_data="platform:youtube")],
        [InlineKeyboardButton(text="Telegram", callback_data="platform:telegram")],
        [InlineKeyboardButton(text="Другое", callback_data="platform:other")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _goal_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Продажи", callback_data="goal:sales")],
        [InlineKeyboardButton(text="Охват", callback_data="goal:reach")],
        [InlineKeyboardButton(text="Подписки", callback_data="goal:follows")],
        [InlineKeyboardButton(text="Лид-магнит", callback_data="goal:leads")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _content_type_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Видео", callback_data="content:video")],
        [InlineKeyboardButton(text="Картинка", callback_data="content:image")],
        [InlineKeyboardButton(text="Текст", callback_data="content:text")],
        [InlineKeyboardButton(text="Озвучка", callback_data="content:audio")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _recommended_keyboard(has_recommendations: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_recommendations:
        rows.extend([
            [InlineKeyboardButton(text="🔥 Лучший вариант (1-click)", callback_data="rec:best")],
            [InlineKeyboardButton(text="🎛 Выбрать из 3–5 рекомендаций", callback_data="rec:list")],
        ])
    rows.extend([
        [InlineKeyboardButton(text="📚 Все модели в этой категории", callback_data="rec:all")],
        [InlineKeyboardButton(text="🔎 Поиск", callback_data="rec:search")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _tool_card_keyboard(model_id: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить", callback_data=f"gen:{model_id}")],
            [InlineKeyboardButton(text="⭐ Цена/что входит", callback_data=f"tool:price:{model_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
        ]
    )


def _model_list_keyboard(models: List[Dict[str, Any]], back_cb: str) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for model in models:
        model_id = model.get("model_id", "unknown")
        title = presenter.display_name(model)
        rows.append([InlineKeyboardButton(text=title, callback_data=f"tool:{model_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _catalog_keyboard(model_ids: List[str], page: int, back_cb: str) -> InlineKeyboardMarkup:
    start = page * CATALOG_PAGE_SIZE
    end = start + CATALOG_PAGE_SIZE
    page_ids = model_ids[start:end]
    rows = [
        [InlineKeyboardButton(text=presenter.display_name(_model_by_id(model_id) or {}), callback_data=f"tool:{model_id}")]
        for model_id in page_ids
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"catalog:page:{page - 1}"))
    if end < len(model_ids):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"catalog:page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _input_keyboard(step: WizardStep) -> InlineKeyboardMarkup:
    buttons = []
    if InputWizard.expects_enum(step):
        buttons.extend([[InlineKeyboardButton(text=str(val), callback_data=f"enum:{val}")] for val in step.spec.get("enum", [])])
    buttons.append([InlineKeyboardButton(text="💡 Подсказка", callback_data="hint")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _context_from_state(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "platform": data.get("platform"),
        "goal": data.get("goal"),
        "content_type": data.get("content_type"),
        "template_id": data.get("template_id"),
    }


def _log(handler: str, user_id: int, state: Optional[str]) -> None:
    logger.info("entered %s user_id=%s state=%s", handler, user_id, state)


def _new_context() -> FlowContext:
    return FlowContext()


def _context_dict(context: FlowContext) -> Dict[str, Any]:
    return context.__dict__.copy()


def _context_from_dict(data: Dict[str, Any]) -> FlowContext:
    return FlowContext(**data)


@router.callback_query(F.data == "home:quick")
async def quick_templates_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("home:quick", callback.from_user.id, await state.get_state())
    await callback.answer()
    await state.update_data(template_id=None, content_type=None)
    await state.set_state(FlowState.pick_platform)
    await callback.message.edit_text("📍 Где публикуем?", reply_markup=_platform_keyboard())


@router.callback_query(F.data.startswith("tmpl:"), FlowState.pick_template)
async def template_select_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("tmpl_select", callback.from_user.id, await state.get_state())
    await callback.answer()
    template_id = callback.data.split(":", 1)[1]
    template = mt.template_by_id(template_id)
    if not template:
        await callback.message.edit_text("⚠️ Шаблон не найден.", reply_markup=_quick_templates_keyboard())
        return
    await state.update_data(template_id=template_id, content_type=template.content_type)
    await state.set_state(FlowState.pick_platform)
    await callback.message.edit_text("📍 Где публикуем?", reply_markup=_platform_keyboard())


@router.callback_query(F.data.in_({
    "home:video",
    "home:image",
    "home:enhance",
    "home:edit",
    "home:top",
}))
async def content_shortcut_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("home_shortcut", callback.from_user.id, await state.get_state())
    await callback.answer()
    mapping = {
        "home:video": "video",
        "home:image": "image",
        "home:enhance": "enhance",
        "home:edit": "enhance",
    }
    if callback.data == "home:top":
        await _show_top_tools(callback, state)
        return
    await state.update_data(content_type=mapping.get(callback.data))
    await state.set_state(FlowState.pick_platform)
    await callback.message.edit_text("📍 Где публикуем?", reply_markup=_platform_keyboard())


@router.callback_query(F.data.startswith("platform:"), FlowState.pick_platform)
async def platform_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("platform", callback.from_user.id, await state.get_state())
    await callback.answer()
    platform = callback.data.split(":", 1)[1]
    await state.update_data(platform=platform)
    await state.set_state(FlowState.pick_goal)
    await callback.message.edit_text("🎯 Цель контента?", reply_markup=_goal_keyboard())


@router.callback_query(F.data.startswith("goal:"), FlowState.pick_goal)
async def goal_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("goal", callback.from_user.id, await state.get_state())
    await callback.answer()
    goal = callback.data.split(":", 1)[1]
    await state.update_data(goal=goal)
    data = await state.get_data()
    if not data.get("content_type"):
        await state.set_state(FlowState.pick_content_type)
        await callback.message.edit_text("🧩 Что делаем?", reply_markup=_content_type_keyboard())
        return
    await _show_recommendations(callback, state)


@router.callback_query(F.data.startswith("content:"), FlowState.pick_content_type)
async def content_type_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("content", callback.from_user.id, await state.get_state())
    await callback.answer()
    content_type = callback.data.split(":", 1)[1]
    await state.update_data(content_type=content_type)
    await _show_recommendations(callback, state)


async def _show_recommendations(callback: CallbackQuery, state: FSMContext) -> None:
    _log("show_recommendations", callback.from_user.id, await state.get_state())
    data = await state.get_data()
    context = _context_from_state(data)
    recommendations = mt.recommend_models(_models(), context, limit=5)
    await state.update_data(recommendations=[m["model_id"] for m in recommendations])
    await state.set_state(FlowState.pick_tool)
    await callback.message.edit_text(
        "✅ Рекомендуемые инструменты под вашу задачу",
        reply_markup=_recommended_keyboard(bool(recommendations)),
    )


@router.callback_query(F.data == "rec:best", FlowState.pick_tool)
async def recommended_best_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("rec_best", callback.from_user.id, await state.get_state())
    await callback.answer()
    data = await state.get_data()
    recommendations = data.get("recommendations", [])
    if not recommendations:
        await callback.message.edit_text("⚠️ Рекомендаций нет. Попробуйте каталог.")
        return
    await _show_tool_card(callback, state, recommendations[0], "rec:back")


@router.callback_query(F.data == "rec:back")
async def recommended_back_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("rec_back", callback.from_user.id, await state.get_state())
    await callback.answer()
    await _show_recommendations(callback, state)


@router.callback_query(F.data == "rec:list", FlowState.pick_tool)
async def recommended_list_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("rec_list", callback.from_user.id, await state.get_state())
    await callback.answer()
    data = await state.get_data()
    recommendations = [_model_by_id(mid) for mid in data.get("recommendations", [])]
    models = [model for model in recommendations if model]
    if not models:
        await callback.message.edit_text("⚠️ Рекомендаций нет. Попробуйте каталог.")
        return
    await state.update_data(back_cb="rec:back")
    await state.set_state(FlowState.pick_tool)
    await callback.message.edit_text(
        "Выберите инструмент:",
        reply_markup=_model_list_keyboard(models, "rec:back"),
    )


@router.callback_query(F.data == "rec:all", FlowState.pick_tool)
async def recommended_all_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("rec_all", callback.from_user.id, await state.get_state())
    await callback.answer()
    data = await state.get_data()
    context = _context_from_state(data)
    model_ids = [m["model_id"] for m in mt.models_for_context(_models(), context)]
    await state.update_data(catalog_ids=model_ids, back_cb="rec:back")
    await state.set_state(FlowState.pick_tool)
    await callback.message.edit_text(
        "📚 Каталог инструментов",
        reply_markup=_catalog_keyboard(model_ids, 0, "rec:back"),
    )


@router.callback_query(F.data == "rec:search", FlowState.pick_tool)
async def recommended_search_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("rec_search", callback.from_user.id, await state.get_state())
    await callback.answer()
    await state.update_data(search_mode=True)
    await callback.message.edit_text(
        "🔎 Введите слово для поиска по названию/описанию.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="rec:back")]]
        ),
    )


@router.callback_query(F.data.startswith("catalog:all:"))
async def catalog_all_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("catalog_all", callback.from_user.id, await state.get_state())
    await callback.answer()
    page = int(callback.data.split(":", 2)[2])
    model_ids = [model["model_id"] for model in _models()]
    await state.update_data(catalog_ids=model_ids, back_cb="home:quick")
    await callback.message.edit_text(
        "📚 Все инструменты",
        reply_markup=_catalog_keyboard(model_ids, page, "home:quick"),
    )


@router.callback_query(F.data.startswith("catalog:page:"))
async def catalog_page_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("catalog_page", callback.from_user.id, await state.get_state())
    await callback.answer()
    page = int(callback.data.split(":", 2)[2])
    data = await state.get_data()
    model_ids = data.get("catalog_ids", [])
    back_cb = data.get("back_cb", "home")
    await callback.message.edit_text(
        "📚 Каталог инструментов",
        reply_markup=_catalog_keyboard(model_ids, page, back_cb),
    )


@router.callback_query(F.data.startswith("tool:price:"))
async def tool_price_cb(callback: CallbackQuery) -> None:
    _log("tool_price", callback.from_user.id, None)
    await callback.answer()
    model_id = callback.data.split(":", 2)[2]
    model = _model_by_id(model_id)
    if not model:
        await callback.message.answer("⚠️ Инструмент не найден.")
        return
    await callback.message.answer(presenter.price_info(model))


@router.callback_query(F.data.startswith("tool:"))
async def tool_card_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("tool_card", callback.from_user.id, await state.get_state())
    await callback.answer()
    if callback.data.startswith("tool:price:"):
        return
    model_id = callback.data.split(":", 1)[1]
    await _show_tool_card(callback, state, model_id, "rec:back")


async def _show_tool_card(callback: CallbackQuery, state: FSMContext, model_id: str, back_cb: str) -> None:
    _log("show_tool_card", callback.from_user.id, await state.get_state())
    model = _model_by_id(model_id)
    if not model:
        await callback.message.edit_text("⚠️ Инструмент не найден.")
        return
    data = await state.get_data()
    context = _context_from_state(data)
    await state.update_data(model_id=model_id, back_cb=back_cb)
    await state.set_state(FlowState.tool_card)
    await callback.message.edit_text(
        presenter.tool_card(model, context),
        reply_markup=_tool_card_keyboard(model_id, back_cb),
    )


@router.callback_query(F.data == "home:balance")
async def balance_cb(callback: CallbackQuery) -> None:
    _log("home_balance", callback.from_user.id, None)
    await callback.answer()
    balance = get_charge_manager().get_user_balance(callback.from_user.id)
    await callback.message.edit_text(
        f"⭐ Баланс: {balance:.2f} ⭐\n\n"
        "Списание только при успехе.\n"
        "Пополнение: ⭐ Stars или СБП — напишите в поддержку.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🆘 Поддержка", callback_data="home:support")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
            ]
        ),
    )


@router.callback_query(F.data == "home:history")
async def history_cb(callback: CallbackQuery) -> None:
    _log("home_history", callback.from_user.id, None)
    await callback.answer()
    await callback.message.edit_text(
        "📦 История будет доступна в ближайшее время.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")]]
        ),
    )


@router.callback_query(F.data == "home:support")
async def support_cb(callback: CallbackQuery) -> None:
    _log("home_support", callback.from_user.id, None)
    await callback.answer()
    await callback.message.edit_text(
        "🆘 Поддержка\n\nНапишите в поддержку, если нужна помощь.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")]]
        ),
    )


@router.callback_query(F.data.startswith("gen:"))
async def generate_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("generate", callback.from_user.id, await state.get_state())
    await callback.answer()
    model_id = callback.data.split(":", 1)[1]
    model = _model_by_id(model_id)
    if not model:
        await callback.message.edit_text("⚠️ Инструмент не найден.")
        return

    wizard = InputWizard(model)
    steps = wizard.steps()
    await state.update_data(model_id=model_id, wizard_steps=[step.__dict__ for step in steps], step_index=0, inputs={})

    if not steps:
        await _show_confirmation(callback.message, state, model)
        return

    step = steps[0]
    await state.set_state(FlowState.input_step)
    await callback.message.answer(
        wizard.prompt(step),
        reply_markup=_input_keyboard(step),
    )


@router.callback_query(F.data == "hint", FlowState.input_step)
async def hint_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("hint", callback.from_user.id, await state.get_state())
    await callback.answer()
    data = await state.get_data()
    steps = [WizardStep(**step) for step in data.get("wizard_steps", [])]
    index = data.get("step_index", 0)
    if index >= len(steps):
        return
    await callback.message.answer(steps[index].help_text)


@router.callback_query(F.data.startswith("enum:"), FlowState.input_step)
async def enum_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("enum", callback.from_user.id, await state.get_state())
    await callback.answer()
    value = callback.data.split(":", 1)[1]
    await _save_input_and_continue(callback.message, state, value)


@router.message(FlowState.input_step)
async def input_message(message: Message, state: FSMContext) -> None:
    _log("input_message", message.from_user.id, await state.get_state())
    data = await state.get_data()
    steps = [WizardStep(**step) for step in data.get("wizard_steps", [])]
    index = data.get("step_index", 0)
    if index >= len(steps):
        await message.answer("⚠️ Шаг не найден. Нажмите /start.")
        return
    step = steps[index]
    wizard = InputWizard(_model_by_id(data.get("model_id", "")) or {})

    if InputWizard.expects_file(step):
        file_id = None
        file_size = None
        if message.photo:
            file_id = message.photo[-1].file_id
            file_size = message.photo[-1].file_size
        elif message.document:
            file_id = message.document.file_id
            file_size = message.document.file_size
            if message.document.mime_type and not message.document.mime_type.startswith(("image/", "video/", "audio/")):
                await message.answer("⚠️ Неподдерживаемый тип файла. Отправьте изображение/видео/аудио.")
                return
        elif message.video:
            file_id = message.video.file_id
            file_size = message.video.file_size
        elif message.audio:
            file_id = message.audio.file_id
            file_size = message.audio.file_size
        if file_size and file_size > MAX_FILE_SIZE_BYTES:
            await message.answer(
                "⚠️ Файл слишком большой. Попробуйте отправить ссылку или уменьшите файл."
            )
            return
        if not file_id and message.text and message.text.startswith(("http://", "https://")):
            await _save_input_and_continue(message, state, message.text)
            return
        if not file_id:
            await message.answer("⚠️ Нужен файл. Отправьте фото/документ/видео/аудио.")
            return
        await _save_input_and_continue(message, state, file_id)
        return

    if InputWizard.expects_url(step):
        if message.photo or message.document or message.video or message.audio:
            await message.answer("⚠️ Нужна ссылка текстом (http/https).")
            return
        if message.text is None:
            await message.answer("⚠️ Нужна ссылка в тексте (http/https).")
            return
        if not message.text.startswith(("http://", "https://")):
            await message.answer("⚠️ Нужна ссылка с http:// или https://.")
            return

    value = message.text
    if value is None:
        await message.answer("⚠️ Ожидается текстовое значение.")
        return
    await _save_input_and_continue(message, state, value)


async def _save_input_and_continue(message: Message, state: FSMContext, value: Any) -> None:
    _log("save_input", message.from_user.id, await state.get_state())
    data = await state.get_data()
    steps = [WizardStep(**step) for step in data.get("wizard_steps", [])]
    index = data.get("step_index", 0)
    if index >= len(steps):
        return
    step = steps[index]
    model = _model_by_id(data.get("model_id", ""))
    wizard = InputWizard(model or {})

    coerced = wizard.coerce(value, step.spec)
    try:
        wizard.validate(coerced, step)
    except ModelContractError as e:
        await message.answer(f"⚠️ {e}")
        return

    inputs = data.get("inputs", {})
    inputs[step.name] = coerced
    index += 1
    await state.update_data(inputs=inputs, step_index=index)

    if index >= len(steps):
        await _show_confirmation(message, state, model)
        return

    next_step = steps[index]
    await message.answer(
        wizard.prompt(next_step),
        reply_markup=_input_keyboard(next_step),
    )


async def _show_confirmation(message: Message, state: FSMContext, model: Optional[Dict[str, Any]]) -> None:
    _log("show_confirmation", message.from_user.id, await state.get_state())
    if not model:
        await message.answer("⚠️ Инструмент не найден.")
        return
    data = await state.get_data()
    price = model.get("price") or "N/A"
    balance = get_charge_manager().get_user_balance(message.from_user.id)
    context = _context_from_state(data)
    await state.set_state(FlowState.confirm)
    await message.answer(
        presenter.confirmation_text(model, context, data.get("inputs", {}), price, balance),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить и запустить", callback_data="confirm")],
                [InlineKeyboardButton(text="✏️ Изменить", callback_data="edit")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
            ]
        ),
    )


@router.callback_query(F.data == "edit", FlowState.confirm)
async def edit_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("edit_confirm", callback.from_user.id, await state.get_state())
    await callback.answer()
    data = await state.get_data()
    inputs = data.get("inputs", {})
    if not inputs:
        await callback.message.answer("⚠️ Нет параметров для редактирования.")
        return
    rows = [
        [InlineKeyboardButton(text=presenter.friendly_param(name), callback_data=f"edit:{name}")]
        for name in inputs.keys()
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="confirm_back")])
    await callback.message.answer(
        "Что изменить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "confirm_back", FlowState.confirm)
async def confirm_back_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("confirm_back", callback.from_user.id, await state.get_state())
    await callback.answer()
    model = _model_by_id((await state.get_data()).get("model_id", ""))
    await _show_confirmation(callback.message, state, model)


@router.callback_query(F.data.startswith("edit:"), FlowState.confirm)
async def edit_field_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("edit_field", callback.from_user.id, await state.get_state())
    await callback.answer()
    field_name = callback.data.split(":", 1)[1]
    data = await state.get_data()
    steps = [WizardStep(**step) for step in data.get("wizard_steps", [])]
    try:
        index = next(i for i, step in enumerate(steps) if step.name == field_name)
    except StopIteration:
        await callback.message.answer("⚠️ Поле не найдено.")
        return
    await state.update_data(step_index=index)
    await state.set_state(FlowState.input_step)
    model = _model_by_id(data.get("model_id", ""))
    wizard = InputWizard(model or {})
    await callback.message.answer(
        wizard.prompt(steps[index]),
        reply_markup=_input_keyboard(steps[index]),
    )


@router.callback_query(F.data == "cancel", FlowState.confirm)
async def cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("confirm_cancel", callback.from_user.id, await state.get_state())
    await callback.answer()
    await state.clear()
    await state.set_state(FlowState.home)
    await callback.message.edit_text(
        "❌ Отменено. Возврат в меню.",
        reply_markup=_home_keyboard(),
    )


@router.callback_query(F.data == "confirm", FlowState.confirm)
async def confirm_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("confirm", callback.from_user.id, await state.get_state())
    await callback.answer()
    if await state.get_state() == FlowState.generating:
        await callback.message.answer("⚠️ Генерация уже идёт.")
        return
    data = await state.get_data()
    model = _model_by_id(data.get("model_id", ""))
    if not model:
        await callback.message.edit_text("⚠️ Инструмент не найден.")
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
                    [InlineKeyboardButton(text="⭐ Баланс / Оплата", callback_data="home:balance")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
                ]
            ),
        )
        await state.clear()
        return

    trace_id = uuid.uuid4().hex[:10]
    logger.info("generation start trace_id=%s user_id=%s model_id=%s", trace_id, callback.from_user.id, model.get("model_id"))
    progress_message = await callback.message.edit_text(
        "⏳ Генерим креатив… Обычно 30–90 сек.\n"
        "Если долго — вернём средства автоматически.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛑 Отменить", callback_data="gen:cancel")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
            ]
        ),
    )

    charge_task_id = f"charge_{callback.from_user.id}_{callback.message.message_id}"
    await state.update_data(pending_charge_id=charge_task_id, progress_message_id=progress_message.message_id, trace_id=trace_id)
    await state.set_state(FlowState.generating)

    async def update_progress(text: str) -> None:
        try:
            await callback.bot.edit_message_text(
                text,
                chat_id=callback.message.chat.id,
                message_id=progress_message.message_id,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🛑 Отменить", callback_data="gen:cancel")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
                    ]
                ),
            )
        except Exception:
            pass

    def heartbeat(text: str) -> None:
        asyncio.create_task(update_progress(text))

    result = await generate_with_payment(
        model_id=model.get("model_id"),
        user_inputs=data.get("inputs", {}),
        user_id=callback.from_user.id,
        amount=amount,
        progress_callback=heartbeat,
        task_id=charge_task_id,
        reserve_balance=True,
        timeout=GENERATION_TIMEOUT_SEC,
        commit_on_success=False,
    )

    data = await state.get_data()
    cancel_requested = data.get("cancel_requested", False)
    await state.clear()

    if cancel_requested:
        await charge_manager.release_charge(charge_task_id, reason="cancel")
        await callback.message.answer(
            "🛑 Генерация отменена. Средства не списаны.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")]]
            ),
        )
        return

    if result.get("payment_status") == "insufficient_balance":
        await callback.message.answer(
            "❌ Недостаточно средств. Пополните баланс и попробуйте снова.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="⭐ Баланс / Оплата", callback_data="home:balance")]]
            ),
        )
        return

    if result.get("success"):
        urls = result.get("result_urls") or []
        if urls:
            await callback.message.answer("\n".join(urls))
        commit_result = await charge_manager.commit_charge(charge_task_id)
        if commit_result.get("status") != "committed":
            await callback.message.answer(
                "⚠️ Оплата не подтверждена автоматически. Свяжитесь с поддержкой.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🆘 Поддержка", callback_data="home:support")]]
                ),
            )
        await callback.message.answer(
            "✅ Готово! Хотите ещё варианты?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Ещё 3 варианта", callback_data=f"gen:{model.get('model_id')}")],
                    [InlineKeyboardButton(text="✏️ Изменить оффер/тон", callback_data=f"gen:{model.get('model_id')}")],
                    [InlineKeyboardButton(text="📦 В историю", callback_data="home:history")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
                ]
            ),
        )
    else:
        await callback.message.answer(
            f"❌ Не получилось: {result.get('message', 'ошибка')}\n\n"
            "Средства не списаны / возвращены.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔁 Попробовать ещё раз", callback_data=f"gen:{model.get('model_id')}")],
                    [InlineKeyboardButton(text="🆘 Поддержка", callback_data="home:support")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
                ]
            ),
        )


@router.callback_query(F.data == "gen:cancel", FlowState.generating)
async def generation_cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("generation_cancel", callback.from_user.id, await state.get_state())
    await callback.answer()
    await state.update_data(cancel_requested=True)
    await callback.message.answer("Останавливаем задачу…")


@router.message(FlowState.pick_tool)
async def pick_tool_message(message: Message, state: FSMContext) -> None:
    _log("pick_tool_message", message.from_user.id, await state.get_state())
    data = await state.get_data()
    if not data.get("search_mode"):
        await message.answer(
            "Выберите инструмент из меню или нажмите /start.",
            reply_markup=_home_keyboard(),
        )
        return
    query = (message.text or "").strip().lower()
    if not query:
        await message.answer("Введите слово для поиска.")
        return
    matches = [
        model for model in _models()
        if query in (model.get("model_id", "").lower())
        or query in (model.get("description", "").lower())
    ]
    await state.update_data(search_mode=False)
    if not matches:
        await message.answer("⚠️ Ничего не найдено.", reply_markup=_home_keyboard())
        return
    await message.answer(
        "Результаты поиска:",
        reply_markup=_model_list_keyboard(matches[:10], "home"),
    )


@router.message(FlowState.home)
async def home_message(message: Message, state: FSMContext) -> None:
    _log("home_message", message.from_user.id, await state.get_state())
    await message.answer(_home_text(message.from_user.id), reply_markup=_home_keyboard())


@router.message(FlowState.pick_platform)
async def pick_platform_message(message: Message, state: FSMContext) -> None:
    _log("pick_platform_message", message.from_user.id, await state.get_state())
    await message.answer("Выберите платформу из меню:", reply_markup=_platform_keyboard())


@router.message(FlowState.pick_goal)
async def pick_goal_message(message: Message, state: FSMContext) -> None:
    _log("pick_goal_message", message.from_user.id, await state.get_state())
    await message.answer("Выберите цель из меню:", reply_markup=_goal_keyboard())


@router.message(FlowState.pick_content_type)
async def pick_content_message(message: Message, state: FSMContext) -> None:
    _log("pick_content_message", message.from_user.id, await state.get_state())
    await message.answer("Выберите формат контента:", reply_markup=_content_type_keyboard())


@router.message(FlowState.tool_card)
async def tool_card_message(message: Message, state: FSMContext) -> None:
    _log("tool_card_message", message.from_user.id, await state.get_state())
    await message.answer("Выберите действие кнопками ниже.", reply_markup=_home_keyboard())


@router.message(FlowState.confirm)
async def confirm_message(message: Message, state: FSMContext) -> None:
    _log("confirm_message", message.from_user.id, await state.get_state())
    await message.answer("Подтвердите запуск кнопками ниже.", reply_markup=_home_keyboard())


@router.message(FlowState.generating)
async def generating_message(message: Message, state: FSMContext) -> None:
    _log("generating_message", message.from_user.id, await state.get_state())
    await message.answer("⏳ Генерация уже идёт. Можно отменить в меню.")


async def _show_top_tools(callback: CallbackQuery, state: FSMContext) -> None:
    models = _models()
    scored = sorted(models, key=lambda model: mt.score_model(model, {}), reverse=True)
    top = scored[:5]
    await state.update_data(back_cb="home")
    await state.set_state(FlowState.pick_tool)
    rows = [
        [InlineKeyboardButton(text=presenter.display_name(model), callback_data=f"tool:{model.get('model_id')}")]
        for model in top
    ]
    rows.append([InlineKeyboardButton(text="📚 Все модели", callback_data="catalog:all:0")])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")])
    await callback.message.edit_text(
        "🔥 Топ инструменты",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )

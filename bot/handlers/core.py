"""Core entrypoints for menu navigation."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.utils.runtime_state import runtime_state
from app.payments.charges import get_charge_manager
from bot.handlers import flow

router = Router(name="core")
logger = logging.getLogger(__name__)


def _log(handler: str, user_id: int, state: str | None) -> None:
    logger.info("entered %s user_id=%s state=%s", handler, user_id, state)


async def _show_home(message: Message, state: FSMContext, reset: bool = True) -> None:
    if reset:
        await state.clear()
    await state.set_state(flow.FlowState.home)
    await state.update_data(**flow._context_dict(flow._new_context()))
    await message.answer(flow._home_text(message.from_user.id), reply_markup=flow._home_keyboard())


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext) -> None:
    _log("start", message.from_user.id, await state.get_state())
    if runtime_state.lock_acquired is False:
        await message.answer("⚠️ Сервис перезапускается, попробуйте через 30 сек.")
        return
    charge_manager = get_charge_manager()
    charge_manager.ensure_welcome_credit(message.from_user.id, flow.WELCOME_CREDITS)
    await _show_home(message, state, reset=True)


@router.message(Command("menu"))
async def menu_cmd(message: Message, state: FSMContext) -> None:
    _log("menu", message.from_user.id, await state.get_state())
    await _show_home(message, state, reset=False)


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    _log("cancel", message.from_user.id, await state.get_state())
    data = await state.get_data()
    charge_id = data.get("pending_charge_id")
    if charge_id:
        await get_charge_manager().release_charge(charge_id, reason="cancel")
    await _show_home(message, state, reset=True)


@router.callback_query(F.data == "home")
async def home_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("home_cb", callback.from_user.id, await state.get_state())
    await callback.answer()
    await _show_home(callback.message, state, reset=True)


@router.callback_query(F.data == "back")
async def back_cb(callback: CallbackQuery, state: FSMContext) -> None:
    _log("back_cb", callback.from_user.id, await state.get_state())
    await callback.answer()
    await _show_home(callback.message, state, reset=False)

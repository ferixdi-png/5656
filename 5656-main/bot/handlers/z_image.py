"""
Z-Image handler for SINGLE_MODEL mode.

Provides simple flow:
1. User clicks "Создать картинку"
2. Bot asks for prompt
3. User sends prompt
4. Bot generates via Kie.ai z-image
5. Bot sends result
"""

import asyncio
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.kie.z_image_client import get_z_image_client, TaskStatus

logger = logging.getLogger(__name__)
router = Router(name="z_image")


class ZImageStates(StatesGroup):
    """States for z-image flow."""
    waiting_prompt = State()
    waiting_aspect_ratio = State()


ASPECT_RATIOS = {
    "1:1": "Квадрат 1:1",
    "16:9": "Широкий 16:9",
    "9:16": "Вертикальный 9:16",
    "4:3": "Классический 4:3",
    "3:4": "Портрет 3:4",
}


@router.callback_query(F.data == "zimage:start")
async def zimage_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start z-image generation flow (master input style)."""
    from app.ux.copy_ru import t
    
    await callback.answer()
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


@router.message(ZImageStates.waiting_prompt)
async def zimage_prompt(message: Message, state: FSMContext) -> None:
    """Handle prompt input."""
    prompt = message.text.strip()
    
    if not prompt or len(prompt) < 3:
        await message.answer(
            "❌ Описание слишком короткое. Попробуйте ещё раз:"
        )
        return
    
    # Store prompt
    await state.update_data(prompt=prompt)
    await state.set_state(ZImageStates.waiting_aspect_ratio)
    
    # Ask for aspect ratio
    keyboard = []
    for ratio, label in ASPECT_RATIOS.items():
        keyboard.append([InlineKeyboardButton(
            text=label, 
            callback_data=f"zimage:ratio:{ratio}"
        )])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="zimage:start")])
    
    from app.ux.copy_ru import t
    
    await message.answer(
        f"{t('step_ratio_title', current=2, total=3)}\n\n"
        f"{t('step_ratio_explanation')}\n\n"
        f"📝 <b>Ваш запрос:</b>\n<i>{prompt[:100]}</i>\n\n"
        f"<i>{t('step_ratio_next')}</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@router.callback_query(F.data.startswith("zimage:ratio:"))
async def zimage_generate(callback: CallbackQuery, state: FSMContext) -> None:
    """Generate image with selected aspect ratio."""
    # CRITICAL: None checks
    if not callback.from_user:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[ZIMAGE] callback.from_user is None in zimage_generate")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[ZIMAGE] callback.message is None in zimage_generate")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    
    ratio = callback.data.split(":", 2)[2]
    if ratio not in ASPECT_RATIOS:
        ratio = "1:1"
    
    # Get stored data
    data = await state.get_data()
    prompt = data.get("prompt", "")
    
    if not prompt:
        await callback.message.edit_text(
            "❌ Ошибка: промпт не найден. Начните заново:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🖼 Создать картинку", callback_data="zimage:start")]
            ])
        )
        await state.clear()
        return
    
    # BATCH 48.44: Check free model limits before generation
    from bot.handlers.marketing import _get_free_manager
    free_manager = _get_free_manager()
    if free_manager:
        # CRITICAL: Use check_limits_and_reserve for atomic limit check + usage logging
        limits_check = await free_manager.check_limits_and_reserve(
            callback.from_user.id, 
            "z-image", 
            job_id=None  # Will be set later when job is created
        )
        
        if not limits_check['allowed']:
            reason = limits_check['reason']
            text = ""
            if reason == 'daily_limit_exceeded':
                text = (
                    f"⏰ <b>Лимит исчерпан</b>\n\n"
                    f"Вы использовали все бесплатные генерации Z-Image на сегодня.\n\n"
                    f"Использовано: {limits_check['daily_used']}/{limits_check['daily_limit']}\n\n"
                    f"Вы можете:\n"
                    f"• Подождать до завтра\n"
                    f"• Пригласить друга, чтобы увеличить лимит!"
                )
            elif reason == 'hourly_limit_exceeded':
                text = (
                    f"⏰ <b>Временный лимит</b>\n\n"
                    f"Достигнут часовой лимит для Z-Image.\n\n"
                    f"Использовано: {limits_check['hourly_used']}/{limits_check['hourly_limit']}\n\n"
                    f"Попробуйте через час или пригласите друга, чтобы увеличить лимит!"
                )
            else:
                text = "❌ Лимит использования Z-Image исчерпан"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="menu:referral")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
            await callback.message.edit_text(text, reply_markup=keyboard)
            await state.clear()
            return
    
    # Clear state (generation complete)
    await state.clear()
    
    # Show "generating" message
    status_msg = await callback.message.edit_text(
        f"⏳ <b>Генерирую изображение...</b>\n\n"
        f"📝 Запрос: <i>{prompt[:100]}</i>\n"
        f"📐 Формат: {ASPECT_RATIOS[ratio]}\n\n"
        f"⏱ Это займёт 10-30 секунд",
        reply_markup=None
    )
    
    # Get z-image client
    client = get_z_image_client()
    
    # Build callback URL for async completion notification
    callback_url = None
    try:
        from app.utils.webhook import build_kie_callback_url, get_webhook_base_url
        webhook_base = get_webhook_base_url()
        if webhook_base:
            callback_url = build_kie_callback_url(webhook_base, None)  # Will use default path
            if callback_url:
                logger.info(f"[ZIMAGE] Using callback_url={callback_url[:60]}... for task_id (will be set after create)")
            else:
                logger.warning(f"[ZIMAGE] Failed to build callback URL (will use polling only)")
    except Exception as e:
        logger.warning(f"[ZIMAGE] Failed to build callback URL (will use polling only): {e}")
    
    try:
        # Create task with callback URL for async completion
        result = await client.create_task(
            prompt=prompt,
            aspect_ratio=ratio,
            callback_url=callback_url,
        )
        
        task_id = result.task_id
        
        logger.info(f"[ZIMAGE] Task created: task_id={task_id}, prompt={prompt[:50]}, ratio={ratio}, callback_url={'set' if callback_url else 'none'}")
        
        # Create job in storage so callback handler can find it and deliver result
        user_id = callback.from_user.id if callback.from_user else None
        chat_id = callback.message.chat.id if callback.message else None
        if user_id:
            try:
                from app.storage import get_storage
                storage = get_storage()
                # Ensure user exists
                await storage.ensure_user(
                    user_id=user_id,
                    username=callback.from_user.username if callback.from_user else None,
                    first_name=callback.from_user.first_name if callback.from_user else None,
                )
                # Create job for callback handler
                job_id = await storage.add_generation_job(
                    user_id=user_id,
                    model_id="z-image",
                    model_name="z-image",
                    params={
                        "prompt": prompt,
                        "aspect_ratio": ratio,
                        "chat_id": chat_id,
                    },
                    price=0.0,  # z-image is free
                    task_id=task_id,
                    status="running",
                    chat_id=chat_id  # BATCH 48.44: Pass chat_id for result delivery
                )
                logger.info(f"[ZIMAGE] Job created in storage: job_id={job_id}, task_id={task_id}")
                
                # BATCH 48.44: Log free usage with job_id
                if free_manager:
                    await free_manager.log_usage(callback.from_user.id, "z-image", job_id)
                    logger.info(f"[ZIMAGE] Free usage logged for z-image: user={callback.from_user.id}, job={job_id}")
            except Exception as storage_error:
                logger.warning(f"[ZIMAGE] Failed to create job in storage (callback may not work): {storage_error}")
                # Continue with polling - job creation is optional for z-image
        
        # Update status
        await status_msg.edit_text(
            f"⏳ <b>Генерация запущена</b>\n\n"
            f"🆔 ID: <code>{task_id}</code>\n"
            f"📝 Запрос: <i>{prompt[:100]}</i>\n\n"
            f"⏱ Ожидайте результат...",
        )
        
        # Poll for completion (max 5 minutes) with progress logging
        logger.info(f"[ZIMAGE] Starting polling for task_id={task_id}, max_wait=300s, poll_interval=3s")
        try:
            final_result = await client.poll_until_complete(
                task_id=task_id,
                max_wait=300.0,
                poll_interval=3.0,
            )
            logger.info(f"[ZIMAGE] Polling completed: task_id={task_id}, status={final_result.status.value}")
        except Exception as poll_error:
            logger.error(f"[ZIMAGE] Polling failed for task_id={task_id}: {poll_error}")
            # Try to get final status once more
            try:
                final_result = await client.get_task_status(task_id)
                logger.info(f"[ZIMAGE] Final status check: task_id={task_id}, status={final_result.status.value}")
            except Exception as status_error:
                logger.error(f"[ZIMAGE] Failed to get final status: {status_error}")
                raise poll_error
        
        # Check result
        if final_result.status == TaskStatus.SUCCESS and final_result.image_url:
            # Send image
            await callback.message.answer_photo(
                photo=final_result.image_url,
                caption=f"✅ <b>Готово!</b>\n\n"
                        f"📝 Запрос: <i>{prompt[:100]}</i>\n"
                        f"🆔 ID: <code>{task_id}</code>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🖼 Создать ещё", callback_data="zimage:start")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ])
            )
            
            # Delete status message
            try:
                await status_msg.delete()
            except Exception as e:
                logger.debug(f"[Z_IMAGE] Failed to delete status message: {e}")
        
        elif final_result.status == TaskStatus.FAILED:
            error_text = final_result.error or "Неизвестная ошибка"
            await status_msg.edit_text(
                f"❌ <b>Ошибка генерации</b>\n\n"
                f"🆔 ID: <code>{task_id}</code>\n"
                f"📝 Запрос: <i>{prompt[:100]}</i>\n\n"
                f"❗️ {error_text}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="zimage:start")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ])
            )
        
        else:
            # Unknown status
            await status_msg.edit_text(
                f"⚠️ <b>Неожиданный статус</b>\n\n"
                f"🆔 ID: <code>{task_id}</code>\n"
                f"📊 Статус: {final_result.status.value}\n\n"
                f"Попробуйте снова или обратитесь в поддержку.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="zimage:start")],
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
                ])
            )
    
    except asyncio.TimeoutError:
        await status_msg.edit_text(
            f"⏱ <b>Таймаут генерации</b>\n\n"
            f"📝 Запрос: <i>{prompt[:100]}</i>\n\n"
            f"Генерация заняла слишком много времени (>5 минут).\n"
            f"Попробуйте упростить запрос или попробуйте снова позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="zimage:start")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
            ])
        )
    
    except Exception as exc:
        logger.exception(f"[ZIMAGE] Generation failed: {exc}")
        
        await status_msg.edit_text(
            f"❌ <b>Ошибка</b>\n\n"
            f"📝 Запрос: <i>{prompt[:100]}</i>\n\n"
            f"Не удалось создать изображение: {str(exc)[:200]}\n\n"
            f"Попробуйте снова или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="zimage:start")],
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
            ])
        )

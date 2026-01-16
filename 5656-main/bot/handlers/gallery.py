"""
Enhanced model gallery with examples - Syntx-like experience
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from app.telemetry.telemetry_helpers import (
    log_callback_received, log_callback_routed, log_callback_accepted,
    log_callback_rejected, log_ui_render
)
from app.telemetry.logging_contract import ReasonCode
from app.telemetry.ui_registry import ScreenId, ButtonId
import json
from pathlib import Path

router = Router(name="gallery")

# Load recommendations
RECOMMENDATIONS_PATH = Path("artifacts/model_recommendations.json")

def load_recommendations():
    """Load model recommendations"""
    if not RECOMMENDATIONS_PATH.exists():
        return {}
    with open(RECOMMENDATIONS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# Example prompts gallery for popular models
EXAMPLE_GALLERY = {
    "flux-2/flex-text-to-image": {
        "name": "Flux-2 Text to Image",
        "examples": [
            {
                "prompt": "Неоновый баннер для Instagram, стиль киберпанк, тёмный фон",
                "use_case": "Пост для Instagram",
                "description": "Идеально для соцсетей"
            },
            {
                "prompt": "Логотип для стартапа в сфере AI, минимализм, векторный стиль",
                "use_case": "Дизайн логотипа",
                "description": "Для бизнеса"
            },
            {
                "prompt": "Обложка для YouTube видео про путешествия, яркие цвета",
                "use_case": "Обложка для YouTube",
                "description": "Для YouTube"
            }
        ]
    },
    "sora-2-text-to-video": {
        "name": "Sora2 Text to Video",
        "examples": [
            {
                "prompt": "Таймлапс восхода солнца над океаном, 5 секунд",
                "use_case": "Reels/TikTok",
                "description": "Для коротких видео"
            },
            {
                "prompt": "Анимация логотипа с эффектом появления, 3 секунды",
                "use_case": "Интро/Аутро",
                "description": "Для видео-интро"
            }
        ]
    },
    "z-image": {
        "name": "Z-Image (БЕСПЛАТНО)",
        "examples": [
            {
                "prompt": "Красивый закат на пляже",
                "use_case": "Общее использование",
                "description": "Бесплатно!"
            }
        ]
    }
}


@router.callback_query(F.data == "gallery:trending")
async def show_trending_gallery(callback: CallbackQuery, state: FSMContext, cid=None, bot_state=None):
    """Show trending models with example gallery"""
    # CRITICAL: None checks
    if not callback.from_user:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[GALLERY] callback.from_user is None in show_trending_gallery")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[GALLERY] callback.message is None in show_trending_gallery")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    
    recs = load_recommendations()
    trending = recs.get('quick_actions', {}).get('trending', [])
    
    if not trending:
        await callback.message.edit_text(
            "🔥 <b>Популярные модели</b>\n\n"
            "Скоро появятся популярные модели!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )
        return
    
    # Build gallery buttons
    buttons = []
    for model_id in trending[:5]:  # Top 5 trending
        model_name = model_id.split('/')[-1].replace('-', ' ').title()
        buttons.append([
            InlineKeyboardButton(
                text=f"🔥 {model_name}",
                callback_data=f"gallery:show:{model_id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "🔥 <b>Популярные сейчас</b>\n\n"
        "Самые популярные модели с примерами использования:\n\n"
        "👆 Выберите модель чтобы посмотреть примеры",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("gallery:show:"))
async def show_model_gallery(callback: CallbackQuery, state: FSMContext, cid=None, bot_state=None, data: dict = None):
    """Show example gallery for specific model"""
    # CRITICAL: None checks
    if not callback.from_user:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[GALLERY] callback.from_user is None in show_model_gallery")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[GALLERY] callback.message is None in show_model_gallery")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    from app.utils.correlation import ensure_correlation_id
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    # Get cid from data or generate
    if cid is None and data:
        cid = data.get("cid")
    if cid is None:
        cid = ensure_correlation_id(str(callback.id))
    
    # Get bot_state from data
    if bot_state is None and data:
        bot_state = data.get("bot_state")

    if cid:
        log_callback_received(cid, callback.id, user_id, chat_id, "gallery:trending", bot_state)
        log_callback_routed(cid, user_id, chat_id, "show_trending_gallery", "gallery:trending", ButtonId.UNKNOWN)

    await callback.answer()
    
    model_id = callback.data.split(":", 2)[2]
    gallery = EXAMPLE_GALLERY.get(model_id, {})
    
    if not gallery:
        await callback.message.edit_text(
            f"📸 <b>Примеры для {model_id}</b>\n\n"
            "Скоро добавим примеры использования!\n\n"
            "А пока можете попробовать создать что-то своё 🎨",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Попробовать", callback_data=f"model:{model_id}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="gallery:trending")]
            ])
        )
        return
    
    examples = gallery.get('examples', [])
    name = gallery.get('name', model_id)
    
    # Build examples text
    examples_text = f"✨ <b>{name}</b>\n\n<b>Примеры использования:</b>\n\n"
    
    for idx, ex in enumerate(examples, 1):
        examples_text += (
            f"{idx}. <b>{ex['use_case']}</b>\n"
            f"   <i>{ex['description']}</i>\n"
            f"   Prompt: \"{ex['prompt']}\"\n\n"
        )
    
    examples_text += "💡 Выберите пример или создайте свой!"
    
    # Build buttons - examples + try button
    buttons = []
    for idx, ex in enumerate(examples):
        buttons.append([
            InlineKeyboardButton(
                text=f"✨ {ex['use_case']}",
                callback_data=f"example:use:{model_id}:{idx}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="🎨 Свой промпт", callback_data=f"model:{model_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="gallery:trending")
    ])
    
    await callback.message.edit_text(
        examples_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("example:use:"))
async def use_example(callback: CallbackQuery, state: FSMContext):
    """Use example prompt directly"""
    # CRITICAL: None checks
    if not callback.from_user:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[GALLERY] callback.from_user is None in use_example")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[GALLERY] callback.message is None in use_example")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer("Используем пример!")
    
    parts = callback.data.split(":")
    model_id = parts[2]
    example_idx = int(parts[3])
    
    gallery = EXAMPLE_GALLERY.get(model_id, {})
    examples = gallery.get('examples', [])
    
    if example_idx >= len(examples):
        await callback.message.answer("⚠️ Пример не найден")
        return
    
    example = examples[example_idx]
    prompt = example['prompt']
    
    # Pre-fill prompt and redirect to generation
    await state.update_data(
        model_id=model_id,
        prompt=prompt,
        from_example=True
    )
    
    # Show confirmation with pre-filled prompt
    await callback.message.edit_text(
        f"✨ <b>Создаём с примером!</b>\n\n"
        f"<b>Модель:</b> {gallery.get('name', model_id)}\n"
        f"<b>Промпт:</b> {prompt}\n\n"
        f"Начинаем генерацию?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, создать!", callback_data=f"gen:{model_id}")],
            [InlineKeyboardButton(text="✏️ Изменить промпт", callback_data=f"model:{model_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"gallery:show:{model_id}")]
        ])
    )


@router.callback_query(F.data == "gallery:free")
async def show_free_models(callback: CallbackQuery, state: FSMContext, cid=None, bot_state=None):
    # CRITICAL: None checks
    if not callback.from_user:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[GALLERY] callback.from_user is None in show_free_models")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("[GALLERY] callback.message is None in show_free_models")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    if cid:
        log_callback_received(cid, callback.id, user_id, chat_id, "gallery:free", bot_state)
        log_callback_routed(cid, user_id, chat_id, "show_free_models", "gallery:free", ButtonId.UNKNOWN)

    """Show FREE models with real model names from catalog"""
    await callback.answer()
    
    # BATCH 48.48: Get free models from FreeModelManager with real names
    try:
        from app.free.manager import FreeModelManager
        from app.services.wiring import get_free_manager
        from bot.handlers.flow import _get_models_list
        
        free_manager = get_free_manager()
        if not free_manager:
            # Fallback to recommendations if manager not available
            recs = load_recommendations()
            free_model_ids = recs.get('quick_actions', {}).get('free', [])
        else:
            free_models_list = await free_manager.get_all_free_models()
            free_model_ids = [fm['model_id'] for fm in free_models_list]
        
        if not free_model_ids:
            await callback.message.edit_text(
                "🆓 <b>Бесплатные модели</b>\n\n"
                "⚠️ Сейчас нет доступных бесплатных моделей.\n"
                "Следите за обновлениями!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
                ])
            )
            return
        
        # Get full model info from catalog to get real display names
        all_models = _get_models_list()
        free_models = [m for m in all_models if m.get("model_id") in free_model_ids]
        
        # Build buttons with real model names
        buttons = []
        for model in free_models:
            # Use display_name if available, otherwise use model_id
            display_name = model.get("display_name") or model.get("name") or model.get("model_id")
            # Fallback: format model_id nicely if no display_name
            if not display_name or display_name == model.get("model_id"):
                # Try to extract readable name from model_id
                model_id = model.get("model_id", "")
                if "/" in model_id:
                    display_name = model_id.split("/")[-1].replace("-", " ").replace("_", " ").title()
                else:
                    display_name = model_id.replace("-", " ").replace("_", " ").title()
            
            # Truncate long names
            if len(display_name) > 35:
                display_name = display_name[:32] + "..."
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"🆓 {display_name}",
                    callback_data=f"model:{model.get('model_id')}"
                )
            ])
        
        buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
        
        await callback.message.edit_text(
            "🆓 <b>Бесплатные модели</b>\n\n"
            "🎨 Попробуйте без списания баланса!\n\n"
            "✨ Полностью бесплатно\n"
            "⚡️ 5 генераций в час\n"
            "💯 Высокое качество\n\n"
            "Выберите модель:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to show free models: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Ошибка при загрузке бесплатных моделей",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
            ])
        )

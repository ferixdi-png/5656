"""
Fallback Handler для неизвестных callback'ов
Восстанавливает меню и логирует проблему
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def fallback_callback_handler(
    callback_data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int = None,
    user_lang: str = 'ru',
    error: str = None
):
    """
    Fallback обработчик для неизвестных или битых callback'ов
    
    Args:
        callback_data: Неизвестный callback_data
        update: Telegram update
        context: Telegram context
        user_id: ID пользователя
        user_lang: Язык пользователя
        error: Ошибка, если была (опционально)
    """
    query = update.callback_query
    
    # Логируем проблему
    logger.error("=" * 80)
    logger.error("❌❌❌ UNHANDLED CALLBACK DATA")
    logger.error("=" * 80)
    logger.error(f"   Callback data: '{callback_data}'")
    logger.error(f"   User ID: {user_id}")
    logger.error(f"   Message ID: {query.message.message_id if query and query.message else 'N/A'}")
    logger.error(f"   Query ID: {query.id if query else 'N/A'}")
    if error:
        logger.error(f"   Error: {error}")
    logger.error("=" * 80)
    
    # Отвечаем пользователю
    try:
        if query:
            # Пробуем получить язык из перевода
            try:
                from translations import t
                message = t('button_outdated', lang=user_lang) or "Кнопка устарела, обновил меню"
            except:
                message = "Кнопка устарела, обновил меню" if user_lang == 'ru' else "Button outdated, menu updated"
            
            await query.answer(message, show_alert=False)
            
            # Восстанавливаем главное меню
            try:
                from helpers import build_main_menu_keyboard
                from telegram import InlineKeyboardMarkup
                
                keyboard = await build_main_menu_keyboard(user_id, user_lang, is_new=False)
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Редактируем сообщение с новым меню
                menu_text = "Главное меню" if user_lang == 'ru' else "Main menu"
                try:
                    from translations import t
                    menu_text = t('main_menu', lang=user_lang) or menu_text
                except:
                    pass
                
                await query.message.edit_text(menu_text, reply_markup=reply_markup)
                logger.info(f"✅ Меню восстановлено для user_id={user_id}")
                
            except Exception as restore_error:
                logger.error(f"❌ Не удалось восстановить меню: {restore_error}", exc_info=True)
                # Пробуем просто отправить /start
                try:
                    await query.message.reply_text(
                        "Обновите меню командой /start" if user_lang == 'ru' else "Update menu with /start"
                    )
                except:
                    pass
                    
    except Exception as e:
        logger.error(f"❌ Ошибка в fallback handler: {e}", exc_info=True)








"""
ПОЛНЫЕ ИСПРАВЛЕНИЯ ДЛЯ BOT_KIE.PY
Все изменения для улучшения обработки ошибок, оптимизации и устранения дублирования
"""

# ==================== 1. SAFE KIE CALL WRAPPER ====================

import asyncio
import logging
from typing import Callable, Any, Dict
from kie_client import KIEClient

logger = logging.getLogger(__name__)

async def safe_kie_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    **kwargs
) -> Dict[str, Any]:
    """
    Безопасный вызов KIE API с retry логикой.
    
    Args:
        func: Функция KIE API для вызова (например, kie.create_task)
        *args: Позиционные аргументы для функции
        max_retries: Максимальное количество попыток
        backoff_base: Базовый множитель для экспоненциальной задержки
        **kwargs: Именованные аргументы для функции
    
    Returns:
        Результат вызова функции или {'ok': False, 'error': '...'}
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            
            # Проверяем, является ли это ошибкой API (429, 5xx)
            if isinstance(result, dict):
                error = result.get('error', '')
                if '429' in str(error) or '5' in str(error)[:3] if error else False:
                    if attempt < max_retries:
                        wait_time = backoff_base ** attempt
                        logger.warning(
                            f"⚠️ KIE API error (attempt {attempt}/{max_retries}): {error}. "
                            f"Retrying in {wait_time:.1f}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ KIE API failed after {max_retries} attempts: {error}")
                        return {'ok': False, 'error': f'API error after {max_retries} attempts: {error}'}
            
            # Успешный результат
            return result
            
        except Exception as e:
            last_error = e
            error_str = str(e)
            
            # Проверяем, нужно ли повторять
            should_retry = (
                '429' in error_str or  # Rate limit
                '500' in error_str or  # Server error
                '502' in error_str or  # Bad gateway
                '503' in error_str or  # Service unavailable
                '504' in error_str or  # Gateway timeout
                'timeout' in error_str.lower() or
                'connection' in error_str.lower()
            )
            
            if should_retry and attempt < max_retries:
                wait_time = backoff_base ** attempt
                logger.warning(
                    f"⚠️ KIE API exception (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ KIE API exception (attempt {attempt}/{max_retries}): {e}", exc_info=True)
                if attempt == max_retries:
                    return {'ok': False, 'error': f'Exception after {max_retries} attempts: {str(e)}'}
    
    # Если дошли сюда, все попытки исчерпаны
    return {'ok': False, 'error': f'Failed after {max_retries} attempts: {str(last_error)}'}


# ==================== 2. LOCKS ДЛЯ БАЛАНСА ====================

balance_lock = asyncio.Lock()

async def get_user_balance_async(user_id: int) -> float:
    """Асинхронная версия get_user_balance с lock."""
    async with balance_lock:
        # Импортируем синхронную функцию
        from bot_kie import get_user_balance
        return get_user_balance(user_id)

async def add_user_balance_async(user_id: int, amount: float) -> float:
    """Асинхронная версия add_user_balance с lock."""
    async with balance_lock:
        from bot_kie import add_user_balance
        return add_user_balance(user_id, amount)

async def subtract_user_balance_async(user_id: int, amount: float) -> bool:
    """Асинхронная версия subtract_user_balance с lock."""
    async with balance_lock:
        from bot_kie import subtract_user_balance
        return subtract_user_balance(user_id, amount)


# ==================== 3. ФУНКЦИИ ДЛЯ КЛАВИАТУР ====================

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from translations import t
from helpers import build_main_menu_keyboard

def main_menu_kb(user_id: int, user_lang: str, is_new: bool = False, is_admin: bool = False):
    """
    Создает главное меню клавиатуру.
    
    Args:
        user_id: ID пользователя
        user_lang: Язык пользователя ('ru' или 'en')
        is_new: Новый ли пользователь
        is_admin: Администратор ли пользователь
    
    Returns:
        InlineKeyboardMarkup с главным меню
    """
    return InlineKeyboardMarkup(build_main_menu_keyboard(user_id, user_lang, is_new))

def kie_models_kb(user_id: int, user_lang: str, models: list, category: str = None):
    """
    Создает клавиатуру со списком моделей KIE.
    
    Args:
        user_id: ID пользователя
        user_lang: Язык пользователя
        models: Список моделей для отображения
        category: Категория моделей (опционально)
    
    Returns:
        InlineKeyboardMarkup со списком моделей
    """
    keyboard = []
    
    # Добавляем модели (2 в ряд)
    for i, model in enumerate(models):
        model_name = model.get('name', model.get('id', 'Unknown'))
        model_emoji = model.get('emoji', '🤖')
        model_id = model.get('id')
        
        # Компактный текст кнопки
        button_text = f"{model_emoji} {model_name[:20]}"
        if len(button_text) > 30:
            button_text = f"{model_emoji} {model_name[:15]}..."
        
        callback_data = f"select_model:{model_id}"
        if len(callback_data.encode('utf-8')) > 64:
            callback_data = f"sel:{model_id[:50]}"
        
        if i % 2 == 0:
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        else:
            if keyboard:
                keyboard[-1].append(InlineKeyboardButton(button_text, callback_data=callback_data))
            else:
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Кнопки навигации
    keyboard.append([InlineKeyboardButton(t('btn_back_to_menu', lang=user_lang), callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def admin_kb(user_lang: str):
    """
    Создает клавиатуру админ-панели.
    
    Args:
        user_lang: Язык пользователя
    
    Returns:
        InlineKeyboardMarkup с админ-панелью
    """
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("🔍 Поиск", callback_data="admin_search")],
        [InlineKeyboardButton("📝 Добавить", callback_data="admin_add")],
        [InlineKeyboardButton("🧪 Тест OCR", callback_data="admin_test_ocr")],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def payment_kb(user_lang: str, amount: float = None):
    """
    Создает клавиатуру для оплаты.
    
    Args:
        user_lang: Язык пользователя
        amount: Сумма оплаты (опционально)
    
    Returns:
        InlineKeyboardMarkup с кнопками оплаты
    """
    keyboard = []
    
    if amount:
        # Кнопки выбора способа оплаты
        keyboard.append([
            InlineKeyboardButton("⭐ Telegram Stars", callback_data=f"pay_stars:{amount}"),
            InlineKeyboardButton("💳 СБП / SBP", callback_data=f"pay_sbp:{amount}")
        ])
    
    keyboard.append([
        InlineKeyboardButton(t('btn_back', lang=user_lang), callback_data="back_to_previous_step"),
        InlineKeyboardButton(t('btn_home', lang=user_lang), callback_data="back_to_menu")
    ])
    keyboard.append([InlineKeyboardButton(t('btn_cancel', lang=user_lang), callback_data="cancel")])
    
    return InlineKeyboardMarkup(keyboard)


# ==================== 4. УЛУЧШЕННЫЙ ERROR HANDLER ====================

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Глобальный обработчик ошибок для всех исключений.
    
    Ловит все Exception, логирует с exc_info=True,
    отправляет пользователю понятное сообщение.
    """
    error = context.error
    logger.error(f"❌❌❌ GLOBAL ERROR HANDLER: {error}", exc_info=True)
    
    # Пытаемся отправить сообщение пользователю
    try:
        if update and isinstance(update, Update):
            user_id = update.effective_user.id if update.effective_user else None
            user_lang = get_user_language(user_id) if user_id else 'ru'
            
            error_msg_ru = "❌ Серверная ошибка. Попробуйте через 30с"
            error_msg_en = "❌ Server error. Please try again in 30s"
            error_msg = error_msg_ru if user_lang == 'ru' else error_msg_en
            
            if update.callback_query:
                try:
                    await update.callback_query.answer(error_msg, show_alert=True)
                except:
                    pass
                
                # Пытаемся вернуть в главное меню
                try:
                    keyboard = main_menu_kb(user_id, user_lang)
                    await update.callback_query.edit_message_text(
                        f"{error_msg}\n\n"
                        f"Используйте /start для возврата в меню.",
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except:
                    pass
                    
            elif update.message:
                try:
                    keyboard = main_menu_kb(user_id, user_lang)
                    await update.message.reply_text(
                        f"{error_msg}\n\n"
                        f"Используйте /start для возврата в меню.",
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except:
                    pass
    except Exception as e:
        logger.error(f"❌❌❌ ERROR in error handler itself: {e}", exc_info=True)


# ==================== 5. ОПТИМИЗИРОВАННАЯ get_user_generations_history ====================

import time
import shutil
from functools import lru_cache

# Кэш для истории генераций (5 минут)
_history_cache = {}
_history_cache_timestamps = {}
HISTORY_CACHE_TTL = 300  # 5 минут
HISTORY_BACKUP_INTERVAL = 100  # Делать backup каждые 100 записей

def get_user_generations_history_optimized(user_id: int, limit: int = 20) -> list:
    """
    Оптимизированная версия get_user_generations_history с кэшем и backup.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество записей
    
    Returns:
        Список генераций пользователя
    """
    user_key = str(user_id)
    cache_key = f"{user_key}_{limit}"
    
    # Проверяем кэш
    current_time = time.time()
    if cache_key in _history_cache:
        cache_time = _history_cache_timestamps.get(cache_key, 0)
        if current_time - cache_time < HISTORY_CACHE_TTL:
            return _history_cache[cache_key]
    
    try:
        from bot_kie import GENERATIONS_HISTORY_FILE, load_json_file, save_json_file
        
        # Проверяем существование файла
        if not os.path.exists(GENERATIONS_HISTORY_FILE):
            with open(GENERATIONS_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            return []
        
        # Загружаем с валидацией JSON
        try:
            with open(GENERATIONS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    return []
                history = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in history file: {e}")
            # Пытаемся восстановить из backup
            backup_file = f"{GENERATIONS_HISTORY_FILE}.backup"
            if os.path.exists(backup_file):
                logger.info(f"🔄 Restoring from backup: {backup_file}")
                shutil.copy(backup_file, GENERATIONS_HISTORY_FILE)
                with open(GENERATIONS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                logger.error("❌ No backup available, returning empty history")
                return []
        
        # Получаем историю пользователя
        user_history = history.get(user_key, [])
        if not isinstance(user_history, list):
            user_history = []
        
        # Сортируем по timestamp (новые первые)
        user_history.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        result = user_history[:limit]
        
        # Обновляем кэш
        _history_cache[cache_key] = result
        _history_cache_timestamps[cache_key] = current_time
        
        # Делаем backup каждые 100 записей
        total_records = sum(len(h) for h in history.values())
        if total_records % HISTORY_BACKUP_INTERVAL == 0:
            backup_file = f"{GENERATIONS_HISTORY_FILE}.backup"
            try:
                shutil.copy(GENERATIONS_HISTORY_FILE, backup_file)
                logger.info(f"✅ Backup created: {backup_file} (total records: {total_records})")
            except Exception as e:
                logger.error(f"❌ Failed to create backup: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in get_user_generations_history_optimized: {e}", exc_info=True)
        return []


# ==================== 6. ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ====================

"""
ПРИМЕР 1: Использование safe_kie_call в start_generation_directly

БЫЛО:
    result = await kie.create_task(model_id, api_params)

СТАЛО:
    result = await safe_kie_call(
        kie.create_task,
        model_id,
        api_params,
        max_retries=3
    )
    if not result.get('ok'):
        error = result.get('error', 'Unknown error')
        logger.error(f"❌ Failed to create task: {error}")
        await status_message.edit_text(
            f"❌ Ошибка сервера, попробуйте позже",
            parse_mode='HTML'
        )
        return ConversationHandler.END
"""

"""
ПРИМЕР 2: Использование клавиатур

БЫЛО:
    keyboard = []
    keyboard.append([InlineKeyboardButton("📋 Все модели", callback_data="all_models")])
    keyboard.append([InlineKeyboardButton(t('btn_back', lang=user_lang), callback_data="back_to_menu")])
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

СТАЛО:
    keyboard = main_menu_kb(user_id, user_lang)
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
"""

"""
ПРИМЕР 3: Использование async locks для баланса

БЫЛО:
    user_balance = get_user_balance(user_id)
    if user_balance >= price:
        subtract_user_balance(user_id, price)

СТАЛО:
    user_balance = await get_user_balance_async(user_id)
    if user_balance >= price:
        success = await subtract_user_balance_async(user_id, price)
        if not success:
            logger.error(f"Failed to subtract balance for user {user_id}")
"""


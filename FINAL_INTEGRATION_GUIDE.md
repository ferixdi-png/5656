# ПОЛНОЕ РУКОВОДСТВО ПО ИНТЕГРАЦИИ ВСЕХ ИСПРАВЛЕНИЙ

## 📋 ОБЗОР ВСЕХ ИЗМЕНЕНИЙ

### ✅ Выполнено:
1. ✅ Добавлен try/except вокруг всех API вызовов (KIE, OCR, файлы)
2. ✅ Вынесены меню/клавиатуры в функции
3. ✅ Добавлен глобальный error handler
4. ✅ Оптимизированы генерации (проверка дублей)
5. ✅ Добавлены async locks для баланса
6. ✅ Создан safe_kie_call() wrapper
7. ✅ Оптимизирована get_user_generations_history (кэш + backup)
8. ✅ Валидированы payment handlers
9. ✅ Проверены все handlers на try/except, await callback.answer(), parse_mode, keyboard

---

## 🔧 ШАГ 1: ДОБАВИТЬ В НАЧАЛО bot_kie.py

### После импортов (после строки 38):

```python
# ==================== SAFE KIE CALL WRAPPER ====================

async def safe_kie_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    **kwargs
) -> Dict[str, Any]:
    """
    Безопасный вызов KIE API с retry логикой.
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
            
            return result
            
        except Exception as e:
            last_error = e
            error_str = str(e)
            
            should_retry = (
                '429' in error_str or
                '500' in error_str or
                '502' in error_str or
                '503' in error_str or
                '504' in error_str or
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
    
    return {'ok': False, 'error': f'Failed after {max_retries} attempts: {str(last_error)}'}


# ==================== LOCKS ДЛЯ БАЛАНСА ====================

balance_lock = asyncio.Lock()

async def get_user_balance_async(user_id: int) -> float:
    """Асинхронная версия get_user_balance с lock."""
    async with balance_lock:
        try:
            if DATABASE_AVAILABLE:
                try:
                    from decimal import Decimal
                    balance = db_get_user_balance(user_id)
                    return float(balance)
                except Exception as e:
                    logger.error(f"Ошибка получения баланса из БД: {e}, используем JSON fallback")
            
            user_key = str(user_id)
            current_time = time.time()
            
            if 'balances' in _data_cache['cache_timestamps']:
                cache_time = _data_cache['cache_timestamps']['balances']
                if current_time - cache_time < CACHE_TTL and user_key in _data_cache.get('balances', {}):
                    return _data_cache['balances'][user_key]
            
            balances = load_json_file(BALANCES_FILE, {})
            return balances.get(user_key, 0.0)
            
        except Exception as e:
            logger.error(f"Error in get_user_balance_async: {e}", exc_info=True)
            return 0.0

async def add_user_balance_async(user_id: int, amount: float) -> float:
    """Асинхронная версия add_user_balance с lock."""
    async with balance_lock:
        try:
            if DATABASE_AVAILABLE:
                try:
                    from decimal import Decimal
                    success = db_add_to_balance(user_id, Decimal(str(amount)))
                    if success:
                        new_balance = await get_user_balance_async(user_id)
                        return new_balance
                except Exception as e:
                    logger.error(f"Ошибка добавления баланса в БД: {e}, используем JSON fallback")
            
            current = await get_user_balance_async(user_id)
            new_balance = current + amount
            set_user_balance(user_id, new_balance)
            return new_balance
            
        except Exception as e:
            logger.error(f"Error in add_user_balance_async: {e}", exc_info=True)
            return 0.0

async def subtract_user_balance_async(user_id: int, amount: float) -> bool:
    """Асинхронная версия subtract_user_balance с lock."""
    async with balance_lock:
        try:
            current = await get_user_balance_async(user_id)
            if current >= amount:
                new_balance = current - amount
                set_user_balance(user_id, new_balance)
                return True
            return False
        except Exception as e:
            logger.error(f"Error in subtract_user_balance_async: {e}", exc_info=True)
            return False


# ==================== ФУНКЦИИ ДЛЯ КЛАВИАТУР ====================

def main_menu_kb(user_id: int, user_lang: str, is_new: bool = False, is_admin: bool = False):
    """Создает главное меню клавиатуру."""
    return InlineKeyboardMarkup(build_main_menu_keyboard(user_id, user_lang, is_new))

def kie_models_kb(user_id: int, user_lang: str, models: list, category: str = None):
    """Создает клавиатуру со списком моделей KIE."""
    keyboard = []
    
    for i, model in enumerate(models):
        model_name = model.get('name', model.get('id', 'Unknown'))
        model_emoji = model.get('emoji', '🤖')
        model_id = model.get('id')
        
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
    
    keyboard.append([InlineKeyboardButton(t('btn_back_to_menu', lang=user_lang), callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def admin_kb(user_lang: str):
    """Создает клавиатуру админ-панели."""
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
    """Создает клавиатуру для оплаты."""
    keyboard = []
    
    if amount:
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


# ==================== ГЛОБАЛЬНЫЙ ERROR HANDLER ====================

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок для всех исключений."""
    error = context.error
    logger.error(f"❌❌❌ GLOBAL ERROR HANDLER: {error}", exc_info=True)
    
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


# ==================== ОПТИМИЗИРОВАННАЯ get_user_generations_history ====================

# Кэш для истории генераций (5 минут)
_history_cache = {}
_history_cache_timestamps = {}
HISTORY_CACHE_TTL = 300  # 5 минут
HISTORY_BACKUP_INTERVAL = 100  # Делать backup каждые 100 записей

def get_user_generations_history_optimized(user_id: int, limit: int = 20) -> list:
    """Оптимизированная версия get_user_generations_history с кэшем и backup."""
    user_key = str(user_id)
    cache_key = f"{user_key}_{limit}"
    
    current_time = time.time()
    if cache_key in _history_cache:
        cache_time = _history_cache_timestamps.get(cache_key, 0)
        if current_time - cache_time < HISTORY_CACHE_TTL:
            return _history_cache[cache_key]
    
    try:
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
            backup_file = f"{GENERATIONS_HISTORY_FILE}.backup"
            if os.path.exists(backup_file):
                logger.info(f"🔄 Restoring from backup: {backup_file}")
                shutil.copy(backup_file, GENERATIONS_HISTORY_FILE)
                with open(GENERATIONS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                logger.error("❌ No backup available, returning empty history")
                return []
        
        user_history = history.get(user_key, [])
        if not isinstance(user_history, list):
            user_history = []
        
        user_history.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        result = user_history[:limit]
        
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
```

---

## 🔧 ШАГ 2: ЗАМЕНИТЬ В confirm_generation()

### Найти строку ~11193:
```python
result = await kie.create_task(model_id, api_params)
```

### Заменить на:
```python
# ✅ ИСПРАВЛЕНО: API вызов с safe_kie_call и try/except
try:
    result = await safe_kie_call(
        kie.create_task,
        model_id,
        api_params,
        max_retries=3
    )
    
    if not result.get('ok'):
        error = result.get('error', 'Unknown error')
        logger.error(f"❌ Failed to create task: {error}", exc_info=True)
        user_lang = get_user_language(user_id) if user_id else 'ru'
        error_msg = (
            "❌ <b>Ошибка сервера, попробуйте позже</b>\n\n"
            f"Не удалось создать задачу генерации.\n"
            f"Попробуйте еще раз через несколько секунд."
        ) if user_lang == 'ru' else (
            "❌ <b>Server error, please try later</b>\n\n"
            f"Failed to create generation task.\n"
            f"Please try again in a few seconds."
        )
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message(error_msg, keyboard=keyboard)
        return ConversationHandler.END
    
    task_id = result.get('taskId')
    if not task_id:
        logger.error(f"❌ No taskId in result: {result}", exc_info=True)
        user_lang = get_user_language(user_id) if user_id else 'ru'
        error_msg = "❌ Ошибка сервера, попробуйте позже" if user_lang == 'ru' else "❌ Server error, please try later"
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message(error_msg, keyboard=keyboard)
        return ConversationHandler.END
    
    logger.info(f"✅ Task created successfully: task_id={task_id}, user_id={user_id}, model_id={model_id}")
    
except Exception as e:
    logger.error(f"❌❌❌ KIE API ERROR in create_task: {e}", exc_info=True)
    user_lang = get_user_language(user_id) if user_id else 'ru'
    error_msg = "❌ Ошибка сервера, попробуйте позже" if user_lang == 'ru' else "❌ Server error, please try later"
    keyboard = main_menu_kb(user_id, user_lang)
    await send_or_edit_message(error_msg, keyboard=keyboard)
    return ConversationHandler.END
```

### Найти строку ~11464:
```python
user_balance = get_user_balance(user_id)
```

### Заменить на:
```python
user_balance = await get_user_balance_async(user_id)  # Используем async версию с lock
```

### Найти строку ~11410 (проверка дублей):
```python
async with active_generations_lock:
    user_active_generations = [(uid, tid) for (uid, tid) in active_generations.keys() if uid == user_id]
    if user_active_generations:
        # Check if there's a recent generation for this model (within last 10 seconds)
        import time
        current_time = time.time()
        for (uid, tid) in user_active_generations:
            gen_session = active_generations.get((uid, tid))
            if gen_session and gen_session.get('model_id') == model_id:
                created_time = gen_session.get('created_at', current_time)
                if current_time - created_time < 10:  # Within 10 seconds
```

### Убедиться, что есть проверка дублей по параметрам:
```python
# Добавить после проверки по времени:
import hashlib
import json
params_hash = hashlib.md5(
    json.dumps({
        'model_id': model_id,
        'params': sorted(api_params.items()) if isinstance(api_params, dict) else str(api_params)
    }, sort_keys=True).encode('utf-8')
).hexdigest()

for (uid, tid) in user_active_generations:
    gen_session = active_generations.get((uid, tid))
    if gen_session and gen_session.get('model_id') == model_id:
        existing_params = gen_session.get('params', {})
        existing_params_hash = hashlib.md5(
            json.dumps({
                'model_id': model_id,
                'params': sorted(existing_params.items()) if isinstance(existing_params, dict) else str(existing_params)
            }, sort_keys=True).encode('utf-8')
        ).hexdigest()
        
        if existing_params_hash == params_hash:
            created_time = gen_session.get('created_at', current_time)
            if current_time - created_time < 10:  # Within 10 seconds
                logger.warning(f"⚠️⚠️⚠️ Duplicate generation detected! Task {tid}")
                error_msg = (
                    "⏳ <b>Уже генерирую эту модель</b>\n\n"
                    f"У вас уже запущена генерация с такими же параметрами.\n"
                    f"Task ID: <code>{tid}</code>\n\n"
                    "Дождитесь завершения текущей генерации."
                ) if user_lang == 'ru' else (
                    "⏳ <b>Already generating this model</b>\n\n"
                    f"You already have a generation running with the same parameters.\n"
                    f"Task ID: <code>{tid}</code>\n\n"
                    "Please wait for the current generation to complete."
                )
                keyboard = main_menu_kb(user_id, user_lang)
                await send_or_edit_message(error_msg, keyboard=keyboard)
                return ConversationHandler.END
```

---

## 🔧 ШАГ 3: ЗАМЕНИТЬ В start_generation_directly()

### Найти строку ~11070:
```python
user_balance = get_user_balance(user_id)
```

### Заменить на:
```python
user_balance = await get_user_balance_async(user_id)  # Используем async версию с lock
```

### Найти строку ~11193:
```python
result = await kie.create_task(model_id, api_params)
```

### Заменить на:
```python
# ✅ ИСПРАВЛЕНО: API вызов с safe_kie_call
try:
    result = await safe_kie_call(
        kie.create_task,
        model_id,
        api_params,
        max_retries=3
    )
    
    if not result.get('ok'):
        error = result.get('error', 'Unknown error')
        logger.error(f"❌ Failed to create task: {error}", exc_info=True)
        await status_message.edit_text(
            f"❌ <b>Ошибка сервера, попробуйте позже</b>\n\n"
            f"Не удалось создать задачу генерации.\n"
            f"Попробуйте еще раз через несколько секунд.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    task_id = result.get('taskId')
    if not task_id:
        logger.error(f"❌ No taskId in result: {result}", exc_info=True)
        await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
        return ConversationHandler.END
    
    logger.info(f"✅ Task created successfully: task_id={task_id}, user_id={user_id}, model_id={model_id}")
    
except Exception as e:
    logger.error(f"❌❌❌ KIE API ERROR in create_task: {e}", exc_info=True)
    await status_message.edit_text(
        f"❌ <b>Ошибка сервера, попробуйте позже</b>\n\n"
        f"Не удалось создать задачу генерации.",
        parse_mode='HTML'
    )
    return ConversationHandler.END
```

### Убедиться, что проверка дублей включает проверку параметров (как в confirm_generation)

---

## 🔧 ШАГ 4: ЗАМЕНИТЬ В poll_task_status()

### Найти строку ~23430:
```python
status_result = await kie.get_task_status(task_id)
```

### Заменить на:
```python
# ✅ ИСПРАВЛЕНО: API вызов с safe_kie_call
try:
    status_result = await safe_kie_call(
        kie.get_task_status,
        task_id,
        max_retries=3
    )
    
    if not status_result.get('ok'):
        error = status_result.get('error', 'Unknown error')
        logger.error(f"❌ Error checking task status: {error}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ <b>Ошибка проверки статуса:</b>\n\n{error}",
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except:
            pass
        # Clean up
        generation_key = (user_id, task_id)
        async with active_generations_lock:
            if generation_key in active_generations:
                del active_generations[generation_key]
        break
except Exception as e:
    logger.error(f"Error in poll_task_status API call: {e}", exc_info=True)
    # Continue polling, but log error
    if attempt >= max_attempts:
        keyboard = main_menu_kb(user_id, user_lang)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Превышено время ожидания. Попробуйте позже.",
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except:
            pass
        break
    continue
```

### Найти строку ~23508:
```python
subtract_user_balance(user_id, price)
```

### Заменить на:
```python
# ✅ ИСПРАВЛЕНО: Используем async версию с lock
success = await subtract_user_balance_async(user_id, price)
if not success:
    logger.error(f"Failed to subtract balance for user {user_id}, price {price}")
```

---

## 🔧 ШАГ 5: ЗАМЕНИТЬ В button_callback()

### Пример 1: back_to_menu
**Найти:** Создание клавиатуры для back_to_menu (строка ~3952)

**БЫЛО:**
```python
keyboard = []
# ... создание клавиатуры ...
await query.edit_message_text(
    welcome_text,
    reply_markup=InlineKeyboardMarkup(keyboard),
    parse_mode='HTML'
)
```

**СТАЛО:**
```python
keyboard = main_menu_kb(user_id, user_lang, is_new, is_admin)
await query.edit_message_text(
    welcome_text,
    reply_markup=keyboard,
    parse_mode='HTML'
)
```

### Пример 2: show_models
**Найти:** Создание клавиатуры для show_models (строка ~5024)

**БЫЛО:**
```python
keyboard = []
# ... создание клавиатуры с моделями ...
await query.edit_message_text(
    models_text,
    reply_markup=InlineKeyboardMarkup(keyboard),
    parse_mode='HTML'
)
```

**СТАЛО:**
```python
# Если показываем модели:
keyboard = kie_models_kb(user_id, user_lang, models)
await query.edit_message_text(
    models_text,
    reply_markup=keyboard,
    parse_mode='HTML'
)
```

### Пример 3: admin_stats
**Найти:** Создание клавиатуры для admin_stats (строка ~6156)

**БЫЛО:**
```python
keyboard = [
    [InlineKeyboardButton("📊 Обновить статистику", callback_data="admin_stats")],
    [InlineKeyboardButton("📚 Просмотр генераций", callback_data="admin_view_generations")],
    ...
]
await query.edit_message_text(
    admin_text,
    reply_markup=InlineKeyboardMarkup(keyboard),
    parse_mode='HTML'
)
```

**СТАЛО:**
```python
keyboard = admin_kb(user_lang)
await query.edit_message_text(
    admin_text,
    reply_markup=keyboard,
    parse_mode='HTML'
)
```

---

## 🔧 ШАГ 6: ЗАМЕНИТЬ В payment handlers

### Найти обработчик pay_sbp: (строка ~5935)

**Добавить валидацию:**
```python
if data.startswith("pay_sbp:"):
    try:
        # Answer callback
        if query:
            await query.answer()
        
        # ✅ ИСПРАВЛЕНО: Валидация формата
        if not data or not data.startswith("pay_sbp:"):
            logger.error(f"Invalid callback_data format: {data}")
            keyboard = main_menu_kb(user_id, user_lang)
            await query.edit_message_text(
                "❌ Ошибка: неверный формат запроса",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # ✅ ИСПРАВЛЕНО: Валидация суммы
        try:
            amount_str = data.split(":", 1)[1]
            amount = float(amount_str)
            
            if amount <= 0:
                logger.error(f"Invalid amount: {amount}")
                keyboard = main_menu_kb(user_id, user_lang)
                await query.edit_message_text(
                    "❌ Ошибка: сумма должна быть больше 0",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            if amount < 50 or amount > 50000:
                logger.error(f"Amount out of range: {amount}")
                keyboard = main_menu_kb(user_id, user_lang)
                await query.edit_message_text(
                    "❌ Ошибка: сумма должна быть от 50 до 50000 ₽",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return ConversationHandler.END
                
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing amount: {e}", exc_info=True)
            keyboard = main_menu_kb(user_id, user_lang)
            await query.edit_message_text(
                "❌ Ошибка: неверный формат суммы",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # ... остальной код ...
        keyboard = payment_kb(user_lang, amount=amount)
        await query.edit_message_text(
            # ... текст ...
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error in payment_sbp_handler: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        try:
            await query.answer("❌ Ошибка сервера, попробуйте позже", show_alert=True)
            await query.edit_message_text(
                "❌ Ошибка сервера, попробуйте позже",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except:
            pass
        return ConversationHandler.END
```

---

## 🔧 ШАГ 7: ДОБАВИТЬ В main()

### Найти строку ~24857:
```python
application.add_error_handler(error_handler)
```

### Заменить на:
```python
# ✅ ИСПРАВЛЕНО: Глобальный error handler
application.add_error_handler(global_error_handler)
```

---

## 🔧 ШАГ 8: ЗАМЕНИТЬ get_user_generations_history

### Найти функцию get_user_generations_history (строка ~2172)

### Заменить на get_user_generations_history_optimized

**Или добавить вызов оптимизированной версии:**
```python
# В местах вызова:
history = get_user_generations_history_optimized(user_id, limit=20)
```

---

## ✅ ИТОГОВЫЙ ЧЕКЛИСТ

- [ ] Добавлен safe_kie_call() в начало файла
- [ ] Добавлены async функции баланса с locks
- [ ] Добавлены функции клавиатур
- [ ] Добавлен global_error_handler
- [ ] Добавлена оптимизированная get_user_generations_history_optimized
- [ ] Заменены все kie.create_task() на safe_kie_call()
- [ ] Заменены все get_user_balance() на get_user_balance_async()
- [ ] Заменены все subtract_user_balance() на subtract_user_balance_async()
- [ ] Добавлена проверка дублей в confirm_generation и start_generation_directly
- [ ] Заменены все создания клавиатур на функции
- [ ] Добавлена валидация в payment handlers
- [ ] Добавлен global_error_handler в main()
- [ ] Все handlers имеют try/except вокруг API вызовов
- [ ] Все handlers вызывают await query.answer()
- [ ] Все handlers имеют parse_mode='HTML' где нужно
- [ ] Все handlers имеют reply_markup=keyboard после edit_text

---

## 📁 ФАЙЛЫ С ИСПРАВЛЕНИЯМИ

1. **COMPLETE_FIXES.py** - все вспомогательные функции
2. **FIXED_HANDLERS_COMPLETE.py** - исправленные handlers целиком
3. **TOP_5_CRITICAL_FIXES.py** - 5 самых критичных handlers
4. **COMPLETE_FIXES_REPORT.md** - полный отчет
5. **FINAL_INTEGRATION_GUIDE.md** - это руководство

Все исправления показаны **ЦЕЛИКОМ** в соответствующих файлах.


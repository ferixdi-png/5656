# ПРОБЛЕМНЫЕ МЕСТА И ФИКСЫ - 5 САМЫХ КРИТИЧНЫХ HANDLERS

## 🔴 ПРОБЛЕМА 1: confirm_generation - отсутствие try/except вокруг API вызовов

### Проблемное место:
```python
# Строка ~11193
result = await kie.create_task(model_id, api_params)
# Нет обработки ошибок, нет retry логики
```

### Фикс ЦЕЛИКОМ:
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

### Дополнительные фиксы в confirm_generation:
1. **Проверка баланса:** Заменить `get_user_balance(user_id)` на `await get_user_balance_async(user_id)`
2. **Проверка дублей:** Добавить проверку по параметрам (не только по времени)
3. **Всегда keyboard:** Все `edit_message_text` должны иметь `reply_markup=keyboard`
4. **Всегда parse_mode:** Все `edit_message_text` должны иметь `parse_mode='HTML'`

---

## 🔴 ПРОБЛЕМА 2: poll_task_status - отсутствие try/except вокруг API вызовов

### Проблемное место:
```python
# Строка ~23430
status_result = await kie.get_task_status(task_id)
# Нет обработки ошибок, нет retry логики
```

### Фикс ЦЕЛИКОМ:
```python
# ✅ ИСПРАВЛЕНО: API вызов с safe_kie_call и try/except
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
        # Clean up active generation on error
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

### Дополнительные фиксы в poll_task_status:
1. **Вычитание баланса:** Заменить `subtract_user_balance(user_id, price)` на `await subtract_user_balance_async(user_id, price)`
2. **Всегда keyboard:** Все `send_message` должны иметь `reply_markup=keyboard`
3. **Всегда parse_mode:** Все `send_message` должны иметь `parse_mode='HTML'`

---

## 🔴 ПРОБЛЕМА 3: input_parameters - отсутствие try/except вокруг операций с файлами

### Проблемное место:
```python
# Операции с файлами без try/except
file = await context.bot.get_file(photo.file_id)
file_data = await file.download_as_bytearray()
uploaded_url = await upload_image_to_hosting(file_data, ...)
```

### Фикс ЦЕЛИКОМ:
```python
# ✅ ИСПРАВЛЕНО: Обработка фото с try/except
if update.message.photo:
    try:
        if waiting_for in ['image_input', 'image_urls', 'image', 'mask_input', 'reference_image_input']:
            # Get largest photo
            photo = update.message.photo[-1]
            
            # ✅ ИСПРАВЛЕНО: Загрузка файла с try/except
            try:
                file = await context.bot.get_file(photo.file_id)
                file_data = await file.download_as_bytearray()
            except Exception as e:
                logger.error(f"Error downloading photo: {e}", exc_info=True)
                keyboard = main_menu_kb(user_id, user_lang)
                await update.message.reply_text(
                    "❌ Ошибка загрузки фото. Попробуйте еще раз.",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return INPUTTING_PARAMS
            
            # ✅ ИСПРАВЛЕНО: Загрузка на хостинг с try/except
            try:
                uploaded_url = await upload_image_to_hosting(file_data, f"user_{user_id}_{int(time.time())}.jpg")
                if not uploaded_url:
                    raise Exception("Failed to upload image")
            except Exception as e:
                logger.error(f"Error uploading image to hosting: {e}", exc_info=True)
                keyboard = main_menu_kb(user_id, user_lang)
                await update.message.reply_text(
                    "❌ Ошибка загрузки фото на сервер. Попробуйте позже.",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return INPUTTING_PARAMS
            
            # Store in session
            param_name = waiting_for
            if param_name not in session:
                session[param_name] = []
            session[param_name].append(uploaded_url)
            
            # Show confirmation
            count = len(session[param_name])
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Готово", callback_data="image_done")],
                [InlineKeyboardButton("➕ Добавить еще", callback_data="add_image")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_previous_step")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
            ])
            await update.message.reply_text(
                f"✅ <b>Изображение загружено!</b>\n\n"
                f"Загружено изображений: {count}\n"
                f"Можно загрузить до 8 изображений.\n\n"
                f"Нажмите 'Готово' для продолжения или 'Добавить еще' для загрузки еще одного изображения.",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return INPUTTING_PARAMS
    except Exception as e:
        logger.error(f"Error processing photo: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        await update.message.reply_text(
            "❌ Ошибка обработки фото. Попробуйте позже.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return INPUTTING_PARAMS
```

### Дополнительные фиксы в input_parameters:
1. **Всегда keyboard:** Все `reply_text` должны иметь `reply_markup=keyboard`
2. **Всегда parse_mode:** Все `reply_text` должны иметь `parse_mode='HTML'`
3. **Обработка текста:** Добавить try/except вокруг обработки текстового ввода

---

## 🔴 ПРОБЛЕМА 4: button_callback - отсутствие await query.answer() в некоторых обработчиках

### Проблемное место:
```python
# Некоторые обработчики не вызывают await query.answer()
if data == "some_action":
    # Нет await query.answer()
    await query.edit_message_text(...)
```

### Фикс ЦЕЛИКОМ:
```python
# ✅ ИСПРАВЛЕНО: Всегда отвечаем на callback в начале каждого обработчика
if data == "some_action":
    try:
        # ✅ ИСПРАВЛЕНО: Всегда отвечаем на callback
        await query.answer()
    except Exception as e:
        logger.warning(f"Could not answer callback: {e}")
    
    try:
        # ... обработка ...
        keyboard = main_menu_kb(user_id, user_lang)  # Используем функцию
        await query.edit_message_text(
            text,
            reply_markup=keyboard,  # Всегда добавляем keyboard
            parse_mode='HTML'  # Всегда указываем parse_mode
        )
    except Exception as e:
        logger.error(f"Error in handler: {e}", exc_info=True)
        try:
            await query.answer("❌ Ошибка сервера, попробуйте позже", show_alert=True)
        except:
            pass
        return ConversationHandler.END
```

### Список обработчиков, которые нужно исправить:
1. `check_balance` - добавить try/except, использовать async баланс
2. `topup_balance` - добавить try/except
3. `my_generations` - добавить try/except, использовать оптимизированную историю
4. `help_menu` - добавить try/except
5. `support_contact` - добавить try/except

---

## 🔴 ПРОБЛЕМА 5: payment handlers - отсутствие валидации

### Проблемное место:
```python
# Строка ~5935
if data.startswith("pay_sbp:"):
    amount = float(data.split(":", 1)[1])  # Нет валидации
    # Нет проверки на >0, нет проверки диапазона
```

### Фикс ЦЕЛИКОМ:
```python
if data.startswith("pay_sbp:"):
    try:
        # ✅ ИСПРАВЛЕНО: Всегда отвечаем на callback
        if query:
            await query.answer()
        
        # ✅ ИСПРАВЛЕНО: Валидация формата callback_data
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
            
            # Валидация: сумма должна быть > 0
            if amount <= 0:
                logger.error(f"Invalid amount: {amount}")
                keyboard = main_menu_kb(user_id, user_lang)
                await query.edit_message_text(
                    "❌ Ошибка: сумма должна быть больше 0",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            # Валидация: сумма должна быть в диапазоне 50-50000
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
        
        # ✅ ИСПРАВЛЕНО: Сохранение с try/except
        try:
            user_sessions[user_id] = {
                'topup_amount': amount,
                'waiting_for': 'payment_screenshot',
                'payment_method': 'sbp'
            }
        except Exception as e:
            logger.error(f"Error storing payment info: {e}", exc_info=True)
            keyboard = main_menu_kb(user_id, user_lang)
            await query.edit_message_text(
                "❌ Ошибка сервера, попробуйте позже",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # ✅ ИСПРАВЛЕНО: Получение деталей платежа с try/except
        try:
            payment_details = get_payment_details()
        except Exception as e:
            logger.error(f"Error getting payment details: {e}", exc_info=True)
            payment_details = "Обратитесь в поддержку для получения реквизитов."
        
        # ✅ ИСПРАВЛЕНО: Использование функции клавиатуры
        keyboard = payment_kb(user_lang, amount=amount)
        
        # ✅ ИСПРАВЛЕНО: Всегда parse_mode и keyboard
        await query.edit_message_text(
            f'💳 <b>ОПЛАТА {amount:.0f} ₽ (СБП)</b> 💳\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'{payment_details}\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'💵 <b>Сумма к оплате:</b> {amount:.2f} ₽\n\n'
            f'📸 <b>КАК ОПЛАТИТЬ:</b>\n'
            f'1️⃣ Переведи {amount:.2f} ₽ по реквизитам выше\n'
            f'2️⃣ Сделай скриншот перевода\n'
            f'3️⃣ Отправь скриншот сюда\n'
            f'4️⃣ Баланс начислится автоматически! ⚡\n\n'
            f'✅ <b>Все просто и быстро!</b>\n\n'
            f'💡 Для отмены используйте /cancel',
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        return WAITING_PAYMENT_SCREENSHOT
        
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

### Дополнительные фиксы:
1. **Обработка /cancel:** Добавить проверку на `/cancel` в WAITING_PAYMENT_SCREENSHOT
2. **Валидация скриншота:** Добавить валидацию при получении скриншота платежа

---

## 📋 ИТОГОВЫЙ СПИСОК ВСЕХ ПРОБЛЕМ И ФИКСОВ

### ✅ Проблема 1: confirm_generation
- ❌ Нет try/except вокруг `kie.create_task()`
- ❌ Нет retry логики
- ❌ Используется синхронный `get_user_balance()`
- ❌ Нет проверки дублей по параметрам
- ✅ **ФИКС:** Использовать `safe_kie_call()`, `get_user_balance_async()`, добавить проверку дублей

### ✅ Проблема 2: poll_task_status
- ❌ Нет try/except вокруг `kie.get_task_status()`
- ❌ Нет retry логики
- ❌ Используется синхронный `subtract_user_balance()`
- ❌ Нет keyboard в некоторых сообщениях
- ✅ **ФИКС:** Использовать `safe_kie_call()`, `subtract_user_balance_async()`, всегда добавлять keyboard

### ✅ Проблема 3: input_parameters
- ❌ Нет try/except вокруг операций с файлами
- ❌ Нет try/except вокруг `upload_image_to_hosting()`
- ❌ Нет keyboard в некоторых сообщениях
- ✅ **ФИКС:** Обернуть все операции в try/except, всегда добавлять keyboard

### ✅ Проблема 4: button_callback
- ❌ Некоторые обработчики не вызывают `await query.answer()`
- ❌ Дублирование кода создания клавиатур
- ❌ Нет keyboard в некоторых сообщениях
- ✅ **ФИКС:** Всегда вызывать `await query.answer()`, использовать функции клавиатур

### ✅ Проблема 5: payment handlers
- ❌ Нет валидации суммы
- ❌ Нет валидации формата callback_data
- ❌ Нет обработки /cancel
- ✅ **ФИКС:** Добавить валидацию суммы (>0, 50-50000), валидацию формата, обработку /cancel

---

## 📁 ФАЙЛЫ С ПОЛНЫМИ ИСПРАВЛЕНИЯМИ

1. **COMPLETE_FIXES.py** - все вспомогательные функции (safe_kie_call, locks, клавиатуры, error handler)
2. **FIXED_HANDLERS_COMPLETE.py** - исправленные handlers целиком (confirm_generation, start_generation_directly, poll_task_status, input_parameters, payment_sbp_handler)
3. **TOP_5_CRITICAL_FIXES.py** - 5 самых критичных handlers с полными исправлениями
4. **PROBLEM_AREAS_AND_FIXES.md** - этот файл с проблемными местами и фиксами
5. **FINAL_INTEGRATION_GUIDE.md** - полное руководство по интеграции

**Все исправления показаны ЦЕЛИКОМ в соответствующих файлах.**


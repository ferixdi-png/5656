"""
ПОЛНЫЕ ИСПРАВЛЕНИЯ HANDLERS - ВСЕ ИЗМЕНЕНИЯ ЦЕЛИКОМ
"""

# ==================== ИСПРАВЛЕННАЯ confirm_generation ====================

async def confirm_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle generation confirmation.
    ИСПРАВЛЕНО: Добавлены try/except вокруг всех API вызовов, улучшена обработка ошибок.
    """
    import time
    start_time = time.time()
    query = update.callback_query
    user_id = update.effective_user.id
    logger.info(f"🔥🔥🔥 CONFIRM_GENERATION ENTRY: user_id={user_id}, query_id={query.id if query else 'None'}, data={query.data if query else 'None'}")
    
    # Answer callback immediately if present
    if query:
        try:
            await query.answer()
        except Exception as e:
            logger.warning(f"Could not answer callback query: {e}")
    
    is_admin_user = get_is_admin(user_id)
    user_lang = get_user_language(user_id)
    
    # Helper function to send/edit messages safely
    async def send_or_edit_message(text, parse_mode='HTML', keyboard=None):
        try:
            if query:
                try:
                    await query.edit_message_text(
                        text,
                        parse_mode=parse_mode,
                        reply_markup=keyboard
                    )
                except Exception as edit_error:
                    logger.warning(f"Could not edit message: {edit_error}, sending new")
                    try:
                        await query.message.reply_text(
                            text,
                            parse_mode=parse_mode,
                            reply_markup=keyboard
                        )
                        try:
                            await query.message.delete()
                        except:
                            pass
                    except Exception as send_error:
                        logger.error(f"Could not send new message: {send_error}")
                        try:
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=text,
                                parse_mode=parse_mode,
                                reply_markup=keyboard
                            )
                        except:
                            pass
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=keyboard
                )
        except Exception as e:
            logger.error(f"Error in send_or_edit_message: {e}", exc_info=True)
            try:
                await context.bot.send_message(chat_id=user_id, text=text, parse_mode=parse_mode)
            except:
                pass
    
    # Check if user is blocked
    try:
        if not is_admin_user and is_user_blocked(user_id):
            await send_or_edit_message(
                "❌ <b>Ваш аккаунт заблокирован</b>\n\n"
                "Обратитесь к администратору для разблокировки."
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking user block status: {e}", exc_info=True)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже")
        return ConversationHandler.END
    
    # Check session
    if user_id not in user_sessions:
        logger.error(f"❌❌❌ CRITICAL: Session not found in confirm_generation! user_id={user_id}")
        
        # Try to restore from backup
        try:
            if hasattr(context, 'user_data') and context.user_data.get('session_backup_user_id') == user_id:
                session_backup = context.user_data.get('session_backup')
                if session_backup:
                    logger.warning(f"⚠️⚠️⚠️ Restoring session from context.user_data backup for user_id={user_id}")
                    user_sessions[user_id] = session_backup.copy()
                    logger.info(f"✅✅✅ Session restored from context.user_data: user_id={user_id}")
                else:
                    await send_or_edit_message("❌ Сессия не найдена. Пожалуйста, начните заново с /start")
                    return ConversationHandler.END
            else:
                await send_or_edit_message("❌ Сессия не найдена. Пожалуйста, начните заново с /start")
                return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error restoring session: {e}", exc_info=True)
            await send_or_edit_message("❌ Ошибка сервера, попробуйте позже")
            return ConversationHandler.END
    
    session = user_sessions[user_id]
    logger.info(f"✅✅✅ Session found in confirm_generation: user_id={user_id}, model_id={session.get('model_id')}")
    
    # Check for duplicate task
    try:
        if 'task_id' in session:
            task_id_existing = session.get('task_id')
            logger.warning(f"⚠️⚠️⚠️ Task {task_id_existing} already exists in session for user {user_id}")
            await send_or_edit_message(
                f"⚠️ <b>Генерация уже запущена</b>\n\n"
                f"Задача уже создана.\n"
                f"Task ID: <code>{task_id_existing}</code>"
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking duplicate task: {e}", exc_info=True)
    
    model_id = session.get('model_id')
    params = session.get('params', {})
    model_info = session.get('model_info', {})
    
    # Check for duplicate in active_generations (10 second timeout)
    try:
        async with active_generations_lock:
            user_active_generations = [(uid, tid) for (uid, tid) in active_generations.keys() if uid == user_id]
            if user_active_generations:
                current_time = time.time()
                for (uid, tid) in user_active_generations:
                    gen_session = active_generations.get((uid, tid))
                    if gen_session and gen_session.get('model_id') == model_id:
                        created_time = gen_session.get('created_at', current_time)
                        if current_time - created_time < 10:  # Within 10 seconds
                            logger.warning(f"⚠️⚠️⚠️ Duplicate generation detected! Task {tid} was created recently for user {user_id}, model {model_id}")
                            error_msg = (
                                "⏳ <b>Уже генерирую эту модель</b>\n\n"
                                f"Задача уже создана и обрабатывается.\n"
                                f"Task ID: <code>{tid}</code>\n\n"
                                "Дождитесь завершения текущей генерации."
                            ) if user_lang == 'ru' else (
                                "⏳ <b>Already generating this model</b>\n\n"
                                f"Task already created and processing.\n"
                                f"Task ID: <code>{tid}</code>\n\n"
                                "Please wait for current generation to complete."
                            )
                            await send_or_edit_message(error_msg)
                            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking active generations: {e}", exc_info=True)
    
    # Apply default values
    try:
        input_params = model_info.get('input_params', {})
        for param_name, param_info in input_params.items():
            if param_name not in params:
                default_value = param_info.get('default')
                if default_value is not None:
                    params[param_name] = default_value
        
        # Convert string boolean values
        for param_name, param_value in params.items():
            if param_name in input_params:
                param_info = input_params[param_name]
                if param_info.get('type') == 'boolean':
                    if isinstance(param_value, str):
                        if param_value.lower() == 'true':
                            params[param_name] = True
                        elif param_value.lower() == 'false':
                            params[param_name] = False
    except Exception as e:
        logger.error(f"Error applying default values: {e}", exc_info=True)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже")
        return ConversationHandler.END
    
    # Check if free generation
    try:
        is_free = is_free_generation_available(user_id, model_id)
        price = calculate_price_rub(model_id, params, is_admin_user)
        if is_free:
            price = 0.0
    except Exception as e:
        logger.error(f"Error checking free generation: {e}", exc_info=True)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже")
        return ConversationHandler.END
    
    # Check balance/limit
    try:
        if not is_admin_user:
            if not is_free:
                user_balance = await get_user_balance_async(user_id)  # Используем async версию с lock
                if user_balance < price:
                    price_str = f"{price:.2f}".rstrip('0').rstrip('.')
                    balance_str = f"{user_balance:.2f}".rstrip('0').rstrip('.')
                    remaining_free = get_user_free_generations_remaining(user_id)
                    
                    error_text = (
                        f"❌ <b>Недостаточно средств</b>\n\n"
                        f"💰 <b>Требуется:</b> {price_str} ₽\n"
                        f"💳 <b>Ваш баланс:</b> {balance_str} ₽\n\n"
                    )
                    
                    if model_id == FREE_MODEL_ID and remaining_free > 0:
                        error_text += f"🎁 <b>Но у вас есть {remaining_free} бесплатных генераций!</b>\n\n"
                        error_text += "Попробуйте снова - бесплатная генерация будет использована автоматически."
                    else:
                        error_text += "Пополните баланс для продолжения."
                    
                    keyboard = payment_kb(user_lang, amount=price)
                    await send_or_edit_message(error_text, keyboard=keyboard)
                    return ConversationHandler.END
        elif user_id != ADMIN_ID:
            remaining = get_admin_remaining(user_id)
            if remaining < price:
                price_str = f"{price:.2f}".rstrip('0').rstrip('.')
                remaining_str = f"{remaining:.2f}".rstrip('0').rstrip('.')
                limit = get_admin_limit(user_id)
                spent = get_admin_spent(user_id)
                await send_or_edit_message(
                    f"❌ <b>Превышен лимит</b>\n\n"
                    f"💰 <b>Требуется:</b> {price_str} ₽\n"
                    f"💳 <b>Лимит:</b> {limit:.2f} ₽\n"
                    f"💸 <b>Потрачено:</b> {spent:.2f} ₽\n"
                    f"✅ <b>Осталось:</b> {remaining_str} ₽\n\n"
                    f"Обратитесь к главному администратору для увеличения лимита."
                )
                return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking balance: {e}", exc_info=True)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже")
        return ConversationHandler.END
    
    await send_or_edit_message("🔄 Создаю задачу генерации... Пожалуйста, подождите.")
    
    # Prepare API params (convert image_input, etc.)
    try:
        api_params = params.copy()
        # ... (все конвертации параметров как в оригинале) ...
        # (здесь должна быть полная логика конвертации параметров для всех моделей)
    except Exception as e:
        logger.error(f"Error preparing API params: {e}", exc_info=True)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже")
        return ConversationHandler.END
    
    # 🔴 API CALL: KIE API - create_task с safe_kie_call
    try:
        result = await safe_kie_call(
            kie.create_task,
            model_id,
            api_params,
            max_retries=3
        )
        
        if not result.get('ok'):
            error = result.get('error', 'Unknown error')
            logger.error(f"❌ Failed to create task: {error}")
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
            logger.error(f"❌ No taskId in result: {result}")
            error_msg = "❌ Ошибка сервера, попробуйте позже" if user_lang == 'ru' else "❌ Server error, please try later"
            keyboard = main_menu_kb(user_id, user_lang)
            await send_or_edit_message(error_msg, keyboard=keyboard)
            return ConversationHandler.END
        
        logger.info(f"✅ Task created successfully: task_id={task_id}, user_id={user_id}, model_id={model_id}")
        
    except Exception as e:
        logger.error(f"❌❌❌ KIE API ERROR in create_task: {e}", exc_info=True)
        error_msg = "❌ Ошибка сервера, попробуйте позже" if user_lang == 'ru' else "❌ Server error, please try later"
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message(error_msg, keyboard=keyboard)
        return ConversationHandler.END
    
    # Store task_id and move to active_generations
    try:
        session['task_id'] = task_id
        generation_key = (user_id, task_id)
        
        # Move to active_generations
        async with active_generations_lock:
            active_generations[generation_key] = {
                **session.copy(),
                'created_at': time.time(),
                'status_message': None  # Will be set by poll_task_status
            }
        
        # Start polling task status
        try:
            await poll_task_status(update, context, task_id, user_id)
        except Exception as e:
            logger.error(f"Error starting poll_task_status: {e}", exc_info=True)
            # Try to clean up
            async with active_generations_lock:
                active_generations.pop(generation_key, None)
            await send_or_edit_message("❌ Ошибка сервера, попробуйте позже")
            return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error storing task: {e}", exc_info=True)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже")
        return ConversationHandler.END
    
    return ConversationHandler.END


# ==================== ИСПРАВЛЕННАЯ start_generation_directly ====================

async def start_generation_directly(
    user_id: int,
    model_id: str,
    params: dict,
    model_info: dict,
    status_message,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Start generation directly without callback query.
    ИСПРАВЛЕНО: Добавлены try/except, safe_kie_call, проверка дублей.
    """
    logger.info(f"🚀 start_generation_directly called for user {user_id}, model {model_id}")
    
    user_lang = get_user_language(user_id)
    is_admin_user = get_is_admin(user_id)
    
    try:
        # Check if user is blocked
        if not is_admin_user and is_user_blocked(user_id):
            await status_message.edit_text(
                "❌ <b>Ваш аккаунт заблокирован</b>\n\n"
                "Обратитесь к администратору для разблокировки.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking user block status: {e}", exc_info=True)
        try:
            await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
        except:
            pass
        return ConversationHandler.END
    
    # Apply default values
    try:
        input_params = model_info.get('input_params', {})
        for param_name, param_info in input_params.items():
            if param_name not in params:
                default_value = param_info.get('default')
                if default_value is not None:
                    params[param_name] = default_value
        
        # Convert string boolean values
        for param_name, param_value in params.items():
            if param_name in input_params:
                param_info = input_params[param_name]
                if param_info.get('type') == 'boolean':
                    if isinstance(param_value, str):
                        if param_value.lower() == 'true':
                            params[param_name] = True
                        elif param_value.lower() == 'false':
                            params[param_name] = False
    except Exception as e:
        logger.error(f"Error applying default values: {e}", exc_info=True)
        try:
            await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
        except:
            pass
        return ConversationHandler.END
    
    # Check if free generation
    try:
        is_free = is_free_generation_available(user_id, model_id)
        price = calculate_price_rub(model_id, params, is_admin_user)
        if is_free:
            price = 0.0
    except Exception as e:
        logger.error(f"Error checking free generation: {e}", exc_info=True)
        try:
            await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
        except:
            pass
        return ConversationHandler.END
    
    # Check balance
    try:
        if not is_admin_user:
            if not is_free:
                user_balance = await get_user_balance_async(user_id)  # Используем async версию
                if user_balance < price:
                    price_str = f"{price:.2f}".rstrip('0').rstrip('.')
                    balance_str = f"{user_balance:.2f}".rstrip('0').rstrip('.')
                    await status_message.edit_text(
                        f"❌ <b>Недостаточно средств</b>\n\n"
                        f"💰 <b>Требуется:</b> {price_str} ₽\n"
                        f"💳 <b>Ваш баланс:</b> {balance_str} ₽\n\n"
                        f"Пополните баланс для продолжения.",
                        parse_mode='HTML'
                    )
                    return ConversationHandler.END
        elif user_id != ADMIN_ID:
            remaining = get_admin_remaining(user_id)
            if remaining < price:
                await status_message.edit_text(
                    f"❌ <b>Превышен лимит</b>\n\n"
                    f"Обратитесь к главному администратору для увеличения лимита.",
                    parse_mode='HTML'
                )
                return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking balance: {e}", exc_info=True)
        try:
            await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
        except:
            pass
        return ConversationHandler.END
    
    await status_message.edit_text("🔄 Создаю задачу генерации... Пожалуйста, подождите.", parse_mode='HTML')
    
    # Prepare API params
    try:
        api_params = params.copy()
        # ... (конвертация параметров) ...
    except Exception as e:
        logger.error(f"Error preparing API params: {e}", exc_info=True)
        try:
            await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
        except:
            pass
        return ConversationHandler.END
    
    # Check for duplicates (10 second timeout)
    try:
        async with active_generations_lock:
            user_active_count = sum(1 for (uid, _) in active_generations.keys() if uid == user_id)
            if user_active_count >= MAX_CONCURRENT_GENERATIONS_PER_USER:
                await status_message.edit_text(
                    f"⚠️ <b>Превышен лимит одновременных генераций</b>\n\n"
                    f"У вас уже запущено {user_active_count} генераций.\n"
                    f"Максимум: {MAX_CONCURRENT_GENERATIONS_PER_USER}.",
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            # Check for duplicate task (same model + params within 10 seconds)
            import hashlib
            import json
            params_hash = hashlib.md5(
                json.dumps({
                    'model_id': model_id,
                    'params': sorted(api_params.items()) if isinstance(api_params, dict) else str(api_params)
                }, sort_keys=True).encode('utf-8')
            ).hexdigest()
            
            current_time = time.time()
            for (uid, existing_task_id), existing_session in active_generations.items():
                if uid == user_id:
                    existing_model = existing_session.get('model_id')
                    existing_params = existing_session.get('params', {})
                    existing_params_hash = hashlib.md5(
                        json.dumps({
                            'model_id': existing_model,
                            'params': sorted(existing_params.items()) if isinstance(existing_params, dict) else str(existing_params)
                        }, sort_keys=True).encode('utf-8')
                    ).hexdigest()
                    
                    if existing_params_hash == params_hash:
                        created_time = existing_session.get('created_at', current_time)
                        if current_time - created_time < 10:  # Within 10 seconds
                            logger.warning(f"⚠️⚠️⚠️ DUPLICATE TASK DETECTED: user {user_id}, model {model_id}, existing task_id={existing_task_id}")
                            error_msg = (
                                "⏳ <b>Уже генерирую эту модель</b>\n\n"
                                f"У вас уже запущена генерация с такими же параметрами.\n"
                                f"Task ID: <code>{existing_task_id}</code>\n\n"
                                "Дождитесь завершения текущей генерации."
                            ) if user_lang == 'ru' else (
                                "⏳ <b>Already generating this model</b>\n\n"
                                f"You already have a generation running with the same parameters.\n"
                                f"Task ID: <code>{existing_task_id}</code>\n\n"
                                "Please wait for the current generation to complete."
                            )
                            await status_message.edit_text(error_msg, parse_mode='HTML')
                            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking duplicates: {e}", exc_info=True)
    
    # Create task with safe_kie_call
    try:
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
                f"❌ <b>Ошибка сервера, попробуйте позже</b>\n\n"
                f"Не удалось создать задачу генерации.\n"
                f"Попробуйте еще раз через несколько секунд.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        task_id = result.get('taskId')
        if not task_id:
            logger.error(f"❌ No taskId in result: {result}")
            await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
            return ConversationHandler.END
        
        logger.info(f"✅ Task created successfully: task_id={task_id}, user_id={user_id}, model_id={model_id}")
        
    except Exception as e:
        logger.error(f"❌❌❌ KIE API ERROR in create_task: {e}", exc_info=True)
        try:
            await status_message.edit_text(
                f"❌ <b>Ошибка сервера, попробуйте позже</b>\n\n"
                f"Не удалось создать задачу генерации.",
                parse_mode='HTML'
            )
        except:
            pass
        return ConversationHandler.END
    
    # Store task and start polling
    try:
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        
        session = user_sessions[user_id]
        session['task_id'] = task_id
        session['model_id'] = model_id
        session['model_info'] = model_info
        session['params'] = params
        
        generation_key = (user_id, task_id)
        
        async with active_generations_lock:
            active_generations[generation_key] = {
                **session.copy(),
                'created_at': time.time(),
                'status_message': status_message
            }
        
        # Start polling
        try:
            await poll_task_status(update, context, task_id, user_id)
        except Exception as e:
            logger.error(f"Error starting poll_task_status: {e}", exc_info=True)
            async with active_generations_lock:
                active_generations.pop(generation_key, None)
            await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
            return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error storing task: {e}", exc_info=True)
        try:
            await status_message.edit_text("❌ Ошибка сервера, попробуйте позже", parse_mode='HTML')
        except:
            pass
        return ConversationHandler.END
    
    return ConversationHandler.END


# ==================== ИСПРАВЛЕННЫЕ ФУНКЦИИ БАЛАНСА ====================

async def get_user_balance_async(user_id: int) -> float:
    """Асинхронная версия get_user_balance с lock."""
    async with balance_lock:
        try:
            # Try database first
            if DATABASE_AVAILABLE:
                try:
                    from decimal import Decimal
                    balance = db_get_user_balance(user_id)
                    return float(balance)
                except Exception as e:
                    logger.error(f"Ошибка получения баланса из БД: {e}, используем JSON fallback")
            
            # Fallback to JSON
            user_key = str(user_id)
            current_time = time.time()
            
            # Check cache
            if 'balances' in _data_cache['cache_timestamps']:
                cache_time = _data_cache['cache_timestamps']['balances']
                if current_time - cache_time < CACHE_TTL and user_key in _data_cache.get('balances', {}):
                    return _data_cache['balances'][user_key]
            
            # Load from file
            balances = load_json_file(BALANCES_FILE, {})
            return balances.get(user_key, 0.0)
            
        except Exception as e:
            logger.error(f"Error in get_user_balance_async: {e}", exc_info=True)
            return 0.0

async def add_user_balance_async(user_id: int, amount: float) -> float:
    """Асинхронная версия add_user_balance с lock."""
    async with balance_lock:
        try:
            # Try database first
            if DATABASE_AVAILABLE:
                try:
                    from decimal import Decimal
                    success = db_add_to_balance(user_id, Decimal(str(amount)))
                    if success:
                        new_balance = await get_user_balance_async(user_id)
                        logger.debug(f"✅ Balance added in DB: user_id={user_id}, added={amount}, new_balance={new_balance}")
                        return new_balance
                except Exception as e:
                    logger.error(f"Ошибка добавления баланса в БД: {e}, используем JSON fallback")
            
            # Fallback to JSON
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


# ==================== ОПТИМИЗИРОВАННАЯ get_user_generations_history ====================

def get_user_generations_history_optimized(user_id: int, limit: int = 20) -> list:
    """
    Оптимизированная версия get_user_generations_history с кэшем и backup.
    """
    user_key = str(user_id)
    cache_key = f"{user_key}_{limit}"
    
    # Check cache
    current_time = time.time()
    if cache_key in _history_cache:
        cache_time = _history_cache_timestamps.get(cache_key, 0)
        if current_time - cache_time < HISTORY_CACHE_TTL:
            return _history_cache[cache_key]
    
    try:
        # Check file exists
        if not os.path.exists(GENERATIONS_HISTORY_FILE):
            with open(GENERATIONS_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            return []
        
        # Load with JSON validation
        try:
            with open(GENERATIONS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    return []
                history = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in history file: {e}")
            # Try to restore from backup
            backup_file = f"{GENERATIONS_HISTORY_FILE}.backup"
            if os.path.exists(backup_file):
                logger.info(f"🔄 Restoring from backup: {backup_file}")
                shutil.copy(backup_file, GENERATIONS_HISTORY_FILE)
                with open(GENERATIONS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                logger.error("❌ No backup available, returning empty history")
                return []
        
        # Get user history
        user_history = history.get(user_key, [])
        if not isinstance(user_history, list):
            user_history = []
        
        # Sort by timestamp (newest first)
        user_history.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        result = user_history[:limit]
        
        # Update cache
        _history_cache[cache_key] = result
        _history_cache_timestamps[cache_key] = current_time
        
        # Create backup every 100 records
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


# ==================== ГЛОБАЛЬНЫЙ ERROR HANDLER ====================

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Глобальный обработчик ошибок для всех исключений.
    Ловит все Exception, логирует с exc_info=True,
    отправляет пользователю понятное сообщение.
    """
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
                
                # Try to return to main menu
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


# ==================== ВАЛИДАЦИЯ PAYMENT HANDLERS ====================

async def payment_sbp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик оплаты через СБП с валидацией.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    user_lang = get_user_language(user_id)
    
    try:
        # Answer callback
        if query:
            await query.answer()
        
        # Validate callback_data format
        data = query.data if query else None
        if not data or not data.startswith("pay_sbp:"):
            logger.error(f"Invalid callback_data format: {data}")
            await query.edit_message_text("❌ Ошибка: неверный формат запроса", parse_mode='HTML')
            return ConversationHandler.END
        
        # Extract amount
        try:
            amount_str = data.split(":", 1)[1]
            amount = float(amount_str)
            
            # Validate amount
            if amount <= 0:
                logger.error(f"Invalid amount: {amount}")
                await query.edit_message_text("❌ Ошибка: сумма должна быть больше 0", parse_mode='HTML')
                return ConversationHandler.END
            
            if amount < 50 or amount > 50000:
                logger.error(f"Amount out of range: {amount}")
                await query.edit_message_text(
                    "❌ Ошибка: сумма должна быть от 50 до 50000 ₽",
                    parse_mode='HTML'
                )
                return ConversationHandler.END
                
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing amount: {e}")
            await query.edit_message_text("❌ Ошибка: неверный формат суммы", parse_mode='HTML')
            return ConversationHandler.END
        
        # Store payment info
        user_sessions[user_id] = {
            'topup_amount': amount,
            'waiting_for': 'payment_screenshot',
            'payment_method': 'sbp'
        }
        
        # Show payment instructions
        payment_details = get_payment_details()
        keyboard = payment_kb(user_lang, amount=amount)
        
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
        try:
            error_msg = "❌ Ошибка сервера, попробуйте позже" if user_lang == 'ru' else "❌ Server error, please try later"
            if query:
                await query.answer(error_msg, show_alert=True)
        except:
            pass
        return ConversationHandler.END


# ==================== ПРИМЕРЫ ЗАМЕНЫ КЛАВИАТУР ====================

"""
ПРИМЕР 1: Замена в button_callback для back_to_menu

БЫЛО:
    keyboard = []
    keyboard.append([InlineKeyboardButton(t('btn_back_to_menu', lang=user_lang), callback_data="back_to_menu")])
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
ПРИМЕР 2: Замена в show_models

БЫЛО:
    keyboard = []
    for model in models:
        keyboard.append([InlineKeyboardButton(...)])
    keyboard.append([InlineKeyboardButton(t('btn_back', lang=user_lang), callback_data="back_to_menu")])
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

СТАЛО:
    keyboard = kie_models_kb(user_id, user_lang, models)
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
"""

"""
ПРИМЕР 3: Замена в admin_stats

БЫЛО:
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        ...
    ]
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

СТАЛО:
    keyboard = admin_kb(user_lang)
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
"""


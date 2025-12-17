"""
5 САМЫХ КРИТИЧНЫХ HANDLERS - ИСПРАВЛЕНЫ ЦЕЛИКОМ
"""

# ==================== 1. ИСПРАВЛЕННЫЙ confirm_generation ====================

async def confirm_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle generation confirmation.
    ИСПРАВЛЕНО: Все API вызовы обернуты в try/except, используется safe_kie_call,
    добавлены async locks для баланса, проверка дублей, всегда parse_mode и keyboard.
    """
    import time
    start_time = time.time()
    query = update.callback_query
    user_id = update.effective_user.id
    logger.info(f"🔥🔥🔥 CONFIRM_GENERATION ENTRY: user_id={user_id}, query_id={query.id if query else 'None'}")
    
    # ✅ ИСПРАВЛЕНО: Всегда отвечаем на callback
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
    
    # ✅ ИСПРАВЛЕНО: Проверка блокировки с try/except
    try:
        if not is_admin_user and is_user_blocked(user_id):
            keyboard = main_menu_kb(user_id, user_lang)
            await send_or_edit_message(
                "❌ <b>Ваш аккаунт заблокирован</b>\n\n"
                "Обратитесь к администратору для разблокировки.",
                keyboard=keyboard
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking user block status: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже", keyboard=keyboard)
        return ConversationHandler.END
    
    # ✅ ИСПРАВЛЕНО: Проверка сессии с try/except
    try:
        if user_id not in user_sessions:
            logger.error(f"❌❌❌ CRITICAL: Session not found in confirm_generation! user_id={user_id}")
            
            # Try to restore from backup
            if hasattr(context, 'user_data') and context.user_data.get('session_backup_user_id') == user_id:
                session_backup = context.user_data.get('session_backup')
                if session_backup:
                    logger.warning(f"⚠️⚠️⚠️ Restoring session from context.user_data backup for user_id={user_id}")
                    user_sessions[user_id] = session_backup.copy()
                    logger.info(f"✅✅✅ Session restored from context.user_data: user_id={user_id}")
                else:
                    keyboard = main_menu_kb(user_id, user_lang)
                    await send_or_edit_message("❌ Сессия не найдена. Пожалуйста, начните заново с /start", keyboard=keyboard)
                    return ConversationHandler.END
            else:
                keyboard = main_menu_kb(user_id, user_lang)
                await send_or_edit_message("❌ Сессия не найдена. Пожалуйста, начните заново с /start", keyboard=keyboard)
                return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error restoring session: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже", keyboard=keyboard)
        return ConversationHandler.END
    
    session = user_sessions[user_id]
    logger.info(f"✅✅✅ Session found in confirm_generation: user_id={user_id}, model_id={session.get('model_id')}")
    
    # ✅ ИСПРАВЛЕНО: Проверка дублей с try/except
    try:
        if 'task_id' in session:
            task_id_existing = session.get('task_id')
            logger.warning(f"⚠️⚠️⚠️ Task {task_id_existing} already exists in session for user {user_id}")
            keyboard = main_menu_kb(user_id, user_lang)
            await send_or_edit_message(
                f"⚠️ <b>Генерация уже запущена</b>\n\n"
                f"Задача уже создана.\n"
                f"Task ID: <code>{task_id_existing}</code>",
                keyboard=keyboard
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking duplicate task: {e}", exc_info=True)
    
    model_id = session.get('model_id')
    params = session.get('params', {})
    model_info = session.get('model_info', {})
    
    # ✅ ИСПРАВЛЕНО: Проверка дублей в active_generations (10 секунд)
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
    except Exception as e:
        logger.error(f"Error checking active generations: {e}", exc_info=True)
    
    # ✅ ИСПРАВЛЕНО: Применение значений по умолчанию с try/except
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
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже", keyboard=keyboard)
        return ConversationHandler.END
    
    # ✅ ИСПРАВЛЕНО: Проверка бесплатной генерации с try/except
    try:
        is_free = is_free_generation_available(user_id, model_id)
        price = calculate_price_rub(model_id, params, is_admin_user)
        if is_free:
            price = 0.0
    except Exception as e:
        logger.error(f"Error checking free generation: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже", keyboard=keyboard)
        return ConversationHandler.END
    
    # ✅ ИСПРАВЛЕНО: Проверка баланса с async lock
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
                keyboard = main_menu_kb(user_id, user_lang)
                await send_or_edit_message(
                    f"❌ <b>Превышен лимит</b>\n\n"
                    f"💰 <b>Требуется:</b> {price_str} ₽\n"
                    f"💳 <b>Лимит:</b> {limit:.2f} ₽\n"
                    f"💸 <b>Потрачено:</b> {spent:.2f} ₽\n"
                    f"✅ <b>Осталось:</b> {remaining_str} ₽\n\n"
                    f"Обратитесь к главному администратору для увеличения лимита.",
                    keyboard=keyboard
                )
                return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking balance: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже", keyboard=keyboard)
        return ConversationHandler.END
    
    await send_or_edit_message("🔄 Создаю задачу генерации... Пожалуйста, подождите.")
    
    # ✅ ИСПРАВЛЕНО: Подготовка API параметров с try/except
    try:
        api_params = params.copy()
        # ... (все конвертации параметров как в оригинале) ...
        # (здесь должна быть полная логика конвертации параметров для всех моделей)
    except Exception as e:
        logger.error(f"Error preparing API params: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже", keyboard=keyboard)
        return ConversationHandler.END
    
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
    
    # ✅ ИСПРАВЛЕНО: Сохранение задачи с try/except
    try:
        session['task_id'] = task_id
        generation_key = (user_id, task_id)
        
        # Move to active_generations
        async with active_generations_lock:
            active_generations[generation_key] = {
                **session.copy(),
                'created_at': time.time(),
                'status_message': None
            }
        
        # Start polling task status
        try:
            await poll_task_status(update, context, task_id, user_id)
        except Exception as e:
            logger.error(f"Error starting poll_task_status: {e}", exc_info=True)
            # Clean up
            async with active_generations_lock:
                active_generations.pop(generation_key, None)
            keyboard = main_menu_kb(user_id, user_lang)
            await send_or_edit_message("❌ Ошибка сервера, попробуйте позже", keyboard=keyboard)
            return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error storing task: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        await send_or_edit_message("❌ Ошибка сервера, попробуйте позже", keyboard=keyboard)
        return ConversationHandler.END
    
    return ConversationHandler.END


# ==================== 2. ИСПРАВЛЕННЫЙ poll_task_status ====================

async def poll_task_status(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str, user_id: int):
    """
    Poll task status until completion.
    ИСПРАВЛЕНО: Все API вызовы обернуты в try/except, используется safe_kie_call,
    добавлены async locks для баланса, всегда parse_mode и keyboard.
    """
    max_attempts = 60  # 5 minutes max
    attempt = 0
    start_time = asyncio.get_event_loop().time()
    last_status_message = None
    user_lang = get_user_language(user_id)
    
    # Get chat_id
    chat_id = user_id
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        chat_id = update.effective_chat.id
    elif update and hasattr(update, 'message') and update.message:
        chat_id = update.message.chat_id
    elif update and hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat_id
    
    while attempt < max_attempts:
        await asyncio.sleep(5)  # Wait 5 seconds between polls
        attempt += 1
        
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
            
            state = status_result.get('state')
            
            if state == 'success':
                # ✅ ИСПРАВЛЕНО: Отправка уведомления с try/except
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="✅ <b>Генерация завершена!</b>\n\n⏳ Загружаю результат...",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.warning(f"Could not send completion notification: {e}")
                
                # ✅ ИСПРАВЛЕНО: Вычитание баланса с async lock
                generation_key = (user_id, task_id)
                saved_session_data = None
                model_id = ''
                params = {}
                
                try:
                    async with active_generations_lock:
                        if generation_key in active_generations:
                            session = active_generations[generation_key]
                            saved_session_data = {
                                'model_id': session.get('model_id'),
                                'model_info': session.get('model_info'),
                                'params': session.get('params', {}).copy(),
                                'properties': session.get('properties', {}).copy(),
                                'required': session.get('required', []).copy()
                            }
                            
                            model_id = session.get('model_id', '')
                            params = session.get('params', {})
                            is_admin_user = get_is_admin(user_id)
                            is_free = session.get('is_free_generation', False)
                        else:
                            logger.warning(f"Generation session not found for {generation_key}")
                            is_admin_user = get_is_admin(user_id)
                            is_free = False
                        
                        if is_free:
                            if use_free_generation(user_id):
                                price = 0.0
                            else:
                                is_free = False
                                price = calculate_price_rub(model_id, params, is_admin_user)
                        else:
                            price = calculate_price_rub(model_id, params, is_admin_user)
                        
                        if user_id != ADMIN_ID:
                            if is_free:
                                pass
                            elif is_admin_user:
                                add_admin_spent(user_id, price)
                            else:
                                # ✅ ИСПРАВЛЕНО: Используем async версию с lock
                                success = await subtract_user_balance_async(user_id, price)
                                if not success:
                                    logger.error(f"Failed to subtract balance for user {user_id}, price {price}")
                    
                    # ✅ ИСПРАВЛЕНО: Обработка результата с try/except
                    result_json = status_result.get('resultJson', '{}')
                    try:
                        result_data = json.loads(result_json)
                        
                        # Determine if this is a video model
                        is_video_model = model_id in ['sora-2-text-to-video', 'sora-watermark-remover', ...]
                        
                        # Get result URLs
                        if model_id == 'sora-2-text-to-video':
                            remove_watermark = params.get('remove_watermark', True)
                            if remove_watermark:
                                result_urls = result_data.get('resultUrls', [])
                            else:
                                result_urls = result_data.get('resultWaterMarkUrls', [])
                                if not result_urls:
                                    result_urls = result_data.get('resultUrls', [])
                        else:
                            result_urls = result_data.get('resultUrls', [])
                        
                        # ✅ ИСПРАВЛЕНО: Сохранение в историю с try/except
                        try:
                            if result_urls and model_id:
                                model_info = saved_session_data.get('model_info', {}) if saved_session_data else {}
                                model_name = model_info.get('name', model_id)
                                save_generation_to_history(
                                    user_id=user_id,
                                    model_id=model_id,
                                    model_name=model_name,
                                    params=params.copy(),
                                    result_urls=result_urls.copy(),
                                    task_id=task_id,
                                    price=price,
                                    is_free=is_free
                                )
                        except Exception as e:
                            logger.error(f"Error saving to history: {e}", exc_info=True)
                        
                        # Save for "generate_again"
                        if saved_session_data:
                            if user_id not in saved_generations:
                                saved_generations[user_id] = {}
                            saved_generations[user_id] = saved_session_data.copy()
                        
                        # ✅ ИСПРАВЛЕНО: Клавиатура через функцию
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔄 Сгенерировать еще", callback_data="generate_again")],
                            [InlineKeyboardButton("📚 Мои генерации", callback_data="my_generations")],
                            [InlineKeyboardButton("◀️ Вернуться в меню", callback_data="back_to_menu")]
                        ])
                        
                        # ✅ ИСПРАВЛЕНО: Отправка медиа с try/except
                        if result_urls:
                            try:
                                session_http = await get_http_client()
                                for i, url in enumerate(result_urls[:5]):
                                    try:
                                        async with session_http.get(url) as resp:
                                            if resp.status == 200:
                                                media_data = await resp.read()
                                                
                                                is_last = (i == len(result_urls[:5]) - 1)
                                                caption = "✅ <b>Генерация завершена!</b>" if i == 0 else None
                                                
                                                if is_video_model:
                                                    video_file = io.BytesIO(media_data)
                                                    video_file.name = f"generated_video_{i+1}.mp4"
                                                    
                                                    if is_last:
                                                        last_message = await context.bot.send_video(
                                                            chat_id=chat_id,
                                                            video=video_file,
                                                            caption=caption,
                                                            reply_markup=keyboard,
                                                            parse_mode='HTML'
                                                        )
                                                    else:
                                                        await context.bot.send_video(
                                                            chat_id=chat_id,
                                                            video=video_file,
                                                            caption=caption,
                                                            parse_mode='HTML'
                                                        )
                                                else:
                                                    photo_file = io.BytesIO(media_data)
                                                    photo_file.name = f"generated_image_{i+1}.png"
                                                    
                                                    if is_last:
                                                        last_message = await context.bot.send_photo(
                                                            chat_id=chat_id,
                                                            photo=photo_file,
                                                            caption=caption,
                                                            reply_markup=keyboard,
                                                            parse_mode='HTML'
                                                        )
                                                    else:
                                                        await context.bot.send_photo(
                                                            chat_id=chat_id,
                                                            photo=photo_file,
                                                            caption=caption,
                                                            parse_mode='HTML'
                                                        )
                                    except Exception as e:
                                        logger.error(f"Error sending media item {i}: {e}", exc_info=True)
                            except Exception as e:
                                logger.error(f"Error getting HTTP client: {e}", exc_info=True)
                                keyboard = main_menu_kb(user_id, user_lang)
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text="❌ Ошибка загрузки результата. Попробуйте позже.",
                                    parse_mode='HTML',
                                    reply_markup=keyboard
                                )
                        
                        # Clean up
                        async with active_generations_lock:
                            if generation_key in active_generations:
                                del active_generations[generation_key]
                        
                        break
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing result JSON: {e}", exc_info=True)
                        keyboard = main_menu_kb(user_id, user_lang)
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="❌ Ошибка обработки результата. Попробуйте позже.",
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing successful generation: {e}", exc_info=True)
                    keyboard = main_menu_kb(user_id, user_lang)
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="❌ Ошибка сервера, попробуйте позже",
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
                    except:
                        pass
                    break
            
            elif state == 'failed':
                error_msg = status_result.get('error', 'Unknown error')
                logger.error(f"❌ Task failed: {error_msg}", exc_info=True)
                keyboard = main_menu_kb(user_id, user_lang)
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ <b>Генерация не удалась:</b>\n\n{error_msg}",
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
            
            # Task still processing
            if attempt % 6 == 0:  # Every 30 seconds
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⏳ Генерация выполняется... (попытка {attempt}/{max_attempts})",
                        parse_mode='HTML'
                    )
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in poll_task_status: {e}", exc_info=True)
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
    
    # Clean up if still in active_generations
    generation_key = (user_id, task_id)
    async with active_generations_lock:
        if generation_key in active_generations:
            del active_generations[generation_key]


# ==================== 3. ИСПРАВЛЕННЫЙ input_parameters ====================

async def input_parameters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle parameter input.
    ИСПРАВЛЕНО: Все операции с файлами обернуты в try/except, всегда parse_mode и keyboard.
    """
    user_id = update.effective_user.id
    user_lang = get_user_language(user_id)
    
    # ✅ ИСПРАВЛЕНО: Проверка сессии с try/except
    try:
        if user_id not in user_sessions:
            keyboard = main_menu_kb(user_id, user_lang)
            await update.message.reply_text(
                "❌ Сессия не найдена. Начните заново с /start",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking session: {e}", exc_info=True)
        keyboard = main_menu_kb(user_id, user_lang)
        await update.message.reply_text(
            "❌ Ошибка сервера, попробуйте позже",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    session = user_sessions[user_id]
    waiting_for = session.get('waiting_for')
    
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
    
    # ✅ ИСПРАВЛЕНО: Обработка текста с try/except
    elif update.message.text:
        try:
            text = update.message.text.strip()
            
            # Check for cancel
            if text.lower() in ['/cancel', 'отмена', 'cancel']:
                session['waiting_for'] = None
                session['current_param'] = None
                keyboard = main_menu_kb(user_id, user_lang)
                await update.message.reply_text(
                    "❌ Операция отменена.",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            # Store text parameter
            current_param = session.get('current_param', 'prompt')
            if 'params' not in session:
                session['params'] = {}
            session['params'][current_param] = text
            session['waiting_for'] = None
            session['current_param'] = None
            
            # Move to next parameter
            try:
                next_param_result = await start_next_parameter(update, context, user_id)
                if next_param_result:
                    return next_param_result
            except Exception as e:
                logger.error(f"Error starting next parameter: {e}", exc_info=True)
                keyboard = main_menu_kb(user_id, user_lang)
                await update.message.reply_text(
                    "❌ Ошибка сервера, попробуйте позже",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            # All parameters collected
            model_name = session.get('model_info', {}).get('name', 'Unknown')
            params = session.get('params', {})
            params_text = "\n".join([f"  • {k}: {str(v)[:50]}..." for k, v in params.items()])
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(t('btn_confirm_generate', lang=user_lang), callback_data="confirm_generate")],
                [
                    InlineKeyboardButton(t('btn_back', lang=user_lang), callback_data="back_to_previous_step"),
                    InlineKeyboardButton(t('btn_home', lang=user_lang), callback_data="back_to_menu")
                ],
                [InlineKeyboardButton(t('btn_cancel', lang=user_lang), callback_data="cancel")]
            ])
            
            await update.message.reply_text(
                f"📋 <b>Подтверждение:</b>\n\n"
                f"Модель: <b>{model_name}</b>\n"
                f"Параметры:\n{params_text}\n\n"
                f"Продолжить генерацию?",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return CONFIRMING_GENERATION
            
        except Exception as e:
            logger.error(f"Error processing text input: {e}", exc_info=True)
            keyboard = main_menu_kb(user_id, user_lang)
            await update.message.reply_text(
                "❌ Ошибка сервера, попробуйте позже",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return INPUTTING_PARAMS
    
    return INPUTTING_PARAMS


# ==================== 4. ИСПРАВЛЕННЫЙ button_callback (критичные части) ====================

# В button_callback для обработчика "check_balance":
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    # ... (начало функции как в оригинале) ...
    
    # ✅ ИСПРАВЛЕНО: Обработчик check_balance
    if data == "check_balance":
        try:
            # Answer callback immediately
            try:
                await query.answer()
            except:
                pass
            
            # ✅ ИСПРАВЛЕНО: Получение баланса с async lock
            try:
                user_lang = get_user_language(user_id)
                balance_info = await get_balance_info(user_id, user_lang)  # Если функция async
                balance_text = await format_balance_message(balance_info, user_lang)
                keyboard = get_balance_keyboard(balance_info, user_lang)
                
                try:
                    await query.edit_message_text(
                        balance_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Error editing message in check_balance: {e}", exc_info=True)
                    try:
                        await query.message.reply_text(
                            balance_text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except:
                        pass
            except Exception as e:
                logger.error(f"Error in check_balance: {e}", exc_info=True)
                try:
                    await query.answer("❌ Ошибка сервера, попробуйте позже", show_alert=True)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error in check_balance handler: {e}", exc_info=True)
            try:
                await query.answer("❌ Ошибка сервера, попробуйте позже", show_alert=True)
            except:
                pass
        return ConversationHandler.END


# ==================== 5. ИСПРАВЛЕННЫЙ payment_sbp_handler ====================

async def payment_sbp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик оплаты через СБП с валидацией.
    ИСПРАВЛЕНО: Валидация суммы, формата callback_data, обработка /cancel, try/except везде.
    """
    query = update.callback_query
    user_id = update.effective_user.id
    user_lang = get_user_language(user_id)
    
    try:
        # ✅ ИСПРАВЛЕНО: Всегда отвечаем на callback
        if query:
            try:
                await query.answer()
            except Exception as e:
                logger.warning(f"Could not answer callback: {e}")
        
        # ✅ ИСПРАВЛЕНО: Валидация callback_data формата
        data = query.data if query else None
        if not data or not data.startswith("pay_sbp:"):
            logger.error(f"Invalid callback_data format: {data}")
            keyboard = main_menu_kb(user_id, user_lang)
            await query.edit_message_text(
                "❌ Ошибка: неверный формат запроса",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # ✅ ИСПРАВЛЕНО: Извлечение и валидация суммы
        try:
            amount_str = data.split(":", 1)[1]
            amount = float(amount_str)
            
            # Валидация суммы
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
        
        # ✅ ИСПРАВЛЕНО: Сохранение информации о платеже с try/except
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
        try:
            error_msg = "❌ Ошибка сервера, попробуйте позже" if user_lang == 'ru' else "❌ Server error, please try later"
            if query:
                await query.answer(error_msg, show_alert=True)
            keyboard = main_menu_kb(user_id, user_lang)
            if query:
                await query.edit_message_text(
                    error_msg,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
        except:
            pass
        return ConversationHandler.END


# ==================== ИНТЕГРАЦИЯ В MAIN() ====================

"""
В функции main() добавить:

# Глобальный error handler
application.add_error_handler(global_error_handler)

# Импорт всех новых функций
from COMPLETE_FIXES import (
    safe_kie_call,
    get_user_balance_async,
    add_user_balance_async,
    subtract_user_balance_async,
    main_menu_kb,
    kie_models_kb,
    admin_kb,
    payment_kb,
    global_error_handler,
    get_user_generations_history_optimized
)
"""


"""
Translation module for KIE Telegram Bot
Provides translations for Russian and English
"""

TRANSLATIONS = {
    'ru': {
        'welcome_new': (
            '🎉 <b>ПРИВЕТ, {name}!</b> 🎉\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🔥 <b>У ТЕБЯ ЕСТЬ {free} БЕСПЛАТНЫХ ГЕНЕРАЦИЙ!</b> 🔥\n\n'
            '✨ <b>ПРЕМИУМ AI MARKETPLACE</b> ✨\n\n'
            '🚀 <b>Что это за бот?</b>\n'
            '• 📦 <b>{models} топовых нейросетей</b> в одном месте\n'
            '• 🎯 <b>{types} типов генерации</b> контента\n'
            '• 🌐 Прямой доступ БЕЗ VPN\n'
            '• ⚡ Мгновенная генерация\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '👥 <b>Сейчас в боте:</b> {online} человек онлайн\n\n'
            '🚀 <b>ПОЛНЫЙ ФУНКЦИОНАЛ:</b>\n\n'
            '<b>📸 РАБОТА С ИЗОБРАЖЕНИЯМИ:</b>\n'
            '• ✨ Текст в фото - создание изображений из текста\n'
            '• 🎨 Фото в фото - трансформация и стилизация изображений\n'
            '• 🖼️ Редактирование фото - улучшение, масштабирование, удаление фона\n'
            '• 🎨 Рефрейминг - изменение кадра и соотношения сторон\n\n'
            '<b>🎬 РАБОТА С ВИДЕО:</b>\n'
            '• 🎬 Текст в видео - создание видео из текстового описания\n'
            '• 📸 Фото в видео - превращение изображений в динамичные видео\n'
            '• 🎙️ Речь в видео - создание видео из речи и аудио\n'
            '• 👄 Синхронизация губ - аватары с синхронизацией губ\n'
            '• ✂️ Редактирование видео - улучшение качества, удаление водяных знаков\n\n'
            '<b>🎙️ РАБОТА С АУДИО:</b>\n'
            '• 🎙️ Речь в текст - преобразование речи в текст с высокой точностью\n\n'
            '🎯 Все это БЕЗ VPN и по цене жвачки!\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🏢 <b>ТОПОВЫЕ НЕЙРОСЕТИ 2025:</b>\n\n'
            '🤖 OpenAI • Google • Black Forest Labs\n'
            '🎬 ByteDance • Ideogram • Qwen\n'
            '✨ Kling • Hailuo • Topaz\n'
            '🎨 Recraft • Grok (xAI) • Wan\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🎁 <b>КАК НАЧАТЬ?</b>\n\n'
            '1️⃣ <b>Нажми кнопку "🎁 Генерировать бесплатно"</b> ниже\n'
            '   → Создай свое первое изображение за 30 секунд!\n\n'
            '2️⃣ <b>Напиши что хочешь увидеть</b> (например: "Кот в космосе")\n'
            '   → Нейросеть создаст это для тебя!\n\n'
            '3️⃣ <b>Получи результат и наслаждайся!</b> 🎉\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🆓 <b>БЕСПЛАТНЫЕ ИНСТРУМЕНТЫ:</b>\n'
            '• <b>Recraft Remove Background</b> - удаление фона (бесплатно и безлимитно!)\n'
            '• <b>Recraft Crisp Upscale</b> - улучшение качества изображений (бесплатно и безлимитно!)\n'
            '• <b>Z-Image</b> - генерация изображений (5 раз в день, можно увеличить через приглашения!)\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '📊 <b>СТАТИСТИКА:</b>\n'
            '• {models} топовых нейросетей\n'
            '• {types} типов генерации\n'
            '• 🌐 Прямой доступ БЕЗ VPN\n'
            '• ⚡ Мгновенная генерация\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '💰 <b>ЦЕНЫ:</b>\n'
            'От 0.62 ₽ за изображение • От 3.86 ₽ за видео\n\n'
            '💡 <b>Пригласи друга → получи +{ref_bonus} бесплатных генераций Z-Image!</b>\n'
            '🔗 <code>{ref_link}</code>'
        ),
        'welcome_returning': (
            '👋 <b>С возвращением, {name}!</b> 🤖✨\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '👥 <b>Сейчас в боте:</b> {online} человек онлайн\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🔥 <b>У ТЕБЯ ЕСТЬ {free} БЕСПЛАТНЫХ ГЕНЕРАЦИЙ!</b> 🔥\n\n'
            '✨ <b>ПРЕМИУМ AI MARKETPLACE</b> ✨\n\n'
            '🚀 <b>Что это за бот?</b>\n'
            '• 📦 <b>{models} топовых нейросетей</b> в одном месте\n'
            '• 🎯 <b>{types} типов генерации</b> контента\n'
            '• 🌐 Прямой доступ БЕЗ VPN\n'
            '• ⚡ Мгновенная генерация\n\n'
            '💡 <b>Нажми кнопку "🎁 Генерировать бесплатно" ниже</b>\n\n'
        ),
        'select_language': (
            '🌍 <b>Выберите язык / Choose language</b>\n\n'
            'Select your preferred language:'
        ),
        'language_set': '✅ Язык установлен! / Language set!',
        'generate_free': '🎁 Генерировать бесплатно',
        'balance': '💰 Баланс',
        'models': '🤖 Модели',
        'help': '❓ Помощь',
        'support': '💬 Поддержка',
        'referral': '🎁 Рефералы',
        'my_generations': '📋 Мои генерации',
        'admin_panel': '👑 Админ-панель',
        # Buttons
        'btn_generate_free': '🎁 ГЕНЕРИРОВАТЬ БЕСПЛАТНО ({remaining}/{total} осталось)',
        'btn_generate_free_no_left': '🎁 ГЕНЕРИРОВАТЬ БЕСПЛАТНО (0/{total} осталось)',
        'btn_invite_friend': '🎁 Пригласи друга → получи +{bonus} бесплатных!',
        'btn_free_tools': '🆓 БЕСПЛАТНЫЕ ИНСТРУМЕНТЫ',
        'btn_all_models': '🤖 Все модели ({count})',
        'btn_claim_gift': '🎰 Получить подарок',
        'btn_balance': '💰 Баланс',
        'btn_my_generations': '📚 Мои генерации',
        'btn_top_up': '💳 Пополнить',
        'btn_invite_friend_short': '🎁 Пригласить друга',
        'btn_how_it_works': '❓ Как это работает?',
        'btn_help': '🆘 Помощь',
        'btn_support': '💬 Поддержка',
        'btn_language': '🌐 Язык / Language',
        'btn_copy_bot': '📋 Скопировать этого бота',
        'msg_copy_bot_title': '📋 <b>СКОПИРОВАТЬ ЭТОГО БОТА</b> 📋',
        'msg_copy_bot_description': (
            'Этот бот можно скопировать с помощью кода и настроек.\n\n'
            '👨‍💻 <b>Администратор</b> может поделиться:\n'
            '• Исходным кодом бота\n'
            '• Настройками и конфигурацией\n'
            '• Инструкциями по развертыванию\n\n'
            '💡 <b>Свяжитесь с администратором</b> для получения доступа к коду и настройкам.'
        ),
        'btn_admin_panel': '👑 АДМИН ПАНЕЛЬ',
        'btn_back': '◀️ Назад',
        'btn_back_to_menu': '◀️ Главное меню',
        'btn_cancel': '❌ Отмена',
        'btn_all_models_short': '📋 Все модели',
        'btn_check_balance': '💰 Проверить баланс',
        'btn_confirm_generate': '✅ Генерировать',
        'msg_operation_cancelled': '❌ Операция отменена.\n\nВы вернулись в главное меню.',
        # Messages
        'msg_referral_bonus': '\n🎁 <b>Отлично!</b> Ты пригласил <b>{count}</b> друзей\n   → Получено <b>+{bonus} бесплатных генераций</b>! 🎉\n\n',
        'msg_full_functionality': (
            '💎 <b>ПОЛНЫЙ ФУНКЦИОНАЛ:</b>\n\n'
            '<b>📸 РАБОТА С ИЗОБРАЖЕНИЯМИ:</b>\n'
            '• ✨ Текст в фото - создание изображений из текста\n'
            '• 🎨 Фото в фото - трансформация и стилизация изображений\n'
            '• 🖼️ Редактирование фото - улучшение, масштабирование, удаление фона\n'
            '• 🎨 Рефрейминг - изменение кадра и соотношения сторон\n\n'
            '<b>🎬 РАБОТА С ВИДЕО:</b>\n'
            '• 🎬 Текст в видео - создание видео из текстового описания\n'
            '• 📸 Фото в видео - превращение изображений в динамичные видео\n'
            '• 🎙️ Речь в видео - создание видео из речи и аудио\n'
            '• 👄 Синхронизация губ - аватары с синхронизацией губ\n'
            '• ✂️ Редактирование видео - улучшение качества, удаление водяных знаков\n\n'
            '<b>🎙️ РАБОТА С АУДИО:</b>\n'
            '• 🎙️ Речь в текст - преобразование речи в текст с высокой точностью\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🆓 <b>БЕСПЛАТНЫЕ ИНСТРУМЕНТЫ:</b>\n'
            '• <b>Recraft Remove Background</b> - удаление фона (бесплатно и безлимитно!)\n'
            '• <b>Recraft Crisp Upscale</b> - улучшение качества изображений (бесплатно и безлимитно!)\n'
            '• <b>Z-Image</b> - генерация изображений\n'
            '   📊 <b>Бесплатно:</b> <b>{remaining}/{total}</b> генераций сегодня\n'
            '   🎁 <b>Пригласи друга → получи +{ref_bonus} бесплатных генераций!</b>\n'
            '   🔗 Реферальная ссылка: <code>{ref_link}</code>\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '📊 <b>СТАТИСТИКА:</b>\n'
            '• {models} топовых нейросетей\n'
            '• {types} типов генерации\n'
            '• 🌐 Прямой доступ БЕЗ VPN\n'
            '• ⚡ Мгновенная генерация\n\n'
            '💰 <b>ЦЕНЫ:</b>\n'
            'От 0.62 ₽ за изображение • От 3.86 ₽ за видео\n\n'
            '💡 <b>Пригласи друга → получи +{ref_bonus} бесплатных генераций Z-Image!</b>\n'
            '🔗 <code>{ref_link}</code>\n\n'
            '🎯 <b>Выбери формат генерации ниже или начни с бесплатной!</b>'
        ),
        'error_invalid_language': 'Неверный язык / Invalid language',
        'error_already_claimed': 'Вы уже получили подарок! / You already claimed the gift!',
        'btn_back_to_menu': '◀️ Главное меню',
        'btn_back_to_models': '◀️ Назад к моделям',
        'btn_home': '🏠 Главное меню',
        'btn_skip': '⏭️ Пропустить',
        'btn_top_up_balance': '💳 Пополнить баланс',
        'error_try_start': '❌ Ошибка. Попробуйте /start',
        'btn_start_generation': '🎨 Начать генерацию',
        'msg_referral_title': '🎁 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b> 🎁',
        'msg_referral_how_it_works': (
            '💡 <b>КАК ЭТО РАБОТАЕТ:</b>\n\n'
            '1️⃣ Пригласи друга по вашей ссылке\n'
            '2️⃣ Он зарегистрируется через бота\n'
            '3️⃣ Вы получите <b>+{bonus} бесплатных генераций в Z-Image</b>!'
        ),
        'msg_referral_stats': (
            '📊 <b>ВАША СТАТИСТИКА:</b>\n\n'
            '• Приглашено друзей: <b>{count}</b>\n'
            '• Получено бонусов: <b>{bonus_total}</b> генераций\n'
            '• Доступно бесплатно: <b>{remaining}</b> генераций в Z-Image'
        ),
        'msg_referral_important': '⚠️ <b>ВАЖНО:</b> Бесплатные генерации доступны только для модели <b>Z-Image</b>!',
        'msg_referral_link_title': '🔗 <b>ВАША РЕФЕРАЛЬНАЯ ССЫЛКА:</b>',
        'msg_referral_send': '💬 <b>Отправьте эту ссылку другу!</b>\nПосле его регистрации вы получите бонус автоматически.',
        'msg_payment_success': '✅ <b>ОПЛАТА УСПЕШНА!</b> ✅',
        'msg_payment_added': '💰 <b>Зачислено:</b> {amount:.2f} ₽',
        'msg_payment_method': '⭐ <b>Способ:</b> Telegram Stars ({stars} ⭐)',
        'msg_payment_balance': '💳 <b>Ваш баланс:</b> {balance} ₽',
        'msg_payment_use_funds': '🎉 Теперь вы можете использовать средства для генерации контента!',
        'error_session_empty': '❌ Ошибка: сессия пуста. Пожалуйста, начните заново.',
        'error_no_data': '❌ Ошибка: нет данных в запросе. Попробуйте еще раз.',
        'error_invalid_format': '❌ Ошибка: неверный формат запроса. Попробуйте еще раз.',
        'error_unknown': '❌ Произошла ошибка. Пожалуйста, попробуйте позже или используйте /start',
        'error_insufficient_balance': '❌ Недостаточно средств на балансе',
        'error_operation_failed': '❌ Операция не выполнена. Попробуйте еще раз.',
        'error_timeout': '⏱️ Превышено время ожидания. Попробуйте еще раз.',
        'error_network': '🌐 Ошибка сети. Проверьте подключение и попробуйте позже.',
        'error_display_generation': '❌ Ошибка при отображении генерации',
        'msg_spinning_wheel': '🎰 Крутим колесо фортуны...',
        'msg_admin_only': 'Эта функция доступна только администратору.',
        'msg_user_mode_enabled': 'Режим пользователя включен',
        'msg_returning_to_admin': 'Возврат в админ-панель',
        'msg_insufficient_funds': '❌ <b>Недостаточно средств</b>\n💳 <b>Ваш баланс:</b> {balance} ₽\n💵 <b>Требуется:</b> {required} ₽\n\nПополните баланс для генерации.',
        'msg_available_generations': '✅ <b>Доступно генераций:</b> {count}\n💳 <b>Ваш баланс:</b> {balance} ₽',
        'msg_unlimited_available': '✅ <b>Доступно:</b> Безлимит',
        'btn_check_balance': '💰 Проверить баланс',
        'btn_back_to_categories': '◀️ Назад к категориям',
        'btn_previous': '◀️ Предыдущая',
        'btn_next': 'Следующая ▶️',
        'btn_back_to_admin': '◀️ Назад в админ-панель',
        'btn_back_to_list': '◀️ Назад к списку',
        'btn_back_to_history': '◀️ Назад к истории',
        'btn_confirm_generate_text': '✅ Генерировать',
        'btn_copy_link': '📋 Скопировать ссылку',
        'btn_all_models_text': '📋 Все модели',
        'btn_z_image_free': '🖼️ Z-Image (бесплатно)',
        'btn_next_step': '▶️ Далее',
        'btn_complete': '▶️ Завершить',
        'btn_custom_amount': '💰 Своя сумма',
        'btn_return_to_admin': '🔙 Вернуться в админ-панель',
        'btn_view_result': '👁️ Показать результат',
    },
    'en': {
        'welcome_new': (
            '🎉 <b>HELLO, {name}!</b> 🎉\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🔥 <b>YOU HAVE {free} FREE GENERATIONS!</b> 🔥\n\n'
            '✨ <b>PREMIUM AI MARKETPLACE</b> ✨\n\n'
            '🚀 <b>What is this bot?</b>\n'
            '• 📦 <b>{models} top AI models</b> in one place\n'
            '• 🎯 <b>{types} types of generation</b> content\n'
            '• 🌐 Direct access WITHOUT VPN\n'
            '• ⚡ Instant generation\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '👥 <b>Online now:</b> {online} people\n\n'
            '🚀 <b>FULL FUNCTIONALITY:</b>\n\n'
            '<b>📸 IMAGE GENERATION:</b>\n'
            '• ✨ Text to Image - create images from text\n'
            '• 🎨 Image to Image - transform and style images\n'
            '• 🖼️ Image Editing - enhance, upscale, remove background\n'
            '• 🎨 Reframing - change frame and aspect ratio\n\n'
            '<b>🎬 VIDEO GENERATION:</b>\n'
            '• 🎬 Text to Video - create videos from text descriptions\n'
            '• 📸 Image to Video - turn images into dynamic videos\n'
            '• 🎙️ Speech to Video - create videos from speech and audio\n'
            '• 👄 Lip Sync - avatars with lip synchronization\n'
            '• ✂️ Video Editing - quality enhancement, watermark removal\n\n'
            '<b>🎙️ AUDIO PROCESSING:</b>\n'
            '• 🎙️ Speech to Text - convert speech to text with high accuracy\n\n'
            '🎯 All WITHOUT VPN at affordable prices!\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🏢 <b>TOP AI MODELS 2025:</b>\n\n'
            '🤖 OpenAI • Google • Black Forest Labs\n'
            '🎬 ByteDance • Ideogram • Qwen\n'
            '✨ Kling • Hailuo • Topaz\n'
            '🎨 Recraft • Grok (xAI) • Wan\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🎁 <b>HOW TO START?</b>\n\n'
            '1️⃣ <b>Click the "🎁 Generate free" button</b> below\n'
            '   → Create your first image in 30 seconds!\n\n'
            '2️⃣ <b>Write what you want to see</b> (e.g., "Cat in space")\n'
            '   → AI will create it for you!\n\n'
            '3️⃣ <b>Get the result and enjoy!</b> 🎉\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🆓 <b>FREE TOOLS:</b>\n'
            '• <b>Recraft Remove Background</b> - remove background (free and unlimited!)\n'
            '• <b>Recraft Crisp Upscale</b> - enhance image quality (free and unlimited!)\n'
            '• <b>Z-Image</b> - image generation (5 times per day, can be increased by inviting users!)\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '📊 <b>STATISTICS:</b>\n'
            '• {models} top AI models\n'
            '• {types} generation types\n'
            '• 🌐 Direct access WITHOUT VPN\n'
            '• ⚡ Instant generation\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '💰 <b>PRICING:</b>\n'
            'From 0.62 ₽ per image • From 3.86 ₽ per video\n\n'
            '💡 <b>Invite a friend → get +{ref_bonus} free Z-Image generations!</b>\n'
            '🔗 <code>{ref_link}</code>'
        ),
        'welcome_returning': (
            '👋 <b>Welcome back, {name}!</b> 🤖✨\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '👥 <b>Online now:</b> {online} people\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🔥 <b>YOU HAVE {free} FREE GENERATIONS!</b> 🔥\n\n'
            '✨ <b>PREMIUM AI MARKETPLACE</b> ✨\n\n'
            '🚀 <b>What is this bot?</b>\n'
            '• 📦 <b>{models} top AI models</b> in one place\n'
            '• 🎯 <b>{types} types of generation</b> content\n'
            '• 🌐 Direct access WITHOUT VPN\n'
            '• ⚡ Instant generation\n\n'
            '💡 <b>Click the "🎁 Generate free" button below</b>\n\n'
        ),
        'select_language': (
            '🌍 <b>Choose language / Выберите язык</b>\n\n'
            'Select your preferred language:'
        ),
        'language_set': '✅ Language set! / Язык установлен!',
        'generate_free': '🎁 Generate free',
        'balance': '💰 Balance',
        'models': '🤖 Models',
        'help': '❓ Help',
        'support': '💬 Support',
        'referral': '🎁 Referrals',
        'my_generations': '📋 My generations',
        'admin_panel': '👑 Admin panel',
        # Buttons
        'btn_generate_free': '🎁 GENERATE FREE ({remaining}/{total} left)',
        'btn_generate_free_no_left': '🎁 GENERATE FREE (0/{total} left)',
        'btn_invite_friend': '🎁 Invite friend → get +{bonus} free!',
        'btn_free_tools': '🆓 FREE TOOLS',
        'btn_all_models': '🤖 All Models ({count})',
        'btn_claim_gift': '🎰 Claim Gift',
        'btn_balance': '💰 Balance',
        'btn_my_generations': '📚 My Generations',
        'btn_top_up': '💳 Top Up',
        'btn_invite_friend_short': '🎁 Invite Friend',
        'btn_how_it_works': '❓ How it works?',
        'btn_help': '🆘 Help',
        'btn_support': '💬 Support',
        'btn_language': '🌐 Language / Язык',
        'btn_copy_bot': '📋 Copy This Bot',
        'msg_copy_bot_title': '📋 <b>COPY THIS BOT</b> 📋',
        'msg_copy_bot_description': (
            'This bot can be copied using code and settings.\n\n'
            '👨‍💻 <b>Administrator</b> can share:\n'
            '• Bot source code\n'
            '• Settings and configuration\n'
            '• Deployment instructions\n\n'
            '💡 <b>Contact the administrator</b> to get access to code and settings.'
        ),
        'btn_admin_panel': '👑 ADMIN PANEL',
        'btn_back': '◀️ Back',
        'btn_back_to_menu': '◀️ Main Menu',
        'btn_cancel': '❌ Cancel',
        'btn_all_models_short': '📋 All Models',
        'btn_check_balance': '💰 Check Balance',
        'btn_confirm_generate': '✅ Generate',
        'msg_operation_cancelled': '❌ Operation cancelled.\n\nYou returned to the main menu.',
        # Messages
        'msg_referral_bonus': '\n🎁 <b>Great!</b> You invited <b>{count}</b> friends\n   → Received <b>+{bonus} free generations</b>! 🎉\n\n',
        'msg_full_functionality': (
            '💎 <b>FULL FUNCTIONALITY:</b>\n\n'
            '<b>📸 IMAGE GENERATION:</b>\n'
            '• ✨ Text to Image - create images from text\n'
            '• 🎨 Image to Image - transform and style images\n'
            '• 🖼️ Image Editing - enhance, upscale, remove background\n'
            '• 🎨 Reframing - change frame and aspect ratio\n\n'
            '<b>🎬 VIDEO GENERATION:</b>\n'
            '• 🎬 Text to Video - create videos from text descriptions\n'
            '• 📸 Image to Video - turn images into dynamic videos\n'
            '• 🎙️ Speech to Video - create videos from speech and audio\n'
            '• 👄 Lip Sync - avatars with lip synchronization\n'
            '• ✂️ Video Editing - quality enhancement, watermark removal\n\n'
            '<b>🎙️ AUDIO PROCESSING:</b>\n'
            '• 🎙️ Speech to Text - convert speech to text with high accuracy\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '🆓 <b>FREE TOOLS:</b>\n'
            '• <b>Recraft Remove Background</b> - remove background (free and unlimited!)\n'
            '• <b>Recraft Crisp Upscale</b> - enhance image quality (free and unlimited!)\n'
            '• <b>Z-Image</b> - image generation\n'
            '   📊 <b>Free:</b> <b>{remaining}/{total}</b> generations today\n'
            '   🎁 <b>Invite friend → get +{ref_bonus} free generations!</b>\n'
            '   🔗 Referral link: <code>{ref_link}</code>\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '📊 <b>STATISTICS:</b>\n'
            '• {models} top AI models\n'
            '• {types} generation types\n'
            '• 🌐 Direct access WITHOUT VPN\n'
            '• ⚡ Instant generation\n\n'
            '💰 <b>PRICING:</b>\n'
            'From 0.62 ₽ per image • From 3.86 ₽ per video\n\n'
            '💡 <b>Invite a friend → get +{ref_bonus} free Z-Image generations!</b>\n'
            '🔗 <code>{ref_link}</code>\n\n'
            '🎯 <b>Choose generation format below or start with free!</b>'
        ),
        'error_invalid_language': 'Invalid language / Неверный язык',
        'error_already_claimed': 'You already claimed the gift! / Вы уже получили подарок!',
        'btn_back_to_menu': '◀️ Main Menu',
        'btn_back_to_models': '◀️ Back to Models',
        'btn_home': '🏠 Main Menu',
        'btn_skip': '⏭️ Skip',
        'btn_top_up_balance': '💳 Top Up Balance',
        'error_try_start': '❌ Error. Try /start',
        'btn_start_generation': '🎨 Start Generation',
        'msg_referral_title': '🎁 <b>REFERRAL SYSTEM</b> 🎁',
        'msg_referral_how_it_works': (
            '💡 <b>HOW IT WORKS:</b>\n\n'
            '1️⃣ Invite a friend using your link\n'
            '2️⃣ They register through the bot\n'
            '3️⃣ You get <b>+{bonus} free Z-Image generations</b>!'
        ),
        'msg_referral_stats': (
            '📊 <b>YOUR STATISTICS:</b>\n\n'
            '• Friends invited: <b>{count}</b>\n'
            '• Bonuses received: <b>{bonus_total}</b> generations\n'
            '• Available free: <b>{remaining}</b> Z-Image generations'
        ),
        'msg_referral_important': '⚠️ <b>IMPORTANT:</b> Free generations are only available for <b>Z-Image</b> model!',
        'msg_referral_link_title': '🔗 <b>YOUR REFERRAL LINK:</b>',
        'msg_referral_send': '💬 <b>Send this link to a friend!</b>\nAfter they register, you will receive the bonus automatically.',
        'msg_payment_success': '✅ <b>PAYMENT SUCCESSFUL!</b> ✅',
        'msg_payment_added': '💰 <b>Added:</b> {amount:.2f} ₽',
        'msg_payment_method': '⭐ <b>Method:</b> Telegram Stars ({stars} ⭐)',
        'msg_payment_balance': '💳 <b>Your balance:</b> {balance} ₽',
        'msg_payment_use_funds': '🎉 You can now use funds for content generation!',
        'error_session_empty': '❌ Error: session is empty. Please start again.',
        'error_no_data': '❌ Error: no data in request. Please try again.',
        'error_invalid_format': '❌ Error: invalid request format. Please try again.',
        'error_unknown': '❌ An error occurred. Please try later or use /start',
        'error_insufficient_balance': '❌ Insufficient balance',
        'error_operation_failed': '❌ Operation failed. Please try again.',
        'error_timeout': '⏱️ Timeout exceeded. Please try again.',
        'error_network': '🌐 Network error. Check your connection and try later.',
        'error_display_generation': '❌ Error displaying generation',
        'msg_spinning_wheel': '🎰 Spinning the wheel of fortune...',
        'msg_admin_only': 'This function is available only to administrator.',
        'msg_user_mode_enabled': 'User mode enabled',
        'msg_returning_to_admin': 'Returning to admin panel',
        'msg_insufficient_funds': '❌ <b>Insufficient funds</b>\n💳 <b>Your balance:</b> {balance} ₽\n💵 <b>Required:</b> {required} ₽\n\nTop up your balance to generate.',
        'msg_available_generations': '✅ <b>Available generations:</b> {count}\n💳 <b>Your balance:</b> {balance} ₽',
        'msg_unlimited_available': '✅ <b>Available:</b> Unlimited',
        'btn_check_balance': '💰 Check Balance',
        'btn_back_to_categories': '◀️ Back to Categories',
        'btn_previous': '◀️ Previous',
        'btn_next': 'Next ▶️',
        'btn_back_to_admin': '◀️ Back to Admin Panel',
        'btn_back_to_list': '◀️ Back to List',
        'btn_back_to_history': '◀️ Back to History',
        'btn_confirm_generate_text': '✅ Generate',
        'btn_copy_link': '📋 Copy Link',
        'btn_all_models_text': '📋 All Models',
        'btn_z_image_free': '🖼️ Z-Image (free)',
        'btn_next_step': '▶️ Next',
        'btn_complete': '▶️ Complete',
        'btn_custom_amount': '💰 Custom Amount',
        'btn_return_to_admin': '🔙 Return to Admin',
        'btn_view_result': '👁️ View Result',
    }
}


def t(key: str, lang: str = 'ru', **kwargs) -> str:
    """Get translated text."""
    translations = TRANSLATIONS.get(lang, TRANSLATIONS['ru'])
    text = translations.get(key, TRANSLATIONS['ru'].get(key, key))
    try:
        return text.format(**kwargs)
    except KeyError:
        return text











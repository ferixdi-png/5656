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











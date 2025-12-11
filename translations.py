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
            '🚀 <b>ЧТО МОЖНО ДЕЛАТЬ:</b>\n'
            '• 🎨 Создавать изображения из текста\n'
            '• 🎬 Генерировать видео\n'
            '• ✨ Редактировать и трансформировать контент\n'
            '• 🎯 Все это БЕЗ VPN и по цене жвачки!\n\n'
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
            '💡 <b>Пригласи друга → получи +{ref_bonus} бесплатных генераций!</b>\n'
            '🔗 <code>{ref_link}</code>\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '💰 <b>После бесплатных генераций:</b>\n'
            'От 0.62 ₽ за изображение • От 3.86 ₽ за видео'
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
            '🚀 <b>WHAT YOU CAN DO:</b>\n'
            '• 🎨 Create images from text\n'
            '• 🎬 Generate videos\n'
            '• ✨ Edit and transform content\n'
            '• 🎯 All WITHOUT VPN at affordable prices!\n\n'
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
            '💡 <b>Invite a friend → get +{ref_bonus} free generations!</b>\n'
            '🔗 <code>{ref_link}</code>\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            '💰 <b>After free generations:</b>\n'
            'From 0.62 ₽ per image • From 3.86 ₽ per video'
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











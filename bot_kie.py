"""
KIE (Knowledge Is Everything) Telegram Bot
Enhanced version with KIE AI model selection and generation
"""

import logging
import asyncio
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import os
from dotenv import load_dotenv
from knowledge_storage import KnowledgeStorage
from kie_client import get_client
from kie_models import KIE_MODELS, get_model_by_id, get_models_by_category, get_categories
import json
import aiohttp
import io
from io import BytesIO
import re
import platform

# Load environment variables FIRST
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Try to import PIL/Pillow
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL/Pillow not available. Image analysis will be limited.")

# Try to import pytesseract and configure Tesseract path
try:
    import pytesseract
    OCR_AVAILABLE = True
    
    # Try to set Tesseract path
    # On Windows, check common installation paths
    # On Linux (Render), Tesseract should be in PATH
    tesseract_found = False  # Initialize variable for all platforms
    
    if platform.system() == 'Windows':
        # Common Tesseract installation paths on Windows
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                tesseract_found = True
                logger.info(f"Tesseract found at: {path}")
                break
    
    # Try to find Tesseract in PATH (works on both Windows and Linux)
    if not tesseract_found:
        try:
            import shutil
            tesseract_path = shutil.which('tesseract')
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.info(f"Tesseract found in PATH: {tesseract_path}")
                tesseract_found = True
        except Exception as e:
            logger.debug(f"Could not find Tesseract in PATH: {e}")
    
    if not tesseract_found:
        logger.warning("Tesseract not found. OCR analysis will be disabled. Install tesseract-ocr package if needed.")
    
    # Test if Tesseract works
    try:
        pytesseract.get_tesseract_version()
        logger.info("Tesseract OCR is available and working.")
    except Exception as e:
        OCR_AVAILABLE = False
        logger.warning(f"Tesseract OCR is not working: {e}")
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract not available. OCR analysis will be disabled.")

# Bot token from environment variable
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Admin user ID (can be set via environment variable)
ADMIN_ID = int(os.getenv('ADMIN_ID', '6913446846'))

# Price conversion constants
# Based on: 18 credits = $0.09 = 6.95 ₽
CREDIT_TO_USD = 0.005  # 1 credit = $0.005 ($0.09 / 18)
USD_TO_RUB = 6.95 / 0.09  # 1 USD = 77.2222... RUB (calculated from 6.95 ₽ / $0.09)

# Initialize knowledge storage
storage = KnowledgeStorage()
# KIE client (async)
kie = get_client()

# Store user sessions
user_sessions = {}


def get_admin_limits() -> dict:
    """Get admin limits data."""
    return load_json_file(ADMIN_LIMITS_FILE, {})


def save_admin_limits(data: dict):
    """Save admin limits data."""
    save_json_file(ADMIN_LIMITS_FILE, data)


def is_admin(user_id: int) -> bool:
    """Check if user is admin (main admin or limited admin)."""
    if user_id == ADMIN_ID:
        return True
    admin_limits = get_admin_limits()
    return str(user_id) in admin_limits


def get_admin_spent(user_id: int) -> float:
    """Get amount spent by admin (for limited admins)."""
    admin_limits = get_admin_limits()
    admin_data = admin_limits.get(str(user_id), {})
    return admin_data.get('spent', 0.0)


def get_admin_limit(user_id: int) -> float:
    """Get spending limit for admin (100 rubles for limited admins, unlimited for main admin)."""
    if user_id == ADMIN_ID:
        return float('inf')  # Main admin has unlimited
    admin_limits = get_admin_limits()
    admin_data = admin_limits.get(str(user_id), {})
    return admin_data.get('limit', 100.0)  # Default 100 rubles


def add_admin_spent(user_id: int, amount: float):
    """Add to admin's spent amount."""
    if user_id == ADMIN_ID:
        return  # Main admin doesn't have limits
    admin_limits = get_admin_limits()
    if str(user_id) not in admin_limits:
        return
    admin_limits[str(user_id)]['spent'] = admin_limits[str(user_id)].get('spent', 0.0) + amount
    save_admin_limits(admin_limits)


def get_admin_remaining(user_id: int) -> float:
    """Get remaining limit for admin."""
    limit = get_admin_limit(user_id)
    if limit == float('inf'):
        return float('inf')
    spent = get_admin_spent(user_id)
    return max(0.0, limit - spent)


def get_is_admin(user_id: int) -> bool:
    """
    Determine if user is admin, taking into account admin user mode.
    
    If admin is in user mode (admin_user_mode = True), returns False.
    Otherwise, returns True for admin, False for regular users.
    """
    if is_admin(user_id):
        # Check if admin is in user mode (viewing as regular user)
        if user_id in user_sessions and user_sessions[user_id].get('admin_user_mode', False):
            return False  # Show as regular user
        else:
            return True
    else:
        return False


def calculate_price_rub(model_id: str, params: dict = None, is_admin: bool = False) -> float:
    """Calculate price in rubles based on model and parameters."""
    if params is None:
        params = {}
    
    # Base prices in credits
    if model_id == "z-image":
        base_credits = 0.8
    elif model_id == "nano-banana-pro":
        resolution = params.get("resolution", "1K")
        if resolution == "4K":
            base_credits = 24
        else:  # 1K or 2K
            base_credits = 18
    elif model_id == "seedream/4.5-text-to-image" or model_id == "seedream/4.5-edit":
        # Both Seedream models cost 6.5 credits per image
        base_credits = 6.5
    elif model_id == "google/nano-banana" or model_id == "google/nano-banana-edit":
        # Google Nano Banana and Edit both cost 4 credits per image
        base_credits = 4
    elif model_id == "google/imagen4-ultra":
        # Google Imagen 4 Ultra costs 12 credits per image
        base_credits = 12
    elif model_id == "google/imagen4-fast":
        # Google Imagen 4 Fast costs 4 credits per image
        # Price multiplies by num_images if specified
        base_credits = 4
        if params and 'num_images' in params:
            num_images = int(params.get('num_images', '1'))
            base_credits = 4 * num_images
    elif model_id == "google/imagen4":
        # Google Imagen 4 costs 8 credits per image
        # Price multiplies by num_images if specified
        base_credits = 8
        if params and 'num_images' in params:
            num_images = int(params.get('num_images', '1'))
            base_credits = 8 * num_images
    elif model_id == "sora-watermark-remover":
        # Sora watermark remover costs 10 credits per use
        base_credits = 10
    elif model_id == "sora-2-text-to-video":
        # Sora 2 text-to-video costs 30 credits per 10-second video with audio
        base_credits = 30
    elif model_id == "bytedance/v1-pro-fast-image-to-video":
        # ByteDance V1 Pro Fast: 16 credits (720p 5s) / 36 credits (720p 10s) / 36 credits (1080p 5s) / 72 credits (1080p 10s)
        # Default to 720p 5s (16 credits)
        resolution = params.get('resolution', '720p') if params else '720p'
        duration = params.get('duration', '5') if params else '5'
        if resolution == '1080p':
            base_credits = 36 if duration == '5' else 72
        else:  # 720p
            base_credits = 16 if duration == '5' else 36
    elif model_id == "grok-imagine/image-to-video":
        # Grok Imagine image-to-video costs 20 credits per 6-second video
        base_credits = 20
    elif model_id == "grok-imagine/text-to-video":
        # Grok Imagine text-to-video costs 20 credits per 6-second video
        base_credits = 20
    elif model_id == "grok-imagine/text-to-image":
        # Grok Imagine text-to-image costs 4 credits per generation (6 images)
        base_credits = 4
    elif model_id == "grok-imagine/upscale":
        # Grok Imagine upscale costs 10 credits per upscale
        base_credits = 10
    elif model_id == "hailuo/2-3-image-to-video-pro":
        # Hailuo 2.3 Pro: 45 credits (Pro 6s 768P) / 90 credits (Pro 10s 768P) / 80 credits (Pro 6s 1080P)
        # Note: 10s videos are not supported for 1080P
        resolution = params.get('resolution', '768P') if params else '768P'
        duration = params.get('duration', '6') if params else '6'
        if resolution == '1080P':
            # Only 6s supported for 1080P
            base_credits = 80
        else:  # 768P
            base_credits = 45 if duration == '6' else 90
    elif model_id == "hailuo/2-3-image-to-video-standard":
        # Hailuo 2.3 Standard: 30 credits (Standard 6s 768P) / 50 credits (Standard 10s 768P) / 50 credits (Standard 6s 1080P)
        # Note: 10s videos are not supported for 1080P
        resolution = params.get('resolution', '768P') if params else '768P'
        duration = params.get('duration', '6') if params else '6'
        if resolution == '1080P':
            # Only 6s supported for 1080P
            base_credits = 50
        else:  # 768P
            base_credits = 30 if duration == '6' else 50
    else:
        # Default fallback
        base_credits = 1.0
    
    # Convert credits to USD, then to RUB (no rounding)
    price_usd = base_credits * CREDIT_TO_USD
    price_rub = price_usd * USD_TO_RUB
    
    # For regular users, multiply by 2
    if not is_admin:
        price_rub *= 2
    
    # Return exact value without rounding
    return price_rub


def format_price_rub(price: float, is_admin: bool = False) -> str:
    """Format price in rubles with appropriate text (rounded to 2 decimal places)."""
    # Always round to 2 decimal places
    price_rounded = round(price, 2)
    price_str = f"{price_rounded:.2f}"
    if is_admin:
        return f"💰 <b>Безлимит</b> (цена: {price_str} ₽)"
    else:
        return f"💰 <b>{price_str} ₽</b>"


def get_model_price_text(model_id: str, params: dict = None, is_admin: bool = False, user_id: int = None) -> str:
    """Get formatted price text for a model."""
    if model_id == "z-image":
        if not is_admin and user_id is not None:
            # Check if user has free generations available
            remaining = get_user_free_generations_remaining(user_id)
            if remaining > 0:
                price = calculate_price_rub(model_id, params, is_admin)
                price_str = f"{round(price, 2):.2f}"
                return f"🎁 <b>БЕСПЛАТНО</b> ({remaining}/{FREE_GENERATIONS_PER_DAY} в день) или {price_str} ₽"
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin) + " за изображение"
    elif model_id == "nano-banana-pro":
        price_1k = calculate_price_rub(model_id, {"resolution": "1K"}, is_admin)
        price_4k = calculate_price_rub(model_id, {"resolution": "4K"}, is_admin)
        # Format prices to 2 decimal places
        price_1k_str = f"{round(price_1k, 2):.2f}"
        price_4k_str = f"{round(price_4k, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (1K/2K: {price_1k_str} ₽, 4K: {price_4k_str} ₽)"
        else:
            return f"💰 <b>От {price_1k_str} ₽</b> (1K/2K: {price_1k_str} ₽, 4K: {price_4k_str} ₽)"
    elif model_id == "sora-watermark-remover":
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin) + " за использование"
    elif model_id == "sora-2-text-to-video":
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin) + " за 10-секундное видео"
    elif model_id == "bytedance/v1-pro-fast-image-to-video":
        price = calculate_price_rub(model_id, params, is_admin)
        resolution = params.get('resolution', '720p') if params else '720p'
        duration = params.get('duration', '5') if params else '5'
        return format_price_rub(price, is_admin) + f" за {duration}с видео ({resolution})"
    elif model_id == "grok-imagine/image-to-video":
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin) + " за 6-секундное видео"
    elif model_id == "grok-imagine/text-to-video":
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin) + " за 6-секундное видео"
    elif model_id == "grok-imagine/text-to-image":
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin) + " за генерацию (6 изображений)"
    elif model_id == "grok-imagine/upscale":
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin) + " за улучшение качества"
    elif model_id == "hailuo/2-3-image-to-video-pro":
        price = calculate_price_rub(model_id, params, is_admin)
        resolution = params.get('resolution', '768P') if params else '768P'
        duration = params.get('duration', '6') if params else '6'
        return format_price_rub(price, is_admin) + f" за {duration}с видео Pro ({resolution})"
    elif model_id == "hailuo/2-3-image-to-video-standard":
        price = calculate_price_rub(model_id, params, is_admin)
        resolution = params.get('resolution', '768P') if params else '768P'
        duration = params.get('duration', '6') if params else '6'
        return format_price_rub(price, is_admin) + f" за {duration}с видео Standard ({resolution})"
    else:
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin)

# Conversation states for model selection and parameter input
SELECTING_MODEL, INPUTTING_PARAMS, CONFIRMING_GENERATION = range(3)

# Payment states
SELECTING_AMOUNT, WAITING_PAYMENT_SCREENSHOT = range(3, 5)
WAITING_PROMOCODE = 5  # State for entering promo code

# Admin test OCR state
ADMIN_TEST_OCR = 5

# Store user sessions
user_sessions = {}

# Store saved generation data for "generate again" feature
saved_generations = {}

# Rate limiting for flood protection
user_request_times = {}  # {user_id: [timestamps]}
FLOOD_LIMIT = 10  # Max requests per time window
FLOOD_WINDOW = 60  # Time window in seconds (1 minute)
FLOOD_COOLDOWN = 300  # Cooldown period in seconds (5 minutes) if limit exceeded


def check_flood_protection(user_id: int) -> dict:
    """
    Check if user is flooding/spamming requests.
    Returns: {'allowed': bool, 'message': str, 'cooldown_remaining': int}
    """
    import time
    current_time = time.time()
    
    # Initialize user request times if not exists
    if user_id not in user_request_times:
        user_request_times[user_id] = []
    
    # Clean old requests outside the time window
    user_request_times[user_id] = [
        t for t in user_request_times[user_id] 
        if current_time - t < FLOOD_WINDOW
    ]
    
    # Check if user is in cooldown (stored in user_sessions)
    if user_id in user_sessions:
        cooldown_until = user_sessions[user_id].get('flood_cooldown_until', 0)
        if cooldown_until > current_time:
            remaining = int(cooldown_until - current_time)
            minutes = remaining // 60
            seconds = remaining % 60
            time_str = f"{minutes} мин {seconds} сек" if minutes > 0 else f"{seconds} сек"
            return {
                'allowed': False,
                'message': f'⏳ <b>Слишком много запросов!</b>\n\n'
                          f'Пожалуйста, подождите <b>{time_str}</b> перед следующим запросом.\n\n'
                          f'💡 <b>Что это значит?</b>\n'
                          f'Система защищает от спама и перегрузки. Это временная пауза для стабильной работы бота.',
                'cooldown_remaining': remaining
            }
    
    # Check current request count
    request_count = len(user_request_times[user_id])
    
    if request_count >= FLOOD_LIMIT:
        # User exceeded limit - set cooldown
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]['flood_cooldown_until'] = current_time + FLOOD_COOLDOWN
        
        return {
            'allowed': False,
            'message': f'⚠️ <b>Обнаружено слишком много запросов!</b>\n\n'
                      f'Пожалуйста, <b>не флудите</b>. Подождите <b>{FLOOD_COOLDOWN // 60} минут</b> перед следующим запросом.\n\n'
                      f'💡 <b>Что это значит?</b>\n'
                      f'Вы отправили слишком много запросов за короткое время ({FLOOD_LIMIT} запросов за {FLOOD_WINDOW} секунд).\n'
                      f'Это защита от спама и перегрузки сервера.\n\n'
                      f'✅ <b>Рекомендация:</b>\n'
                      f'Делайте паузы между запросами (минимум 6 секунд), чтобы избежать этой блокировки.',
            'cooldown_remaining': FLOOD_COOLDOWN
        }
    
    # Add current request
    user_request_times[user_id].append(current_time)
    
    return {'allowed': True, 'message': '', 'cooldown_remaining': 0}


def get_user_friendly_param_description(param_name: str, param_info: dict, model_id: str = None) -> str:
    """
    Get user-friendly description for a parameter with explanations.
    """
    base_desc = param_info.get('description', '')
    
    # Add explanations for common parameters
    explanations = {
        'prompt': {
            'text': '💬 <b>Что это?</b>\n'
                   'Текстовое описание того, что вы хотите создать. Чем подробнее описание, тем лучше результат!\n\n'
                   '💡 <b>Совет:</b>\n'
                   'Опишите детали: стиль, цвета, композицию, настроение. Например: "Фотореалистичный портрет женщины в стиле 80-х, яркие цвета, ретро атмосфера"',
            'video': '💬 <b>Что это?</b>\n'
                    'Текстовое описание движения и сцены для видео. Опишите, что должно происходить в кадре.\n\n'
                    '💡 <b>Совет:</b>\n'
                    'Опишите движение, камеру, освещение. Например: "Плавное движение камеры вокруг объекта, мягкое освещение, кинематографический стиль"'
        },
        'aspect_ratio': '📐 <b>Что это?</b>\n'
                       'Соотношение сторон (ширина:высота) вашего изображения/видео.\n\n'
                       '💡 <b>Выбор:</b>\n'
                       '• <b>1:1</b> - Квадрат (Instagram, профили)\n'
                       '• <b>16:9</b> - Широкоформатное (YouTube, презентации)\n'
                       '• <b>9:16</b> - Вертикальное (Stories, TikTok)\n'
                       '• <b>3:4</b> - Портретное (вертикальные посты)\n'
                       '• <b>4:3</b> - Классическое (горизонтальные посты)',
        'resolution': '🎬 <b>Что это?</b>\n'
                     'Разрешение (качество) видео или изображения.\n\n'
                     '💡 <b>Выбор:</b>\n'
                     '• <b>720p/768P</b> - Хорошее качество, быстрее генерируется\n'
                     '• <b>1080P</b> - Высокое качество, дольше генерируется\n'
                     '• <b>1K/2K</b> - Стандартное качество\n'
                     '• <b>4K</b> - Максимальное качество для печати и профессионального использования',
        'duration': '⏱️ <b>Что это?</b>\n'
                   'Длительность видео в секундах.\n\n'
                   '💡 <b>Выбор:</b>\n'
                   '• <b>5-6 секунд</b> - Короткое видео, быстрее генерируется\n'
                   '• <b>10-15 секунд</b> - Длиннее видео, больше деталей\n\n'
                   '⚠️ <b>Важно:</b> Некоторые разрешения не поддерживают длинные видео.',
        'negative_prompt': '🚫 <b>Что это?</b>\n'
                          'Опишите, чего НЕ должно быть в результате.\n\n'
                          '💡 <b>Примеры:</b>\n'
                          '• "размытие, низкое качество, артефакты"\n'
                          '• "текст, водяные знаки, логотипы"\n'
                          '• "искажения, деформации"\n\n'
                          'Это поможет улучшить результат, исключив нежелательные элементы.',
        'num_images': '🖼️ <b>Что это?</b>\n'
                     'Количество изображений для генерации за один раз.\n\n'
                     '💡 <b>Выбор:</b>\n'
                     '• <b>1</b> - Одно изображение (быстрее)\n'
                     '• <b>2-4</b> - Несколько вариантов (больше выбор)\n\n'
                     '⚠️ <b>Важно:</b> Цена умножается на количество изображений.',
        'remove_watermark': '🔍 <b>Что это?</b>\n'
                          'Удаление водяного знака с видео.\n\n'
                          '💡 <b>Выбор:</b>\n'
                          '• <b>Да</b> - Видео без водяного знака (рекомендуется)\n'
                          '• <b>Нет</b> - Видео с водяным знаком (быстрее, но с меткой)',
        'mode': '🎨 <b>Что это?</b>\n'
               'Режим генерации, влияющий на стиль и качество.\n\n'
               '💡 <b>Выбор:</b>\n'
               '• <b>normal</b> - Стандартный режим (рекомендуется)\n'
               '• <b>fun</b> - Более креативный и необычный стиль\n'
               '• <b>spicy</b> - Расширенные возможности (не для всех моделей)',
        'quality': '⭐ <b>Что это?</b>\n'
                  'Уровень качества генерации.\n\n'
                  '💡 <b>Выбор:</b>\n'
                  '• <b>basic</b> - Базовое качество (2K, быстрее)\n'
                  '• <b>high</b> - Высокое качество (4K, дольше, дороже)',
        'output_format': '📄 <b>Что это?</b>\n'
                        'Формат файла результата.\n\n'
                        '💡 <b>Выбор:</b>\n'
                        '• <b>png</b> - Лучшее качество, прозрачность (больше размер)\n'
                        '• <b>jpeg/jpg</b> - Меньше размер, хорошее качество',
        'seed': '🎲 <b>Что это?</b>\n'
               'Случайное число для воспроизводимости результатов.\n\n'
               '💡 <b>Как использовать:</b>\n'
               'Если вы хотите получить похожий результат, используйте тот же seed.\n'
               'Если не указать, будет случайный результат каждый раз.',
        'image_url': '🖼️ <b>Что это?</b>\n'
                    'Ссылка на изображение для обработки.\n\n'
                    '💡 <b>Как получить:</b>\n'
                    '1. Загрузите изображение в бот\n'
                    '2. Бот автоматически получит ссылку\n'
                    '3. Или укажите публичную ссылку на изображение',
        'image_urls': '🖼️ <b>Что это?</b>\n'
                     'Список ссылок на изображения (до 10 штук).\n\n'
                     '💡 <b>Как использовать:</b>\n'
                     'Можно загрузить несколько изображений для обработки или редактирования.',
        'n_frames': '🎬 <b>Что это?</b>\n'
                   'Количество кадров (длительность) видео.\n\n'
                   '💡 <b>Выбор:</b>\n'
                   '• <b>10</b> - 10 секунд видео\n'
                   '• <b>15</b> - 15 секунд видео (дольше генерируется)'
    }
    
    # Get specific explanation if available
    explanation = explanations.get(param_name, '')
    
    # For prompt, check if it's for video or image
    if param_name == 'prompt':
        if model_id and any(v in model_id for v in ['video', 'sora', 'hailuo', 'grok-imagine/image-to-video', 'grok-imagine/text-to-video']):
            explanation = explanations['prompt']['video']
        else:
            explanation = explanations['prompt']['text']
    
    # Combine base description with explanation
    if explanation:
        return f"{base_desc}\n\n{explanation}"
    else:
        return base_desc

# Rate limiting for flood protection
user_request_times = {}  # {user_id: [timestamps]}
FLOOD_LIMIT = 10  # Max requests per time window
FLOOD_WINDOW = 60  # Time window in seconds (1 minute)
FLOOD_COOLDOWN = 300  # Cooldown period in seconds (5 minutes) if limit exceeded

# Payment data files
BALANCES_FILE = "user_balances.json"
ADMIN_LIMITS_FILE = "admin_limits.json"  # File to store admins with spending limits
PAYMENTS_FILE = "payments.json"
BLOCKED_USERS_FILE = "blocked_users.json"
PROMOCODES_FILE = "promocodes.json"  # File to store promo codes
FREE_GENERATIONS_FILE = "daily_free_generations.json"  # File to store daily free generations
REFERRALS_FILE = "referrals.json"  # File to store referral data

# Free generation settings
FREE_MODEL_ID = "z-image"  # Model that is free for users
FREE_GENERATIONS_PER_DAY = 5  # Number of free generations per day per user
REFERRAL_BONUS_GENERATIONS = 5  # Bonus generations for inviting a user


# ==================== Payment System Functions ====================

def load_json_file(filename: str, default: dict = None) -> dict:
    """Load JSON file, return default if file doesn't exist."""
    if default is None:
        default = {}
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return default


def save_json_file(filename: str, data: dict):
    """Save data to JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")


def get_user_balance(user_id: int) -> float:
    """Get user balance in rubles."""
    balances = load_json_file(BALANCES_FILE, {})
    return balances.get(str(user_id), 0.0)


def set_user_balance(user_id: int, amount: float):
    """Set user balance in rubles."""
    balances = load_json_file(BALANCES_FILE, {})
    balances[str(user_id)] = amount
    save_json_file(BALANCES_FILE, balances)


def add_user_balance(user_id: int, amount: float) -> float:
    """Add amount to user balance, return new balance."""
    current = get_user_balance(user_id)
    new_balance = current + amount
    set_user_balance(user_id, new_balance)
    return new_balance


def subtract_user_balance(user_id: int, amount: float) -> bool:
    """Subtract amount from user balance. Returns True if successful, False if insufficient funds."""
    current = get_user_balance(user_id)
    if current >= amount:
        set_user_balance(user_id, current - amount)
        return True
    return False


def is_user_blocked(user_id: int) -> bool:
    """Check if user is blocked."""
    blocked = load_json_file(BLOCKED_USERS_FILE, {})
    return blocked.get(str(user_id), False)


def block_user(user_id: int):
    """Block a user."""
    blocked = load_json_file(BLOCKED_USERS_FILE, {})
    blocked[str(user_id)] = True
    save_json_file(BLOCKED_USERS_FILE, blocked)


def unblock_user(user_id: int):
    """Unblock a user."""
    blocked = load_json_file(BLOCKED_USERS_FILE, {})
    if str(user_id) in blocked:
        del blocked[str(user_id)]
        save_json_file(BLOCKED_USERS_FILE, blocked)


def check_duplicate_payment(screenshot_file_id: str) -> bool:
    """Check if this screenshot was already used for payment."""
    if not screenshot_file_id:
        return False
    payments = load_json_file(PAYMENTS_FILE, {})
    for payment in payments.values():
        if payment.get('screenshot_file_id') == screenshot_file_id:
            return True
    return False


def add_payment(user_id: int, amount: float, screenshot_file_id: str = None) -> dict:
    """Add a payment record. Returns payment dict with id, timestamp, etc."""
    payments = load_json_file(PAYMENTS_FILE, {})
    payment_id = len(payments) + 1
    import time
    payment = {
        "id": payment_id,
        "user_id": user_id,
        "amount": amount,
        "timestamp": time.time(),
        "screenshot_file_id": screenshot_file_id,
        "status": "completed"  # Auto-completed
    }
    payments[str(payment_id)] = payment
    save_json_file(PAYMENTS_FILE, payments)
    
    # Auto-add balance
    add_user_balance(user_id, amount)
    
    return payment


def get_all_payments() -> list:
    """Get all payments sorted by timestamp (newest first)."""
    payments = load_json_file(PAYMENTS_FILE, {})
    payment_list = list(payments.values())
    payment_list.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return payment_list


def get_user_payments(user_id: int) -> list:
    """Get all payments for a specific user."""
    all_payments = get_all_payments()
    return [p for p in all_payments if p.get("user_id") == user_id]


def get_payment_stats() -> dict:
    """Get payment statistics."""
    payments = get_all_payments()
    total_amount = sum(p.get("amount", 0) for p in payments)
    total_count = len(payments)
    return {
        "total_amount": total_amount,
        "total_count": total_count,
        "payments": payments
    }


def get_payment_details() -> str:
    """Get payment details from .env (СБП - Система быстрых платежей)."""
    # Reload environment variables to ensure latest values
    from dotenv import load_dotenv
    load_dotenv()
    
    card_holder = os.getenv('PAYMENT_CARD_HOLDER', '').strip()
    phone = os.getenv('PAYMENT_PHONE', '').strip()
    bank = os.getenv('PAYMENT_BANK', '').strip()
    
    details = "💳 <b>Реквизиты для оплаты (СБП):</b>\n\n"
    
    # Check if any payment details are configured
    has_details = False
    
    if phone and phone != '':
        details += f"📱 <b>Номер телефона:</b> <code>{phone}</code>\n"
        has_details = True
    else:
        details += "📱 <b>Номер телефона:</b> <i>Не указан в настройках</i>\n"
    
    if bank and bank != '':
        details += f"🏦 <b>Банк:</b> {bank}\n"
        has_details = True
    else:
        details += "🏦 <b>Банк:</b> <i>Не указан в настройках</i>\n"
    
    if card_holder and card_holder != '':
        details += f"👤 <b>Получатель:</b> {card_holder}\n"
        has_details = True
    else:
        details += "👤 <b>Получатель:</b> <i>Не указан в настройках</i>\n"
    
    if not has_details:
        details += "\n⚠️ <b>ВНИМАНИЕ:</b> Реквизиты не настроены!\n"
        details += "Администратору необходимо указать PAYMENT_PHONE, PAYMENT_BANK и PAYMENT_CARD_HOLDER в файле .env\n\n"
    
    details += "\n⚠️ <b>Важно:</b> После оплаты отправьте скриншот перевода в этот чат.\n\n"
    details += "✅ <b>Баланс начислится автоматически</b> после отправки скриншота."
    
    return details


def get_free_generations_data() -> dict:
    """Get daily free generations data."""
    return load_json_file(FREE_GENERATIONS_FILE, {})


def save_free_generations_data(data: dict):
    """Save daily free generations data."""
    save_json_file(FREE_GENERATIONS_FILE, data)


def get_user_free_generations_today(user_id: int) -> int:
    """Get number of free generations used by user today."""
    from datetime import datetime
    
    data = get_free_generations_data()
    user_key = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_key not in data:
        return 0
    
    user_data = data[user_key]
    if user_data.get('date') == today:
        return user_data.get('count', 0)
    else:
        # Reset for new day
        return 0


def get_user_free_generations_remaining(user_id: int) -> int:
    """Get remaining free generations for user today (including bonus)."""
    used = get_user_free_generations_today(user_id)
    data = get_free_generations_data()
    user_key = str(user_id)
    bonus = data.get(user_key, {}).get('bonus', 0)
    total_available = FREE_GENERATIONS_PER_DAY + bonus
    remaining = total_available - used
    return max(0, remaining)


def use_free_generation(user_id: int) -> bool:
    """Use one free generation. Returns True if successful, False if limit reached."""
    from datetime import datetime
    
    data = get_free_generations_data()
    user_key = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_key not in data:
        data[user_key] = {'date': today, 'count': 0, 'bonus': 0}
    
    user_data = data[user_key]
    
    # Reset if new day (but keep bonus)
    if user_data.get('date') != today:
        old_bonus = user_data.get('bonus', 0)
        user_data['date'] = today
        user_data['count'] = 0
        user_data['bonus'] = old_bonus  # Keep bonus across days
    
    # Get total available (base + bonus)
    bonus = user_data.get('bonus', 0)
    total_available = FREE_GENERATIONS_PER_DAY + bonus
    
    # Check limit (including bonus)
    if user_data.get('count', 0) >= total_available:
        return False
    
    # Increment count
    user_data['count'] = user_data.get('count', 0) + 1
    save_free_generations_data(data)
    return True


def is_free_generation_available(user_id: int, model_id: str) -> bool:
    """Check if free generation is available for this user and model."""
    # Only for regular users (not admins)
    if get_is_admin(user_id):
        return False
    
    # Only for free model
    if model_id != FREE_MODEL_ID:
        return False
    
    # Check if user has remaining free generations
    remaining = get_user_free_generations_remaining(user_id)
    return remaining > 0


def get_support_contact() -> str:
    """Get support contact information from .env (only Telegram)."""
    # Reload environment variables to ensure latest values
    from dotenv import load_dotenv
    load_dotenv()
    
    support_telegram = os.getenv('SUPPORT_TELEGRAM', '').strip()
    support_text = os.getenv('SUPPORT_TEXT', '').strip()
    
    contact = "🆘 <b>Поддержка</b>\n\n"
    
    if support_text:
        contact += f"{support_text}\n\n"
    else:
        contact += "Если у вас возникли вопросы или проблемы, свяжитесь с нами:\n\n"
    
    if support_telegram:
        telegram_username = support_telegram.replace('@', '').strip()
        if telegram_username:
            contact += f"💬 <b>Telegram:</b> @{telegram_username}\n"
        else:
            contact += "⚠️ Контактная информация не настроена.\n"
            contact += "Обратитесь к администратору."
    else:
        contact += "⚠️ Контактная информация не настроена.\n"
        contact += "Обратитесь к администратору."
    
    return contact


def get_referrals_data() -> dict:
    """Get referrals data."""
    return load_json_file(REFERRALS_FILE, {})


def save_referrals_data(data: dict):
    """Save referrals data."""
    save_json_file(REFERRALS_FILE, data)


def get_user_referrals(user_id: int) -> list:
    """Get list of users referred by this user."""
    data = get_referrals_data()
    user_key = str(user_id)
    return data.get(user_key, {}).get('referred_users', [])


def get_referrer(user_id: int) -> int:
    """Get the user who referred this user, or None if not referred."""
    data = get_referrals_data()
    user_key = str(user_id)
    return data.get(user_key, {}).get('referred_by')


def add_referral(referrer_id: int, referred_id: int):
    """Add a referral relationship and give bonus to referrer."""
    import time
    data = get_referrals_data()
    referrer_key = str(referrer_id)
    referred_key = str(referred_id)
    
    # Check if already referred
    if referred_key in data and data[referred_key].get('referred_by'):
        return  # Already referred by someone
    
    # Add referral relationship
    if referred_key not in data:
        data[referred_key] = {}
    data[referred_key]['referred_by'] = referrer_id
    data[referred_key]['referred_at'] = int(time.time())
    
    # Add to referrer's list
    if referrer_key not in data:
        data[referrer_key] = {'referred_users': []}
    if 'referred_users' not in data[referrer_key]:
        data[referrer_key]['referred_users'] = []
    
    if referred_id not in data[referrer_key]['referred_users']:
        data[referrer_key]['referred_users'].append(referred_id)
    
    save_referrals_data(data)
    
    # Give bonus generations to referrer
    give_bonus_generations(referrer_id, REFERRAL_BONUS_GENERATIONS)


def give_bonus_generations(user_id: int, bonus_count: int):
    """Give bonus free generations to a user."""
    from datetime import datetime
    
    data = get_free_generations_data()
    user_key = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_key not in data:
        data[user_key] = {'date': today, 'count': 0, 'bonus': 0}
    
    user_data = data[user_key]
    
    # Reset if new day (but keep bonus)
    if user_data.get('date') != today:
        old_bonus = user_data.get('bonus', 0)
        user_data['date'] = today
        user_data['count'] = 0
        user_data['bonus'] = old_bonus + bonus_count
    else:
        user_data['bonus'] = user_data.get('bonus', 0) + bonus_count
    
    save_free_generations_data(data)


def get_user_referral_link(user_id: int, bot_username: str = None) -> str:
    """Get referral link for user."""
    if bot_username is None:
        bot_username = "Ferixdi_bot_ai_bot"
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


async def analyze_payment_screenshot(image_data: bytes, expected_amount: float, expected_phone: str = None) -> dict:
    """
    Analyze payment screenshot using OCR.
    Returns dict with 'valid', 'amount_found', 'phone_found', 'message'.
    """
    if not OCR_AVAILABLE or not PIL_AVAILABLE:
        # If OCR not available, allow payment without check
        return {
            'valid': True,  # Allow without OCR check
            'amount_found': False,
            'phone_found': False,
            'message': 'ℹ️ OCR недоступен. Баланс начислен автоматически.'
        }
    
    try:
        # Convert bytes to PIL Image
        image = Image.open(BytesIO(image_data))
        
        # Use OCR to extract text
        try:
            extracted_text = pytesseract.image_to_string(image, lang='rus+eng')
        except Exception as e:
            logger.error(f"OCR error: {e}")
            # Try with English only if Russian fails
            try:
                extracted_text = pytesseract.image_to_string(image, lang='eng')
            except:
                extracted_text = pytesseract.image_to_string(image)
        
        extracted_text = extracted_text.lower()
        logger.info(f"Extracted text from screenshot (first 200 chars): {extracted_text[:200]}")
        
        # Check for payment-related keywords (Russian and English)
        payment_keywords = [
            'перевод', 'оплата', 'платеж', 'спб', 'сбп', 'payment', 'transfer',
            'отправлено', 'успешно', 'success', 'получатель', 'получатель:',
            'сумма', 'итого', 'amount', 'total', 'сумма перевода', 'переведено',
            'квитанция', 'receipt', 'статус', 'status', 'комиссия', 'commission'
        ]
        
        has_payment_keywords = any(keyword in extracted_text for keyword in payment_keywords)
        
        # Extract amount from text (look for numbers with ₽, руб, Р, or near payment keywords)
        amount_patterns = [
            # With currency symbols
            r'(\d+[.,]\d+)\s*[₽рубР]',
            r'(\d+)\s*[₽рубР]',
            r'[₽рубР]\s*(\d+[.,]\d+)',
            r'[₽рубР]\s*(\d+)',
            # Near payment keywords
            r'(?:сумма|итого|перевод|amount|total)[:\s]+(\d+[.,]?\d*)',
            r'(\d+[.,]?\d*)\s*(?:сумма|итого|перевод|amount|total)',
            # Standalone numbers near payment context (more flexible)
            r'(?:сумма|итого|перевод|amount|total)[:\s]*\s*(\d+[.,]?\d*)\s*[₽рубР]?',
            # Numbers that might be misrecognized (B instead of Р, 2 instead of Р)
            r'(\d+)\s*[B2]',  # 500 B or 500 2 might be 500 Р
            r'(\d+)\s*[₽рубРB2]',
            # Just numbers in context of payment (last resort)
            r'\b(\d{2,6})\b',  # 2-6 digit numbers (likely amounts)
        ]
        
        amount_found = False
        found_amount = None
        all_found_amounts = []
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, extracted_text, re.IGNORECASE)
            if matches:
                try:
                    amounts = [float(m.replace(',', '.')) for m in matches]
                    all_found_amounts.extend(amounts)
                except:
                    continue
        
        if all_found_amounts:
            # Remove duplicates and sort
            unique_amounts = sorted(set(all_found_amounts), reverse=True)
            
            # Try to find amount that matches expected (with tolerance)
            for amt in unique_amounts:
                # Check if amount matches (allow small difference for rounding)
                diff = abs(amt - expected_amount)
                diff_percent = diff / expected_amount if expected_amount > 0 else 1
                
                # Match if difference is less than 1 ruble or less than 10%
                if diff < 1.0 or diff_percent < 0.1:
                    amount_found = True
                    found_amount = amt
                    break
            
            # If no exact match, use the largest reasonable amount
            if not amount_found and unique_amounts:
                # Filter amounts that are reasonable (between 10 and 100000)
                reasonable_amounts = [a for a in unique_amounts if 10 <= a <= 100000]
                if reasonable_amounts:
                    # Check if any reasonable amount is close to expected
                    for amt in reasonable_amounts:
                        diff = abs(amt - expected_amount)
                        if diff < 10.0:  # Allow up to 10 rubles difference
                            amount_found = True
                            found_amount = amt
                            break
        
        # Extract phone number from text
        phone_found = False
        if expected_phone:
            # Normalize phone (remove +, spaces, dashes)
            normalized_expected = re.sub(r'[+\s\-()]', '', expected_phone)
            
            # Look for phone patterns
            phone_patterns = [
                r'\+?7\d{10}',
                r'\+?7\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}',
                r'\d{11}',
                r'\+?\d{1}\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}',
            ]
            
            for pattern in phone_patterns:
                matches = re.findall(pattern, extracted_text)
                for match in matches:
                    normalized_match = re.sub(r'[+\s\-()]', '', match)
                    if normalized_match == normalized_expected or normalized_match.endswith(normalized_expected[-10:]):
                        phone_found = True
                        break
                if phone_found:
                    break
        
        # Determine if screenshot is valid
        # Improved logic: more flexible for legitimate payments, but still secure
        
        # Score-based validation (more reliable)
        score = 0
        max_score = 3
        
        # Amount match: +2 points (most important)
        if amount_found:
            score += 2
        elif all_found_amounts:
            # If amount found but doesn't match exactly, check if close
            reasonable_amounts = [a for a in all_found_amounts if 10 <= a <= 100000]
            if reasonable_amounts:
                # Check if any amount is within 20% of expected
                for amt in reasonable_amounts:
                    diff_percent = abs(amt - expected_amount) / expected_amount if expected_amount > 0 else 1
                    if diff_percent <= 0.2:  # Within 20%
                        score += 1  # Partial credit
                        break
        
        # Phone match: +1 point (if expected)
        if expected_phone and phone_found:
            score += 1
        
        # Payment keywords: +1 point (required for security)
        if has_payment_keywords:
            score += 1
        else:
            # If no keywords but amount matches perfectly, still allow (OCR might miss keywords)
            if amount_found and abs(found_amount - expected_amount) < 0.5:
                score += 0.5  # Partial credit
        
        # Initialize message parts
        message_parts = []
        
        # Validation: Need at least 2.5 points (flexible but secure)
        # This means: (amount + keywords) OR (amount + phone) OR (amount perfect match)
        valid = score >= 2.5
        
        # Additional security: if no amount found at all, reject (unless OCR failed)
        if not all_found_amounts and not has_payment_keywords:
            valid = False
            message_parts.append("❌ Не удалось найти сумму или признаки платежа в скриншоте")
        
        # Additional check: if amount is found but way off, be more strict
        if amount_found and found_amount:
            diff_percent = abs(found_amount - expected_amount) / expected_amount if expected_amount > 0 else 1
            # If difference is more than 30%, require additional verification
            if diff_percent > 0.3:
                # Require both phone and keywords if amount is way off
                if not (phone_found and has_payment_keywords):
                    valid = False
                    message_parts.append("⚠️ Сумма значительно отличается от ожидаемой. Требуется дополнительная проверка.")
        if amount_found:
            message_parts.append(f"✅ Сумма найдена: {found_amount:.2f} ₽")
        else:
            message_parts.append(f"⚠️ Сумма {expected_amount:.2f} ₽ не найдена в скриншоте")
        
        if expected_phone:
            if phone_found:
                message_parts.append(f"✅ Номер телефона найден")
            else:
                message_parts.append(f"⚠️ Номер телефона не найден")
        
        if has_payment_keywords:
            message_parts.append("✅ Обнаружены признаки платежа")
        else:
            message_parts.append("⚠️ Признаки платежа не обнаружены")
        
        return {
            'valid': valid,
            'amount_found': amount_found,
            'phone_found': phone_found if expected_phone else None,
            'has_payment_keywords': has_payment_keywords,
            'found_amount': found_amount,
            'message': '\n'.join(message_parts)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing payment screenshot: {e}", exc_info=True)
        return {
            'valid': True,  # Allow if analysis fails (fallback)
            'amount_found': False,
            'phone_found': False,
            'message': f'⚠️ Ошибка анализа изображения: {str(e)}. Проверка выполняется вручную.'
        }


# ==================== End Payment System Functions ====================


async def upload_image_to_hosting(image_data: bytes, filename: str = "image.jpg") -> str:
    """Upload image to public hosting and return public URL."""
    if not image_data or len(image_data) == 0:
        logger.error("Empty image data provided")
        return None
    
    # Try multiple hosting services
    hosting_services = [
        # 0x0.st - simple file hosting (most reliable)
        {
            'url': 'https://0x0.st',
            'method': 'POST',
            'data_type': 'form',
            'field_name': 'file'
        },
        # catbox.moe - image hosting
        {
            'url': 'https://catbox.moe/user/api.php',
            'method': 'POST',
            'data_type': 'form',
            'field_name': 'fileToUpload',
            'extra_params': {'reqtype': 'fileupload'}
        },
        # transfer.sh - file sharing
        {
            'url': f'https://transfer.sh/{filename}',
            'method': 'PUT',
            'data_type': 'raw',
            'field_name': None
        }
    ]
    
    for service in hosting_services:
        try:
            logger.info(f"Trying to upload to {service['url']}")
            async with aiohttp.ClientSession() as session:
                if service['data_type'] == 'form':
                    data = aiohttp.FormData()
                    # Add extra params if needed
                    if 'extra_params' in service:
                        for key, value in service['extra_params'].items():
                            data.add_field(key, value)
                    
                    # Add file
                    data.add_field(
                        service['field_name'],
                        BytesIO(image_data),
                        filename=filename,
                        content_type='image/jpeg'
                    )
                    
                    async with session.post(service['url'], data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        status = resp.status
                        text = await resp.text()
                        logger.info(f"Response from {service['url']}: status={status}, text={text[:100]}")
                        
                        if status in [200, 201]:
                            text = text.strip()
                            # For catbox.moe, response is direct URL
                            if 'catbox.moe' in service['url']:
                                if text.startswith('http'):
                                    return text
                            # For 0x0.st, response is direct URL
                            elif text.startswith('http'):
                                return text
                        else:
                            logger.warning(f"Upload to {service['url']} failed with status {status}: {text[:200]}")
                else:  # raw
                    headers = {'Content-Type': 'image/jpeg', 'Max-Downloads': '1', 'Max-Days': '7'}
                    async with session.put(service['url'], data=image_data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        status = resp.status
                        text = await resp.text()
                        logger.info(f"Response from {service['url']}: status={status}, text={text[:100]}")
                        
                        if status in [200, 201]:
                            text = text.strip()
                            if text.startswith('http'):
                                return text
                        else:
                            logger.warning(f"Upload to {service['url']} failed with status {status}: {text[:200]}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout uploading to {service['url']}")
            continue
        except Exception as e:
            logger.error(f"Exception uploading to {service['url']}: {e}", exc_info=True)
            continue
    
    # If all services fail, return None
    logger.error("All image hosting services failed. Image size: {} bytes".format(len(image_data)))
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a marketing welcome message with model selection."""
    user = update.effective_user
    user_id = user.id
    
    # Check flood protection
    flood_check = check_flood_protection(user_id)
    if not flood_check['allowed']:
        await update.message.reply_text(
            flood_check['message'],
            parse_mode='HTML'
        )
        return
    
    # Check if admin is in user mode (viewing as regular user)
    if user_id == ADMIN_ID:
        if user_id in user_sessions and user_sessions[user_id].get('admin_user_mode', False):
            is_admin = False  # Show as regular user
        else:
            is_admin = True
    else:
        is_admin = False
    
    # Get categories and models count
    categories = get_categories()
    total_models = len(KIE_MODELS)
    
    if is_admin:
        # Admin menu - extended version with marketing appeal
        welcome_text = (
            f'👑 <b>✨ ПАНЕЛЬ АДМИНИСТРАТОРА ✨</b>\n\n'
            f'Привет, {user.mention_html()}! 👋\n\n'
            f'🎯 <b>ПОЛНЫЙ КОНТРОЛЬ НАД AI MARKETPLACE</b>\n\n'
            f'📊 <b>СТАТИСТИКА СИСТЕМЫ:</b>\n'
            f'✅ <b>{total_models} премиум моделей</b> в арсенале\n'
            f'✅ <b>{len(categories)} категорий</b> контента\n'
            f'✅ <b>Безлимитный доступ</b> ко всем генерациям\n\n'
            f'🔥 <b>ТОПОВЫЕ МОДЕЛИ В СИСТЕМЕ:</b>\n\n'
            f'🎨 <b>Google Imagen 4 Ultra</b> - Флагман от Google DeepMind\n'
            f'   {get_model_price_text("google/imagen4-ultra", None, True)}\n'
            f'   ⭐ Максимальное качество для тестирования\n\n'
            f'🍌 <b>Nano Banana Pro</b> - 4K от Google\n'
            f'   {get_model_price_text("nano-banana-pro", None, True)}\n'
            f'   🎯 Профессиональная генерация 2K/4K\n\n'
            f'🎥 <b>Sora 2</b> - Видео от OpenAI\n'
            f'   {get_model_price_text("sora-2-text-to-video", None, True)}\n'
            f'   🎬 Кинематографические видео с аудио\n\n'
            f'⚙️ <b>АДМИНИСТРАТИВНЫЕ ВОЗМОЖНОСТИ:</b>\n'
            f'📈 Просмотр статистики и аналитики\n'
            f'👥 Управление пользователями\n'
            f'🎁 Управление промокодами\n'
            f'🧪 Тестирование OCR системы\n'
            f'💼 Полный контроль над ботом\n\n'
            f'💫 <b>НАЧНИТЕ УПРАВЛЕНИЕ ИЛИ ТЕСТИРОВАНИЕ!</b>'
        )
        
        # Admin keyboard - extended
        keyboard = []
        
        # All models button first
        keyboard.append([
            InlineKeyboardButton("📋 Все модели", callback_data="all_models")
        ])
        
        keyboard.append([])  # Empty row for spacing
        
        # Categories
        for category in categories:
            models_in_category = get_models_by_category(category)
            emoji = models_in_category[0]["emoji"] if models_in_category else "📦"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {category} ({len(models_in_category)})",
                callback_data=f"category:{category}"
            )])
        
        # Admin functions row
        keyboard.append([
            InlineKeyboardButton("💰 Баланс", callback_data="check_balance")
        ])
        keyboard.append([
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")
        ])
        keyboard.append([
            InlineKeyboardButton("🔍 Поиск", callback_data="admin_search"),
            InlineKeyboardButton("📝 Добавить", callback_data="admin_add")
        ])
        keyboard.append([
            InlineKeyboardButton("🧪 Тест OCR", callback_data="admin_test_ocr")
        ])
        keyboard.append([
            InlineKeyboardButton("👤 Режим пользователя", callback_data="admin_user_mode")
        ])
        keyboard.append([InlineKeyboardButton("🆘 Помощь", callback_data="help_menu")])
    else:
        # Regular user menu - ultra marketing version
        welcome_text = (
            f'🚀 <b>✨ ДОСТУП К ЛУЧШИМ AI-МОДЕЛЯМ МИРА БЕЗ VPN! ✨</b>\n\n'
            f'Привет, {user.mention_html()}! 👋\n\n'
            f'🎯 <b>ДОСТУП К ТОПОВЫМ НЕЙРОСЕТЯМ 2025!</b>\n\n'
            f'🌟 <b>ЧТО ВАС ЖДЕТ:</b>\n'
            f'🔥 <b>Google Imagen 4 Ultra</b> - только что представлена на Google I/O 2025!\n'
            f'🔥 <b>OpenAI Sora 2</b> - революция в видео-генерации!\n'
            f'🔥 <b>Google Nano Banana</b> - новейшая модель от DeepMind!\n'
            f'🔥 <b>Grok Imagine</b> - от создателей ChatGPT (xAI)!\n'
            f'🔥 <b>ByteDance Seedream</b> - профессиональная 4K генерация!\n\n'
            f'💎 <b>ПРЕИМУЩЕСТВА:</b>\n'
            f'✅ <b>БЕЗ VPN</b> - прямой доступ к мировым AI-моделям\n'
            f'✅ <b>ТОПОВЫЕ МОДЕЛИ</b> - только лучшие нейросети 2025 года\n'
            f'✅ <b>4K КАЧЕСТВО</b> - профессиональная генерация для бизнеса\n'
            f'✅ <b>МГНОВЕННАЯ СКОРОСТЬ</b> - результаты за секунды\n'
            f'✅ <b>ДОСТУПНЫЕ ЦЕНЫ</b> - от 0.8 кредита за изображение\n\n'
            f'🎬 <b>СОЗДАВАЙТЕ:</b>\n'
            f'📸 Фотореалистичные изображения для рекламы\n'
            f'🎥 Кинематографические видео для YouTube\n'
            f'🎨 Художественные иллюстрации для портфолио\n'
            f'📱 Контент для Instagram, TikTok, VK\n'
            f'🎯 Рекламные материалы для бизнеса\n'
            f'💼 Профессиональные визуалы для презентаций\n\n'
            f'🔥 <b>ТОП-3 МОДЕЛИ ПРЯМО СЕЙЧАС:</b>\n\n'
            f'🥇 <b>Google Imagen 4 Ultra</b> - Флагман 2025\n'
            f'   {get_model_price_text("google/imagen4-ultra", None, is_admin)}\n'
            f'   ⭐ Максимальное качество • Google I/O 2025\n\n'
            f'🥈 <b>OpenAI Sora 2</b> - Видео нового поколения\n'
            f'   {get_model_price_text("sora-2-text-to-video", None, is_admin)}\n'
            f'   🎬 Кинематография • Реалистичная физика\n\n'
            f'🥉 <b>Google Nano Banana Pro</b> - 4K от DeepMind\n'
            f'   {get_model_price_text("nano-banana-pro", None, is_admin)}\n'
            f'   🎯 Профессиональная генерация 2K/4K\n\n'
            f'🎁 <b>БЕСПЛАТНЫЕ ГЕНЕРАЦИИ!</b>\n'
            f'✨ <b>Z-Image</b> - {FREE_GENERATIONS_PER_DAY} бесплатных генераций в день!\n'
            f'   Попробуйте без пополнения баланса\n\n'
            f'💫 <b>НАЧНИТЕ СОЗДАВАТЬ ПРЯМО СЕЙЧАС!</b>\n\n'
            f'Выберите категорию или посмотрите все {total_models} моделей:'
        )
        
        # Regular user keyboard - simple
        keyboard = []
        
        # All models button first
        keyboard.append([
            InlineKeyboardButton("📋 Все модели", callback_data="all_models")
        ])
        
        keyboard.append([])  # Empty row for spacing
        
        # Categories
        for category in categories:
            models_in_category = get_models_by_category(category)
            emoji = models_in_category[0]["emoji"] if models_in_category else "📦"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {category} ({len(models_in_category)})",
                callback_data=f"category:{category}"
            )])
        
        # Bottom row
        keyboard.append([
            InlineKeyboardButton("💰 Баланс", callback_data="check_balance")
        ])
        keyboard.append([
            InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")
        ])
        keyboard.append([
            InlineKeyboardButton("🎁 Активировать промокод", callback_data="activate_promo")
        ])
        keyboard.append([
            InlineKeyboardButton("👥 Пригласить друга", callback_data="invite_friend")
        ])
        keyboard.append([InlineKeyboardButton("🆘 Помощь", callback_data="help_menu")])
    
    await update.message.reply_html(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    user_id = update.effective_user.id
    is_admin_user = get_is_admin(user_id)
    
    if is_admin_user:
        # Admin help
        help_text = (
            '📋 <b>Доступные команды:</b>\n\n'
            '/start - Главное меню\n'
            '/models - Показать модели\n'
            '/balance - Проверить баланс\n'
            '/generate - Начать генерацию\n'
            '/help - Справка\n\n'
            '👑 <b>Административные команды:</b>\n'
            '/search - Поиск в базе знаний\n'
            '/add - Добавление знаний\n'
            '/payments - Просмотр платежей\n'
            '/block_user - Заблокировать пользователя\n'
            '/unblock_user - Разблокировать пользователя\n'
            '/user_balance - Баланс пользователя\n'
            '/add_admin - Добавить администратора\n\n'
            '💡 <b>Как использовать:</b>\n'
            '1. Используйте /models чтобы увидеть доступные модели\n'
            '2. Используйте /balance чтобы проверить баланс\n'
            '3. Используйте /generate чтобы начать генерацию\n'
            '4. Выберите модель из списка\n'
            '5. Введите необходимые параметры\n'
            '6. Получите результат!'
        )
    else:
        # Regular user help
        help_text = (
            '📋 <b>Доступные команды:</b>\n\n'
            '/start - Главное меню\n'
            '/models - Показать модели\n'
            '/balance - Проверить баланс\n'
            '/generate - Начать генерацию\n'
            '/help - Справка\n\n'
            '💡 <b>Как использовать:</b>\n'
            '1. Используйте /models чтобы увидеть доступные модели\n'
            '2. Используйте /balance чтобы проверить баланс\n'
            '3. Используйте /generate чтобы начать генерацию\n'
            '4. Выберите модель из списка\n'
            '5. Введите необходимые параметры\n'
            '6. Получите результат!'
        )
    
    await update.message.reply_text(help_text, parse_mode='HTML')


async def list_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available models from static menu."""
    user_id = update.effective_user.id
    
    # Get models grouped by category
    categories = get_categories()
    
    # Create category selection keyboard
    keyboard = []
    for category in categories:
        models_in_category = get_models_by_category(category)
        emoji = models_in_category[0]["emoji"] if models_in_category else "📦"
        keyboard.append([InlineKeyboardButton(
            f"{emoji} {category} ({len(models_in_category)})",
            callback_data=f"category:{category}"
        )])
    
    keyboard.append([InlineKeyboardButton("📋 Все модели", callback_data="all_models")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    models_text = "📋 <b>Доступные модели:</b>\n\n"
    models_text += "Выберите категорию или просмотрите все модели:\n\n"
    for category in categories:
        models_in_category = get_models_by_category(category)
        models_text += f"<b>{category}</b>: {len(models_in_category)} моделей\n"
    
    await update.message.reply_text(
        models_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def start_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the generation process."""
    user_id = update.effective_user.id
    
    # Check if KIE API is configured
    if not kie.api_key:
        await update.message.reply_text(
            '❌ API не настроен. Укажите KIE_API_KEY в файле .env'
        )
        return
    
    await update.message.reply_text(
        '🚀 Начинаем генерацию!\n\n'
        'Сначала выберите модель из списка:',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Показать модели", callback_data="show_models")
        ]])
    )
    
    return SELECTING_MODEL


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Handle admin user mode toggle (MUST be first, before any other checks)
    if data == "admin_user_mode":
        # Toggle user mode for admin
        if user_id != ADMIN_ID:
            await query.answer("Эта функция доступна только администратору.")
            return ConversationHandler.END
        
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        
        current_mode = user_sessions[user_id].get('admin_user_mode', False)
        user_sessions[user_id]['admin_user_mode'] = not current_mode
        
        if not current_mode:
            # Switching to user mode - send new message directly
            await query.answer("Режим пользователя включен")
            user = update.effective_user
            categories = get_categories()
            total_models = len(KIE_MODELS)
            
            welcome_text = (
                f'🚀 <b>✨ ДОСТУП К ЛУЧШИМ AI-МОДЕЛЯМ МИРА БЕЗ VPN! ✨</b>\n\n'
                f'Привет, {user.mention_html()}! 👋\n\n'
                f'🎯 <b>ДОСТУП К ТОПОВЫМ НЕЙРОСЕТЯМ 2025!</b>\n\n'
                f'🌟 <b>ЧТО ВАС ЖДЕТ:</b>\n'
                f'🔥 <b>Google Imagen 4 Ultra</b> - только что представлена на Google I/O 2025!\n'
                f'🔥 <b>OpenAI Sora 2</b> - революция в видео-генерации!\n'
                f'🔥 <b>Google Nano Banana</b> - новейшая модель от DeepMind!\n'
                f'🔥 <b>Grok Imagine</b> - от создателей ChatGPT (xAI)!\n\n'
                f'💎 <b>ПРЕИМУЩЕСТВА:</b>\n'
                f'✅ <b>БЕЗ VPN</b> - прямой доступ к мировым AI-моделям\n'
                f'✅ <b>ТОПОВЫЕ МОДЕЛИ</b> - только лучшие нейросети 2025 года\n'
                f'✅ <b>4K КАЧЕСТВО</b> - профессиональная генерация\n'
                f'✅ <b>МГНОВЕННАЯ СКОРОСТЬ</b> - результаты за секунды\n\n'
                f'💫 <b>НАЧНИТЕ СОЗДАВАТЬ ПРЯМО СЕЙЧАС!</b>\n\n'
                f'Выберите категорию или посмотрите все модели:'
            )
            
            keyboard = []
            # All models button first
            keyboard.append([
                InlineKeyboardButton("📋 Все модели", callback_data="all_models")
            ])
            
            keyboard.append([])
            for category in categories:
                models_in_category = get_models_by_category(category)
                emoji = models_in_category[0]["emoji"] if models_in_category else "📦"
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {category} ({len(models_in_category)})",
                    callback_data=f"category:{category}"
                )])
            
            keyboard.append([
                InlineKeyboardButton("💰 Баланс", callback_data="check_balance")
            ])
            keyboard.append([
                InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")
            ])
            keyboard.append([
                InlineKeyboardButton("🎁 Активировать промокод", callback_data="activate_promo")
            ])
            keyboard.append([
                InlineKeyboardButton("🔙 Вернуться в админ-панель", callback_data="admin_back_to_admin")
            ])
            keyboard.append([
                InlineKeyboardButton("🆘 Помощь", callback_data="help_menu"),
                InlineKeyboardButton("💬 Поддержка", callback_data="support_contact")
            ])
            
            await query.message.reply_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        else:
            # Switching back to admin mode - send new message directly
            user_sessions[user_id]['admin_user_mode'] = False
            await query.answer("Возврат в админ-панель")
            user = update.effective_user
            categories = get_categories()
            total_models = len(KIE_MODELS)
            
            welcome_text = (
                f'👑 <b>✨ ПАНЕЛЬ АДМИНИСТРАТОРА ✨</b>\n\n'
                f'Привет, {user.mention_html()}! 👋\n\n'
                f'🎯 <b>ПОЛНЫЙ КОНТРОЛЬ НАД AI MARKETPLACE</b>\n\n'
                f'📊 <b>СТАТИСТИКА СИСТЕМЫ:</b>\n'
                f'✅ <b>{total_models} премиум моделей</b> в арсенале\n'
                f'✅ <b>{len(categories)} категорий</b> контента\n'
                f'✅ <b>Безлимитный доступ</b> ко всем генерациям\n\n'
                f'🔥 <b>ТОПОВЫЕ МОДЕЛИ В СИСТЕМЕ:</b>\n\n'
                f'🎨 <b>Google Imagen 4 Ultra</b> - Флагман от Google DeepMind\n'
                f'   {get_model_price_text("google/imagen4-ultra", None, True)}\n'
                f'   ⭐ Максимальное качество для тестирования\n\n'
                f'🍌 <b>Nano Banana Pro</b> - 4K от Google\n'
                f'   {get_model_price_text("nano-banana-pro", None, True)}\n'
                f'   🎯 Профессиональная генерация 2K/4K\n\n'
                f'🎥 <b>Sora 2</b> - Видео от OpenAI\n'
                f'   {get_model_price_text("sora-2-text-to-video", None, True)}\n'
                f'   🎬 Кинематографические видео с аудио\n\n'
                f'⚙️ <b>АДМИНИСТРАТИВНЫЕ ВОЗМОЖНОСТИ:</b>\n'
                f'📈 Просмотр статистики и аналитики\n'
                f'👥 Управление пользователями\n'
                f'🎁 Управление промокодами\n'
                f'🧪 Тестирование OCR системы\n'
                f'💼 Полный контроль над ботом\n\n'
                f'💫 <b>НАЧНИТЕ УПРАВЛЕНИЕ ИЛИ ТЕСТИРОВАНИЕ!</b>'
            )
            
            keyboard = []
            # All models button first
            keyboard.append([
                InlineKeyboardButton("📋 Все модели", callback_data="all_models")
            ])
            
            keyboard.append([])
            for category in categories:
                models_in_category = get_models_by_category(category)
                emoji = models_in_category[0]["emoji"] if models_in_category else "📦"
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {category} ({len(models_in_category)})",
                    callback_data=f"category:{category}"
                )])
            
            keyboard.append([
                InlineKeyboardButton("📋 Все модели", callback_data="all_models"),
                InlineKeyboardButton("💰 Баланс", callback_data="check_balance")
            ])
            keyboard.append([
                InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")
            ])
            keyboard.append([
                InlineKeyboardButton("🔍 Поиск", callback_data="admin_search"),
                InlineKeyboardButton("📝 Добавить", callback_data="admin_add")
            ])
            keyboard.append([
                InlineKeyboardButton("🧪 Тест OCR", callback_data="admin_test_ocr")
            ])
            keyboard.append([
                InlineKeyboardButton("👤 Режим пользователя", callback_data="admin_user_mode")
            ])
            keyboard.append([InlineKeyboardButton("🆘 Помощь", callback_data="help_menu")])
            
            await query.message.reply_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
    
    if data == "admin_back_to_admin":
        # Return to admin mode - send new message directly
        if user_id != ADMIN_ID:
            await query.answer("Эта функция доступна только администратору.")
            return ConversationHandler.END
        
        if user_id in user_sessions:
            user_sessions[user_id]['admin_user_mode'] = False
        await query.answer("Возврат в админ-панель")
        user = update.effective_user
        categories = get_categories()
        total_models = len(KIE_MODELS)
        
        welcome_text = (
            f'👑 <b>✨ ПАНЕЛЬ АДМИНИСТРАТОРА ✨</b>\n\n'
            f'Привет, {user.mention_html()}! 👋\n\n'
            f'🎯 <b>ПОЛНЫЙ КОНТРОЛЬ НАД AI MARKETPLACE</b>\n\n'
            f'📊 <b>СТАТИСТИКА СИСТЕМЫ:</b>\n'
            f'✅ <b>{total_models} премиум моделей</b> в арсенале\n'
            f'✅ <b>{len(categories)} категорий</b> контента\n'
            f'✅ <b>Безлимитный доступ</b> ко всем генерациям\n\n'
            f'🔥 <b>ТОПОВЫЕ МОДЕЛИ В СИСТЕМЕ:</b>\n\n'
            f'🎨 <b>Google Imagen 4 Ultra</b> - Флагман от Google DeepMind\n'
            f'   {get_model_price_text("google/imagen4-ultra", None, True)}\n'
            f'   ⭐ Максимальное качество для тестирования\n\n'
            f'🍌 <b>Nano Banana Pro</b> - 4K от Google\n'
            f'   {get_model_price_text("nano-banana-pro", None, True)}\n'
            f'   🎯 Профессиональная генерация 2K/4K\n\n'
            f'🎥 <b>Sora 2</b> - Видео от OpenAI\n'
            f'   {get_model_price_text("sora-2-text-to-video", None, True)}\n'
            f'   🎬 Кинематографические видео с аудио\n\n'
            f'⚙️ <b>АДМИНИСТРАТИВНЫЕ ВОЗМОЖНОСТИ:</b>\n'
            f'📈 Просмотр статистики и аналитики\n'
            f'👥 Управление пользователями\n'
            f'🎁 Управление промокодами\n'
            f'🧪 Тестирование OCR системы\n'
            f'💼 Полный контроль над ботом\n\n'
            f'💫 <b>НАЧНИТЕ УПРАВЛЕНИЕ ИЛИ ТЕСТИРОВАНИЕ!</b>'
        )
        
        keyboard = []
        
        # All models button first
        keyboard.append([
            InlineKeyboardButton("📋 Все модели", callback_data="all_models")
        ])
        
        keyboard.append([])
        for category in categories:
            models_in_category = get_models_by_category(category)
            emoji = models_in_category[0]["emoji"] if models_in_category else "📦"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {category} ({len(models_in_category)})",
                callback_data=f"category:{category}"
            )])
        
        keyboard.append([
            InlineKeyboardButton("💰 Баланс", callback_data="check_balance")
        ])
        keyboard.append([
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")
        ])
        keyboard.append([
            InlineKeyboardButton("🔍 Поиск", callback_data="admin_search"),
            InlineKeyboardButton("📝 Добавить", callback_data="admin_add")
        ])
        keyboard.append([
            InlineKeyboardButton("🧪 Тест OCR", callback_data="admin_test_ocr")
        ])
        keyboard.append([
            InlineKeyboardButton("👤 Режим пользователя", callback_data="admin_user_mode")
        ])
        keyboard.append([InlineKeyboardButton("🆘 Помощь", callback_data="help_menu")])
        
        await query.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    if data == "back_to_menu":
        # Return to start menu - send new message directly
        user = update.effective_user
        user_id = user.id
        
        # Check if admin is in user mode
        if user_id == ADMIN_ID:
            if user_id in user_sessions and user_sessions[user_id].get('admin_user_mode', False):
                is_admin = False
            else:
                is_admin = True
        else:
            is_admin = False
        
        categories = get_categories()
        total_models = len(KIE_MODELS)
        
        if is_admin:
            welcome_text = (
                f'👑 <b>✨ ПАНЕЛЬ АДМИНИСТРАТОРА ✨</b>\n\n'
                f'Привет, {user.mention_html()}! 👋\n\n'
                f'🎯 <b>ПОЛНЫЙ КОНТРОЛЬ НАД AI MARKETPLACE</b>\n\n'
                f'📊 <b>СТАТИСТИКА СИСТЕМЫ:</b>\n'
                f'✅ <b>{total_models} премиум моделей</b> в арсенале\n'
                f'✅ <b>{len(categories)} категорий</b> контента\n'
                f'✅ <b>Безлимитный доступ</b> ко всем генерациям\n\n'
                f'🔥 <b>ТОПОВЫЕ МОДЕЛИ В СИСТЕМЕ:</b>\n\n'
                f'🎨 <b>Google Imagen 4 Ultra</b> - Флагман от Google DeepMind\n'
                f'   {get_model_price_text("google/imagen4-ultra", None, True)}\n'
                f'   ⭐ Максимальное качество для тестирования\n\n'
                f'🍌 <b>Nano Banana Pro</b> - 4K от Google\n'
                f'   {get_model_price_text("nano-banana-pro", None, True)}\n'
                f'   🎯 Профессиональная генерация 2K/4K\n\n'
                f'🎥 <b>Sora 2</b> - Видео от OpenAI\n'
                f'   {get_model_price_text("sora-2-text-to-video", None, True)}\n'
                f'   🎬 Кинематографические видео с аудио\n\n'
                f'⚙️ <b>АДМИНИСТРАТИВНЫЕ ВОЗМОЖНОСТИ:</b>\n'
                f'📈 Просмотр статистики и аналитики\n'
                f'👥 Управление пользователями\n'
                f'🎁 Управление промокодами\n'
                f'🧪 Тестирование OCR системы\n'
                f'💼 Полный контроль над ботом\n\n'
                f'💫 <b>НАЧНИТЕ УПРАВЛЕНИЕ ИЛИ ТЕСТИРОВАНИЕ!</b>'
            )
            
            keyboard = []
            # All models button first
            keyboard.append([
                InlineKeyboardButton("📋 Все модели", callback_data="all_models")
            ])
            
            keyboard.append([])
            for category in categories:
                models_in_category = get_models_by_category(category)
                emoji = models_in_category[0]["emoji"] if models_in_category else "📦"
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {category} ({len(models_in_category)})",
                    callback_data=f"category:{category}"
                )])
            
            keyboard.append([
                InlineKeyboardButton("📋 Все модели", callback_data="all_models"),
                InlineKeyboardButton("💰 Баланс", callback_data="check_balance")
            ])
            keyboard.append([
                InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")
            ])
            keyboard.append([
                InlineKeyboardButton("🔍 Поиск", callback_data="admin_search"),
                InlineKeyboardButton("📝 Добавить", callback_data="admin_add")
            ])
            keyboard.append([
                InlineKeyboardButton("🧪 Тест OCR", callback_data="admin_test_ocr")
            ])
            keyboard.append([
                InlineKeyboardButton("👤 Режим пользователя", callback_data="admin_user_mode")
            ])
            keyboard.append([InlineKeyboardButton("🆘 Помощь", callback_data="help_menu")])
        else:
            welcome_text = (
                f'🚀 <b>✨ ДОСТУП К ЛУЧШИМ AI-МОДЕЛЯМ МИРА БЕЗ VPN! ✨</b>\n\n'
                f'Привет, {user.mention_html()}! 👋\n\n'
                f'🎯 <b>ДОСТУП К ТОПОВЫМ НЕЙРОСЕТЯМ 2025!</b>\n\n'
                f'🌟 <b>ЧТО ВАС ЖДЕТ:</b>\n'
                f'🔥 <b>Google Imagen 4 Ultra</b> - только что представлена на Google I/O 2025!\n'
                f'🔥 <b>OpenAI Sora 2</b> - революция в видео-генерации!\n'
                f'🔥 <b>Google Nano Banana</b> - новейшая модель от DeepMind!\n'
                f'🔥 <b>Grok Imagine</b> - от создателей ChatGPT (xAI)!\n\n'
                f'💎 <b>ПРЕИМУЩЕСТВА:</b>\n'
                f'✅ <b>БЕЗ VPN</b> - прямой доступ к мировым AI-моделям\n'
                f'✅ <b>ТОПОВЫЕ МОДЕЛИ</b> - только лучшие нейросети 2025 года\n'
                f'✅ <b>4K КАЧЕСТВО</b> - профессиональная генерация\n'
                f'✅ <b>МГНОВЕННАЯ СКОРОСТЬ</b> - результаты за секунды\n\n'
                f'💫 <b>НАЧНИТЕ СОЗДАВАТЬ ПРЯМО СЕЙЧАС!</b>\n\n'
                f'Выберите категорию или посмотрите все модели:'
            )
            
            keyboard = []
            
            # All models button first
            keyboard.append([
                InlineKeyboardButton("📋 Все модели", callback_data="all_models")
            ])
            
            keyboard.append([])
            for category in categories:
                models_in_category = get_models_by_category(category)
                emoji = models_in_category[0]["emoji"] if models_in_category else "📦"
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {category} ({len(models_in_category)})",
                    callback_data=f"category:{category}"
                )])
            
            keyboard.append([
                InlineKeyboardButton("💰 Баланс", callback_data="check_balance")
            ])
            keyboard.append([
                InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")
            ])
            # Add admin back button if admin is in user mode
            if user_id == ADMIN_ID and user_id in user_sessions and user_sessions[user_id].get('admin_user_mode', False):
                keyboard.append([
                    InlineKeyboardButton("🔙 Вернуться в админ-панель", callback_data="admin_back_to_admin")
                ])
            keyboard.append([
                InlineKeyboardButton("🆘 Помощь", callback_data="help_menu"),
                InlineKeyboardButton("💬 Поддержка", callback_data="support_contact")
            ])
        
        await query.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    if data == "generate_again":
        # Generate again - restore model and show model info, then ask for new prompt
        await query.answer()  # Acknowledge the callback
        
        logger.info(f"Generate again requested by user {user_id}")
        
        if user_id not in saved_generations:
            logger.warning(f"No saved generation data for user {user_id}")
            await query.edit_message_text(
                "❌ <b>Данные для повторной генерации не найдены</b>\n\n"
                "Начните новую генерацию через меню.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        saved_data = saved_generations[user_id]
        logger.info(f"Restoring generation data for user {user_id}, model: {saved_data.get('model_id')}")
        
        # Restore session with model info, but clear params to start fresh
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        
        model_id = saved_data['model_id']
        model_info = saved_data['model_info']
        
        # Restore model info but clear params - user will enter new prompt
        user_sessions[user_id].update({
            'model_id': model_id,
            'model_info': model_info,
            'properties': saved_data['properties'].copy(),
            'required': saved_data['required'].copy(),
            'params': {}  # Clear params - start fresh
        })
        
        # Get user balance and calculate available generations (same as select_model)
        user_balance = get_user_balance(user_id)
        is_admin = get_is_admin(user_id)
        
        # Calculate price for default parameters (minimum price)
        default_params = {}
        if model_id == "nano-banana-pro":
            default_params = {"resolution": "1K"}  # Cheapest option
        elif model_id == "seedream/4.5-text-to-image" or model_id == "seedream/4.5-edit":
            default_params = {"quality": "basic"}  # Basic quality (same price, but for consistency)
        
        min_price = calculate_price_rub(model_id, default_params, is_admin)
        price_text = format_price_rub(min_price, is_admin)
        
        # Calculate how many generations available
        if is_admin:
            available_count = "Безлимит"
        elif user_balance >= min_price:
            available_count = int(user_balance / min_price)
        else:
            available_count = 0
        
        # Show model info with price and available generations (same format as select_model)
        model_name = model_info.get('name', model_id)
        model_emoji = model_info.get('emoji', '🤖')
        model_desc = model_info.get('description', '')
        
        model_info_text = (
            f"{model_emoji} <b>{model_name}</b>\n\n"
            f"{model_desc}\n\n"
            f"💰 <b>Цена генерации:</b> {price_text} ₽\n"
        )
        
        if is_admin:
            model_info_text += f"✅ <b>Доступно:</b> Безлимит\n\n"
        else:
            if available_count > 0:
                model_info_text += f"✅ <b>Доступно генераций:</b> {available_count}\n"
                model_info_text += f"💳 <b>Ваш баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n\n"
            else:
                # Not enough balance - show warning
                model_info_text += (
                    f"❌ <b>Недостаточно средств</b>\n"
                    f"💳 <b>Ваш баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n"
                    f"💵 <b>Требуется:</b> {price_text} ₽\n\n"
                    f"Пополните баланс для генерации."
                )
                
                keyboard = [
                    [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
                    [InlineKeyboardButton("◀️ Назад к моделям", callback_data="back_to_menu")]
                ]
                
                await query.edit_message_text(
                    model_info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                return ConversationHandler.END
        
        # Check balance before starting generation
        if not is_admin and user_balance < min_price:
            keyboard = [
                [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
                [InlineKeyboardButton("◀️ Назад к моделям", callback_data="back_to_menu")]
            ]
            
            await query.edit_message_text(
                f"❌ <b>Недостаточно средств для генерации</b>\n\n"
                f"💳 <b>Ваш баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n"
                f"💵 <b>Требуется минимум:</b> {price_text} ₽\n\n"
                f"Пополните баланс, чтобы начать генерацию.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # Get input parameters from model info
        input_params = model_info.get('input_params', {})
        
        if not input_params:
            # If no params defined, ask for simple text input
            await query.edit_message_text(
                f"{model_info_text}"
                f"Введите текст для генерации:",
                parse_mode='HTML'
            )
            user_sessions[user_id]['params'] = {}
            user_sessions[user_id]['waiting_for'] = 'text'
            return INPUTTING_PARAMS
        
        # Store session data
        user_sessions[user_id]['params'] = {}
        user_sessions[user_id]['properties'] = input_params
        user_sessions[user_id]['required'] = [p for p, info in input_params.items() if info.get('required', False)]
        user_sessions[user_id]['current_param'] = None
        
        # Start with prompt parameter first
        if 'prompt' in input_params:
            # Check if model supports image input (image_input or image_urls)
            has_image_input = 'image_input' in input_params or 'image_urls' in input_params
            
            prompt_text = (
                f"{model_info_text}"
            )
            
            if has_image_input:
                prompt_text += (
                    f"📝 <b>Шаг 1: Введите промпт</b>\n\n"
                    f"Опишите изображение, которое хотите сгенерировать.\n\n"
                    f"💡 <i>После ввода промпта вы сможете добавить изображение (опционально)</i>"
                )
            else:
                prompt_text += (
                    f"📝 <b>Шаг 1: Введите промпт</b>\n\n"
                    f"Опишите изображение, которое хотите сгенерировать:"
                )
            
            await query.edit_message_text(
                prompt_text,
                parse_mode='HTML'
            )
            user_sessions[user_id]['current_param'] = 'prompt'
            user_sessions[user_id]['waiting_for'] = 'prompt'
            user_sessions[user_id]['has_image_input'] = has_image_input
        else:
            # If no prompt, start with first required parameter
            await start_next_parameter(update, context, user_id)
        
        return INPUTTING_PARAMS
    
    if data == "cancel":
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text("❌ Операция отменена.")
        return ConversationHandler.END
    
    # Handle category selection (can be called from main menu)
    if data.startswith("category:"):
        category = data.split(":", 1)[1]
        models = get_models_by_category(category)
        
        if not models:
            await query.edit_message_text(f"❌ В категории {category} нет моделей.")
            return ConversationHandler.END
        
        # Get user balance for showing available generations
        user_balance = get_user_balance(user_id)
        is_admin = get_is_admin(user_id)
        
        keyboard = []
        for model in models:
            # Calculate price and available count
            default_params = {}
            if model['id'] == "nano-banana-pro":
                default_params = {"resolution": "1K"}
            min_price = calculate_price_rub(model['id'], default_params, is_admin)
            
            if is_admin:
                button_text = f"{model['emoji']} {model['name']} (Безлимит)"
            else:
                if user_balance >= min_price:
                    available = int(user_balance / min_price)
                    button_text = f"{model['emoji']} {model['name']} ({available} шт)"
                else:
                    button_text = f"{model['emoji']} {model['name']} (0 шт)"
            
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"select_model:{model['id']}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        
        models_text = f"📋 <b>Модели категории {category}:</b>\n\n"
        for model in models:
            default_params = {}
            if model['id'] == "nano-banana-pro":
                default_params = {"resolution": "1K"}
            min_price = calculate_price_rub(model['id'], default_params, is_admin)
            
            if is_admin:
                available_text = "Безлимит"
            else:
                # Check for free generations for z-image
                if model['id'] == FREE_MODEL_ID:
                    remaining = get_user_free_generations_remaining(user_id)
                    if remaining > 0:
                        available_text = f"🎁 {remaining} бесплатно в день"
                    elif user_balance >= min_price:
                        available = int(user_balance / min_price)
                        available_text = f"{available} генераций"
                    else:
                        available_text = "0 генераций"
                elif user_balance >= min_price:
                    available = int(user_balance / min_price)
                    available_text = f"{available} генераций"
                else:
                    available_text = "0 генераций"
            
            # Get price text with free generation info
            price_display = get_model_price_text(model['id'], default_params, is_admin, user_id)
            
            models_text += (
                f"{model['emoji']} <b>{model['name']}</b>\n"
                f"{model['description']}\n"
                f"💰 Цена: {price_display} | ✅ Доступно: {available_text}\n\n"
            )
        
        await query.edit_message_text(
            models_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return SELECTING_MODEL
    
    if data == "show_models" or data == "all_models":
        # Show all models
        # Get user balance for showing available generations
        user_balance = get_user_balance(user_id)
        is_admin = get_is_admin(user_id)
        
        keyboard = []
        for model in KIE_MODELS:
            # Calculate price and available count
            default_params = {}
            if model['id'] == "nano-banana-pro":
                default_params = {"resolution": "1K"}
            min_price = calculate_price_rub(model['id'], default_params, is_admin)
            
            if is_admin:
                button_text = f"{model['emoji']} {model['name']} (Безлимит)"
            else:
                if user_balance >= min_price:
                    available = int(user_balance / min_price)
                    button_text = f"{model['emoji']} {model['name']} ({available} шт)"
                else:
                    button_text = f"{model['emoji']} {model['name']} (0 шт)"
            
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"select_model:{model['id']}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        
        models_text = "📋 <b>Все доступные модели:</b>\n\n"
        for model in KIE_MODELS:
            default_params = {}
            if model['id'] == "nano-banana-pro":
                default_params = {"resolution": "1K"}
            min_price = calculate_price_rub(model['id'], default_params, is_admin)
            
            if is_admin:
                available_text = "Безлимит"
            else:
                # Check for free generations for z-image
                if model['id'] == FREE_MODEL_ID:
                    remaining = get_user_free_generations_remaining(user_id)
                    if remaining > 0:
                        available_text = f"🎁 {remaining} бесплатно в день"
                    elif user_balance >= min_price:
                        available = int(user_balance / min_price)
                        available_text = f"{available} генераций"
                    else:
                        available_text = "0 генераций"
                elif user_balance >= min_price:
                    available = int(user_balance / min_price)
                    available_text = f"{available} генераций"
                else:
                    available_text = "0 генераций"
            
            # Get price text with free generation info
            price_display = get_model_price_text(model['id'], default_params, is_admin, user_id)
            
            models_text += (
                f"{model['emoji']} <b>{model['name']}</b>\n"
                f"{model['description']}\n"
                f"💰 Цена: {price_display} | ✅ Доступно: {available_text}\n\n"
            )
        
        await query.edit_message_text(
            models_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return SELECTING_MODEL
    
    if data == "add_image":
        await query.edit_message_text(
            "📷 <b>Загрузите изображение</b>\n\n"
            "Отправьте фото, которое хотите использовать как референс или для трансформации.\n"
            "Можно загрузить до 8 изображений.",
            parse_mode='HTML'
        )
        session = user_sessions.get(user_id, {})
        # Determine which parameter name to use (image_input or image_urls)
        model_info = session.get('model_info', {})
        input_params = model_info.get('input_params', {})
        if 'image_urls' in input_params:
            image_param_name = 'image_urls'
        else:
            image_param_name = 'image_input'
        session['waiting_for'] = image_param_name
        session[image_param_name] = []  # Initialize as array
        return INPUTTING_PARAMS
    
    if data == "image_done":
        session = user_sessions.get(user_id, {})
        image_param_name = session.get('waiting_for', 'image_input')
        if image_param_name in session and session[image_param_name]:
            session['params'][image_param_name] = session[image_param_name]
            await query.edit_message_text(
                f"✅ Добавлено изображений: {len(session[image_param_name])}\n\n"
                f"Продолжаю..."
            )
        session['waiting_for'] = None
        
        # Move to next parameter
        try:
            next_param_result = await start_next_parameter(update, context, user_id)
            if next_param_result:
                return next_param_result
            else:
                # All parameters collected
                model_name = session.get('model_info', {}).get('name', 'Unknown')
                model_id = session.get('model_id', '')
                params = session.get('params', {})
                params_text = "\n".join([f"  • {k}: {str(v)[:50]}..." for k, v in params.items()])
                
                # Check for free generation
                is_admin_user = get_is_admin(user_id)
                is_free = is_free_generation_available(user_id, model_id)
                free_info = ""
                if is_free:
                    remaining = get_user_free_generations_remaining(user_id)
                    free_info = f"\n\n🎁 <b>БЕСПЛАТНАЯ ГЕНЕРАЦИЯ!</b>\n"
                    free_info += f"Осталось бесплатных: {remaining}/{FREE_GENERATIONS_PER_DAY} в день"
                else:
                    price = calculate_price_rub(model_id, params, is_admin_user)
                    price_str = f"{price:.2f}".rstrip('0').rstrip('.')
                    free_info = f"\n\n💰 <b>Стоимость:</b> {price_str} ₽"
                
                keyboard = [
                    [InlineKeyboardButton("✅ Генерировать", callback_data="confirm_generate")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
                ]
                
                await query.edit_message_text(
                    f"📋 <b>Подтверждение:</b>\n\n"
                    f"Модель: <b>{model_name}</b>\n"
                    f"Параметры:\n{params_text}{free_info}\n\n"
                    f"Продолжить генерацию?",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                return CONFIRMING_GENERATION
        except Exception as e:
            logger.error(f"Error after image done: {e}")
            await query.edit_message_text("❌ Ошибка при переходе к следующему параметру.")
            return INPUTTING_PARAMS
    
    if data == "skip_image":
        await query.answer("Изображение пропущено")
        # Move to next parameter
        try:
            next_param_result = await start_next_parameter(update, context, user_id)
            if next_param_result:
                return next_param_result
            else:
                # All parameters collected
                session = user_sessions[user_id]
                model_name = session.get('model_info', {}).get('name', 'Unknown')
                params = session.get('params', {})
                params_text = "\n".join([f"  • {k}: {str(v)[:50]}..." for k, v in params.items()])
                
                keyboard = [
                    [InlineKeyboardButton("✅ Генерировать", callback_data="confirm_generate")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
                ]
                
                await query.edit_message_text(
                    f"📋 <b>Подтверждение:</b>\n\n"
                    f"Модель: <b>{model_name}</b>\n"
                    f"Параметры:\n{params_text}\n\n"
                    f"Продолжить генерацию?",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                return CONFIRMING_GENERATION
        except Exception as e:
            logger.error(f"Error after skipping image: {e}")
            await query.edit_message_text("❌ Ошибка при переходе к следующему параметру.")
            return INPUTTING_PARAMS
    
    if data.startswith("set_param:"):
        # Handle parameter setting via button
        parts = data.split(":", 2)
        if len(parts) == 3:
            param_name = parts[1]
            param_value = parts[2]
            
            if user_id not in user_sessions:
                await query.edit_message_text("❌ Сессия не найдена.")
                return ConversationHandler.END
            
            session = user_sessions[user_id]
            properties = session.get('properties', {})
            param_info = properties.get(param_name, {})
            param_type = param_info.get('type', 'string')
            
            # Convert boolean string to actual boolean
            if param_type == 'boolean':
                if param_value.lower() == 'true':
                    param_value = True
                elif param_value.lower() == 'false':
                    param_value = False
                else:
                    # Use default if invalid
                    param_value = param_info.get('default', True)
            
            session['params'][param_name] = param_value
            session['current_param'] = None
            
            # Check if there are more parameters
            required = session.get('required', [])
            params = session.get('params', {})
            missing = [p for p in required if p not in params]
            
            if missing:
                await query.edit_message_text(f"✅ {param_name} установлен: {param_value}")
                # Move to next parameter
                try:
                    next_param_result = await start_next_parameter(update, context, user_id)
                    if next_param_result:
                        return next_param_result
                except Exception as e:
                    logger.error(f"Error starting next parameter: {e}")
                    await query.edit_message_text("❌ Ошибка при переходе к следующему параметру.")
                    return INPUTTING_PARAMS
            else:
                # All parameters collected
                model_name = session.get('model_info', {}).get('name', 'Unknown')
                params_text = "\n".join([f"  • {k}: {v}" for k, v in params.items()])
                
                keyboard = [
                    [InlineKeyboardButton("✅ Генерировать", callback_data="confirm_generate")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
                ]
                
                await query.edit_message_text(
                    f"📋 <b>Подтверждение:</b>\n\n"
                    f"Модель: <b>{model_name}</b>\n"
                    f"Параметры:\n{params_text}\n\n"
                    f"Продолжить генерацию?",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                return CONFIRMING_GENERATION
    
    if data == "check_balance":
        # Check balance
        is_admin_user = get_is_admin(user_id)
        is_main_admin = (user_id == ADMIN_ID)
        
        if is_main_admin:
            # Main admin - show KIE API balance
            await query.edit_message_text('💳 Проверяю баланс...')
            try:
                result = await kie.get_credits()
                
                if result.get('ok'):
                    credits = result.get('credits', 0)
                    # Convert credits to rubles (no rounding)
                    credits_rub = credits * CREDIT_TO_USD * USD_TO_RUB
                    credits_rub_str = f"{credits_rub:.2f}".rstrip('0').rstrip('.')
                    
                    keyboard = [
                        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
                    ]
                    
                    await query.edit_message_text(
                        f'💳 <b>Баланс KIE API:</b> {credits_rub_str} ₽\n'
                        f'<i>({credits} кредитов)</i>\n\n'
                        f'👑 <b>Безлимитный доступ</b> ко всем генерациям.',
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='HTML'
                    )
                else:
                    error = result.get('error', 'Unknown error')
                    await query.edit_message_text(
                        f'❌ <b>Ошибка проверки баланса:</b>\n{error}',
                        parse_mode='HTML'
                    )
            except Exception as e:
                logger.error(f"Error checking balance: {e}")
                await query.edit_message_text(f'❌ Ошибка: {str(e)}')
        elif is_admin_user:
            # Limited admin - show limit info
            limit = get_admin_limit(user_id)
            spent = get_admin_spent(user_id)
            remaining = get_admin_remaining(user_id)
            keyboard = [
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
            ]
            
            await query.edit_message_text(
                f'👑 <b>Баланс администратора:</b>\n\n'
                f'💳 <b>Лимит:</b> {limit:.2f} ₽\n'
                f'💸 <b>Потрачено:</b> {spent:.2f} ₽\n'
                f'✅ <b>Осталось:</b> {remaining:.2f} ₽',
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            # Regular user - show user balance from user_balances.json
            user_balance = get_user_balance(user_id)
            balance_str = f"{user_balance:.2f}".rstrip('0').rstrip('.')
            
            # Check for free generations
            remaining_free = get_user_free_generations_remaining(user_id)
            total_free = FREE_GENERATIONS_PER_DAY + get_free_generations_data().get(str(user_id), {}).get('bonus', 0)
            free_info = ""
            if remaining_free > 0:
                free_info = f"\n\n🎁 <b>Бесплатные генерации:</b> {remaining_free}/{total_free} в день"
            
            keyboard = [
                [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
            ]
            
            await query.edit_message_text(
                f'💳 <b>Баланс:</b> {balance_str} ₽{free_info}\n\n'
                f'Доступно для генерации контента.',
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        
        return ConversationHandler.END
    
    if data == "topup_balance":
        # Check if user is blocked
        if is_user_blocked(user_id):
            await query.edit_message_text(
                "❌ <b>Ваш аккаунт заблокирован</b>\n\n"
                "Обратитесь к администратору для разблокировки.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # Show amount selection
        keyboard = [
            [
                InlineKeyboardButton("100 ₽", callback_data="topup_amount:100"),
                InlineKeyboardButton("500 ₽", callback_data="topup_amount:500")
            ],
            [
                InlineKeyboardButton("1000 ₽", callback_data="topup_amount:1000"),
                InlineKeyboardButton("2000 ₽", callback_data="topup_amount:2000")
            ],
            [
                InlineKeyboardButton("5000 ₽", callback_data="topup_amount:5000"),
                InlineKeyboardButton("Другая сумма", callback_data="topup_custom")
            ],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
        ]
        
        current_balance = get_user_balance(user_id)
        balance_str = f"{current_balance:.2f}".rstrip('0').rstrip('.')
        
        await query.edit_message_text(
            f"💳 <b>Пополнение баланса</b>\n\n"
            f"💰 <b>Текущий баланс:</b> {balance_str} ₽\n\n"
            f"Выберите сумму для пополнения:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return SELECTING_AMOUNT
    
    if data == "activate_promo":
        # Activate promo code - show beautiful notification
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        
        # Set waiting state for promo code
        user_sessions[user_id]['waiting_for'] = 'promocode'
        
        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            f"🎁 <b>✨ АКТИВАЦИЯ ПРОМОКОДА ✨</b>\n\n"
            f"💎 <b>Введите промокод для получения бонусов!</b>\n\n"
            f"📝 <b>Как использовать:</b>\n"
            f"1. Введите промокод в следующем сообщении\n"
            f"2. Бонусы будут начислены автоматически\n"
            f"3. Проверьте баланс после активации\n\n"
            f"💡 <i>Промокоды обновляются ежедневно</i>\n\n"
            f"🔤 <b>Введите промокод сейчас:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_PROMOCODE
    
    if data.startswith("topup_amount:"):
        # User selected a preset amount
        amount = float(data.split(":")[1])
        user_sessions[user_id] = {
            'topup_amount': amount,
            'waiting_for': 'payment_screenshot'
        }
        
        payment_details = get_payment_details()
        
        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        
        await query.edit_message_text(
            f"{payment_details}\n\n"
            f"💵 <b>Сумма к оплате:</b> {amount:.2f} ₽\n\n"
            f"После оплаты отправьте скриншот перевода в этот чат.\n\n"
            f"✅ <b>Баланс начислится автоматически</b> после отправки скриншота.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_PAYMENT_SCREENSHOT
    
    if data == "topup_custom":
        # User wants to enter custom amount
        await query.edit_message_text(
            "💳 <b>Введите сумму пополнения</b>\n\n"
            "Отправьте число (например: 1500)\n"
            "Минимальная сумма: 50 ₽\n"
            "Максимальная сумма: 50000 ₽",
            parse_mode='HTML'
        )
        user_sessions[user_id] = {
            'waiting_for': 'topup_amount_input'
        }
        return SELECTING_AMOUNT
    
    # Admin functions (only for admin)
    if user_id == ADMIN_ID:
        if data == "admin_stats":
            # Get statistics
            total_models = len(KIE_MODELS)
            categories = get_categories()
            active_sessions = len(user_sessions)
            
            # Try to get balance
            balance_info = ""
            try:
                balance_result = await kie.get_credits()
                if balance_result.get('ok'):
                    balance = balance_result.get('credits', 0)
                    # Convert credits to rubles (no rounding)
                    balance_rub = balance * CREDIT_TO_USD * USD_TO_RUB
                    balance_rub_str = f"{balance_rub:.2f}".rstrip('0').rstrip('.')
                    balance_info = f"💰 <b>Баланс:</b> {balance_rub_str} ₽\n<i>({balance} кредитов)</i>\n"
            except:
                balance_info = "💰 <b>Баланс:</b> Недоступен\n"
            
            stats_text = (
                f'📊 <b>Статистика бота:</b>\n\n'
                f'{balance_info}'
                f'📦 <b>Моделей:</b> {total_models}\n'
                f'📁 <b>Категорий:</b> {len(categories)}\n'
                f'👥 <b>Активных сессий:</b> {active_sessions}\n\n'
                f'🔄 Обновлено: {asyncio.get_event_loop().time():.0f}'
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
            ]
            
            await query.edit_message_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_settings":
            # Get support contact info
            support_telegram = os.getenv('SUPPORT_TELEGRAM', 'Не указано')
            
            settings_text = (
                f'⚙️ <b>Настройки администратора:</b>\n\n'
                f'🔧 <b>Доступные функции:</b>\n\n'
                f'✅ Управление моделями\n'
                f'✅ Просмотр статистики\n'
                f'✅ Управление пользователями\n'
                f'✅ Настройки API\n\n'
                f'💡 <b>Команды:</b>\n'
                f'/models - Управление моделями\n'
                f'/balance - Проверка баланса\n'
                f'/search - Поиск в базе знаний\n'
                f'/add - Добавление знаний\n'
                f'/payments - Просмотр платежей\n'
                f'/block_user - Заблокировать пользователя\n'
                f'/unblock_user - Разблокировать пользователя\n'
                f'/user_balance - Баланс пользователя\n\n'
                f'💬 <b>Настройки поддержки:</b>\n\n'
                f'💬 Telegram: {support_telegram if support_telegram != "Не указано" else "Не указано"}\n\n'
                f'💡 Для изменения настроек поддержки отредактируйте файл .env'
            )
            
            keyboard = [
                [InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promocodes")],
                [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
            ]
            
            await query.edit_message_text(
                settings_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_promocodes":
            # Show promocodes menu
            promocodes = load_promocodes()
            active_promo = get_active_promocode()
            
            promocodes_text = "🎁 <b>Управление промокодами</b>\n\n"
            
            if active_promo:
                promo_code = active_promo.get('code', 'N/A')
                promo_value = active_promo.get('value', 0)
                promo_expires = active_promo.get('expires', 'N/A')
                promo_used = active_promo.get('used_count', 0)
                
                promocodes_text += (
                    f"✅ <b>Активный промокод:</b>\n"
                    f"🔑 <b>Код:</b> <code>{promo_code}</code>\n"
                    f"💰 <b>Значение:</b> {promo_value} ₽\n"
                    f"📅 <b>Действителен до:</b> {promo_expires}\n"
                    f"👥 <b>Использовано раз:</b> {promo_used}\n\n"
                )
            else:
                promocodes_text += "❌ <b>Нет активного промокода</b>\n\n"
            
            promocodes_text += "💡 <b>Доступные действия:</b>\n"
            promocodes_text += "• Создать новый промокод\n"
            promocodes_text += "• Просмотреть все промокоды\n"
            promocodes_text += "• Управление промокодами\n"
            
            keyboard = [
                [InlineKeyboardButton("🆕 Создать новый промокод", callback_data="admin_create_promo")],
                [InlineKeyboardButton("📋 Просмотреть все промокоды", callback_data="admin_list_promos")],
                [InlineKeyboardButton("🔄 Обновить", callback_data="admin_promocodes")],
                [InlineKeyboardButton("◀️ Назад", callback_data="admin_settings")]
            ]
            
            await query.edit_message_text(
                promocodes_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_create_promo":
            # Generate new daily promo code
            new_promo = generate_daily_promocode()
            promo_code = new_promo.get('code', 'N/A')
            promo_value = new_promo.get('value', 0)
            promo_expires = new_promo.get('expires', 'N/A')
            
            keyboard = [
                [InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promocodes")],
                [InlineKeyboardButton("◀️ Назад", callback_data="admin_settings")]
            ]
            
            await query.edit_message_text(
                f"✅ <b>Новый промокод создан!</b>\n\n"
                f"🔑 <b>Код:</b> <code>{promo_code}</code>\n"
                f"💰 <b>Значение:</b> {promo_value} ₽\n"
                f"📅 <b>Действителен до:</b> {promo_expires}\n\n"
                f"💡 Промокод автоматически обновляется каждый день.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_list_promos":
            # List all promocodes
            promocodes = load_promocodes()
            
            promocodes_text = "📋 <b>Все промокоды:</b>\n\n"
            
            if not promocodes or len(promocodes) == 0:
                promocodes_text += "❌ <b>Нет созданных промокодов</b>\n\n"
            else:
                for i, promo in enumerate(promocodes, 1):
                    promo_code = promo.get('code', 'N/A')
                    promo_value = promo.get('value', 0)
                    promo_expires = promo.get('expires', 'N/A')
                    promo_used = promo.get('used_count', 0)
                    is_active = promo.get('active', False)
                    
                    status = "✅ Активен" if is_active else "❌ Неактивен"
                    
                    promocodes_text += (
                        f"{i}. <b>{status}</b>\n"
                        f"   🔑 <code>{promo_code}</code>\n"
                        f"   💰 {promo_value} ₽ | 👥 {promo_used} использований\n"
                        f"   📅 До: {promo_expires}\n\n"
                    )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data="admin_list_promos")],
                [InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promocodes")],
                [InlineKeyboardButton("◀️ Назад", callback_data="admin_settings")]
            ]
            
            await query.edit_message_text(
                promocodes_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_search":
            await query.edit_message_text(
                '🔍 <b>Поиск в базе знаний</b>\n\n'
                'Используйте команду:\n'
                '<code>/search [запрос]</code>\n\n'
                'Пример:\n'
                '<code>/search нейросети</code>',
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_add":
            await query.edit_message_text(
                '📝 <b>Добавление знаний</b>\n\n'
                'Используйте команду:\n'
                '<code>/add [заголовок] | [содержание]</code>\n\n'
                'Пример:\n'
                '<code>/add AI | Искусственный интеллект - это...</code>',
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_test_ocr":
            if not OCR_AVAILABLE or not PIL_AVAILABLE:
                await query.edit_message_text(
                    '❌ <b>OCR недоступен</b>\n\n'
                    'Tesseract OCR не установлен или библиотеки не найдены.\n\n'
                    'Установите:\n'
                    '1. pip install Pillow pytesseract\n'
                    '2. Tesseract OCR (см. TESSERACT_INSTALL.txt)',
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            await query.edit_message_text(
                '🧪 <b>Тест OCR</b>\n\n'
                'Отправьте изображение со скриншотом платежа.\n\n'
                'Система проверит:\n'
                '✅ Распознавание текста\n'
                '✅ Поиск сумм\n'
                '✅ Работа Tesseract OCR\n\n'
                'Или нажмите /cancel для отмены.',
                parse_mode='HTML'
            )
            user_sessions[user_id] = {
                'waiting_for': 'admin_test_ocr'
            }
            return ADMIN_TEST_OCR
        
        if data == "admin_test_ocr":
            if not OCR_AVAILABLE or not PIL_AVAILABLE:
                await query.edit_message_text(
                    '❌ <b>OCR недоступен</b>\n\n'
                    'Tesseract OCR не установлен или библиотеки не найдены.\n\n'
                    'Установите:\n'
                    '1. pip install Pillow pytesseract\n'
                    '2. Tesseract OCR (см. TESSERACT_INSTALL.txt)',
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            await query.edit_message_text(
                '🧪 <b>Тест OCR</b>\n\n'
                'Отправьте изображение со скриншотом платежа.\n\n'
                'Система проверит:\n'
                '✅ Распознавание текста\n'
                '✅ Поиск суммы\n'
                '✅ Работа Tesseract OCR\n\n'
                'Или нажмите /cancel для отмены.',
                parse_mode='HTML'
            )
            user_sessions[user_id] = {
                'waiting_for': 'admin_test_ocr'
            }
            return ADMIN_TEST_OCR
    
    if data == "help_menu":
        is_admin_user = get_is_admin(user_id)
        
        if is_admin_user:
            # Admin help
            help_text = (
                '📋 <b>Доступные команды:</b>\n\n'
                '/start - Главное меню\n'
                '/models - Показать модели\n'
                '/balance - Проверить баланс\n'
                '/generate - Начать генерацию\n'
                '/help - Справка\n\n'
                '👑 <b>Административные команды:</b>\n'
                '/search - Поиск в базе знаний\n'
                '/add - Добавление знаний\n'
                '/payments - Просмотр платежей\n'
                '/block_user - Заблокировать пользователя\n'
                '/unblock_user - Разблокировать пользователя\n'
                '/user_balance - Баланс пользователя\n'
                '/add_admin - Добавить администратора\n\n'
                '💡 <b>Как использовать:</b>\n'
                '1. Выберите модель из меню\n'
                '2. Введите промпт (описание)\n'
                '3. Выберите параметры через кнопки\n'
                '4. Подтвердите генерацию\n'
                '5. Получите результат!'
            )
        else:
            # Regular user help
            help_text = (
                '📋 <b>Доступные команды:</b>\n\n'
                '/start - Главное меню\n'
                '/models - Показать модели\n'
                '/balance - Проверить баланс\n'
                '/generate - Начать генерацию\n'
                '/help - Справка\n\n'
                '💡 <b>Как использовать:</b>\n'
                '1. Выберите модель из меню\n'
                '2. Введите промпт (описание)\n'
                '3. Выберите параметры через кнопки\n'
                '4. Подтвердите генерацию\n'
                '5. Получите результат!'
            )
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    if data == "support_contact":
        support_info = get_support_contact()
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            support_info,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    if data.startswith("select_model:"):
        model_id = data.split(":", 1)[1]
        
        # Get model from static list
        model_info = get_model_by_id(model_id)
        
        if not model_info:
            await query.edit_message_text(f"❌ Модель {model_id} не найдена.")
            return
        
        # Check user balance and calculate available generations
        user_balance = get_user_balance(user_id)
        is_admin = get_is_admin(user_id)
        
        # Calculate price for default parameters (minimum price)
        default_params = {}
        if model_id == "nano-banana-pro":
            default_params = {"resolution": "1K"}  # Cheapest option
        elif model_id == "seedream/4.5-text-to-image" or model_id == "seedream/4.5-edit":
            default_params = {"quality": "basic"}  # Basic quality (same price, but for consistency)
        
        min_price = calculate_price_rub(model_id, default_params, is_admin)
        price_text = format_price_rub(min_price, is_admin)
        
        # Calculate how many generations available
        if is_admin:
            available_count = "Безлимит"
        elif user_balance >= min_price:
            available_count = int(user_balance / min_price)
        else:
            available_count = 0
        
        # Show model info with price and available generations
        model_name = model_info.get('name', model_id)
        model_emoji = model_info.get('emoji', '🤖')
        model_desc = model_info.get('description', '')
        
        model_info_text = (
            f"{model_emoji} <b>{model_name}</b>\n\n"
            f"{model_desc}\n\n"
            f"💰 <b>Цена генерации:</b> {price_text} ₽\n"
        )
        
        if is_admin:
            model_info_text += f"✅ <b>Доступно:</b> Безлимит\n\n"
        else:
            if available_count > 0:
                model_info_text += f"✅ <b>Доступно генераций:</b> {available_count}\n"
                model_info_text += f"💳 <b>Ваш баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n\n"
            else:
                # Not enough balance - show warning
                model_info_text += (
                    f"❌ <b>Недостаточно средств</b>\n"
                    f"💳 <b>Ваш баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n"
                    f"💵 <b>Требуется:</b> {price_text} ₽\n\n"
                    f"Пополните баланс для генерации."
                )
                
                keyboard = [
                    [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
                    [InlineKeyboardButton("◀️ Назад к моделям", callback_data="back_to_menu")]
                ]
                
                await query.edit_message_text(
                    model_info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                return ConversationHandler.END
        
        # Check balance before starting generation
        if not is_admin and user_balance < min_price:
            keyboard = [
                [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
                [InlineKeyboardButton("◀️ Назад к моделям", callback_data="back_to_menu")]
            ]
            
            await query.edit_message_text(
                f"❌ <b>Недостаточно средств для генерации</b>\n\n"
                f"💳 <b>Ваш баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n"
                f"💵 <b>Требуется минимум:</b> {price_text} ₽\n\n"
                f"Пополните баланс, чтобы начать генерацию.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # Store selected model
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]['model_id'] = model_id
        user_sessions[user_id]['model_info'] = model_info
        
        # Get input parameters from static definition
        input_params = model_info.get('input_params', {})
        
        if not input_params:
            # If no params defined, ask for simple text input
            await query.edit_message_text(
                f"{model_info_text}"
                f"Введите текст для генерации:",
                parse_mode='HTML'
            )
            user_sessions[user_id]['params'] = {}
            user_sessions[user_id]['waiting_for'] = 'text'
            return INPUTTING_PARAMS
        
        # Store session data
        user_sessions[user_id]['params'] = {}
        user_sessions[user_id]['properties'] = input_params
        user_sessions[user_id]['required'] = [p for p, info in input_params.items() if info.get('required', False)]
        user_sessions[user_id]['current_param'] = None
        
        # Start with prompt parameter first
        if 'prompt' in input_params:
            # Check if model supports image input (image_input or image_urls)
            has_image_input = 'image_input' in input_params or 'image_urls' in input_params
            
            prompt_text = (
                f"{model_info_text}"
            )
            
            if has_image_input:
                prompt_text += (
                    f"📝 <b>Шаг 1: Введите промпт</b>\n\n"
                    f"Опишите изображение, которое хотите сгенерировать.\n\n"
                    f"💡 <i>После ввода промпта вы сможете добавить изображение (опционально)</i>"
                )
            else:
                prompt_text += (
                    f"📝 <b>Шаг 1: Введите промпт</b>\n\n"
                    f"Опишите изображение, которое хотите сгенерировать:"
                )
            
            await query.edit_message_text(
                prompt_text,
                parse_mode='HTML'
            )
            user_sessions[user_id]['current_param'] = 'prompt'
            user_sessions[user_id]['waiting_for'] = 'prompt'
            user_sessions[user_id]['has_image_input'] = has_image_input
        else:
            # If no prompt, start with first required parameter
            await start_next_parameter(update, context, user_id)
        
        return INPUTTING_PARAMS


async def start_next_parameter(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Start input for next parameter."""
    session = user_sessions[user_id]
    properties = session.get('properties', {})
    params = session.get('params', {})
    required = session.get('required', [])
    
    # Find next unset parameter (skip prompt, image_input, and image_urls as they're handled separately)
    for param_name in required:
        if param_name in ['prompt', 'image_input', 'image_urls']:
            continue
        if param_name not in params:
            param_info = properties.get(param_name, {})
            param_type = param_info.get('type', 'string')
            enum_values = param_info.get('enum')
            
            session['current_param'] = param_name
            
            # Handle boolean parameters
            if param_type == 'boolean':
                default_value = param_info.get('default', True)
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Да (true)", callback_data=f"set_param:{param_name}:true"),
                        InlineKeyboardButton("❌ Нет (false)", callback_data=f"set_param:{param_name}:false")
                    ],
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
                ]
                
                # Get model_id from session for better descriptions
                model_id = session.get('model_id', '')
                param_desc = get_user_friendly_param_description(param_name, param_info, model_id)
                chat_id = None
                if hasattr(update, 'effective_chat') and update.effective_chat:
                    chat_id = update.effective_chat.id
                elif hasattr(update, 'message') and update.message:
                    chat_id = update.message.chat_id
                elif hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message:
                    chat_id = update.callback_query.message.chat_id
                
                if not chat_id:
                    logger.error("Cannot determine chat_id in start_next_parameter")
                    return None
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📝 <b>Выберите {param_name}:</b>\n\n{param_desc}\n\n💡 <b>По умолчанию:</b> {'Да' if default_value else 'Нет'}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                return INPUTTING_PARAMS
            # If parameter has enum values, show buttons
            elif enum_values:
                keyboard = []
                # Create buttons in rows of 2
                for i in range(0, len(enum_values), 2):
                    row = []
                    row.append(InlineKeyboardButton(
                        enum_values[i],
                        callback_data=f"set_param:{param_name}:{enum_values[i]}"
                    ))
                    if i + 1 < len(enum_values):
                        row.append(InlineKeyboardButton(
                            enum_values[i + 1],
                            callback_data=f"set_param:{param_name}:{enum_values[i + 1]}"
                        ))
                    keyboard.append(row)
                keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
                
                # Get model_id from session for better descriptions
                model_id = session.get('model_id', '')
                param_desc = get_user_friendly_param_description(param_name, param_info, model_id)
                # Get chat_id from update
                chat_id = None
                if hasattr(update, 'effective_chat') and update.effective_chat:
                    chat_id = update.effective_chat.id
                elif hasattr(update, 'message') and update.message:
                    chat_id = update.message.chat_id
                elif hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message:
                    chat_id = update.callback_query.message.chat_id
                
                if not chat_id:
                    logger.error("Cannot determine chat_id in start_next_parameter")
                    return None
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📝 <b>Выберите {param_name}:</b>\n\n{param_desc}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                return INPUTTING_PARAMS
            else:
                # Text input
                # Get model_id from session for better descriptions
                model_id = session.get('model_id', '')
                param_desc = get_user_friendly_param_description(param_name, param_info, model_id)
                max_length = param_info.get('max_length')
                max_text = f"\n\n⚠️ <b>Максимум {max_length} символов.</b>" if max_length else ""
                
                # Get chat_id from update
                chat_id = None
                if hasattr(update, 'effective_chat') and update.effective_chat:
                    chat_id = update.effective_chat.id
                elif hasattr(update, 'message') and update.message:
                    chat_id = update.message.chat_id
                elif hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message:
                    chat_id = update.callback_query.message.chat_id
                
                if not chat_id:
                    logger.error("Cannot determine chat_id in start_next_parameter")
                    return None
                
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📝 <b>Введите {param_name}:</b>\n\n{param_desc}{max_text}",
                    parse_mode='HTML'
                )
                session['waiting_for'] = param_name
                return INPUTTING_PARAMS
    
    # All parameters collected
    return None


async def input_parameters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle parameter input."""
    user_id = update.effective_user.id
    
    # Check flood protection
    flood_check = check_flood_protection(user_id)
    if not flood_check['allowed']:
        await update.message.reply_text(
            flood_check['message'],
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Handle admin OCR test
    if user_id == ADMIN_ID and user_id in user_sessions and user_sessions[user_id].get('waiting_for') == 'admin_test_ocr':
        if update.message.photo:
            photo = update.message.photo[-1]
            loading_msg = await update.message.reply_text("🔍 Анализирую изображение...")
            
            try:
                file = await context.bot.get_file(photo.file_id)
                image_data = await file.download_as_bytearray()
                
                # Test OCR - extract text
                try:
                    image = Image.open(BytesIO(image_data))
                    try:
                        extracted_text = pytesseract.image_to_string(image, lang='rus+eng')
                    except Exception as e:
                        logger.warning(f"Error with rus+eng, trying eng only: {e}")
                        try:
                            extracted_text = pytesseract.image_to_string(image, lang='eng')
                        except Exception as e2:
                            logger.warning(f"Error with eng, trying default: {e2}")
                            extracted_text = pytesseract.image_to_string(image)
                except Exception as e:
                    error_msg = str(e)
                    if "tesseract is not installed" in error_msg.lower() or "not in your path" in error_msg.lower():
                        raise Exception("Tesseract OCR не найден. Убедитесь, что он установлен и добавлен в PATH.")
                    else:
                        raise Exception(f"Ошибка распознавания текста: {error_msg}")
                
                extracted_text_lower = extracted_text.lower()
                
                # Find amounts in text (improved patterns)
                amount_patterns = [
                    # With currency symbols
                    r'(\d+[.,]\d+)\s*[₽рубР]',
                    r'(\d+)\s*[₽рубР]',
                    r'[₽рубР]\s*(\d+[.,]\d+)',
                    r'[₽рубР]\s*(\d+)',
                    # Near payment keywords
                    r'(?:сумма|итого|перевод|amount|total)[:\s]+(\d+[.,]?\d*)',
                    r'(\d+[.,]?\d*)\s*(?:сумма|итого|перевод|amount|total)',
                    # Misrecognized currency (B instead of Р, 2 instead of Р)
                    r'(\d+)\s*[B2]',
                    r'(\d+)\s*[₽рубРB2]',
                    # Standalone numbers (filtered later)
                    r'\b(\d{2,6})\b',
                ]
                
                found_amounts = []
                for pattern in amount_patterns:
                    matches = re.findall(pattern, extracted_text, re.IGNORECASE)
                    for match in matches:
                        try:
                            amount = float(match.replace(',', '.'))
                            # Filter reasonable amounts (10-100000 rubles)
                            if 10 <= amount <= 100000:
                                found_amounts.append(amount)
                        except:
                            continue
                
                # Check for payment keywords
                payment_keywords = [
                    'перевод', 'оплата', 'платеж', 'спб', 'сбп', 'payment', 'transfer',
                    'отправлено', 'успешно', 'success', 'получатель', 'сумма', 'итого',
                    'квитанция', 'receipt', 'статус', 'status', 'комиссия', 'commission'
                ]
                has_keywords = any(keyword in extracted_text_lower for keyword in payment_keywords)
                
                # Prepare result
                result_text = "🧪 <b>Результаты теста OCR:</b>\n\n"
                
                result_text += f"📝 <b>Распознанный текст (первые 300 символов):</b>\n"
                result_text += f"<code>{extracted_text[:300].replace('<', '&lt;').replace('>', '&gt;')}</code>\n\n"
                
                if found_amounts:
                    result_text += f"💰 <b>Найденные суммы:</b>\n"
                    for amt in sorted(set(found_amounts), reverse=True)[:5]:
                        result_text += f"  • {amt:.2f} ₽\n"
                    result_text += "\n"
                else:
                    result_text += "⚠️ <b>Суммы не найдены</b>\n\n"
                
                if has_keywords:
                    result_text += "✅ <b>Признаки платежа обнаружены</b>\n"
                else:
                    result_text += "⚠️ <b>Признаки платежа не обнаружены</b>\n"
                
                result_text += f"\n📊 <b>Статистика:</b>\n"
                result_text += f"  • Символов распознано: {len(extracted_text)}\n"
                result_text += f"  • Сумм найдено: {len(found_amounts)}\n"
                result_text += f"  • Ключевых слов: {'Да' if has_keywords else 'Нет'}\n"
                
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Тест еще раз", callback_data="admin_test_ocr")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
                ]
                
                await update.message.reply_text(
                    result_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                
                # Clean up session
                if user_id in user_sessions:
                    del user_sessions[user_id]
                
                return ConversationHandler.END
            except Exception as e:
                logger.error(f"Error in admin OCR test: {e}", exc_info=True)
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                error_msg = str(e)
                help_text = ""
                if "tesseract is not installed" in error_msg.lower() or "not in your path" in error_msg.lower() or "tesseract" in error_msg.lower():
                    help_text = (
                        "\n\n💡 <b>Решение:</b>\n"
                        "1. Убедитесь, что Tesseract установлен\n"
                        "2. Проверьте путь: C:\\Program Files\\Tesseract-OCR\\tesseract.exe\n"
                        "3. Или добавьте Tesseract в PATH системы\n"
                        "4. Перезапустите бота после установки"
                    )
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать еще раз", callback_data="admin_test_ocr")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
                ]
                
                await update.message.reply_text(
                    f"❌ <b>Ошибка теста OCR:</b>\n\n{error_msg}{help_text}\n\n"
                    f"Попробуйте еще раз или нажмите /cancel.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                return ADMIN_TEST_OCR
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте изображение (фото).\n\n"
                "Или нажмите /cancel для отмены."
            )
            return ADMIN_TEST_OCR
    
    # Handle payment screenshot
    # Handle promo code input
    if user_id in user_sessions and user_sessions[user_id].get('waiting_for') == 'promocode':
        promocode_text = update.message.text.strip()
        
        # Activate promo code
        result = activate_promocode(user_id, promocode_text)
        
        keyboard = [
            [InlineKeyboardButton("💰 Проверить баланс", callback_data="check_balance")],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
        ]
        
        await update.message.reply_text(
            result['message'],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        
        # Clear waiting state
        if user_id in user_sessions:
            user_sessions[user_id]['waiting_for'] = None
        
        return ConversationHandler.END
    
    if user_id in user_sessions and user_sessions[user_id].get('waiting_for') == 'payment_screenshot':
        if update.message.photo:
            # User sent payment screenshot
            photo = update.message.photo[-1]
            screenshot_file_id = photo.file_id
            
            session = user_sessions[user_id]
            amount = session.get('topup_amount', 0)
            
            # Download and analyze screenshot (if OCR available)
            if OCR_AVAILABLE and PIL_AVAILABLE:
                loading_msg = await update.message.reply_text("🔍 Анализирую скриншот...")
            else:
                loading_msg = await update.message.reply_text("⏳ Обрабатываю платеж...")
            
            try:
                # Check for duplicate screenshot
                if check_duplicate_payment(screenshot_file_id):
                    await update.message.reply_text(
                        f"⚠️ <b>Этот скриншот уже был использован</b>\n\n"
                        f"Пожалуйста, отправьте новый скриншот перевода.\n\n"
                        f"Если вы уверены, что это новый платеж, обратитесь к администратору.",
                        parse_mode='HTML'
                    )
                    return WAITING_PAYMENT_SCREENSHOT
                
                file = await context.bot.get_file(photo.file_id)
                image_data = await file.download_as_bytearray()
                
                # Get expected phone from .env
                expected_phone = os.getenv('PAYMENT_PHONE', '')
                
                # Analyze screenshot (only if OCR available)
                analysis_msg = None
                if OCR_AVAILABLE and PIL_AVAILABLE:
                    analysis = await analyze_payment_screenshot(image_data, amount, expected_phone if expected_phone else None)
                    
                    # Delete loading message
                    try:
                        await loading_msg.delete()
                    except:
                        pass
                    
                    # Check if screenshot is valid - STRICT CHECK (default False)
                    if not analysis.get('valid', False):
                        support_info = get_support_contact()
                        await update.message.reply_text(
                            f"❌ <b>Скриншот не прошел проверку</b>\n\n"
                            f"{analysis.get('message', '')}\n\n"
                            f"😔 <b>Извините!</b> Если наша система не распознала вашу оплату, напишите администратору - он постарается оперативно начислить баланс.\n\n"
                            f"{support_info}",
                            parse_mode='HTML'
                        )
                        return WAITING_PAYMENT_SCREENSHOT
                    
                    # Show analysis results
                    analysis_msg = await update.message.reply_text(
                        f"🔍 <b>Результаты проверки:</b>\n\n"
                        f"{analysis.get('message', '')}\n\n"
                        f"⏳ Начисляю баланс...",
                        parse_mode='HTML'
                    )
                else:
                    # OCR not available - skip analysis and credit balance directly
                    try:
                        await loading_msg.delete()
                    except:
                        pass
                
                # Add payment and auto-credit balance
                payment = add_payment(user_id, amount, screenshot_file_id)
                new_balance = get_user_balance(user_id)
                balance_str = f"{new_balance:.2f}".rstrip('0').rstrip('.')
                
                # Delete analysis message (if exists)
                if analysis_msg:
                    try:
                        await analysis_msg.delete()
                    except:
                        pass
                
                # Clean up session
                del user_sessions[user_id]
                
                await update.message.reply_text(
                    f"✅ <b>Оплата получена!</b>\n\n"
                    f"💵 <b>Сумма:</b> {amount:.2f} ₽\n"
                    f"💰 <b>Новый баланс:</b> {balance_str} ₽\n\n"
                    f"Спасибо за пополнение! Теперь вы можете использовать баланс для генерации контента.",
                    parse_mode='HTML'
                )
                return ConversationHandler.END
                
            except Exception as e:
                logger.error(f"Error processing payment screenshot: {e}", exc_info=True)
                try:
                    await loading_msg.delete()
                except:
                    pass
                await update.message.reply_text(
                    f"❌ <b>Ошибка обработки скриншота</b>\n\n"
                    f"Попробуйте отправить скриншот еще раз.\n"
                    f"Или нажмите /cancel для отмены.",
                    parse_mode='HTML'
                )
                return WAITING_PAYMENT_SCREENSHOT
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте скриншот перевода (фото).\n\n"
                "Или нажмите /cancel для отмены."
            )
            return WAITING_PAYMENT_SCREENSHOT
    
    # Handle custom topup amount input
    if user_id in user_sessions and user_sessions[user_id].get('waiting_for') == 'topup_amount_input':
        try:
            amount = float(update.message.text.replace(',', '.'))
            
            if amount < 50:
                await update.message.reply_text("❌ Минимальная сумма пополнения: 50 ₽")
                return SELECTING_AMOUNT
            
            if amount > 50000:
                await update.message.reply_text("❌ Максимальная сумма пополнения: 50000 ₽")
                return SELECTING_AMOUNT
            
            # Set amount and show payment details
            user_sessions[user_id]['topup_amount'] = amount
            user_sessions[user_id]['waiting_for'] = 'payment_screenshot'
            
            payment_details = get_payment_details()
            
            keyboard = [
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
            ]
            
            await update.message.reply_text(
                f"{payment_details}\n\n"
                f"💵 <b>Сумма к оплате:</b> {amount:.2f} ₽\n\n"
                f"После оплаты отправьте скриншот перевода в этот чат.\n\n"
                f"✅ <b>Баланс начислится автоматически</b> после отправки скриншота.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return WAITING_PAYMENT_SCREENSHOT
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число (например: 1500)\n\n"
                "Или нажмите /cancel для отмены."
            )
            return SELECTING_AMOUNT
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Сессия не найдена. Начните заново с /start")
        return ConversationHandler.END
    
    session = user_sessions[user_id]
    properties = session.get('properties', {})
    
    # Handle image input (for image_input or image_urls)
    waiting_for_image = session.get('waiting_for') in ['image_input', 'image_urls']
    if update.message.photo and waiting_for_image:
        photo = update.message.photo[-1]  # Get largest photo
        file = await context.bot.get_file(photo.file_id)
        
        # Download image from Telegram
        loading_msg = None
        try:
            # Show loading message
            loading_msg = await update.message.reply_text("📤 Загрузка...")
            
            # Download image
            try:
                image_data = await file.download_as_bytearray()
            except Exception as e:
                logger.error(f"Error downloading file from Telegram: {e}", exc_info=True)
                if loading_msg:
                    try:
                        await loading_msg.delete()
                    except:
                        pass
                await update.message.reply_text(
                    "❌ <b>Ошибка загрузки</b>\n\n"
                    "Не удалось скачать изображение из Telegram.\n"
                    "Попробуйте еще раз или пропустите этот шаг.",
                    parse_mode='HTML'
                )
                return INPUTTING_PARAMS
            
            # Check file size (max 30MB as per KIE API)
            if len(image_data) > 30 * 1024 * 1024:
                if loading_msg:
                    try:
                        await loading_msg.delete()
                    except:
                        pass
                await update.message.reply_text(
                    "❌ <b>Файл слишком большой</b>\n\n"
                    "Максимальный размер: 30 MB.\n"
                    "Попробуйте другое изображение или пропустите этот шаг.",
                    parse_mode='HTML'
                )
                return INPUTTING_PARAMS
            
            if len(image_data) == 0:
                if loading_msg:
                    try:
                        await loading_msg.delete()
                    except:
                        pass
                await update.message.reply_text(
                    "❌ <b>Ошибка загрузки</b>\n\n"
                    "Изображение пустое.\n"
                    "Попробуйте еще раз или пропустите этот шаг.",
                    parse_mode='HTML'
                )
                return INPUTTING_PARAMS
            
            logger.info(f"Downloaded image: {len(image_data)} bytes")
            
            # Upload to public hosting
            public_url = await upload_image_to_hosting(image_data, filename=f"image_{user_id}_{photo.file_id[:8]}.jpg")
            
            # Delete loading message
            if loading_msg:
                try:
                    await loading_msg.delete()
                except:
                    pass
            
            if not public_url:
                await update.message.reply_text(
                    "❌ <b>Ошибка загрузки</b>\n\n"
                    "Не удалось обработать изображение.\n"
                    "Попробуйте еще раз или пропустите этот шаг.",
                    parse_mode='HTML'
                )
                return INPUTTING_PARAMS
            
            logger.info(f"Successfully uploaded image to: {public_url}")
            
            # Add to image_input array
            # Determine which parameter name to use
            image_param_name = session.get('waiting_for', 'image_input')  # image_input or image_urls
            if image_param_name not in session:
                session[image_param_name] = []
            session[image_param_name].append(public_url)
            
        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            # Try to delete loading message if exists
            if loading_msg:
                try:
                    await loading_msg.delete()
                except:
                    pass
            
            await update.message.reply_text(
                "❌ <b>Ошибка обработки</b>\n\n"
                "Не удалось обработать изображение.\n"
                "Попробуйте еще раз или пропустите этот шаг.",
                parse_mode='HTML'
            )
            return INPUTTING_PARAMS
        
        image_param_name = session.get('waiting_for', 'image_input')
        image_count = len(session[image_param_name])
        
        if image_count < 8:
            keyboard = [
                [InlineKeyboardButton("📷 Добавить еще", callback_data="add_image")],
                [InlineKeyboardButton("✅ Готово", callback_data="image_done")]
            ]
            await update.message.reply_text(
                f"✅ Изображение {image_count} добавлено!\n\n"
                f"Загружено: {image_count}/8\n\n"
                f"Добавить еще изображение или продолжить?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                f"✅ Изображение {image_count} добавлено!\n\n"
                f"Достигнут максимум (8 изображений). Продолжаю..."
            )
            session['params'][image_param_name] = session[image_param_name]
            session['waiting_for'] = None
            # Move to next parameter
            try:
                next_param_result = await start_next_parameter(update, context, user_id)
                if next_param_result:
                    return next_param_result
            except Exception as e:
                logger.error(f"Error after image input: {e}")
        
        return INPUTTING_PARAMS
    
    # Handle text input
    if not update.message.text:
        await update.message.reply_text("❌ Пожалуйста, отправьте текстовое сообщение.")
        return INPUTTING_PARAMS
    
    text = update.message.text.strip()
    
    # If waiting for text input (prompt or other text parameter)
    waiting_for = session.get('waiting_for')
    if waiting_for:
        current_param = session.get('current_param', waiting_for)
        param_info = properties.get(current_param, {})
        max_length = param_info.get('max_length')
        
        # Validate max length
        if max_length and len(text) > max_length:
            await update.message.reply_text(
                f"❌ Текст слишком длинный (макс. {max_length} символов). Попробуйте снова."
            )
            return INPUTTING_PARAMS
        
        # Set parameter value
        session['params'][current_param] = text
        session['waiting_for'] = None
        session['current_param'] = None
        
        # Confirm parameter was set
        await update.message.reply_text(
            f"✅ <b>{current_param}</b> установлен!\n\n"
            f"Значение: {text[:100]}{'...' if len(text) > 100 else ''}",
            parse_mode='HTML'
        )
        
        # If prompt was entered and model supports image input, offer to add image
        if current_param == 'prompt' and session.get('has_image_input'):
            model_info = session.get('model_info', {})
            input_params = model_info.get('input_params', {})
            # Check if image is required (for image_urls or image_input)
            image_required = False
            if 'image_urls' in input_params:
                image_required = input_params['image_urls'].get('required', False)
            elif 'image_input' in input_params:
                image_required = input_params['image_input'].get('required', False)
            
            if image_required:
                # Image is required - show button without skip option
                keyboard = [
                    [InlineKeyboardButton("📷 Загрузить изображение", callback_data="add_image")]
                ]
                await update.message.reply_text(
                    "📷 <b>Загрузите изображение для редактирования</b>\n\n"
                    "Отправьте фото, которое хотите отредактировать.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            else:
                # Image is optional - show button with skip option
                keyboard = [
                    [InlineKeyboardButton("📷 Добавить изображение", callback_data="add_image")],
                    [InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_image")]
                ]
                await update.message.reply_text(
                    "📷 <b>Хотите добавить изображение?</b>\n\n"
                    "Вы можете загрузить изображение для использования как референс или для трансформации.\n"
                    "Или пропустите этот шаг.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            return INPUTTING_PARAMS
        
        # Check if there are more parameters
        required = session.get('required', [])
        params = session.get('params', {})
        missing = [p for p in required if p not in params and p not in ['prompt', 'image_input', 'image_urls']]
        
        if missing:
            # Move to next parameter
            try:
                # Small delay to show confirmation
                await asyncio.sleep(0.5)
                next_param_result = await start_next_parameter(update, context, user_id)
                if next_param_result:
                    return next_param_result
            except Exception as e:
                logger.error(f"Error starting next parameter: {e}", exc_info=True)
                await update.message.reply_text(
                    f"❌ Ошибка при переходе к следующему параметру: {str(e)}"
                )
                return INPUTTING_PARAMS
        else:
            # All parameters collected, show confirmation
            model_name = session.get('model_info', {}).get('name', 'Unknown')
            model_id = session.get('model_id', '')
            params_text = "\n".join([f"  • {k}: {str(v)[:50]}..." for k, v in params.items()])
            
            # Check for free generation
            is_admin_user = get_is_admin(user_id)
            is_free = is_free_generation_available(user_id, model_id)
            free_info = ""
            if is_free:
                remaining = get_user_free_generations_remaining(user_id)
                free_info = f"\n\n🎁 <b>БЕСПЛАТНАЯ ГЕНЕРАЦИЯ!</b>\n"
                free_info += f"Осталось бесплатных: {remaining}/{FREE_GENERATIONS_PER_DAY} в день"
            else:
                price = calculate_price_rub(model_id, params, is_admin_user)
                price_str = f"{price:.2f}".rstrip('0').rstrip('.')
                free_info = f"\n\n💰 <b>Стоимость:</b> {price_str} ₽"
            
            keyboard = [
                [InlineKeyboardButton("✅ Генерировать", callback_data="confirm_generate")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
            ]
            
            await update.message.reply_text(
                f"📋 <b>Подтверждение:</b>\n\n"
                f"Модель: <b>{model_name}</b>\n"
                f"Параметры:\n{params_text}{free_info}\n\n"
                f"Продолжить генерацию?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return CONFIRMING_GENERATION
    
    # If we get here and waiting_for is not set, something went wrong
    if not waiting_for:
        await update.message.reply_text(
            "❌ Ошибка: не ожидается ввод параметра. Начните заново с /models"
        )
        return ConversationHandler.END
    
    return INPUTTING_PARAMS


async def confirm_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle generation confirmation."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    is_admin_user = get_is_admin(user_id)
    
    # Check if user is blocked
    if not is_admin_user and is_user_blocked(user_id):
        await query.edit_message_text(
            "❌ <b>Ваш аккаунт заблокирован</b>\n\n"
            "Обратитесь к администратору для разблокировки.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    if user_id not in user_sessions:
        await query.edit_message_text("❌ Сессия не найдена.")
        return ConversationHandler.END
    
    session = user_sessions[user_id]
    model_id = session.get('model_id')
    params = session.get('params', {})
    model_info = session.get('model_info', {})
    
    # Check if this is a free generation
    is_free = is_free_generation_available(user_id, model_id)
    
    # Calculate price (admins pay admin price, users pay user price)
    price = calculate_price_rub(model_id, params, is_admin_user)
    
    # For free generations, price is 0
    if is_free:
        price = 0.0
    
    # Check balance/limit before generation
    if not is_admin_user:
        # Regular user - check balance (unless free generation)
        if not is_free:
            user_balance = get_user_balance(user_id)
            if user_balance < price:
                price_str = f"{price:.2f}".rstrip('0').rstrip('.')
                balance_str = f"{user_balance:.2f}".rstrip('0').rstrip('.')
            
            # Create keyboard with topup button
            keyboard = [
                [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
                [InlineKeyboardButton("💰 Проверить баланс", callback_data="check_balance")],
                [InlineKeyboardButton("◀️ Назад к моделям", callback_data="back_to_menu")]
            ]
            
            await query.edit_message_text(
                f"❌ <b>Недостаточно средств для генерации</b>\n\n"
                f"💵 <b>Требуется:</b> {price_str} ₽\n"
                f"💳 <b>Ваш баланс:</b> {balance_str} ₽\n\n"
                f"⚠️ <b>Генерация не будет выполнена</b> до пополнения баланса.\n\n"
                f"Пополните баланс, чтобы продолжить.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            # Clean up session to prevent generation
            if user_id in user_sessions:
                del user_sessions[user_id]
            return ConversationHandler.END
    elif user_id != ADMIN_ID:
        # Limited admin - check limit
        remaining = get_admin_remaining(user_id)
        if remaining < price:
            price_str = f"{price:.2f}".rstrip('0').rstrip('.')
            remaining_str = f"{remaining:.2f}".rstrip('0').rstrip('.')
            limit = get_admin_limit(user_id)
            spent = get_admin_spent(user_id)
            await query.edit_message_text(
                f"❌ <b>Превышен лимит</b>\n\n"
                f"💰 <b>Требуется:</b> {price_str} ₽\n"
                f"💳 <b>Лимит:</b> {limit:.2f} ₽\n"
                f"💸 <b>Потрачено:</b> {spent:.2f} ₽\n"
                f"✅ <b>Осталось:</b> {remaining_str} ₽\n\n"
                f"Обратитесь к главному администратору для увеличения лимита.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
    
    await query.edit_message_text("🔄 Создаю задачу генерации... Пожалуйста, подождите.")
    
    try:
        # Prepare params for API (convert image_input to image_urls if needed for seedream/4.5-edit)
        api_params = params.copy()
        if model_id == "seedream/4.5-edit" and 'image_input' in api_params:
            # Convert image_input to image_urls for seedream/4.5-edit
            api_params['image_urls'] = api_params.pop('image_input')
        
        # Create task (for async models like z-image)
        result = await kie.create_task(model_id, api_params)
        
        if result.get('ok'):
            task_id = result.get('taskId')
            
            # Store task ID for polling
            session['task_id'] = task_id
            session['poll_attempts'] = 0
            session['max_poll_attempts'] = 60  # Poll for up to 5 minutes (60 * 5 seconds)
            
            # Show Task ID only for admin
            if is_admin_user:
                message_text = (
                    f"✅ <b>Задача создана!</b>\n\n"
                    f"Task ID: <code>{task_id}</code>\n\n"
                    f"⏳ Ожидаю завершения генерации..."
                )
            else:
                message_text = (
                    f"✅ <b>Задача создана!</b>\n\n"
                    f"⏳ Ожидаю завершения генерации..."
                )
            
            await query.edit_message_text(
                message_text,
                parse_mode='HTML'
            )
            
            # Start polling for task completion
            asyncio.create_task(poll_task_status(update, context, task_id, user_id))
        else:
            error = result.get('error', 'Unknown error')
            await query.edit_message_text(
                f"❌ <b>Ошибка создания задачи:</b>\n\n{error}",
                parse_mode='HTML'
            )
            # Clean up session
            if user_id in user_sessions:
                del user_sessions[user_id]
    
    except Exception as e:
        logger.error(f"Error during generation: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ <b>Произошла ошибка:</b>\n\n{str(e)}",
            parse_mode='HTML'
        )
        # Clean up session
        if user_id in user_sessions:
            del user_sessions[user_id]
    
    return ConversationHandler.END


async def poll_task_status(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str, user_id: int):
    """Poll task status until completion."""
    max_attempts = 60  # 5 minutes max
    attempt = 0
    start_time = asyncio.get_event_loop().time()
    last_status_message = None
    
    while attempt < max_attempts:
        await asyncio.sleep(5)  # Wait 5 seconds between polls
        attempt += 1
        
        try:
            status_result = await kie.get_task_status(task_id)
            
            if not status_result.get('ok'):
                error = status_result.get('error', 'Unknown error')
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ <b>Ошибка проверки статуса:</b>\n\n{error}",
                    parse_mode='HTML'
                )
                break
            
            state = status_result.get('state')
            
            if state == 'success':
                # Task completed successfully - deduct balance
                # Save session data before cleanup (for "generate again" button)
                saved_session_data = None
                model_id = ''
                params = {}
                if user_id in user_sessions:
                    session = user_sessions[user_id]
                    saved_session_data = {
                        'model_id': session.get('model_id'),
                        'model_info': session.get('model_info'),
                        'params': session.get('params', {}).copy(),
                        'properties': session.get('properties', {}).copy(),
                        'required': session.get('required', []).copy()
                    }
                    
                    # Get price and deduct from balance or limit
                    model_id = session.get('model_id', '')
                    params = session.get('params', {})
                    is_admin_user = get_is_admin(user_id)
                    
                    # Check if this is a free generation
                    is_free = is_free_generation_available(user_id, model_id)
                    if is_free:
                        # Use free generation
                        if use_free_generation(user_id):
                            price = 0.0
                        else:
                            # Free generation limit reached, treat as paid
                            is_free = False
                            price = calculate_price_rub(model_id, params, is_admin_user)
                    else:
                        price = calculate_price_rub(model_id, params, is_admin_user)
                    
                    if user_id != ADMIN_ID:
                        if is_free:
                            # Free generation - no deduction needed
                            pass
                        elif is_admin_user:
                            # Limited admin - deduct from limit
                            add_admin_spent(user_id, price)
                        else:
                            # Regular user - deduct from balance
                            # Double-check balance before deducting (safety check)
                            current_balance = get_user_balance(user_id)
                            if current_balance >= price:
                                success = subtract_user_balance(user_id, price)
                                if not success:
                                    logger.warning(f"Failed to deduct balance for user {user_id}. Balance: {current_balance}, Price: {price}")
                                    await context.bot.send_message(
                                        chat_id=update.effective_chat.id,
                                        text=f"⚠️ <b>Ошибка списания баланса</b>\n\n"
                                             f"Обратитесь к администратору.",
                                        parse_mode='HTML'
                                    )
                            else:
                                logger.warning(f"Insufficient balance for user {user_id}. Balance: {current_balance}, Price: {price}")
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text=f"❌ <b>Недостаточно средств</b>\n\n"
                                         f"💳 <b>Ваш баланс:</b> {format_price_rub(current_balance, False)} ₽\n"
                                         f"💵 <b>Требуется:</b> {format_price_rub(price, False)} ₽\n\n"
                                         f"Пополните баланс для получения результата.",
                                    parse_mode='HTML'
                                )
                                return  # Don't send results if balance is insufficient
                
                # Task completed successfully
                result_json = status_result.get('resultJson', '{}')
                last_message = None
                try:
                    result_data = json.loads(result_json)
                    
                    # Determine if this is a video model
                    is_video_model = model_id in [
                        'sora-2-text-to-video', 
                        'sora-watermark-remover',
                        'bytedance/v1-pro-fast-image-to-video',
                        'grok-imagine/image-to-video',
                        'grok-imagine/text-to-video',
                        'grok-imagine/upscale',
                        'hailuo/2-3-image-to-video-pro',
                        'hailuo/2-3-image-to-video-standard'
                    ]
                    
                    # For sora-2-text-to-video, check remove_watermark parameter
                    if model_id == 'sora-2-text-to-video':
                        remove_watermark = params.get('remove_watermark', True)
                        # If remove_watermark is True, use resultUrls (without watermark)
                        # If False, use resultWaterMarkUrls (with watermark)
                        if remove_watermark:
                            result_urls = result_data.get('resultUrls', [])
                        else:
                            result_urls = result_data.get('resultWaterMarkUrls', [])
                            # Fallback to resultUrls if resultWaterMarkUrls is empty
                            if not result_urls:
                                result_urls = result_data.get('resultUrls', [])
                    else:
                        # For other models, use resultUrls
                        result_urls = result_data.get('resultUrls', [])
                    
                    # Prepare buttons for last message
                    keyboard = [
                        [InlineKeyboardButton("◀️ Вернуться в меню", callback_data="back_to_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    if result_urls:
                        # Send media (video or image) directly
                        for i, url in enumerate(result_urls[:5]):  # Limit to 5 items
                            try:
                                # Try to download media and send it
                                async with aiohttp.ClientSession() as session_http:
                                    async with session_http.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                                        if resp.status == 200:
                                            media_data = await resp.read()
                                            
                                            # Add buttons only to the last item
                                            is_last = (i == len(result_urls[:5]) - 1)
                                            caption = "✅ <b>Генерация завершена!</b>" if i == 0 else None
                                            
                                            if is_video_model:
                                                # Send as video
                                                video_file = io.BytesIO(media_data)
                                                video_file.name = f"generated_video_{i+1}.mp4"
                                                
                                                if is_last:
                                                    last_message = await context.bot.send_video(
                                                        chat_id=update.effective_chat.id,
                                                        video=video_file,
                                                        caption=caption,
                                                        reply_markup=reply_markup,
                                                        parse_mode='HTML'
                                                    )
                                                else:
                                                    await context.bot.send_video(
                                                        chat_id=update.effective_chat.id,
                                                        video=video_file,
                                                        caption=caption,
                                                        parse_mode='HTML'
                                                    )
                                            else:
                                                # Send as image
                                                photo_file = io.BytesIO(media_data)
                                                photo_file.name = f"generated_image_{i+1}.png"
                                                
                                                if is_last:
                                                    last_message = await context.bot.send_photo(
                                                        chat_id=update.effective_chat.id,
                                                        photo=photo_file,
                                                        caption=caption,
                                                        reply_markup=reply_markup,
                                                        parse_mode='HTML'
                                                    )
                                                else:
                                                    await context.bot.send_photo(
                                                        chat_id=update.effective_chat.id,
                                                        photo=photo_file,
                                                        caption=caption,
                                                        parse_mode='HTML'
                                                    )
                                        else:
                                            # If download fails, try sending URL directly
                                            if is_video_model:
                                                if i == len(result_urls[:5]) - 1:
                                                    last_message = await context.bot.send_video(
                                                        chat_id=update.effective_chat.id,
                                                        video=url,
                                                        caption="✅ <b>Генерация завершена!</b>" if i == 0 else None,
                                                        reply_markup=reply_markup,
                                                        parse_mode='HTML'
                                                    )
                                                else:
                                                    await context.bot.send_video(
                                                        chat_id=update.effective_chat.id,
                                                        video=url,
                                                        caption="✅ <b>Генерация завершена!</b>" if i == 0 else None,
                                                        parse_mode='HTML'
                                                    )
                                            else:
                                                if i == len(result_urls[:5]) - 1:
                                                    last_message = await context.bot.send_photo(
                                                        chat_id=update.effective_chat.id,
                                                        photo=url,
                                                        caption="✅ <b>Генерация завершена!</b>" if i == 0 else None,
                                                        reply_markup=reply_markup,
                                                        parse_mode='HTML'
                                                    )
                                                else:
                                                    await context.bot.send_photo(
                                                        chat_id=update.effective_chat.id,
                                                        photo=url,
                                                        caption="✅ <b>Генерация завершена!</b>" if i == 0 else None,
                                                        parse_mode='HTML'
                                                    )
                            except Exception as e:
                                # If all methods fail, try sending URL directly as last resort
                                media_type = "video" if is_video_model else "photo"
                                logger.warning(f"Failed to send {media_type} {url}: {e}")
                                try:
                                    is_last = (i == len(result_urls[:5]) - 1)
                                    if is_video_model:
                                        if is_last:
                                            last_message = await context.bot.send_video(
                                                chat_id=update.effective_chat.id,
                                                video=url,
                                                caption="✅ <b>Генерация завершена!</b>" if i == 0 else None,
                                                reply_markup=reply_markup,
                                                parse_mode='HTML'
                                            )
                                        else:
                                            await context.bot.send_video(
                                                chat_id=update.effective_chat.id,
                                                video=url,
                                                caption="✅ <b>Генерация завершена!</b>" if i == 0 else None,
                                                parse_mode='HTML'
                                            )
                                    else:
                                        if is_last:
                                            last_message = await context.bot.send_photo(
                                                chat_id=update.effective_chat.id,
                                                photo=url,
                                                caption="✅ <b>Генерация завершена!</b>" if i == 0 else None,
                                                reply_markup=reply_markup,
                                                parse_mode='HTML'
                                            )
                                        else:
                                            await context.bot.send_photo(
                                                chat_id=update.effective_chat.id,
                                                photo=url,
                                                caption="✅ <b>Генерация завершена!</b>" if i == 0 else None,
                                                parse_mode='HTML'
                                            )
                                except Exception as e2:
                                    logger.error(f"Failed to send {media_type} even via URL: {e2}")
                                    # Last resort: send as message
                                    is_last = (i == len(result_urls[:5]) - 1)
                                    media_name = "Видео" if is_video_model else "Изображение"
                                    if is_last:
                                        last_message = await context.bot.send_message(
                                            chat_id=update.effective_chat.id,
                                            text=f"✅ <b>Генерация завершена!</b>\n\n{media_name}: {url}",
                                            reply_markup=reply_markup,
                                            parse_mode='HTML'
                                        )
                                    else:
                                        await context.bot.send_message(
                                            chat_id=update.effective_chat.id,
                                            text=f"✅ <b>Генерация завершена!</b>\n\n{media_name}: {url}",
                                            parse_mode='HTML'
                                        )
                    else:
                        last_message = await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="✅ <b>Генерация завершена!</b>\n\nРезультат готов.",
                            reply_markup=reply_markup,
                            parse_mode='HTML'
                        )
                except json.JSONDecodeError:
                    last_message = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"✅ <b>Генерация завершена!</b>\n\nРезультат: {result_json[:500]}",
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                
                # Clean up session
                if user_id in user_sessions:
                    del user_sessions[user_id]
                break
            
            elif state == 'fail':
                # Task failed
                fail_msg = status_result.get('failMsg', 'Unknown error')
                fail_code = status_result.get('failCode', '')
                
                error_text = f"❌ <b>Генерация завершена с ошибкой</b>\n\n"
                if fail_code:
                    error_text += f"Код ошибки: {fail_code}\n"
                error_text += f"Сообщение: {fail_msg}"
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=error_text,
                    parse_mode='HTML'
                )
                
                # Clean up session
                if user_id in user_sessions:
                    del user_sessions[user_id]
                break
            
            elif state in ['waiting', 'queuing', 'generating']:
                # Still processing, continue polling
                # Update status every 30 seconds (6 attempts * 5 seconds)
                if attempt % 6 == 0:
                    elapsed_time = int(asyncio.get_event_loop().time() - start_time)
                    minutes = elapsed_time // 60
                    seconds = elapsed_time % 60
                    
                    status_text = f"⏳ Статус: <b>{state}</b>\nОжидаю завершения..."
                    if minutes > 0:
                        status_text += f"\n⏱ Прошло: {minutes} мин {seconds} сек"
                    else:
                        status_text += f"\n⏱ Прошло: {seconds} сек"
                    
                    # Edit previous status message if exists, otherwise send new one
                    if last_status_message:
                        try:
                            await context.bot.edit_message_text(
                                chat_id=update.effective_chat.id,
                                message_id=last_status_message,
                                text=status_text,
                                parse_mode='HTML'
                            )
                        except Exception:
                            # If edit fails, send new message
                            msg = await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=status_text,
                                parse_mode='HTML'
                            )
                            last_status_message = msg.message_id
                    else:
                        msg = await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=status_text,
                            parse_mode='HTML'
                        )
                        last_status_message = msg.message_id
                continue
            else:
                # Unknown state
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"⚠️ Неизвестный статус: {state}\nПродолжаю ожидание...",
                    parse_mode='HTML'
                )
                continue
        
        except Exception as e:
            logger.error(f"Error polling task status: {e}", exc_info=True)
            if attempt >= max_attempts:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ Превышено время ожидания. Попробуйте начать генерацию заново.",
                    parse_mode='HTML'
                )
                break
    
    if attempt >= max_attempts:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⏰ Время ожидания истекло. Попробуйте начать генерацию заново.",
            parse_mode='HTML'
        )


async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user balance in rubles."""
    user_id = update.effective_user.id
    is_admin_user = get_is_admin(user_id)
    is_main_admin = (user_id == ADMIN_ID)
    
    if is_main_admin:
        # Main admin - show KIE API balance
        try:
            result = await kie.get_credits()
            
            if result.get('ok'):
                credits = result.get('credits', 0)
                # Convert credits to rubles (no rounding)
                credits_rub = credits * CREDIT_TO_USD * USD_TO_RUB
                credits_rub_str = f"{credits_rub:.2f}".rstrip('0').rstrip('.')
                
                await update.message.reply_text(
                    f'💳 <b>Баланс KIE API:</b> {credits_rub_str} ₽\n'
                    f'<i>({credits} кредитов)</i>\n\n'
                    f'👑 <b>Безлимитный доступ</b> ко всем генерациям.',
                    parse_mode='HTML'
                )
            else:
                error = result.get('error', 'Unknown error')
                await update.message.reply_text(
                    f'❌ <b>Ошибка проверки баланса:</b>\n{error}',
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            await update.message.reply_text(f'❌ Ошибка: {str(e)}')
    elif is_admin_user:
        # Limited admin - show limit info
        limit = get_admin_limit(user_id)
        spent = get_admin_spent(user_id)
        remaining = get_admin_remaining(user_id)
        
        await update.message.reply_text(
            f'👑 <b>Баланс администратора:</b>\n\n'
            f'💳 <b>Лимит:</b> {limit:.2f} ₽\n'
            f'💸 <b>Потрачено:</b> {spent:.2f} ₽\n'
            f'✅ <b>Осталось:</b> {remaining:.2f} ₽',
            parse_mode='HTML'
        )
    else:
        # Regular user - show user balance from user_balances.json
        user_balance = get_user_balance(user_id)
        balance_str = f"{user_balance:.2f}".rstrip('0').rstrip('.')
        
        # Check for free generations
        remaining_free = get_user_free_generations_remaining(user_id)
        total_free = FREE_GENERATIONS_PER_DAY + get_free_generations_data().get(str(user_id), {}).get('bonus', 0)
        free_info = ""
        if remaining_free > 0:
            free_info = f"\n\n🎁 <b>Бесплатные генерации:</b> {remaining_free}/{total_free} в день"
        
        await update.message.reply_text(
            f'💳 <b>Баланс:</b> {balance_str} ₽{free_info}\n\n'
            f'Доступно для генерации контента.',
            parse_mode='HTML'
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current operation."""
    user_id = update.effective_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    await update.message.reply_text("❌ Операция отменена.")
    return ConversationHandler.END


# Keep existing handlers
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle search queries."""
    query = ' '.join(context.args) if context.args else ''
    
    if not query:
        await update.message.reply_text('Пожалуйста, укажите запрос. Использование: /search [запрос]')
        return
    
    results = storage.search_entries(query)
    
    if results:
        response = f'Найдено {len(results)} результат(ов) для "{query}":\n\n'
        for i, result in enumerate(results[:5], 1):
            response += f'{i}. {result["content"][:100]}...\n'
    else:
        response = f'По запросу "{query}" ничего не найдено.'
    
    await update.message.reply_text(response)


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle questions."""
    question = ' '.join(context.args) if context.args else ''
    
    if not question:
        await update.message.reply_text('Пожалуйста, задайте вопрос. Использование: /ask [вопрос]')
        return
    
    results = storage.search_entries(question)
    
    if results:
        response = f'По вашему вопросу "{question}":\n\n'
        for i, result in enumerate(results[:3], 1):
            response += f'{i}. {result["content"]}\n\n'
    else:
        kie_model = os.getenv('KIE_DEFAULT_MODEL') or os.getenv('KIE_MODEL')
        if kie_model:
            try:
                await update.message.reply_text('🤔 Ищу ответ...')
                kie_resp = await kie.invoke_model(kie_model, {'text': question})
                if kie_resp.get('ok'):
                    result = kie_resp.get('result')
                    if isinstance(result, dict) and 'output' in result:
                        output = result['output']
                    else:
                        output = result
                    response = f'Вопрос: {question}\n\nОтвет:\n{output}'
                else:
                    response = f'Вопрос: {question}\n\nОшибка KIE: {kie_resp.get("error")}'
            except Exception as e:
                response = f'Вопрос: {question}\n\nОшибка: {e}'
        else:
            response = f'По вашему вопросу "{question}" ничего не найдено.'
    
    await update.message.reply_text(response)


async def add_knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new knowledge."""
    knowledge = ' '.join(context.args) if context.args else ''
    
    if not knowledge:
        await update.message.reply_text('Пожалуйста, укажите знание для добавления. Использование: /add [знание]')
        return
    
    success = storage.add_entry(knowledge, update.effective_user.id)
    
    if success:
        await update.message.reply_text(f'✅ Знание добавлено: "{knowledge[:50]}..."')
    else:
        await update.message.reply_text('❌ Не удалось добавить знание.')


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables!")
        return
    
    # Verify models are loaded correctly
    categories = get_categories()
    sora_models = [m for m in KIE_MODELS if m['id'] == 'sora-watermark-remover']
    logger.info(f"Bot starting with {len(KIE_MODELS)} models in {len(categories)} categories: {categories}")
    if sora_models:
        logger.info(f"✅ Sora model loaded: {sora_models[0]['name']} ({sora_models[0]['category']})")
    else:
        logger.warning(f"⚠️  Sora model NOT found! Available models: {[m['id'] for m in KIE_MODELS]}")
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Create conversation handler for generation
    generation_handler = ConversationHandler(
        entry_points=[
            CommandHandler('generate', start_generation),
            CommandHandler('models', list_models),
            CallbackQueryHandler(button_callback, pattern='^show_models$'),
            CallbackQueryHandler(button_callback, pattern='^category:'),
            CallbackQueryHandler(button_callback, pattern='^all_models$'),
            CallbackQueryHandler(button_callback, pattern='^check_balance$'),
            CallbackQueryHandler(button_callback, pattern='^help_menu$'),
            CallbackQueryHandler(button_callback, pattern='^support_contact$'),
            CallbackQueryHandler(button_callback, pattern='^select_model:'),
            CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
            CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
            CallbackQueryHandler(button_callback, pattern='^admin_search$'),
            CallbackQueryHandler(button_callback, pattern='^admin_add$'),
            CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
            CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
            CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
            CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
            CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
            CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
            CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
            CallbackQueryHandler(button_callback, pattern='^generate_again$'),
            CallbackQueryHandler(button_callback, pattern='^activate_promo$'),
            CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
            CallbackQueryHandler(button_callback, pattern='^admin_create_promo$'),
            CallbackQueryHandler(button_callback, pattern='^admin_list_promos$'),
            CallbackQueryHandler(button_callback, pattern='^admin_delete_promo:'),
            CallbackQueryHandler(button_callback, pattern='^admin_toggle_promo:')
        ],
        states={
            SELECTING_MODEL: [
                CallbackQueryHandler(button_callback, pattern='^select_model:'),
                CallbackQueryHandler(button_callback, pattern='^show_models$'),
                CallbackQueryHandler(button_callback, pattern='^category:'),
                CallbackQueryHandler(button_callback, pattern='^all_models$'),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            CONFIRMING_GENERATION: [
                CallbackQueryHandler(confirm_generation, pattern='^confirm_generate$'),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            INPUTTING_PARAMS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                MessageHandler(filters.PHOTO, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^set_param:'),
                CallbackQueryHandler(button_callback, pattern='^add_image$'),
                CallbackQueryHandler(button_callback, pattern='^skip_image$'),
                CallbackQueryHandler(button_callback, pattern='^image_done$'),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            SELECTING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
                CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            WAITING_PAYMENT_SCREENSHOT: [
                MessageHandler(filters.PHOTO, input_parameters),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            WAITING_PROMOCODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            ADMIN_TEST_OCR: [
                MessageHandler(filters.PHOTO, input_parameters),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel, pattern='^cancel$')
        ]
    )
    
    # Add handlers
    # Admin commands
    async def admin_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all payments (admin only)."""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Эта команда доступна только администратору.")
            return
        
        stats = get_payment_stats()
        payments = stats['payments']
        
        if not payments:
            await update.message.reply_text("📊 <b>Платежи</b>\n\nНет зарегистрированных платежей.", parse_mode='HTML')
            return
        
        # Show last 10 payments
        total_amount = stats['total_amount']
        total_count = stats['total_count']
        total_str = f"{total_amount:.2f}".rstrip('0').rstrip('.')
        
        text = f"📊 <b>Статистика платежей:</b>\n\n"
        text += f"💰 <b>Всего:</b> {total_str} ₽\n"
        text += f"📝 <b>Количество:</b> {total_count}\n\n"
        text += f"<b>Последние платежи:</b>\n\n"
        
        import datetime
        for payment in payments[:10]:
            user_id = payment.get('user_id', 0)
            amount = payment.get('amount', 0)
            timestamp = payment.get('timestamp', 0)
            amount_str = f"{amount:.2f}".rstrip('0').rstrip('.')
            
            if timestamp:
                dt = datetime.datetime.fromtimestamp(timestamp)
                date_str = dt.strftime("%d.%m.%Y %H:%M")
            else:
                date_str = "Неизвестно"
            
            text += f"👤 ID: {user_id} | 💵 {amount_str} ₽ | 📅 {date_str}\n"
        
        if total_count > 10:
            text += f"\n... и еще {total_count - 10} платежей"
        
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def admin_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Block a user (admin only)."""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Эта команда доступна только администратору.")
            return
        
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Использование: /block_user [user_id]")
            return
        
        try:
            user_id = int(context.args[0])
            block_user(user_id)
            await update.message.reply_text(f"✅ Пользователь {user_id} заблокирован.")
        except ValueError:
            await update.message.reply_text("❌ Неверный формат user_id. Используйте число.")
    
    async def admin_unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unblock a user (admin only)."""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Эта команда доступна только администратору.")
            return
        
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Использование: /unblock_user [user_id]")
            return
        
        try:
            user_id = int(context.args[0])
            unblock_user(user_id)
            await update.message.reply_text(f"✅ Пользователь {user_id} разблокирован.")
        except ValueError:
            await update.message.reply_text("❌ Неверный формат user_id. Используйте число.")
    
    async def admin_user_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user balance (admin only)."""
        user_id = update.effective_user.id
        if not get_is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администратору.")
            return
        
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Использование: /user_balance [user_id]")
            return
        
        try:
            user_id = int(context.args[0])
            balance = get_user_balance(user_id)
            balance_str = f"{balance:.2f}".rstrip('0').rstrip('.')
            is_blocked = is_user_blocked(user_id)
            blocked_text = "🔒 Заблокирован" if is_blocked else "✅ Активен"
            
            # Get user payments
            user_payments = get_user_payments(user_id)
            total_paid = sum(p.get('amount', 0) for p in user_payments)
            total_paid_str = f"{total_paid:.2f}".rstrip('0').rstrip('.')
            
            # Check if user is limited admin
            admin_info = ""
            if is_admin(user_id) and user_id != ADMIN_ID:
                limit = get_admin_limit(user_id)
                spent = get_admin_spent(user_id)
                remaining = get_admin_remaining(user_id)
                admin_info = (
                    f"\n👑 <b>Админ с лимитом:</b>\n"
                    f"💳 Лимит: {limit:.2f} ₽\n"
                    f"💸 Потрачено: {spent:.2f} ₽\n"
                    f"✅ Осталось: {remaining:.2f} ₽"
                )
            
            text = (
                f"👤 <b>Пользователь:</b> {user_id}\n"
                f"💰 <b>Баланс:</b> {balance_str} ₽\n"
                f"💵 <b>Всего пополнено:</b> {total_paid_str} ₽\n"
                f"📝 <b>Платежей:</b> {len(user_payments)}\n"
                f"🔐 <b>Статус:</b> {blocked_text}"
                f"{admin_info}"
            )
            
            await update.message.reply_text(text, parse_mode='HTML')
        except ValueError:
            await update.message.reply_text("❌ Неверный формат user_id. Используйте число.")
    
    async def admin_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add admin with 100 rubles limit (main admin only)."""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Эта команда доступна только главному администратору.")
            return
        
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Использование: /add_admin [user_id]\n\nДобавляет админа с лимитом 100 ₽ на тесты.")
            return
        
        try:
            new_admin_id = int(context.args[0])
            
            # Check if already admin
            if new_admin_id == ADMIN_ID:
                await update.message.reply_text("❌ Это главный администратор.")
                return
            
            admin_limits = get_admin_limits()
            if str(new_admin_id) in admin_limits:
                await update.message.reply_text(f"❌ Пользователь {new_admin_id} уже является админом.")
                return
            
            # Add admin with 100 rubles limit
            import time
            admin_limits[str(new_admin_id)] = {
                'limit': 100.0,
                'spent': 0.0,
                'added_by': update.effective_user.id,
                'added_at': int(time.time())
            }
            save_admin_limits(admin_limits)
            
            await update.message.reply_text(
                f"✅ <b>Админ добавлен!</b>\n\n"
                f"👤 User ID: {new_admin_id}\n"
                f"💳 Лимит: 100.00 ₽\n"
                f"💸 Потрачено: 0.00 ₽\n"
                f"✅ Осталось: 100.00 ₽",
                parse_mode='HTML'
            )
        except ValueError:
            await update.message.reply_text("❌ Неверный формат user_id. Используйте число.")
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", check_balance))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("ask", ask))
    application.add_handler(CommandHandler("add", add_knowledge))
    application.add_handler(CommandHandler("payments", admin_payments))
    application.add_handler(CommandHandler("block_user", admin_block_user))
    application.add_handler(CommandHandler("unblock_user", admin_unblock_user))
    application.add_handler(CommandHandler("user_balance", admin_user_balance))
    application.add_handler(CommandHandler("add_admin", admin_add_admin))
    application.add_handler(generation_handler)
    application.add_handler(CommandHandler("models", list_models))
    
    # Run the bot
    logger.info("Bot starting...")
    application.run_polling()


if __name__ == '__main__':
    main()


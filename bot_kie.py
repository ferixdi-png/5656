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
from kie_models import (
    KIE_MODELS, get_model_by_id, get_models_by_category, get_categories,
    get_generation_types, get_models_by_generation_type, get_generation_type_info
)
import json
import aiohttp
import io
from io import BytesIO
import re
import platform
import random
import time

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
    tesseract_found = False
    
    # Try to set Tesseract path
    # On Windows, check common installation paths
    # On Linux (Render/Timeweb), Tesseract should be in PATH
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
    else:
        # On Linux, assume Tesseract is in PATH (installed via apt-get in Dockerfile)
        # Don't search PATH at import time - it can cause timeout
        # pytesseract will try to find tesseract automatically when needed
        logger.info("Tesseract should be in PATH (Linux). Will auto-detect when OCR is used.")
        # Assume it's available if we're on Linux (installed in Dockerfile)
        tesseract_found = True
    
    if not tesseract_found:
        logger.warning("Tesseract not found. OCR analysis will be disabled. Install tesseract-ocr package if needed.")
        OCR_AVAILABLE = False
    else:
        # Don't test Tesseract at import time - it can hang or timeout
        # Test will happen when OCR is actually needed
        logger.info("Tesseract OCR path configured. Will be tested when needed.")
except ImportError:
    OCR_AVAILABLE = False
    tesseract_found = False
    logger.warning("pytesseract not available. OCR analysis will be disabled.")

# Bot token from environment variable
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Admin user ID (can be set via environment variable)
try:
    admin_id_str = os.getenv('ADMIN_ID', '6913446846')
    if admin_id_str and admin_id_str != 'your_admin_id_here':
        ADMIN_ID = int(admin_id_str)
    else:
        ADMIN_ID = 6913446846  # Default fallback
except (ValueError, TypeError):
    ADMIN_ID = 6913446846  # Default fallback if invalid

# Price conversion constants
# Based on: 18 credits = $0.09 = 6.95 ₽
CREDIT_TO_USD = 0.005  # 1 credit = $0.005 ($0.09 / 18)
USD_TO_RUB = 6.95 / 0.09  # 1 USD = 77.2222... RUB (calculated from 6.95 ₽ / $0.09)

# Initialize knowledge storage and KIE client (will be initialized in main() to avoid blocking import)
storage = None
kie = None

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
    elif model_id == "sora-watermark-remover":
        # Sora watermark remover costs 10 credits per use
        base_credits = 10
    elif model_id == "sora-2-text-to-video":
        # Sora 2 text-to-video costs 30 credits per 10-second video with audio
        base_credits = 30
    elif model_id == "kling-2.6/image-to-video" or model_id == "kling-2.6/text-to-video":
        # Kling 2.6 pricing (same for both image-to-video and text-to-video):
        # 5s no-audio: 55 credits
        # 10s no-audio: 110 credits
        # 5s with audio: 110 credits
        # 10s with audio: 220 credits
        duration = params.get("duration", "5")
        sound = params.get("sound", False)
        
        if duration == "5":
            if sound:
                base_credits = 110  # 5s with audio
            else:
                base_credits = 55  # 5s no-audio
        else:  # duration == "10"
            if sound:
                base_credits = 220  # 10s with audio
            else:
                base_credits = 110  # 10s no-audio
    elif model_id == "kling/v2-5-turbo-text-to-video-pro" or model_id == "kling/v2-5-turbo-image-to-video-pro":
        # Kling 2.5 Turbo pricing (same for both text-to-video and image-to-video):
        # 5s: 42 credits
        # 10s: 84 credits
        duration = params.get("duration", "5")
        if duration == "10":
            base_credits = 84
        else:  # duration == "5"
            base_credits = 42
    elif model_id == "wan/2-5-image-to-video" or model_id == "wan/2-5-text-to-video":
        # WAN 2.5 pricing (same for both image-to-video and text-to-video):
        # 720p: 12 credits per second
        # 1080p: 20 credits per second
        duration = params.get("duration", "5")
        resolution = params.get("resolution", "720p")
        
        duration_int = int(duration)
        if resolution == "1080p":
            base_credits = 20 * duration_int  # 20 credits per second
        else:  # 720p
            base_credits = 12 * duration_int  # 12 credits per second
    elif model_id == "wan/2-2-animate-move" or model_id == "wan/2-2-animate-replace":
        # WAN 2.2 Animate pricing (same for both move and replace):
        # 480p: 6 credits per second
        # 580p: 9.5 credits per second
        # 720p: 12.5 credits per second
        # Note: Duration is determined by input video length (up to 30 seconds)
        # For pricing calculation, we'll use a default of 5 seconds as minimum
        resolution = params.get("resolution", "480p")
        
        # Default duration for pricing (actual duration comes from video)
        default_duration = 5
        
        if resolution == "720p":
            base_credits = 12.5 * default_duration  # 12.5 credits per second
        elif resolution == "580p":
            base_credits = 9.5 * default_duration  # 9.5 credits per second
        else:  # 480p
            base_credits = 6 * default_duration  # 6 credits per second
    elif model_id == "hailuo/02-text-to-video-pro" or model_id == "hailuo/02-image-to-video-pro":
        # Hailuo 02 Pro pricing:
        # 9.5 credits per second for 1080p
        # One generation yields a 6-second 1080p video
        # So: 9.5 * 6 = 57 credits per generation
        base_credits = 57  # Fixed price for 6-second 1080p video
    elif model_id == "hailuo/02-image-to-video-standard":
        # Hailuo 02 Standard image-to-video pricing:
        # 512P: 2 credits per second
        # 768P: 5 credits per second
        resolution = params.get("resolution", "768P")
        duration = params.get("duration", "6")
        duration_int = int(duration)
        
        if resolution == "768P":
            base_credits = 5 * duration_int  # 5 credits per second
        else:  # 512P
            base_credits = 2 * duration_int  # 2 credits per second
    elif model_id == "hailuo/02-text-to-video-standard":
        # Hailuo 02 Standard text-to-video pricing:
        # 768P: 5 credits per second
        duration = params.get("duration", "6")
        duration_int = int(duration)
        base_credits = 5 * duration_int  # 5 credits per second for 768P
    elif model_id == "topaz/video-upscale":
        # Topaz Video Upscale pricing:
        # 12 credits per second
        # Note: Duration is determined by input video length
        # For pricing calculation, we'll use a default of 5 seconds as minimum
        default_duration = 5
        base_credits = 12 * default_duration  # 12 credits per second
    elif model_id == "kling/v1-avatar-standard":
        # Kling Avatar Standard pricing:
        # 8 credits per second for 720P
        # Up to 15 seconds per generation
        # For pricing calculation, we'll use a default of 5 seconds as minimum
        default_duration = 5
        base_credits = 8 * default_duration  # 8 credits per second for 720P
    elif model_id == "kling/ai-avatar-v1-pro":
        # Kling Avatar Pro pricing:
        # 16 credits per second for 1080P
        # Up to 15 seconds per generation
        # For pricing calculation, we'll use a default of 5 seconds as minimum
        default_duration = 5
        base_credits = 16 * default_duration  # 16 credits per second for 1080P
    elif model_id == "bytedance/seedream-v4-text-to-image" or model_id == "bytedance/seedream-v4-edit":
        # Seedream V4 pricing:
        # 5 credits per image
        # Price is independent of resolution, determined by number of images returned
        max_images = params.get("max_images", 1) if params else 1
        base_credits = 5 * max_images  # 5 credits per image
    elif model_id == "infinitalk/from-audio":
        # InfiniteTalk pricing:
        # 480P: 3 credits per second
        # 720P: 12 credits per second
        # Up to 15 seconds per generation
        # For pricing calculation, we'll use a default of 5 seconds as minimum
        resolution = params.get("resolution", "480p")
        default_duration = 5
        
        if resolution == "720p":
            base_credits = 12 * default_duration  # 12 credits per second
        else:  # 480p
            base_credits = 3 * default_duration  # 3 credits per second
    elif model_id == "recraft/remove-background":
        # Recraft Remove Background pricing:
        # 1 credit per image
        base_credits = 1
    elif model_id == "recraft/crisp-upscale":
        # Recraft Crisp Upscale pricing:
        # 0.5 credits per upscale
        base_credits = 0.5
    elif model_id == "ideogram/v3-reframe" or model_id == "ideogram/v3-text-to-image" or model_id == "ideogram/v3-edit" or model_id == "ideogram/v3-remix":
        # Ideogram V3 pricing (same for all variants):
        # TURBO: 3.5 credits per image
        # BALANCED: 7 credits per image
        # QUALITY: 10 credits per image
        rendering_speed = params.get("rendering_speed", "BALANCED") if params else "BALANCED"
        num_images = int(params.get("num_images", "1")) if params else 1
        
        if rendering_speed == "TURBO":
            credits_per_image = 3.5
        elif rendering_speed == "QUALITY":
            credits_per_image = 10
        else:  # BALANCED
            credits_per_image = 7
        
        base_credits = credits_per_image * num_images
    elif model_id == "wan/2-2-a14b-speech-to-video-turbo":
        # WAN 2.2 Speech-to-Video pricing:
        # 480P: 12 credits per second
        # 580P: 18 credits per second
        # 720P: 24 credits per second
        # Note: Duration is determined by audio length
        # For pricing calculation, we'll use a default of 5 seconds as minimum
        resolution = params.get("resolution", "480p")
        default_duration = 5
        
        if resolution == "720p":
            base_credits = 24 * default_duration  # 24 credits per second
        elif resolution == "580p":
            base_credits = 18 * default_duration  # 18 credits per second
        else:  # 480p
            base_credits = 12 * default_duration  # 12 credits per second
    elif model_id == "wan/2-2-a14b-text-to-video-turbo" or model_id == "wan/2-2-a14b-image-to-video-turbo":
        # WAN 2.2 A14B Turbo pricing:
        # 480p: 8 credits per second
        # 580p: 12 credits per second
        # 720p: 16 credits per second
        # For pricing calculation, we'll use a default of 5 seconds as minimum
        resolution = params.get("resolution", "720p") if params else "720p"
        default_duration = 5
        
        if resolution == "720p":
            base_credits = 16 * default_duration  # 16 credits per second
        elif resolution == "580p":
            base_credits = 12 * default_duration  # 12 credits per second
        else:  # 480p
            base_credits = 8 * default_duration  # 8 credits per second
    elif model_id == "bytedance/seedream":
        # Seedream 3.0 pricing:
        # 3.5 credits per image
        base_credits = 3.5
    elif model_id == "qwen/text-to-image":
        # Qwen Image pricing:
        # 4 credits per megapixel
        # Need to calculate megapixels based on image_size
        # Approximate resolutions:
        # square: 512x512 = 0.26 MP
        # square_hd: 1024x1024 = 1.05 MP
        # portrait_4_3: 768x1024 = 0.79 MP
        # portrait_16_9: 1024x1792 = 1.84 MP
        # landscape_4_3: 1024x768 = 0.79 MP
        # landscape_16_9: 1792x1024 = 1.84 MP
        image_size = params.get("image_size", "square_hd") if params else "square_hd"
        
        # Calculate megapixels based on image size
        mp_map = {
            "square": 0.26,  # 512x512
            "square_hd": 1.05,  # 1024x1024
            "portrait_4_3": 0.79,  # 768x1024
            "portrait_16_9": 1.84,  # 1024x1792
            "landscape_4_3": 0.79,  # 1024x768
            "landscape_16_9": 1.84  # 1792x1024
        }
        
        megapixels = mp_map.get(image_size, 1.05)  # Default to square_hd
        base_credits = 4 * megapixels  # 4 credits per megapixel
    elif model_id == "qwen/image-to-image":
        # Qwen Image-to-Image pricing:
        # 4 credits per image
        base_credits = 4
    elif model_id == "qwen/image-edit":
        # Qwen Image Edit pricing:
        # ≈ $0.03 per megapixel, depending on image aspect ratio
        # Need to calculate megapixels based on image_size
        # Use same mapping as qwen/text-to-image
        image_size = params.get("image_size", "landscape_4_3") if params else "landscape_4_3"
        num_images = int(params.get("num_images", "1")) if params else 1
        
        # Calculate megapixels based on image size (same as qwen/text-to-image)
        mp_map = {
            "square": 0.26,  # 512x512
            "square_hd": 1.05,  # 1024x1024
            "portrait_4_3": 0.79,  # 768x1024
            "portrait_16_9": 1.84,  # 1024x1792
            "landscape_4_3": 0.79,  # 1024x768
            "landscape_16_9": 1.84  # 1792x1024
        }
        
        megapixels = mp_map.get(image_size, 0.79)  # Default to landscape_4_3
        # $0.03 per MP ≈ 6 credits per MP (assuming $0.005 per credit)
        base_credits = 6 * megapixels * num_images
    elif model_id == "google/imagen4-ultra":
        # Google Imagen 4 Ultra pricing:
        # 12 credits per image
        base_credits = 12
    elif model_id == "google/imagen4-fast":
        # Google Imagen 4 Fast pricing:
        # 4 credits per image
        num_images = int(params.get("num_images", "1")) if params else 1
        base_credits = 4 * num_images
    elif model_id == "google/imagen4":
        # Google Imagen 4 pricing:
        # 8 credits per image
        num_images = int(params.get("num_images", "1")) if params else 1
        base_credits = 8 * num_images
    elif model_id == "ideogram/character-edit" or model_id == "ideogram/character-remix" or model_id == "ideogram/character":
        # Ideogram Character pricing (same for edit, remix, and base):
        # TURBO: 12 credits
        # BALANCED: 18 credits
        # QUALITY: 24 credits
        rendering_speed = params.get("rendering_speed", "BALANCED") if params else "BALANCED"
        num_images = int(params.get("num_images", "1")) if params else 1
        
        if rendering_speed == "TURBO":
            credits_per_image = 12
        elif rendering_speed == "QUALITY":
            credits_per_image = 24
        else:  # BALANCED
            credits_per_image = 18
        
        base_credits = credits_per_image * num_images
    elif model_id == "flux-2/pro-image-to-image" or model_id == "flux-2/pro-text-to-image":
        # Flux 2 Pro pricing (same for both image-to-image and text-to-image):
        # 1K: 5 credits
        # 2K: 7 credits
        resolution = params.get("resolution", "1K")
        if resolution == "2K":
            base_credits = 7
        else:  # 1K
            base_credits = 5
    elif model_id == "flux-2/flex-image-to-image" or model_id == "flux-2/flex-text-to-image":
        # Flux 2 Flex pricing (same for both image-to-image and text-to-image):
        # 1K: 14 credits
        # 2K: 24 credits
        resolution = params.get("resolution", "1K")
        if resolution == "2K":
            base_credits = 24
        else:  # 1K
            base_credits = 14
    elif model_id == "topaz/image-upscale":
        # Topaz Image Upscale pricing:
        # 1x (≤2K): 10 credits
        # 2x/4x (4K): 20 credits
        # 8x (8K): 40 credits
        upscale_factor = params.get("upscale_factor", "2")
        if upscale_factor == "8":
            base_credits = 40  # 8K
        elif upscale_factor in ["2", "4"]:
            base_credits = 20  # 4K
        else:  # upscale_factor == "1"
            base_credits = 10  # ≤2K
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
        price = calculate_price_rub(model_id, params, is_admin)
        if not is_admin and user_id is not None:
            # Check if user has free generations available
            remaining = get_user_free_generations_remaining(user_id)
            if remaining > 0:
                price_str = f"{round(price, 2):.2f}"
                return f"🎁 <b>БЕСПЛАТНО</b> ({remaining}/{FREE_GENERATIONS_PER_DAY} в день) или {price_str} ₽"
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
    elif model_id == "kling-2.6/image-to-video" or model_id == "kling-2.6/text-to-video":
        # Show price range based on duration and sound
        duration = params.get("duration", "5") if params else "5"
        sound = params.get("sound", False) if params else False
        
        if duration == "5":
            if sound:
                price = calculate_price_rub(model_id, {"duration": "5", "sound": True}, is_admin)
                return format_price_rub(price, is_admin) + " за 5с видео (со звуком)"
            else:
                price = calculate_price_rub(model_id, {"duration": "5", "sound": False}, is_admin)
                return format_price_rub(price, is_admin) + " за 5с видео (без звука)"
        else:  # duration == "10"
            if sound:
                price = calculate_price_rub(model_id, {"duration": "10", "sound": True}, is_admin)
                return format_price_rub(price, is_admin) + " за 10с видео (со звуком)"
            else:
                price = calculate_price_rub(model_id, {"duration": "10", "sound": False}, is_admin)
                return format_price_rub(price, is_admin) + " за 10с видео (без звука)"
    elif model_id == "kling/v2-5-turbo-text-to-video-pro" or model_id == "kling/v2-5-turbo-image-to-video-pro":
        # Show price based on duration
        duration = params.get("duration", "5") if params else "5"
        price_5s = calculate_price_rub(model_id, {"duration": "5"}, is_admin)
        price_10s = calculate_price_rub(model_id, {"duration": "10"}, is_admin)
        price_5s_str = f"{round(price_5s, 2):.2f}"
        price_10s_str = f"{round(price_10s, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (5с: {price_5s_str} ₽, 10с: {price_10s_str} ₽)"
        else:
            return f"💰 <b>От {price_5s_str} ₽</b> (5с: {price_5s_str} ₽, 10с: {price_10s_str} ₽)"
    elif model_id == "wan/2-5-image-to-video" or model_id == "wan/2-5-text-to-video":
        # Show price based on duration and resolution
        duration = params.get("duration", "5") if params else "5"
        resolution = params.get("resolution", "720p") if params else "720p"
        price_720p_5s = calculate_price_rub(model_id, {"duration": "5", "resolution": "720p"}, is_admin)
        price_1080p_5s = calculate_price_rub(model_id, {"duration": "5", "resolution": "1080p"}, is_admin)
        price_720p_10s = calculate_price_rub(model_id, {"duration": "10", "resolution": "720p"}, is_admin)
        price_1080p_10s = calculate_price_rub(model_id, {"duration": "10", "resolution": "1080p"}, is_admin)
        price_720p_5s_str = f"{round(price_720p_5s, 2):.2f}"
        price_1080p_5s_str = f"{round(price_1080p_5s, 2):.2f}"
        price_720p_10s_str = f"{round(price_720p_10s, 2):.2f}"
        price_1080p_10s_str = f"{round(price_1080p_10s, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (720p: {price_720p_5s_str}₽/5с, {price_720p_10s_str}₽/10с | 1080p: {price_1080p_5s_str}₽/5с, {price_1080p_10s_str}₽/10с)"
        else:
            return f"💰 <b>От {price_720p_5s_str} ₽</b> (720p: {price_720p_5s_str}₽/5с, {price_720p_10s_str}₽/10с | 1080p: {price_1080p_5s_str}₽/5с, {price_1080p_10s_str}₽/10с)"
    elif model_id == "wan/2-2-animate-move" or model_id == "wan/2-2-animate-replace":
        # Show price based on resolution
        resolution = params.get("resolution", "480p") if params else "480p"
        price_480p = calculate_price_rub(model_id, {"resolution": "480p"}, is_admin)
        price_580p = calculate_price_rub(model_id, {"resolution": "580p"}, is_admin)
        price_720p = calculate_price_rub(model_id, {"resolution": "720p"}, is_admin)
        price_480p_str = f"{round(price_480p, 2):.2f}"
        price_580p_str = f"{round(price_580p, 2):.2f}"
        price_720p_str = f"{round(price_720p, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (480p: {price_480p_str}₽/5с, 580p: {price_580p_str}₽/5с, 720p: {price_720p_str}₽/5с)"
        else:
            return f"💰 <b>От {price_480p_str} ₽</b> (480p: {price_480p_str}₽/5с, 580p: {price_580p_str}₽/5с, 720p: {price_720p_str}₽/5с)"
    elif model_id == "hailuo/02-text-to-video-pro" or model_id == "hailuo/02-image-to-video-pro":
        # Show fixed price for 6-second 1080p video
        price = calculate_price_rub(model_id, params, is_admin)
        price_str = f"{round(price, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> ({price_str} ₽ за 6с 1080p видео)"
        else:
            return f"💰 <b>{price_str} ₽</b> за 6с 1080p видео"
    elif model_id == "hailuo/02-image-to-video-standard":
        # Show price based on resolution and duration
        resolution = params.get("resolution", "768P") if params else "768P"
        duration = params.get("duration", "6") if params else "6"
        price_512p_6s = calculate_price_rub(model_id, {"resolution": "512P", "duration": "6"}, is_admin)
        price_768p_6s = calculate_price_rub(model_id, {"resolution": "768P", "duration": "6"}, is_admin)
        price_512p_10s = calculate_price_rub(model_id, {"resolution": "512P", "duration": "10"}, is_admin)
        price_768p_10s = calculate_price_rub(model_id, {"resolution": "768P", "duration": "10"}, is_admin)
        price_512p_6s_str = f"{round(price_512p_6s, 2):.2f}"
        price_768p_6s_str = f"{round(price_768p_6s, 2):.2f}"
        price_512p_10s_str = f"{round(price_512p_10s, 2):.2f}"
        price_768p_10s_str = f"{round(price_768p_10s, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (512P: {price_512p_6s_str}₽/6с, {price_512p_10s_str}₽/10с | 768P: {price_768p_6s_str}₽/6с, {price_768p_10s_str}₽/10с)"
        else:
            return f"💰 <b>От {price_512p_6s_str} ₽</b> (512P: {price_512p_6s_str}₽/6с, {price_512p_10s_str}₽/10с | 768P: {price_768p_6s_str}₽/6с, {price_768p_10s_str}₽/10с)"
    elif model_id == "hailuo/02-text-to-video-standard":
        # Show price based on duration (fixed 768P)
        duration = params.get("duration", "6") if params else "6"
        price_6s = calculate_price_rub(model_id, {"duration": "6"}, is_admin)
        price_10s = calculate_price_rub(model_id, {"duration": "10"}, is_admin)
        price_6s_str = f"{round(price_6s, 2):.2f}"
        price_10s_str = f"{round(price_10s, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (768P: {price_6s_str}₽/6с, {price_10s_str}₽/10с)"
        else:
            return f"💰 <b>От {price_6s_str} ₽</b> (768P: {price_6s_str}₽/6с, {price_10s_str}₽/10с)"
    elif model_id == "topaz/video-upscale":
        # Show price per second
        price_per_sec = calculate_price_rub(model_id, {}, is_admin) / 5  # Divide by default 5 seconds
        price_per_sec_str = f"{round(price_per_sec, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> ({price_per_sec_str} ₽/сек)"
        else:
            return f"💰 <b>{price_per_sec_str} ₽/сек</b>"
    elif model_id == "kling/v1-avatar-standard":
        # Show price per second for 720P
        price_per_sec = calculate_price_rub(model_id, {}, is_admin) / 5  # Divide by default 5 seconds
        price_per_sec_str = f"{round(price_per_sec, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> ({price_per_sec_str} ₽/сек, 720P, до 15с)"
        else:
            return f"💰 <b>{price_per_sec_str} ₽/сек</b> (720P, до 15с)"
    elif model_id == "kling/ai-avatar-v1-pro":
        # Show price per second for 1080P
        price_per_sec = calculate_price_rub(model_id, {}, is_admin) / 5  # Divide by default 5 seconds
        price_per_sec_str = f"{round(price_per_sec, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> ({price_per_sec_str} ₽/сек, 1080P, до 15с)"
        else:
            return f"💰 <b>{price_per_sec_str} ₽/сек</b> (1080P, до 15с)"
    elif model_id == "bytedance/seedream-v4-text-to-image" or model_id == "bytedance/seedream-v4-edit":
        # Show price per image
        max_images = params.get("max_images", 1) if params else 1
        price_per_image = calculate_price_rub(model_id, {"max_images": 1}, is_admin)
        price_total = calculate_price_rub(model_id, {"max_images": max_images}, is_admin)
        price_per_image_str = f"{round(price_per_image, 2):.2f}"
        price_total_str = f"{round(price_total, 2):.2f}"
        if is_admin:
            if max_images > 1:
                return f"💰 <b>Безлимит</b> ({price_per_image_str} ₽/изображение, до {max_images} изображений = {price_total_str} ₽)"
            else:
                return f"💰 <b>Безлимит</b> ({price_per_image_str} ₽/изображение)"
        else:
            if max_images > 1:
                return f"💰 <b>{price_per_image_str} ₽/изображение</b> (до {max_images} изображений = {price_total_str} ₽)"
            else:
                return f"💰 <b>{price_per_image_str} ₽/изображение</b>"
    elif model_id == "infinitalk/from-audio":
        # Show price per second based on resolution
        resolution = params.get("resolution", "480p") if params else "480p"
        price_per_sec_480p = calculate_price_rub(model_id, {"resolution": "480p"}, is_admin) / 5
        price_per_sec_720p = calculate_price_rub(model_id, {"resolution": "720p"}, is_admin) / 5
        price_per_sec_480p_str = f"{round(price_per_sec_480p, 2):.2f}"
        price_per_sec_720p_str = f"{round(price_per_sec_720p, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (480P: {price_per_sec_480p_str}₽/сек, 720P: {price_per_sec_720p_str}₽/сек, до 15с)"
        else:
            return f"💰 <b>От {price_per_sec_480p_str} ₽/сек</b> (480P: {price_per_sec_480p_str}₽/сек, 720P: {price_per_sec_720p_str}₽/сек, до 15с)"
    elif model_id == "recraft/remove-background":
        # Show fixed price per image
        price = calculate_price_rub(model_id, {}, is_admin)
        price_str = f"{round(price, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> ({price_str} ₽ за изображение)"
        else:
            return f"💰 <b>{price_str} ₽</b> за изображение"
    elif model_id == "recraft/crisp-upscale":
        # Show fixed price per upscale
        price = calculate_price_rub(model_id, {}, is_admin)
        price_str = f"{round(price, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> ({price_str} ₽ за апскейл)"
        else:
            return f"💰 <b>{price_str} ₽</b> за апскейл"
    elif model_id == "ideogram/v3-reframe" or model_id == "ideogram/v3-text-to-image" or model_id == "ideogram/v3-edit" or model_id == "ideogram/v3-remix":
        # Show price based on rendering speed (same for all Ideogram V3 models)
        rendering_speed = params.get("rendering_speed", "BALANCED") if params else "BALANCED"
        price_turbo = calculate_price_rub(model_id, {"rendering_speed": "TURBO", "num_images": "1"}, is_admin)
        price_balanced = calculate_price_rub(model_id, {"rendering_speed": "BALANCED", "num_images": "1"}, is_admin)
        price_quality = calculate_price_rub(model_id, {"rendering_speed": "QUALITY", "num_images": "1"}, is_admin)
        price_turbo_str = f"{round(price_turbo, 2):.2f}"
        price_balanced_str = f"{round(price_balanced, 2):.2f}"
        price_quality_str = f"{round(price_quality, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (Turbo: {price_turbo_str}₽, Balanced: {price_balanced_str}₽, Quality: {price_quality_str}₽)"
        else:
            return f"💰 <b>От {price_turbo_str} ₽</b> (Turbo: {price_turbo_str}₽, Balanced: {price_balanced_str}₽, Quality: {price_quality_str}₽)"
    elif model_id == "wan/2-2-a14b-speech-to-video-turbo":
        # Show price per second based on resolution
        resolution = params.get("resolution", "480p") if params else "480p"
        price_per_sec_480p = calculate_price_rub(model_id, {"resolution": "480p"}, is_admin) / 5
        price_per_sec_580p = calculate_price_rub(model_id, {"resolution": "580p"}, is_admin) / 5
        price_per_sec_720p = calculate_price_rub(model_id, {"resolution": "720p"}, is_admin) / 5
        price_per_sec_480p_str = f"{round(price_per_sec_480p, 2):.2f}"
        price_per_sec_580p_str = f"{round(price_per_sec_580p, 2):.2f}"
        price_per_sec_720p_str = f"{round(price_per_sec_720p, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (480P: {price_per_sec_480p_str}₽/сек, 580P: {price_per_sec_580p_str}₽/сек, 720P: {price_per_sec_720p_str}₽/сек)"
        else:
            return f"💰 <b>От {price_per_sec_480p_str} ₽/сек</b> (480P: {price_per_sec_480p_str}₽/сек, 580P: {price_per_sec_580p_str}₽/сек, 720P: {price_per_sec_720p_str}₽/сек)"
    elif model_id == "bytedance/seedream":
        # Show fixed price per image
        price = calculate_price_rub(model_id, {}, is_admin)
        price_str = f"{round(price, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> ({price_str} ₽ за изображение)"
        else:
            return f"💰 <b>{price_str} ₽</b> за изображение"
    elif model_id == "qwen/text-to-image":
        # Show price range based on image size (megapixels)
        price_square = calculate_price_rub(model_id, {"image_size": "square"}, is_admin)
        price_square_hd = calculate_price_rub(model_id, {"image_size": "square_hd"}, is_admin)
        price_portrait = calculate_price_rub(model_id, {"image_size": "portrait_16_9"}, is_admin)
        price_square_str = f"{round(price_square, 2):.2f}"
        price_square_hd_str = f"{round(price_square_hd, 2):.2f}"
        price_portrait_str = f"{round(price_portrait, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (от {price_square_str}₽, зависит от разрешения: 4 кредита/МП)"
        else:
            return f"💰 <b>От {price_square_str} ₽</b> (зависит от разрешения: 4 кредита/МП)"
    elif model_id == "qwen/image-to-image":
        # Show fixed price per image
        price = calculate_price_rub(model_id, {}, is_admin)
        price_str = f"{round(price, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> ({price_str} ₽ за изображение)"
        else:
            return f"💰 <b>{price_str} ₽</b> за изображение"
    elif model_id == "qwen/image-edit":
        # Show price range based on image size (megapixels)
        price_square = calculate_price_rub(model_id, {"image_size": "square", "num_images": "1"}, is_admin)
        price_landscape = calculate_price_rub(model_id, {"image_size": "landscape_4_3", "num_images": "1"}, is_admin)
        price_portrait = calculate_price_rub(model_id, {"image_size": "portrait_16_9", "num_images": "1"}, is_admin)
        price_square_str = f"{round(price_square, 2):.2f}"
        price_landscape_str = f"{round(price_landscape, 2):.2f}"
        price_portrait_str = f"{round(price_portrait, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (от {price_square_str}₽, зависит от разрешения: ≈6 кредитов/МП)"
        else:
            return f"💰 <b>От {price_square_str} ₽</b> (зависит от разрешения: ≈6 кредитов/МП)"
    elif model_id == "ideogram/character-edit" or model_id == "ideogram/character-remix" or model_id == "ideogram/character":
        # Show price based on rendering speed
        rendering_speed = params.get("rendering_speed", "BALANCED") if params else "BALANCED"
        price_turbo = calculate_price_rub(model_id, {"rendering_speed": "TURBO", "num_images": "1"}, is_admin)
        price_balanced = calculate_price_rub(model_id, {"rendering_speed": "BALANCED", "num_images": "1"}, is_admin)
        price_quality = calculate_price_rub(model_id, {"rendering_speed": "QUALITY", "num_images": "1"}, is_admin)
        price_turbo_str = f"{round(price_turbo, 2):.2f}"
        price_balanced_str = f"{round(price_balanced, 2):.2f}"
        price_quality_str = f"{round(price_quality, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (Turbo: {price_turbo_str}₽, Balanced: {price_balanced_str}₽, Quality: {price_quality_str}₽)"
        else:
            return f"💰 <b>От {price_turbo_str} ₽</b> (Turbo: {price_turbo_str}₽, Balanced: {price_balanced_str}₽, Quality: {price_quality_str}₽)"
    elif model_id == "flux-2/pro-image-to-image" or model_id == "flux-2/pro-text-to-image":
        # Show price based on resolution
        resolution = params.get("resolution", "1K") if params else "1K"
        price_1k = calculate_price_rub(model_id, {"resolution": "1K"}, is_admin)
        price_2k = calculate_price_rub(model_id, {"resolution": "2K"}, is_admin)
        price_1k_str = f"{round(price_1k, 2):.2f}"
        price_2k_str = f"{round(price_2k, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (1K: {price_1k_str} ₽, 2K: {price_2k_str} ₽)"
        else:
            return f"💰 <b>От {price_1k_str} ₽</b> (1K: {price_1k_str} ₽, 2K: {price_2k_str} ₽)"
    elif model_id == "flux-2/flex-image-to-image" or model_id == "flux-2/flex-text-to-image":
        # Show price based on resolution
        resolution = params.get("resolution", "1K") if params else "1K"
        price_1k = calculate_price_rub(model_id, {"resolution": "1K"}, is_admin)
        price_2k = calculate_price_rub(model_id, {"resolution": "2K"}, is_admin)
        price_1k_str = f"{round(price_1k, 2):.2f}"
        price_2k_str = f"{round(price_2k, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (1K: {price_1k_str} ₽, 2K: {price_2k_str} ₽)"
        else:
            return f"💰 <b>От {price_1k_str} ₽</b> (1K: {price_1k_str} ₽, 2K: {price_2k_str} ₽)"
    elif model_id == "topaz/image-upscale":
        # Show price based on upscale factor
        upscale_factor = params.get("upscale_factor", "2") if params else "2"
        price_1x = calculate_price_rub(model_id, {"upscale_factor": "1"}, is_admin)
        price_2x = calculate_price_rub(model_id, {"upscale_factor": "2"}, is_admin)
        price_8x = calculate_price_rub(model_id, {"upscale_factor": "8"}, is_admin)
        price_1x_str = f"{round(price_1x, 2):.2f}"
        price_2x_str = f"{round(price_2x, 2):.2f}"
        price_8x_str = f"{round(price_8x, 2):.2f}"
        if is_admin:
            return f"💰 <b>Безлимит</b> (1x: {price_1x_str} ₽, 2x/4x: {price_2x_str} ₽, 8x: {price_8x_str} ₽)"
        else:
            return f"💰 <b>От {price_1x_str} ₽</b> (1x: {price_1x_str} ₽, 2x/4x: {price_2x_str} ₽, 8x: {price_8x_str} ₽)"
    else:
        price = calculate_price_rub(model_id, params, is_admin)
        return format_price_rub(price, is_admin)

# Conversation states for model selection and parameter input
SELECTING_MODEL, INPUTTING_PARAMS, CONFIRMING_GENERATION = range(3)

# Payment states
SELECTING_AMOUNT, WAITING_PAYMENT_SCREENSHOT = range(3, 5)

# Admin test OCR state
ADMIN_TEST_OCR = 5

# Broadcast states
WAITING_BROADCAST_MESSAGE = 6

# Admin test OCR state
ADMIN_TEST_OCR = 5

# Store user sessions
user_sessions = {}

# Store saved generation data for "generate again" feature
saved_generations = {}

# Store saved generation data for "generate again" feature
saved_generations = {}

# Payment data files
BALANCES_FILE = "user_balances.json"
ADMIN_LIMITS_FILE = "admin_limits.json"  # File to store admins with spending limits
PAYMENTS_FILE = "payments.json"
BLOCKED_USERS_FILE = "blocked_users.json"
FREE_GENERATIONS_FILE = "daily_free_generations.json"  # File to store daily free generations
PROMOCODES_FILE = "promocodes.json"  # File to store promo codes
REFERRALS_FILE = "referrals.json"  # File to store referral data
BROADCASTS_FILE = "broadcasts.json"  # File to store broadcast statistics
GENERATIONS_HISTORY_FILE = "generations_history.json"  # File to store user generation history

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


# ==================== Free Generations System ====================

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


# ==================== Referral System ====================

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


def get_fake_online_count() -> int:
    """Generate dynamic fake online user count - changes every time it's called."""
    # Base number around 500
    base = 500
    # Random variation ±80 for more dynamic changes
    variation = random.randint(-80, 80)
    # Time-based variation (slight changes based on time of day)
    current_hour = time.localtime().tm_hour
    # More activity during day hours (9-22)
    if 9 <= current_hour <= 22:
        time_multiplier = random.randint(0, 50)
    else:
        time_multiplier = random.randint(-30, 20)
    
    # Add microsecond-based variation for more randomness
    microsecond_variation = random.randint(-20, 20)
    
    count = base + variation + time_multiplier + microsecond_variation
    # Ensure reasonable bounds (300-700 range)
    return max(300, min(700, count))


# ==================== Promocodes System ====================

def load_promocodes() -> list:
    """Load promocodes from file."""
    data = load_json_file(PROMOCODES_FILE, {})
    return data.get('promocodes', [])


def save_promocodes(promocodes: list):
    """Save promocodes to file."""
    data = {'promocodes': promocodes}
    save_json_file(PROMOCODES_FILE, data)


def get_active_promocode() -> dict:
    """Get the currently active promocode."""
    promocodes = load_promocodes()
    for promo in promocodes:
        if promo.get('active', False):
            return promo
    return None


# ==================== Broadcast System ====================

def get_all_users() -> list:
    """Get list of all user IDs from various sources."""
    user_ids = set()
    
    # From user balances
    balances = load_json_file(BALANCES_FILE, {})
    user_ids.update([int(uid) for uid in balances.keys() if uid.isdigit()])
    
    # From payments
    payments = load_json_file(PAYMENTS_FILE, {})
    for payment in payments.values():
        if 'user_id' in payment:
            user_ids.add(payment['user_id'])
    
    # From referrals
    referrals = get_referrals_data()
    for user_key in referrals.keys():
        if user_key.isdigit():
            user_ids.add(int(user_key))
        # Also get referred users
        referred_users = referrals.get(user_key, {}).get('referred_users', [])
        user_ids.update(referred_users)
    
    # From free generations
    free_gens = get_free_generations_data()
    for user_key in free_gens.keys():
        if user_key.isdigit():
            user_ids.add(int(user_key))
    
    return sorted(list(user_ids))


def save_broadcast(broadcast_data: dict):
    """Save broadcast statistics."""
    broadcasts = load_json_file(BROADCASTS_FILE, {})
    broadcast_id = broadcast_data.get('id', len(broadcasts) + 1)
    broadcasts[str(broadcast_id)] = broadcast_data
    save_json_file(BROADCASTS_FILE, broadcasts)
    return broadcast_id


def get_broadcasts() -> dict:
    """Get all broadcasts."""
    return load_json_file(BROADCASTS_FILE, {})


def get_broadcast(broadcast_id: int) -> dict:
    """Get specific broadcast by ID."""
    broadcasts = get_broadcasts()
    return broadcasts.get(str(broadcast_id), {})


# ==================== Generations History System ====================

def save_generation_to_history(user_id: int, model_id: str, model_name: str, params: dict, result_urls: list, task_id: str, price: float = 0.0, is_free: bool = False):
    """Save generation to user history."""
    import time
    history = load_json_file(GENERATIONS_HISTORY_FILE, {})
    user_key = str(user_id)
    
    if user_key not in history:
        history[user_key] = []
    
    generation_entry = {
        'id': len(history[user_key]) + 1,
        'timestamp': int(time.time()),
        'model_id': model_id,
        'model_name': model_name,
        'params': params.copy(),
        'result_urls': result_urls.copy(),
        'task_id': task_id,
        'price': price,
        'is_free': is_free
    }
    
    history[user_key].append(generation_entry)
    
    # Keep only last 100 generations per user
    if len(history[user_key]) > 100:
        history[user_key] = history[user_key][-100:]
    
    save_json_file(GENERATIONS_HISTORY_FILE, history)
    return generation_entry['id']


def get_user_generations_history(user_id: int, limit: int = 20) -> list:
    """Get user's generation history."""
    history = load_json_file(GENERATIONS_HISTORY_FILE, {})
    user_key = str(user_id)
    
    if user_key not in history:
        return []
    
    # Return last N generations, sorted by timestamp (newest first)
    user_history = history[user_key]
    user_history.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    return user_history[:limit]


def get_generation_by_id(user_id: int, generation_id: int) -> dict:
    """Get specific generation by ID."""
    history = load_json_file(GENERATIONS_HISTORY_FILE, {})
    user_key = str(user_id)
    
    if user_key not in history:
        return None
    
    for gen in history[user_key]:
        if gen.get('id') == generation_id:
            return gen
    
    return None


def is_new_user(user_id: int) -> bool:
    """Check if user is new (no balance, no history, no payments)."""
    # Check balance
    balance = get_user_balance(user_id)
    if balance > 0:
        return False
    
    # Check history
    history = get_user_generations_history(user_id, limit=1)
    if history:
        return False
    
    # Check payments
    payments = get_user_payments(user_id)
    if payments:
        return False
    
    return True


async def send_broadcast(context: ContextTypes.DEFAULT_TYPE, broadcast_id: int, user_ids: list, message_text: str = None, message_photo=None):
    """Send broadcast message to all users."""
    sent = 0
    delivered = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            # Skip blocked users
            if is_user_blocked(user_id):
                continue
            
            # Send message
            if message_photo:
                # Send photo with caption
                try:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=message_photo.file_id,
                        caption=message_text,
                        parse_mode='HTML'
                    )
                    delivered += 1
                except Exception as e:
                    logger.error(f"Error sending broadcast photo to {user_id}: {e}")
                    failed += 1
            else:
                # Send text message
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message_text,
                        parse_mode='HTML'
                    )
                    delivered += 1
                except Exception as e:
                    logger.error(f"Error sending broadcast message to {user_id}: {e}")
                    failed += 1
            
            sent += 1
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.05)  # 50ms delay between messages
            
        except Exception as e:
            logger.error(f"Error in broadcast to {user_id}: {e}")
            failed += 1
            sent += 1
    
    # Update broadcast statistics
    broadcasts = get_broadcasts()
    if str(broadcast_id) in broadcasts:
        broadcasts[str(broadcast_id)]['sent'] = sent
        broadcasts[str(broadcast_id)]['delivered'] = delivered
        broadcasts[str(broadcast_id)]['failed'] = failed
        save_json_file(BROADCASTS_FILE, broadcasts)
        
        # Notify admin
        try:
            admin_id = ADMIN_ID
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"✅ <b>Рассылка #{broadcast_id} завершена!</b>\n\n"
                    f"📊 <b>Статистика:</b>\n"
                    f"✅ Отправлено: {sent}\n"
                    f"📬 Доставлено: {delivered}\n"
                    f"❌ Ошибок: {failed}\n\n"
                    f"📈 <b>Успешность:</b> {(delivered/sent*100) if sent > 0 else 0:.1f}%"
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error notifying admin about broadcast: {e}")


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
    # Reload .env to ensure latest values are loaded
    # On Render, environment variables are set via dashboard, not .env file
    # But we still try to load .env for local development
    try:
        load_dotenv(override=True)
    except Exception as e:
        logger.debug(f"Could not reload .env: {e}")
    
    # Get from environment (works both for .env and Render Environment Variables)
    card_holder = os.getenv('PAYMENT_CARD_HOLDER', '').strip()
    phone = os.getenv('PAYMENT_PHONE', '').strip()
    bank = os.getenv('PAYMENT_BANK', '').strip()
    
    # Enhanced debug logging for troubleshooting
    logger.debug(f"Loading payment details - PAYMENT_PHONE: {'SET' if phone else 'NOT SET'}, PAYMENT_BANK: {'SET' if bank else 'NOT SET'}, PAYMENT_CARD_HOLDER: {'SET' if card_holder else 'NOT SET'}")
    
    # Check if any payment details are missing
    if not phone and not bank and not card_holder:
        logger.warning("Payment details not found in environment variables!")
        logger.warning("Make sure these environment variables are set in Render dashboard:")
        logger.warning("  - PAYMENT_PHONE")
        logger.warning("  - PAYMENT_BANK")
        logger.warning("  - PAYMENT_CARD_HOLDER")
        # Also log all environment variables that start with PAYMENT_ for debugging
        payment_env_vars = {k: v for k, v in os.environ.items() if k.startswith('PAYMENT_')}
        logger.debug(f"All PAYMENT_* environment variables: {payment_env_vars}")
    
    details = "💳 <b>Реквизиты для оплаты (СБП):</b>\n\n"
    
    if phone:
        details += f"📱 <b>Номер телефона:</b> <code>{phone}</code>\n"
    if bank:
        details += f"🏦 <b>Банк:</b> {bank}\n"
    if card_holder:
        details += f"👤 <b>Получатель:</b> {card_holder}\n"
    
    if not phone and not bank and not card_holder:
        details += "⚠️ <b>ВНИМАНИЕ: Реквизиты не настроены!</b>\n\n"
        details += "Администратору необходимо указать следующие переменные окружения:\n"
        details += "• <code>PAYMENT_PHONE</code> - номер телефона для СБП\n"
        details += "• <code>PAYMENT_BANK</code> - название банка\n"
        details += "• <code>PAYMENT_CARD_HOLDER</code> - имя получателя\n\n"
        details += "На Render: добавьте их в разделе Environment Variables\n"
        details += "Локально: добавьте в файл .env\n\n"
    
    details += "\n⚠️ <b>Важно:</b> После оплаты отправьте скриншот перевода в этот чат.\n\n"
    details += "✅ <b>Баланс начислится автоматически</b> после отправки скриншота."
    
    return details


def get_support_contact() -> str:
    """Get support contact information from .env (only Telegram)."""
    # Reload .env to ensure latest values are loaded
    # On Render, environment variables are set via dashboard, not .env file
    # But we still try to load .env for local development
    try:
        load_dotenv(override=True)
    except Exception as e:
        logger.debug(f"Could not reload .env: {e}")
    
    support_telegram = os.getenv('SUPPORT_TELEGRAM', '').strip()
    support_text = os.getenv('SUPPORT_TEXT', '').strip()
    
    # Enhanced debug logging for troubleshooting
    logger.debug(f"Loading support contact - SUPPORT_TELEGRAM: {'SET' if support_telegram else 'NOT SET'}, SUPPORT_TEXT: {'SET' if support_text else 'NOT SET'}")
    
    contact = "🆘 <b>Поддержка</b>\n\n"
    
    if support_text:
        contact += f"{support_text}\n\n"
    else:
        contact += "Если у вас возникли вопросы или проблемы, свяжитесь с нами:\n\n"
    
    if support_telegram:
        telegram_username = support_telegram.replace('@', '')
        contact += f"💬 <b>Telegram:</b> @{telegram_username}\n"
    else:
        logger.warning("Support contact not found in environment variables!")
        logger.warning("Make sure these environment variables are set in Render dashboard:")
        logger.warning("  - SUPPORT_TELEGRAM")
        logger.warning("  - SUPPORT_TEXT (optional)")
        # Also log all environment variables that start with SUPPORT_ for debugging
        support_env_vars = {k: v for k, v in os.environ.items() if k.startswith('SUPPORT_')}
        logger.debug(f"All SUPPORT_* environment variables: {support_env_vars}")
        contact += "⚠️ <b>Контактная информация не настроена.</b>\n\n"
        contact += "Администратору необходимо указать SUPPORT_TELEGRAM в файле .env или в настройках Render (Environment Variables).\n\n"
        contact += "Обратитесь к администратору."
    
    return contact


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
        
        # Improved validation with scoring system
        score = 0
        max_score = 4
        
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
        
        # Additional checks for better validation
        # Check for duplicate screenshots (by file_id if available)
        # This will be checked in the payment handler
        
        # Validation: Need at least 2.5 points (flexible but secure)
        # This means: (amount + keywords) OR (amount + phone) OR (amount perfect match)
        valid = score >= 2.5
        
        # Additional security: if no amount found at all, reject (unless OCR failed)
        if not all_found_amounts and not has_payment_keywords:
            valid = False
        
        # Additional check: if amount is found but way off, be more strict
        if amount_found and found_amount:
            diff_percent = abs(found_amount - expected_amount) / expected_amount if expected_amount > 0 else 1
            # If difference is more than 30%, require additional verification
            if diff_percent > 0.3:
                # Require both phone and keywords if amount is way off
                if not (phone_found and has_payment_keywords):
                    valid = False
        
        message_parts = []
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
    
    # Check if user is admin
    is_admin = (user_id == ADMIN_ID)
    
    # Get generation types and models count
    generation_types = get_generation_types()
    total_models = len(KIE_MODELS)
    
    # Both admin and regular users see the same menu, but admin gets additional "Admin Panel" button
    # Common menu for both admin and regular users
    remaining_free = get_user_free_generations_remaining(user_id)
    is_new = is_new_user(user_id)
    referral_link = get_user_referral_link(user_id)
    referrals_count = len(get_user_referrals(user_id))
    
    if is_new:
        # Enhanced marketing welcome for new users - максимальный акцент на бесплатный Z-Image
        online_count = get_fake_online_count()
        
        welcome_text = (
            f'🎉 <b>ПРИВЕТ, {user.mention_html()}!</b> 🎉\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'🔥 <b>У ТЕБЯ ЕСТЬ {remaining_free if remaining_free > 0 else FREE_GENERATIONS_PER_DAY} БЕСПЛАТНЫХ ГЕНЕРАЦИЙ!</b> 🔥\n\n'
            f'✨ <b>ПРЕМИУМ AI MARKETPLACE</b> ✨\n\n'
            f'🚀 <b>Что это за бот?</b>\n'
            f'• 📦 <b>{total_models} топовых нейросетей</b> в одном месте\n'
            f'• 🎯 <b>{len(generation_types)} типов генерации</b> контента\n'
            f'• 🌐 Прямой доступ БЕЗ VPN\n'
            f'• ⚡ Мгновенная генерация\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'✨ <b>Z-Image - САМАЯ КРУТАЯ НЕЙРОСЕТЬ ДЛЯ ИЗОБРАЖЕНИЙ!</b> ✨\n\n'
            f'💎 <b>Почему Z-Image?</b>\n'
            f'• 🎨 Профессиональное качество изображений\n'
            f'• ⚡ Мгновенная генерация (10-30 секунд)\n'
            f'• 🎯 Работает БЕЗ VPN\n'
            f'• 💰 <b>ПОЛНОСТЬЮ БЕСПЛАТНО для тебя!</b>\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'👥 <b>Сейчас в боте:</b> {online_count} человек онлайн\n\n'
            f'🚀 <b>ЧТО МОЖНО ДЕЛАТЬ:</b>\n'
            f'• 🎨 Создавать изображения из текста\n'
            f'• 🎬 Генерировать видео\n'
            f'• ✨ Редактировать и трансформировать контент\n'
            f'• 🎯 Все это БЕЗ VPN и по цене жвачки!\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'🏢 <b>ТОПОВЫЕ НЕЙРОСЕТИ 2025:</b>\n\n'
            f'🤖 OpenAI • Google • Black Forest Labs\n'
            f'🎬 ByteDance • Ideogram • Qwen\n'
            f'✨ Kling • Hailuo • Topaz\n'
            f'🎨 Recraft • Grok (xAI) • Wan\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'🎁 <b>КАК НАЧАТЬ?</b>\n\n'
            f'1️⃣ <b>Нажми кнопку "🎁 Генерировать бесплатно"</b> ниже\n'
            f'   → Создай свое первое изображение за 30 секунд!\n\n'
            f'2️⃣ <b>Напиши что хочешь увидеть</b> (например: "Кот в космосе")\n'
            f'   → Z-Image создаст это для тебя!\n\n'
            f'3️⃣ <b>Получи результат и наслаждайся!</b> 🎉\n\n'
            f'💡 <b>Пригласи друга → получи +{REFERRAL_BONUS_GENERATIONS} бесплатных генераций!</b>\n'
            f'🔗 <code>{referral_link}</code>\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'💰 <b>После бесплатных генераций:</b>\n'
            f'От 0.62 ₽ за изображение • От 3.86 ₽ за видео'
        )
    else:
        # Marketing welcome for existing users - акцент на бесплатный Z-Image
        online_count = get_fake_online_count()
        referral_bonus_text = ""
        if referrals_count > 0:
            referral_bonus_text = (
                f"\n🎁 <b>Отлично!</b> Ты пригласил <b>{referrals_count}</b> друзей\n"
                f"   → Получено <b>+{referrals_count * REFERRAL_BONUS_GENERATIONS} бесплатных генераций</b>! 🎉\n\n"
            )
        
        welcome_text = (
            f'👋 <b>С возвращением, {user.mention_html()}!</b> 🤖✨\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'👥 <b>Сейчас в боте:</b> {online_count} человек онлайн\n\n'
        )
        
        if remaining_free > 0:
            welcome_text += (
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                f'🔥 <b>У ТЕБЯ ЕСТЬ {remaining_free} БЕСПЛАТНЫХ ГЕНЕРАЦИЙ!</b> 🔥\n\n'
                f'✨ <b>ПРЕМИУМ AI MARKETPLACE</b> ✨\n\n'
                f'🚀 <b>Что это за бот?</b>\n'
                f'• 📦 <b>{total_models} топовых нейросетей</b> в одном месте\n'
                f'• 🎯 <b>{len(generation_types)} типов генерации</b> контента\n'
                f'• 🌐 Прямой доступ БЕЗ VPN\n'
                f'• ⚡ Мгновенная генерация\n\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                f'✨ <b>Z-Image - САМАЯ КРУТАЯ НЕЙРОСЕТЬ ДЛЯ ИЗОБРАЖЕНИЙ!</b> ✨\n\n'
                f'💎 <b>Почему Z-Image?</b>\n'
                f'• 🎨 Профессиональное качество изображений\n'
                f'• ⚡ Мгновенная генерация (10-30 секунд)\n'
                f'• 🎯 Работает БЕЗ VPN\n'
                f'• 💰 <b>ПОЛНОСТЬЮ БЕСПЛАТНО для тебя!</b>\n\n'
                f'💡 <b>Нажми кнопку "🎁 Генерировать бесплатно" ниже</b>\n\n'
            )
        
        welcome_text += (
            f'{referral_bonus_text}'
            f'💎 <b>ДОСТУПНО:</b>\n'
            f'• {len(generation_types)} типов генерации\n'
            f'• {total_models} топовых нейросетей\n'
            f'• Без VPN, прямо здесь!\n\n'
            f'💰 <b>После бесплатных генераций:</b>\n'
            f'От 0.62 ₽ за изображение • От 3.86 ₽ за видео\n\n'
            f'💡 <b>Пригласи друга → получи +{REFERRAL_BONUS_GENERATIONS} бесплатных генераций!</b>\n'
            f'🔗 <code>{referral_link}</code>\n\n'
            f'🎯 <b>Выбери формат генерации ниже или начни с бесплатной!</b>'
        )
    
    # Common keyboard for both admin and regular users
    keyboard = []
    
    # Free generation button (ALWAYS prominent - biggest button)
    if remaining_free > 0:
        keyboard.append([
            InlineKeyboardButton(f"🎁 ГЕНЕРИРОВАТЬ БЕСПЛАТНО ({remaining_free} осталось)", callback_data="select_model:z-image")
        ])
        keyboard.append([])  # Empty row for spacing
    
    # Generation types buttons (compact, 2 per row)
    gen_type_rows = []
    for i, gen_type in enumerate(generation_types):
        gen_info = get_generation_type_info(gen_type)
        models_count = len(get_models_by_generation_type(gen_type))
        button_text = f"{gen_info.get('name', gen_type)} ({models_count})"
        
        if i % 2 == 0:
            gen_type_rows.append([InlineKeyboardButton(
                button_text,
                callback_data=f"gen_type:{gen_type}"
            )])
        else:
            if gen_type_rows:
                gen_type_rows[-1].append(InlineKeyboardButton(
                    button_text,
                    callback_data=f"gen_type:{gen_type}"
                ))
            else:
                gen_type_rows.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f"gen_type:{gen_type}"
                )])
    
    keyboard.extend(gen_type_rows)
    
    # Bottom action buttons
    keyboard.append([])  # Empty row for spacing
    keyboard.append([
        InlineKeyboardButton("💰 Баланс", callback_data="check_balance"),
        InlineKeyboardButton("📚 Мои генерации", callback_data="my_generations")
    ])
    keyboard.append([
        InlineKeyboardButton("💳 Пополнить", callback_data="topup_balance"),
        InlineKeyboardButton("🎁 Пригласить друга", callback_data="referral_info")
    ])
    
    # Add tutorial button for new users
    if is_new:
        keyboard.append([
            InlineKeyboardButton("❓ Как это работает?", callback_data="tutorial_start")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🆘 Помощь", callback_data="help_menu"),
        InlineKeyboardButton("💬 Поддержка", callback_data="support_contact")
    ])
    
    # Add admin panel button ONLY for admin (at the end)
    if is_admin:
        keyboard.append([])  # Empty row for admin section
        keyboard.append([
            InlineKeyboardButton("👑 АДМИН ПАНЕЛЬ", callback_data="admin_stats")
        ])
    
    await update.message.reply_html(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        '📋 <b>Доступные команды:</b>\n\n'
        '/start - Начать работу с ботом\n'
        '/models - Показать список доступных моделей\n'
        '/generate - Начать генерацию контента\n'
        '/balance - Проверить баланс\n'
        '/cancel - Отменить текущую операцию\n'
        '/search [запрос] - Поиск в базе знаний\n'
        '/ask [вопрос] - Задать вопрос\n'
        '/add [знание] - Добавить знание в базу\n\n'
        '💡 <b>Как использовать:</b>\n'
        '1. Используйте /models чтобы увидеть доступные модели\n'
        '2. Используйте /balance чтобы проверить баланс\n'
        '3. Используйте /generate чтобы начать генерацию\n'
        '4. Выберите модель из списка\n'
        '5. Введите необходимые параметры\n'
        '6. Получите результат!',
        parse_mode='HTML'
    )


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
    global kie
    user_id = update.effective_user.id
    
    # Check if KIE API is configured (initialize if needed)
    if kie is None:
        kie = get_client()
    if not kie.api_key:
        await update.message.reply_text(
            '❌ API не настроен. Укажите API ключ в файле .env'
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
    try:
        query = update.callback_query
        if not query:
            logger.error("No callback_query in update")
            return ConversationHandler.END
        
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if not data:
            logger.error("No data in callback_query")
            try:
                await query.answer("Ошибка: нет данных в запросе", show_alert=True)
            except:
                pass
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in button_callback setup: {e}", exc_info=True)
        return ConversationHandler.END
    
    # Wrap all callback handling in try-except for error handling
    try:
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
                
                remaining_free = get_user_free_generations_remaining(user_id)
                free_info = ""
                if remaining_free > 0:
                    free_info = f"\n🎁 <b>Бесплатно:</b> {remaining_free} генераций Z-Image\n"
                
                welcome_text = (
                    f'✨ <b>ПРЕМИУМ AI MARKETPLACE</b> ✨\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'👋 Привет, {user.mention_html()}!\n\n'
                    f'🚀 <b>Топовые нейросети без VPN</b>\n'
                    f'📦 <b>{total_models} моделей</b> | <b>{len(categories)} категорий</b>{free_info}\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'💎 <b>Преимущества:</b>\n'
                    f'• Прямой доступ к мировым AI\n'
                    f'• Профессиональное качество 2K/4K\n'
                    f'• Мгновенная генерация\n\n'
                    f'🎯 <b>Выберите категорию или все модели</b>'
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
                # Switching back to admin mode - send new message with full admin panel
                user_sessions[user_id]['admin_user_mode'] = False
                await query.answer("Возврат в админ-панель")
                user = update.effective_user
                generation_types = get_generation_types()
                total_models = len(KIE_MODELS)
                
                welcome_text = (
                    f'👑 ✨ <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b> ✨\n\n'
                    f'Привет, {user.mention_html()}! 👋\n\n'
                    f'🎯 <b>ПОЛНЫЙ КОНТРОЛЬ НАД AI MARKETPLACE</b>\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'📊 <b>СТАТИСТИКА СИСТЕМЫ:</b>\n\n'
                    f'✅ <b>{total_models} премиум моделей</b> в арсенале\n'
                    f'✅ <b>{len(generation_types)} категорий</b> контента\n'
                    f'✅ Безлимитный доступ ко всем генерациям\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'🔥 <b>ТОПОВЫЕ МОДЕЛИ В СИСТЕМЕ:</b>\n\n'
                    f'🎨 <b>Google Imagen 4 Ultra</b> - Флагман от Google DeepMind\n'
                    f'   💰 Безлимит (цена: 4.63 ₽)\n'
                    f'   ⭐️ Максимальное качество для тестирования\n\n'
                    f'🍌 <b>Nano Banana Pro</b> - 4K от Google\n'
                    f'   💰 Безлимит (1K/2K: 6.95 ₽, 4K: 9.27 ₽)\n'
                    f'   🎯 Профессиональная генерация 2K/4K\n\n'
                    f'🎥 <b>Sora 2</b> - Видео от OpenAI\n'
                    f'   💰 Безлимит (цена: 11.58 ₽) за 10-секундное видео\n'
                    f'   🎬 Кинематографические видео с аудио\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'⚙️ <b>АДМИНИСТРАТИВНЫЕ ВОЗМОЖНОСТИ:</b>\n\n'
                    f'📈 Просмотр статистики и аналитики\n'
                    f'👥 Управление пользователями\n'
                    f'🎁 Управление промокодами\n'
                    f'🧪 Тестирование OCR системы\n'
                    f'💼 Полный контроль над ботом\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
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
                f'👑 <b>Панель администратора</b>\n\n'
                f'Привет, {user.mention_html()}! 👋\n\n'
                f'🚀 <b>Расширенное меню управления</b>\n\n'
                f'📊 <b>Статистика:</b>\n'
                f'✅ <b>{total_models} моделей</b> доступно\n'
                f'✅ <b>{len(categories)} категорий</b>\n\n'
                f'⚙️ <b>Административные функции доступны</b>'
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
            keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
            
            await query.message.reply_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "back_to_menu":
            # Return to start menu - recreate the same menu as /start
            try:
            user = update.effective_user
            user_id = user.id
            is_admin = (user_id == ADMIN_ID)
            
            generation_types = get_generation_types()
            total_models = len(KIE_MODELS)
            remaining_free = get_user_free_generations_remaining(user_id)
            is_new = is_new_user(user_id)
            referral_link = get_user_referral_link(user_id)
            referrals_count = len(get_user_referrals(user_id))
            
            if is_new:
                online_count = get_fake_online_count()
                welcome_text = (
                    f'🎉 <b>ПРИВЕТ, {user.mention_html()}!</b> 🎉\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'🔥 <b>У ТЕБЯ ЕСТЬ {remaining_free if remaining_free > 0 else FREE_GENERATIONS_PER_DAY} БЕСПЛАТНЫХ ГЕНЕРАЦИЙ!</b> 🔥\n\n'
                    f'✨ <b>ПРЕМИУМ AI MARKETPLACE</b> ✨\n\n'
                    f'🚀 <b>Что это за бот?</b>\n'
                    f'• 📦 <b>{total_models} топовых нейросетей</b> в одном месте\n'
                    f'• 🎯 <b>{len(generation_types)} типов генерации</b> контента\n'
                    f'• 🌐 Прямой доступ БЕЗ VPN\n'
                    f'• ⚡ Мгновенная генерация\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'✨ <b>Z-Image - САМАЯ КРУТАЯ НЕЙРОСЕТЬ ДЛЯ ИЗОБРАЖЕНИЙ!</b> ✨\n\n'
                    f'💎 <b>Почему Z-Image?</b>\n'
                    f'• 🎨 Профессиональное качество изображений\n'
                    f'• ⚡ Мгновенная генерация (10-30 секунд)\n'
                    f'• 🎯 Работает БЕЗ VPN\n'
                    f'• 💰 <b>ПОЛНОСТЬЮ БЕСПЛАТНО для тебя!</b>\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'👥 <b>Сейчас в боте:</b> {online_count} человек онлайн\n\n'
                    f'🚀 <b>ЧТО МОЖНО ДЕЛАТЬ:</b>\n'
                    f'• 🎨 Создавать изображения из текста\n'
                    f'• 🎬 Генерировать видео\n'
                    f'• ✨ Редактировать и трансформировать контент\n'
                    f'• 🎯 Все это БЕЗ VPN и по цене жвачки!\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'🏢 <b>ТОПОВЫЕ НЕЙРОСЕТИ 2025:</b>\n\n'
                    f'🤖 OpenAI • Google • Black Forest Labs\n'
                    f'🎬 ByteDance • Ideogram • Qwen\n'
                    f'✨ Kling • Hailuo • Topaz\n'
                    f'🎨 Recraft • Grok (xAI) • Wan\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'🎁 <b>КАК НАЧАТЬ?</b>\n\n'
                    f'1️⃣ <b>Нажми кнопку "🎁 Генерировать бесплатно"</b> ниже\n'
                    f'   → Создай свое первое изображение за 30 секунд!\n\n'
                    f'2️⃣ <b>Напиши что хочешь увидеть</b> (например: "Кот в космосе")\n'
                    f'   → Z-Image создаст это для тебя!\n\n'
                    f'3️⃣ <b>Получи результат и наслаждайся!</b> 🎉\n\n'
                    f'💡 <b>Пригласи друга → получи +{REFERRAL_BONUS_GENERATIONS} бесплатных генераций!</b>\n'
                    f'🔗 <code>{referral_link}</code>\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'💰 <b>После бесплатных генераций:</b>\n'
                    f'От 0.62 ₽ за изображение • От 3.86 ₽ за видео'
                )
            else:
                online_count = get_fake_online_count()
                referral_bonus_text = ""
                if referrals_count > 0:
                    referral_bonus_text = (
                        f"\n🎁 <b>Отлично!</b> Ты пригласил <b>{referrals_count}</b> друзей\n"
                        f"   → Получено <b>+{referrals_count * REFERRAL_BONUS_GENERATIONS} бесплатных генераций</b>! 🎉\n\n"
                    )
                
                welcome_text = (
                    f'👋 <b>С возвращением, {user.mention_html()}!</b> 🤖✨\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'👥 <b>Сейчас в боте:</b> {online_count} человек онлайн\n\n'
                )
                
                if remaining_free > 0:
                    welcome_text += (
                        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                        f'🔥 <b>У ТЕБЯ ЕСТЬ {remaining_free} БЕСПЛАТНЫХ ГЕНЕРАЦИЙ!</b> 🔥\n\n'
                        f'✨ <b>ПРЕМИУМ AI MARKETPLACE</b> ✨\n\n'
                        f'🚀 <b>Что это за бот?</b>\n'
                        f'• 📦 <b>{total_models} топовых нейросетей</b> в одном месте\n'
                        f'• 🎯 <b>{len(generation_types)} типов генерации</b> контента\n'
                        f'• 🌐 Прямой доступ БЕЗ VPN\n'
                        f'• ⚡ Мгновенная генерация\n\n'
                        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                        f'✨ <b>Z-Image - САМАЯ КРУТАЯ НЕЙРОСЕТЬ ДЛЯ ИЗОБРАЖЕНИЙ!</b> ✨\n\n'
                        f'💎 <b>Почему Z-Image?</b>\n'
                        f'• 🎨 Профессиональное качество изображений\n'
                        f'• ⚡ Мгновенная генерация (10-30 секунд)\n'
                        f'• 🎯 Работает БЕЗ VPN\n'
                        f'• 💰 <b>ПОЛНОСТЬЮ БЕСПЛАТНО для тебя!</b>\n\n'
                        f'💡 <b>Нажми кнопку "🎁 Генерировать бесплатно" ниже</b>\n\n'
                    )
                
                welcome_text += (
                    f'{referral_bonus_text}'
                    f'💎 <b>ДОСТУПНО:</b>\n'
                    f'• {len(generation_types)} типов генерации\n'
                    f'• {total_models} топовых нейросетей\n'
                    f'• Без VPN, прямо здесь!\n\n'
                    f'💰 <b>После бесплатных генераций:</b>\n'
                    f'От 0.62 ₽ за изображение • От 3.86 ₽ за видео\n\n'
                    f'💡 <b>Пригласи друга → получи +{REFERRAL_BONUS_GENERATIONS} бесплатных генераций!</b>\n'
                    f'🔗 <code>{referral_link}</code>\n\n'
                    f'🎯 <b>Выбери формат генерации ниже или начни с бесплатной!</b>'
                )
            
            # Common keyboard for both admin and regular users
            keyboard = []
            
            # Free generation button (ALWAYS prominent - biggest button)
            if remaining_free > 0:
                keyboard.append([
                    InlineKeyboardButton(f"🎁 ГЕНЕРИРОВАТЬ БЕСПЛАТНО ({remaining_free} осталось)", callback_data="select_model:z-image")
                ])
                keyboard.append([])  # Empty row for spacing
            
            # Generation types buttons (compact, 2 per row)
            gen_type_rows = []
            for i, gen_type in enumerate(generation_types):
                gen_info = get_generation_type_info(gen_type)
                models_count = len(get_models_by_generation_type(gen_type))
                button_text = f"{gen_info.get('name', gen_type)} ({models_count})"
                
                if i % 2 == 0:
                    gen_type_rows.append([InlineKeyboardButton(
                        button_text,
                        callback_data=f"gen_type:{gen_type}"
                    )])
                else:
                    if gen_type_rows:
                        gen_type_rows[-1].append(InlineKeyboardButton(
                            button_text,
                            callback_data=f"gen_type:{gen_type}"
                        ))
                    else:
                        gen_type_rows.append([InlineKeyboardButton(
                            button_text,
                            callback_data=f"gen_type:{gen_type}"
                        )])
            
            keyboard.extend(gen_type_rows)
            
            # Bottom action buttons
            keyboard.append([])  # Empty row for spacing
            keyboard.append([
                InlineKeyboardButton("💰 Баланс", callback_data="check_balance"),
                InlineKeyboardButton("📚 Мои генерации", callback_data="my_generations")
            ])
            keyboard.append([
                InlineKeyboardButton("💳 Пополнить", callback_data="topup_balance"),
                InlineKeyboardButton("🎁 Пригласить друга", callback_data="referral_info")
            ])
            
            # Add tutorial button for new users
            if is_new:
                keyboard.append([
                    InlineKeyboardButton("❓ Как это работает?", callback_data="tutorial_start")
                ])
            
            keyboard.append([
                InlineKeyboardButton("🆘 Помощь", callback_data="help_menu"),
                InlineKeyboardButton("💬 Поддержка", callback_data="support_contact")
            ])
            
            # Add admin panel button ONLY for admin (at the end)
            if is_admin:
                keyboard.append([])  # Empty row for admin section
                keyboard.append([
                    InlineKeyboardButton("👑 АДМИН ПАНЕЛЬ", callback_data="admin_stats")
                ])
            
            await query.edit_message_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error in back_to_menu: {e}", exc_info=True)
            try:
                await query.answer("❌ Ошибка. Попробуйте /start", show_alert=True)
            except:
                pass
        return ConversationHandler.END
    
    # OLD back_to_menu code removed - now using start() function directly
    if False:  # This block is now disabled
        if is_admin:
            # Admin menu - same structure as user menu
            remaining_free = get_user_free_generations_remaining(user_id)
            is_new = is_new_user(user_id)
            referral_link = get_user_referral_link(user_id)
            referrals_count = len(get_user_referrals(user_id))
            
            if is_new:
                online_count = get_fake_online_count()
                welcome_text = (
                    f'👋 <b>Привет, {user.mention_html()}!</b> Я твой AI-напарник! 🤖✨\n\n'
                    f'👑 <b>РЕЖИМ АДМИНИСТРАТОРА</b> - Безлимитный доступ\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'🎉 <b>ОТЛИЧНЫЕ НОВОСТИ!</b> Ты попал в самый крутой AI-генератор контента! 🚀\n\n'
                    f'👥 <b>Сейчас в боте:</b> {online_count} человек онлайн\n\n'
                    f'💡 <b>Я помогу тебе:</b>\n'
                    f'• 🎨 Создавать потрясающие изображения\n'
                    f'• 🎬 Генерировать крутые видео\n'
                    f'• ✨ Трансформировать и редактировать контент\n'
                    f'• 🎯 Делать все это БЕЗ VPN и по цене жвачки!\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'🏢 <b>НАШИ ПОСТАВЩИКИ:</b>\n\n'
                    f'🤖 OpenAI • Google • Black Forest Labs\n'
                    f'🎬 ByteDance • Ideogram • Qwen\n'
                    f'✨ Kling • Hailuo • Topaz\n'
                    f'🎨 Recraft • Grok (xAI) • Wan\n\n'
                    f'💎 <b>Только топовые нейросети 2025 года!</b>\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'🎁 <b>НАЧНИ БЕСПЛАТНО ПРЯМО СЕЙЧАС!</b>\n\n'
                    f'✨ <b>У тебя есть:</b>\n'
                    f'• 🎁 <b>{remaining_free if remaining_free > 0 else FREE_GENERATIONS_PER_DAY} бесплатных генераций</b> Z-Image!\n'
                    f'• 💎 Каждый день обновляется\n'
                    f'• 🎯 Пригласи друга → получи <b>+{REFERRAL_BONUS_GENERATIONS} генераций</b>!\n\n'
                    f'🔗 <b>Твоя реферальная ссылка:</b>\n'
                    f'<code>{referral_link}</code>\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'💼 <b>ИДЕАЛЬНО ДЛЯ:</b>\n'
                    f'📊 Маркетологов • 🎨 Дизайнеров • 💻 Фрилансеров\n'
                    f'🚀 SMM-щиков • ✨ Креаторов • 🎬 Контент-мейкеров\n\n'
                    f'💰 <b>ГЕНЕРАЦИЯ ПО ЦЕНЕ ЖВАЧКИ!</b>\n'
                    f'От 0.62 ₽ за изображение • От 3.86 ₽ за видео\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'🎯 <b>ЧТО ДЕЛАТЬ ДАЛЬШЕ?</b>\n\n'
                    f'1️⃣ <b>Нажми кнопку "🎁 Генерировать бесплатно"</b> ниже\n'
                    f'   → Попробуй Z-Image прямо сейчас!\n\n'
                    f'2️⃣ <b>Или выбери формат генерации</b> из меню\n'
                    f'   → Я покажу все доступные нейросети\n\n'
                    f'3️⃣ <b>Создавай крутой контент!</b> 🎉\n\n'
                    f'💡 <b>Не знаешь с чего начать?</b>\n'
                    f'Нажми "❓ Как это работает?" - я все расскажу!'
                )
            else:
                online_count = get_fake_online_count()
                referral_bonus_text = ""
                if referrals_count > 0:
                    referral_bonus_text = (
                        f"\n🎁 <b>Отлично!</b> Ты пригласил <b>{referrals_count}</b> друзей\n"
                        f"   → Получено <b>+{referrals_count * REFERRAL_BONUS_GENERATIONS} генераций</b>! 🎉\n\n"
                    )
                
                welcome_text = (
                    f'👋 <b>С возвращением, {user.mention_html()}!</b> Рад тебя видеть! 🤖✨\n\n'
                    f'👑 <b>РЕЖИМ АДМИНИСТРАТОРА</b> - Безлимитный доступ\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'👥 <b>Сейчас в боте:</b> {online_count} человек онлайн\n\n'
                )
                
                if remaining_free > 0:
                    welcome_text += (
                        f'🎁 <b>У ТЕБЯ ЕСТЬ БЕСПЛАТНЫЕ ГЕНЕРАЦИИ!</b>\n\n'
                        f'✨ <b>{remaining_free} генераций Z-Image</b> доступно прямо сейчас!\n'
                        f'💡 Нажми кнопку "🎁 Генерировать бесплатно" ниже\n\n'
                    )
                
                welcome_text += (
                    f'{referral_bonus_text}'
                    f'💰 <b>ГЕНЕРАЦИЯ ПО ЦЕНЕ ЖВАЧКИ!</b>\n'
                    f'От 0.62 ₽ за изображение • От 3.86 ₽ за видео\n\n'
                    f'💡 <b>Пригласи друга → получи +{REFERRAL_BONUS_GENERATIONS} генераций!</b>\n'
                    f'🔗 <code>{referral_link}</code>\n\n'
                    f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                    f'💼 <b>ИДЕАЛЬНО ДЛЯ:</b>\n'
                    f'📊 Маркетологов • 🎨 Дизайнеров • 💻 Фрилансеров\n'
                    f'🚀 SMM-щиков • ✨ Креаторов • 🎬 Контент-мейкеров\n\n'
                    f'💎 <b>ДОСТУПНО:</b>\n'
                    f'• {len(generation_types)} типов генерации\n'
                    f'• {total_models} топовых нейросетей\n'
                    f'• Без VPN, прямо здесь!\n\n'
                    f'🎯 <b>Выбери формат генерации ниже</b> или начни с бесплатной генерации!'
                )
            
            keyboard = []
            
            # Free generation button
            if remaining_free > 0:
                keyboard.append([
                    InlineKeyboardButton(f"🎁 Генерировать бесплатно ({remaining_free} осталось)", callback_data="select_model:z-image")
                ])
                keyboard.append([])
            
            # Generation types (same as user menu)
            gen_type_rows = []
            for i, gen_type in enumerate(generation_types):
                gen_info = get_generation_type_info(gen_type)
                models_count = len(get_models_by_generation_type(gen_type))
                button_text = f"{gen_info.get('name', gen_type)} ({models_count})"
                
                if i % 2 == 0:
                    gen_type_rows.append([InlineKeyboardButton(button_text, callback_data=f"gen_type:{gen_type}")])
                else:
                    if gen_type_rows:
                        gen_type_rows[-1].append(InlineKeyboardButton(button_text, callback_data=f"gen_type:{gen_type}"))
                    else:
                        gen_type_rows.append([InlineKeyboardButton(button_text, callback_data=f"gen_type:{gen_type}")])
            
            keyboard.extend(gen_type_rows)
            keyboard.append([])
            
            # User functions (same as regular users)
            keyboard.append([
                InlineKeyboardButton("💰 Баланс", callback_data="check_balance"),
                InlineKeyboardButton("📚 Мои генерации", callback_data="my_generations")
            ])
            keyboard.append([
                InlineKeyboardButton("💳 Пополнить", callback_data="topup_balance"),
                InlineKeyboardButton("🎁 Пригласить друга", callback_data="referral_info")
            ])
            keyboard.append([
                InlineKeyboardButton("❓ Как это работает?", callback_data="help_menu"),
                InlineKeyboardButton("💬 Поддержка", callback_data="support_contact")
            ])
            
            keyboard.append([])  # Empty row for admin section
            
            # Admin functions (additional)
            keyboard.append([
                InlineKeyboardButton("👑 АДМИН ПАНЕЛЬ", callback_data="admin_stats")
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
        else:
            remaining_free = get_user_free_generations_remaining(user_id)
            free_info = ""
            if remaining_free > 0:
                free_info = f"\n🎁 <b>Бесплатно:</b> {remaining_free} генераций Z-Image\n"
            
            welcome_text = (
                f'✨ <b>ПРЕМИУМ AI MARKETPLACE</b> ✨\n\n'
                f'━━━━━━━━━━━━━━━━━━━━\n\n'
                f'👋 Привет, {user.mention_html()}!\n\n'
                f'🚀 <b>Топовые нейросети без VPN</b>\n'
                f'📦 <b>{total_models} моделей</b> | <b>{len(categories)} категорий</b>{free_info}\n\n'
                f'━━━━━━━━━━━━━━━━━━━━\n\n'
                f'💎 <b>Преимущества:</b>\n'
                f'• Прямой доступ к мировым AI\n'
                f'• Профессиональное качество 2K/4K\n'
                f'• Мгновенная генерация\n\n'
                f'🎯 <b>Выберите категорию или все модели</b>'
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
        if data.startswith("gen_type:"):
        # User selected a generation type
        gen_type = data.split(":", 1)[1]
        gen_info = get_generation_type_info(gen_type)
        models = get_models_by_generation_type(gen_type)
        
        if not models:
            await query.edit_message_text(
                f"❌ Модели для этого типа генерации не найдены.",
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # Show generation type info and models with marketing text
        remaining_free = get_user_free_generations_remaining(user_id)
        
        gen_type_text = (
            f"🎨 <b>{gen_info.get('name', gen_type)}</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 <b>Описание:</b>\n"
            f"{gen_info.get('description', '')}\n\n"
        )
        
        if remaining_free > 0 and gen_type == "text-to-image":
            gen_type_text += (
                f"🎁 <b>БЕСПЛАТНО:</b> {remaining_free} генераций Z-Image доступно!\n"
                f"💡 Пригласи друга → получи +{REFERRAL_BONUS_GENERATIONS} генераций\n\n"
            )
        
        gen_type_text += (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖 <b>Доступные нейросети ({len(models)}):</b>\n\n"
            f"💡 <b>Выберите модель ниже</b>"
        )
        
        # Create keyboard with models (2 per row for compact display)
        keyboard = []
        
        # Free generation button if available and this is text-to-image
        if remaining_free > 0 and gen_type == "text-to-image":
            keyboard.append([
                InlineKeyboardButton(f"🎁 Генерировать бесплатно ({remaining_free} осталось)", callback_data="select_model:z-image")
            ])
            keyboard.append([])  # Empty row
        
        # Show models in compact format with prices (2 per row)
        model_rows = []
        for i, model in enumerate(models):
            model_name = model.get('name', model.get('id', 'Unknown'))
            model_emoji = model.get('emoji', '🤖')
            model_id = model.get('id')
            
            # Calculate price for display
            default_params = {}
            if model_id == "nano-banana-pro":
                default_params = {"resolution": "1K"}
            elif model_id in ["seedream/4.5-text-to-image", "seedream/4.5-edit"]:
                default_params = {"quality": "basic"}
            
            min_price = calculate_price_rub(model_id, default_params, is_admin_user)
            price_text = get_model_price_text(model_id, default_params, is_admin_user, user_id)
            
            # Extract price number from price_text for compact display
            import re
            price_match = re.search(r'(\d+\.?\d*)\s*₽', price_text)
            if price_match:
                price_display = price_match.group(1)
                # Check if it's "От" (from) or fixed price
                if "От" in price_text or "от" in price_text.lower():
                    price_display = f"от {price_display} ₽"
                else:
                    price_display = f"{price_display} ₽"
            elif "БЕСПЛАТНО" in price_text or "Бесплатно" in price_text:
                price_display = "бесплатно"
            else:
                # Fallback: show calculated price
                price_display = f"{min_price:.2f} ₽"
            
            # Compact button text (shorten if too long)
            button_text = f"{model_emoji} {model_name}"
            if len(button_text) > 30:
                # Truncate model name if too long
                button_text = f"{model_emoji} {model_name[:25]}..."
            
            button_text_with_price = f"{button_text} • {price_display}"
            
            if i % 2 == 0:
                # First button in row
                model_rows.append([InlineKeyboardButton(
                    button_text_with_price,
                    callback_data=f"select_model:{model_id}"
                )])
            else:
                # Second button in row - add to last row
                if model_rows:
                    model_rows[-1].append(InlineKeyboardButton(
                        button_text_with_price,
                        callback_data=f"select_model:{model_id}"
                    ))
                else:
                    model_rows.append([InlineKeyboardButton(
                        button_text_with_price,
                        callback_data=f"select_model:{model_id}"
                    )])
        
        keyboard.extend(model_rows)
        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
        
        try:
            await query.edit_message_text(
                gen_type_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error editing message in gen_type: {e}", exc_info=True)
            try:
                await query.message.reply_text(
                    gen_type_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            except Exception as e2:
                logger.error(f"Error sending new message in gen_type: {e2}", exc_info=True)
                await query.answer("❌ Ошибка. Попробуйте еще раз", show_alert=True)
        
        return ConversationHandler.END
        
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
            # Calculate price for display
            default_params = {}
            if model['id'] == "nano-banana-pro":
                default_params = {"resolution": "1K"}
            elif model['id'] in ["seedream/4.5-text-to-image", "seedream/4.5-edit"]:
                default_params = {"quality": "basic"}
            
            min_price = calculate_price_rub(model['id'], default_params, is_admin)
            price_text = get_model_price_text(model['id'], default_params, is_admin, user_id)
            
            # Extract price number from price_text for compact display
            import re
            price_match = re.search(r'(\d+\.?\d*)\s*₽', price_text)
            if price_match:
                price_display = price_match.group(1)
                # Check if it's "От" (from) or fixed price
                if "От" in price_text or "от" in price_text.lower():
                    price_display = f"от {price_display} ₽"
                else:
                    price_display = f"{price_display} ₽"
            elif "БЕСПЛАТНО" in price_text or "Бесплатно" in price_text:
                price_display = "бесплатно"
            else:
                # Fallback: show calculated price
                price_display = f"{min_price:.2f} ₽"
            
            # Compact button text with price
            button_text = f"{model['emoji']} {model['name']} • {price_display}"
            
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"select_model:{model['id']}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="show_models")])
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")])
        
        # Premium formatted header
        category_emoji = {
            "Видео": "🎬",
            "Изображения": "🖼️",
            "Редактирование": "✏️"
        }.get(category, "📁")
        
        models_text = (
            f"✨ <b>ПРЕМИУМ КАТАЛОГ</b> ✨\n\n"
            f"{category_emoji} <b>Категория: {category}</b>\n"
            f"📦 <b>Доступно моделей:</b> {len(models)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💡 <i>Выберите модель из списка ниже</i>\n"
            f"<i>Подробная информация отобразится при выборе</i>"
        )
        
        await query.edit_message_text(
            models_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return SELECTING_MODEL
        
        if data == "show_models" or data == "all_models":
        # Show generation types instead of all models with marketing text
        generation_types = get_generation_types()
        remaining_free = get_user_free_generations_remaining(user_id)
        
        models_text = (
            f"🎨 <b>ВЫБЕРИТЕ ФОРМАТ ГЕНЕРАЦИИ</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>ГЕНЕРАЦИЯ ПО ЦЕНЕ ЖВАЧКИ!</b>\n\n"
            f"💼 <b>ИДЕАЛЬНО ДЛЯ:</b>\n"
            f"• Маркетологов • SMM-щиков • Дизайнеров\n"
            f"• Фрилансеров • Креаторов • Контент-мейкеров\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💡 <b>КАК ЭТО РАБОТАЕТ:</b>\n"
            f"1️⃣ Выберите формат генерации\n"
            f"2️⃣ Выберите одну из предложенных нейросетей\n"
            f"3️⃣ Создавайте крутой контент! 🚀\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        if remaining_free > 0:
            models_text += (
                f"🎁 <b>БЕСПЛАТНО:</b> {remaining_free} генераций Z-Image доступно!\n"
                f"💡 Пригласи друга → получи +{REFERRAL_BONUS_GENERATIONS} генераций\n\n"
            )
        
        models_text += (
            f"📦 <b>Доступно:</b> {len(generation_types)} типов генерации\n"
            f"🤖 <b>Моделей:</b> {len(KIE_MODELS)} топовых нейросетей"
        )
        
        keyboard = []
        
        # Free generation button if available
        if remaining_free > 0:
            keyboard.append([
                InlineKeyboardButton(f"🎁 Генерировать бесплатно ({remaining_free} осталось)", callback_data="select_model:z-image")
            ])
            keyboard.append([])  # Empty row
        
        # Generation types buttons (2 per row for compact display)
        gen_type_rows = []
        for i, gen_type in enumerate(generation_types):
            gen_info = get_generation_type_info(gen_type)
            models_count = len(get_models_by_generation_type(gen_type))
            button_text = f"{gen_info.get('name', gen_type)} ({models_count})"
            
            if i % 2 == 0:
                # First button in row
                gen_type_rows.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f"gen_type:{gen_type}"
                )])
            else:
                # Second button in row - add to last row
                if gen_type_rows:
                    gen_type_rows[-1].append(InlineKeyboardButton(
                        button_text,
                        callback_data=f"gen_type:{gen_type}"
                    ))
                else:
                    gen_type_rows.append([InlineKeyboardButton(
                        button_text,
                        callback_data=f"gen_type:{gen_type}"
                    )])
        
        keyboard.extend(gen_type_rows)
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")])
        
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
        # Check user's personal balance (NOT KIE balance)
        user_balance = get_user_balance(user_id)
        balance_str = f"{user_balance:.2f}".rstrip('0').rstrip('.')
        is_admin = get_is_admin(user_id)
        
        keyboard = [
            [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
        ]
        
        balance_text = (
            f'💳 <b>ВАШ БАЛАНС</b> 💳\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'💰 <b>Доступно:</b> {balance_str} ₽\n\n'
        )
        
        if is_admin:
            balance_text += (
                f'👑 <b>Статус:</b> Администратор\n'
                f'✅ Безлимитный доступ ко всем моделям\n\n'
            )
        else:
            if user_balance > 0:
                balance_text += (
                    f'💡 <b>Доступно для генерации:</b>\n'
                    f'• ~{int(user_balance / 0.62)} изображений (Z-Image)\n'
                    f'• ~{int(user_balance / 3.86)} видео (базовая модель)\n\n'
                )
            else:
                balance_text += (
                    f'💡 <b>Пополните баланс для генерации контента</b>\n\n'
                )
        
        balance_text += (
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'🎁 <b>Не забудьте:</b> У вас есть бесплатные генерации Z-Image!'
        )
        
        await query.edit_message_text(
            balance_text,
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
        
        # Show amount selection - focus on small amounts with marketing
        keyboard = [
            [
                InlineKeyboardButton("💎 50 ₽", callback_data="topup_amount:50"),
                InlineKeyboardButton("💎 100 ₽", callback_data="topup_amount:100"),
                InlineKeyboardButton("💎 150 ₽", callback_data="topup_amount:150")
            ],
            [
                InlineKeyboardButton("💰 Своя сумма", callback_data="topup_custom")
            ],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
        ]
        
        current_balance = get_user_balance(user_id)
        balance_str = f"{current_balance:.2f}".rstrip('0').rstrip('.')
        
        await query.edit_message_text(
            f'💳 <b>ПОПОЛНЕНИЕ БАЛАНСА</b> 💳\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'💰 <b>Твой текущий баланс:</b> {balance_str} ₽\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'💡 <b>Доступные модели:</b>\n'
            f'• От 3.86 ₽ за видео\n'
            f'• От 0.62 ₽ за изображение\n'
            f'• Редактирование от 0.5 ₽\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'🚀 <b>ВЫБЕРИ СУММУ:</b>\n'
            f'• Быстрый выбор: 50, 100, 150 ₽\n'
            f'• Или укажи свою сумму\n\n'
            f'📝 <b>Ограничения:</b>\n'
            f'Минимум: 50 ₽ | Максимум: 50000 ₽',
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return SELECTING_AMOUNT
        
        if data.startswith("topup_amount:"):
        # User selected a preset amount
        amount = float(data.split(":")[1])
        user_sessions[user_id] = {
            'topup_amount': amount,
            'waiting_for': 'payment_screenshot'
        }
        
        payment_details = get_payment_details()
        
        # Calculate what user can generate
        examples_count = int(amount / 0.62)  # Z-Image price
        video_count = int(amount / 3.86)  # Basic video price
        
        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        
        await query.edit_message_text(
            f'💳 <b>ОПЛАТА {amount:.0f} ₽</b> 💳\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'{payment_details}\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'💵 <b>Сумма к оплате:</b> {amount:.2f} ₽\n\n'
            f'🎯 <b>ЧТО ТЫ ПОЛУЧИШЬ:</b>\n'
            f'• ~{examples_count} изображений Z-Image\n'
            f'• ~{video_count} видео (базовая модель)\n'
            f'• Или комбинацию разных моделей!\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'📸 <b>КАК ОПЛАТИТЬ:</b>\n'
            f'1️⃣ Переведи {amount:.2f} ₽ по реквизитам выше\n'
            f'2️⃣ Сделай скриншот перевода\n'
            f'3️⃣ Отправь скриншот сюда\n'
            f'4️⃣ Баланс начислится автоматически! ⚡\n\n'
            f'✅ <b>Все просто и быстро!</b>',
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_PAYMENT_SCREENSHOT
        
        if data == "topup_custom":
        # User wants to enter custom amount
        await query.edit_message_text(
            f'💰 <b>ВВЕДИ СВОЮ СУММУ</b> 💰\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'📝 <b>Просто отправь число</b> (например: 250)\n\n'
            f'💡 <b>Доступные модели:</b>\n'
            f'• От 3.86 ₽ за видео\n'
            f'• От 0.62 ₽ за изображение\n'
            f'• Редактирование от 0.5 ₽\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'📋 <b>Ограничения:</b>\n'
            f'• Минимум: 50 ₽\n'
            f'• Максимум: 50000 ₽\n\n'
            f'💬 <b>Отправь сумму цифрами</b> (например: 250)',
            parse_mode='HTML'
        )
        user_sessions[user_id] = {
            'waiting_for': 'topup_amount_input'
        }
        return SELECTING_AMOUNT
    
    # If we get here and no handler matched, log and return END
    logger.warning(f"Unhandled callback data: {data} from user {user_id}")
    try:
        await query.answer("❌ Неизвестная команда. Используйте /start", show_alert=True)
    except:
        pass
    return ConversationHandler.END
    
    # Admin functions (only for admin)
    if user_id == ADMIN_ID:
        if data == "admin_stats":
            # Show full admin panel menu
            generation_types = get_generation_types()
            total_models = len(KIE_MODELS)
            
            # Get KIE API balance (for admin info only)
            kie_balance_info = ""
            try:
                balance_result = await kie.get_credits()
                if balance_result.get('ok'):
                    balance = balance_result.get('credits', 0)
                    balance_rub = balance * CREDIT_TO_USD * USD_TO_RUB
                    balance_rub_str = f"{balance_rub:.2f}".rstrip('0').rstrip('.')
                    kie_balance_info = f"💰 <b>Баланс KIE API:</b> {balance_rub_str} ₽ ({balance} кредитов)\n\n"
            except Exception as e:
                logger.error(f"Error getting KIE balance: {e}")
                kie_balance_info = "💰 <b>Баланс KIE API:</b> Недоступен\n\n"
            
            admin_text = (
                f'👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b> 👑\n\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                f'{kie_balance_info}'
                f'📊 <b>СТАТИСТИКА СИСТЕМЫ:</b>\n\n'
                f'✅ <b>{total_models} премиум моделей</b> в арсенале\n'
                f'✅ <b>{len(generation_types)} категорий</b> контента\n'
                f'✅ Безлимитный доступ ко всем генерациям\n\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                f'⚙️ <b>АДМИНИСТРАТИВНЫЕ ФУНКЦИИ:</b>\n\n'
                f'📈 Просмотр статистики и аналитики\n'
                f'👥 Управление пользователями\n'
                f'🎁 Управление промокодами\n'
                f'🧪 Тестирование OCR системы\n'
                f'💼 Полный контроль над ботом\n\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
                f'💫 <b>ВЫБЕРИТЕ ДЕЙСТВИЕ:</b>'
            )
            
            keyboard = [
                [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
                [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
                [InlineKeyboardButton("🔍 Поиск", callback_data="admin_search")],
                [InlineKeyboardButton("📝 Добавить", callback_data="admin_add")],
                [InlineKeyboardButton("🧪 Тест OCR", callback_data="admin_test_ocr")],
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
            ]
            
            await query.edit_message_text(
                admin_text,
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
                [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
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
            
            # Show all promocodes
            if promocodes:
                promocodes_text += f"📋 <b>Все промокоды ({len(promocodes)}):</b>\n\n"
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
            else:
                promocodes_text += "📋 <b>Нет созданных промокодов</b>\n\n"
            
            promocodes_text += "💡 <b>Доступные действия:</b>\n"
            promocodes_text += "• Просмотр всех промокодов\n"
            promocodes_text += "• Информация об активном промокоде\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data="admin_promocodes")],
                [InlineKeyboardButton("◀️ Назад", callback_data="admin_settings")]
            ]
            
            await query.edit_message_text(
                promocodes_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_broadcast":
            # Show broadcast menu
            broadcasts = get_broadcasts()
            total_users = len(get_all_users())
            
            broadcast_text = "📢 <b>Рассылка сообщений</b>\n\n"
            broadcast_text += f"👥 <b>Всего пользователей:</b> {total_users}\n\n"
            
            if broadcasts:
                broadcast_text += f"📋 <b>История рассылок ({len(broadcasts)}):</b>\n\n"
                # Show last 5 broadcasts
                sorted_broadcasts = sorted(
                    broadcasts.items(),
                    key=lambda x: x[1].get('created_at', 0),
                    reverse=True
                )[:5]
                
                for broadcast_id, broadcast in sorted_broadcasts:
                    created_at = broadcast.get('created_at', 0)
                    sent = broadcast.get('sent', 0)
                    delivered = broadcast.get('delivered', 0)
                    failed = broadcast.get('failed', 0)
                    message_preview = broadcast.get('message', '')[:30] + '...' if len(broadcast.get('message', '')) > 30 else broadcast.get('message', '')
                    
                    from datetime import datetime
                    if created_at:
                        date_str = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H:%M')
                    else:
                        date_str = 'N/A'
                    
                    broadcast_text += (
                        f"📨 <b>#{broadcast_id}</b> ({date_str})\n"
                        f"   📝 {message_preview}\n"
                        f"   ✅ Отправлено: {sent} | 📬 Доставлено: {delivered} | ❌ Ошибок: {failed}\n\n"
                    )
            else:
                broadcast_text += "📋 <b>Нет истории рассылок</b>\n\n"
            
            broadcast_text += "💡 <b>Создать новую рассылку:</b>\n"
            broadcast_text += "Нажмите кнопку ниже и отправьте сообщение для рассылки."
            
            keyboard = [
                [InlineKeyboardButton("📢 Создать рассылку", callback_data="admin_create_broadcast")],
                [InlineKeyboardButton("📊 Статистика", callback_data="admin_broadcast_stats")],
                [InlineKeyboardButton("◀️ Назад", callback_data="admin_settings")]
            ]
            
            await query.edit_message_text(
                broadcast_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        if data == "admin_create_broadcast":
            # Start broadcast creation
            await query.edit_message_text(
                "📢 <b>Создание рассылки</b>\n\n"
                "Отправьте сообщение, которое хотите разослать всем пользователям.\n\n"
                "💡 <b>Поддерживается:</b>\n"
                "• Текст\n"
                "• HTML форматирование\n"
                "• Изображения\n\n"
                "Или нажмите /cancel для отмены.",
                parse_mode='HTML'
            )
            user_sessions[user_id] = {
                'waiting_for': 'broadcast_message'
            }
            return WAITING_BROADCAST_MESSAGE
        
        if data == "admin_broadcast_stats":
            # Show detailed broadcast statistics
            broadcasts = get_broadcasts()
            total_users = len(get_all_users())
            
            if not broadcasts:
                await query.edit_message_text(
                    "📊 <b>Статистика рассылок</b>\n\n"
                    "❌ Нет истории рассылок",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("◀️ Назад", callback_data="admin_broadcast")]
                    ]),
                    parse_mode='HTML'
                )
                return ConversationHandler.END
            
            # Calculate totals
            total_sent = sum(b.get('sent', 0) for b in broadcasts.values())
            total_delivered = sum(b.get('delivered', 0) for b in broadcasts.values())
            total_failed = sum(b.get('failed', 0) for b in broadcasts.values())
            
            stats_text = (
                f"📊 <b>Статистика рассылок</b>\n\n"
                f"👥 <b>Всего пользователей:</b> {total_users}\n"
                f"📨 <b>Всего рассылок:</b> {len(broadcasts)}\n\n"
                f"📈 <b>Общая статистика:</b>\n"
                f"✅ Отправлено: {total_sent}\n"
                f"📬 Доставлено: {total_delivered}\n"
                f"❌ Ошибок: {total_failed}\n\n"
            )
            
            if total_sent > 0:
                success_rate = (total_delivered / total_sent) * 100
                stats_text += f"📊 <b>Успешность доставки:</b> {success_rate:.1f}%\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data="admin_broadcast_stats")],
                [InlineKeyboardButton("◀️ Назад", callback_data="admin_broadcast")]
            ]
            
            await query.edit_message_text(
                stats_text,
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
        
        if data == "tutorial_start":
        # Interactive tutorial for new users
        tutorial_text = (
            '🎓 <b>ИНТЕРАКТИВНЫЙ ТУТОРИАЛ</b>\n\n'
            '━━━━━━━━━━━━━━━━━━━━\n\n'
            '👋 Добро пожаловать! Давайте разберемся, как пользоваться ботом.\n\n'
            '📚 <b>Что вы узнаете:</b>\n'
            '• Что такое AI-генерация\n'
            '• Как выбрать модель\n'
            '• Как создать контент\n'
            '• Как пополнить баланс\n\n'
            '💡 <b>Это займет 2 минуты!</b>'
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Начать туториал", callback_data="tutorial_step1")],
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
        
        if data == "tutorial_step1":
        tutorial_text = (
            '📖 <b>ШАГ 1: Что такое AI-генерация?</b>\n\n'
            '━━━━━━━━━━━━━━━━━━━━\n\n'
            '🤖 <b>Искусственный интеллект</b> может создавать:\n\n'
            '🎨 <b>Изображения</b>\n'
            'Опишите картинку словами, и AI создаст её!\n'
            'Пример: "Кот в космосе, пиксель-арт"\n\n'
            '🎬 <b>Видео</b>\n'
            'Создавайте короткие видео из текста\n'
            'Пример: "Летящий дракон над городом"\n\n'
            '🖼️ <b>Улучшение качества</b>\n'
            'Увеличивайте разрешение фото в 4-8 раз\n\n'
            '💡 <b>Все это без VPN!</b> Прямой доступ к лучшим AI-моделям.'
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Далее", callback_data="tutorial_step2")],
            [InlineKeyboardButton("◀️ Назад", callback_data="tutorial_start")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
        
        if data == "tutorial_step2":
        categories = get_categories()
        total_models = len(KIE_MODELS)
        tutorial_text = (
            f'📖 <b>ШАГ 2: Как выбрать модель?</b>\n\n'
            f'━━━━━━━━━━━━━━━━━━━━\n\n'
            f'🎯 <b>У нас {total_models} моделей в {len(categories)} категориях:</b>\n\n'
            f'🖼️ <b>Изображения</b>\n'
            f'• Z-Image - быстрая генерация (бесплатно 5 раз в день!)\n'
            f'• Nano Banana Pro - качество 2K/4K\n'
            f'• Imagen 4 Ultra - новейшая от Google\n\n'
            f'🎬 <b>Видео</b>\n'
            f'• Sora 2 - реалистичные видео\n'
            f'• Grok Imagine - мультимодальная модель\n\n'
            f'💡 <b>Совет:</b> Начните с Z-Image - она бесплатная!'
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Далее", callback_data="tutorial_step3")],
            [InlineKeyboardButton("◀️ Назад", callback_data="tutorial_step1")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
        
        if data == "tutorial_step3":
        tutorial_text = (
            '📖 <b>ШАГ 3: Как создать контент?</b>\n\n'
            '━━━━━━━━━━━━━━━━━━━━\n\n'
            '📝 <b>Простой процесс:</b>\n\n'
            '1️⃣ Нажмите "📋 Все модели"\n'
            '2️⃣ Выберите модель (например, Z-Image)\n'
            '3️⃣ Введите описание (промпт)\n'
            '   Пример: "Красивый закат над океаном"\n'
            '4️⃣ Выберите параметры (размер, стиль и т.д.)\n'
            '5️⃣ Нажмите "✅ Генерировать"\n'
            '6️⃣ Подождите 10-60 секунд\n'
            '7️⃣ Получите результат! 🎉\n\n'
            '💡 <b>Совет:</b> Чем подробнее описание, тем лучше результат!'
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Далее", callback_data="tutorial_step4")],
            [InlineKeyboardButton("◀️ Назад", callback_data="tutorial_step2")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
        
        if data == "tutorial_step4":
        remaining_free = get_user_free_generations_remaining(user_id)
        tutorial_text = (
            '📖 <b>ШАГ 4: Баланс и оплата</b>\n\n'
            '━━━━━━━━━━━━━━━━━━━━\n\n'
            '💰 <b>Как это работает:</b>\n\n'
            '🎁 <b>Бесплатно:</b>\n'
            f'• {remaining_free if remaining_free > 0 else FREE_GENERATIONS_PER_DAY} генераций Z-Image в день\n'
            '• Пригласите друга - получите +5 генераций!\n\n'
            '💳 <b>Пополнение баланса:</b>\n'
            '• Минимальная сумма: 50 ₽\n'
            '• Быстрый выбор: 50, 100, 150 ₽\n'
            '• Или укажите свою сумму\n'
            '• Оплата через СБП (Система быстрых платежей)\n\n'
            '💡 <b>Совет:</b> Начните с бесплатных генераций!'
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Завершить", callback_data="tutorial_complete")],
            [InlineKeyboardButton("◀️ Назад", callback_data="tutorial_step3")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
        
        if data == "tutorial_complete":
        tutorial_text = (
            '🎉 <b>ТУТОРИАЛ ЗАВЕРШЕН!</b>\n\n'
            '━━━━━━━━━━━━━━━━━━━━\n\n'
            '✅ Теперь вы знаете:\n'
            '• Что такое AI-генерация\n'
            '• Как выбрать модель\n'
            '• Как создать контент\n'
            '• Как пополнить баланс\n\n'
            '🚀 <b>Готовы начать?</b>\n\n'
            '💡 <b>Рекомендация:</b>\n'
            'Начните с бесплатной генерации Z-Image!\n'
            'Просто выберите модель и опишите, что хотите создать.'
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Все модели", callback_data="all_models")],
            [InlineKeyboardButton("🖼️ Z-Image (бесплатно)", callback_data="select_model:z-image")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
        
        if data == "help_menu":
        is_new = is_new_user(user_id)
        
        if is_new:
            help_text = (
                '📋 <b>ПОМОЩЬ ДЛЯ НОВЫХ ПОЛЬЗОВАТЕЛЕЙ</b>\n\n'
                '━━━━━━━━━━━━━━━━━━━━\n\n'
                '👋 <b>Добро пожаловать!</b>\n\n'
                '🎯 <b>Быстрый старт:</b>\n'
                '1. Нажмите "📋 Все модели"\n'
                '2. Выберите "🖼️ Z-Image" (она бесплатная!)\n'
                '3. Введите описание, например: "Кот в космосе"\n'
                '4. Нажмите "✅ Генерировать"\n'
                '5. Получите результат через 10-30 секунд!\n\n'
                '━━━━━━━━━━━━━━━━━━━━\n\n'
                '💡 <b>Полезные команды:</b>\n'
                '/start - Главное меню\n'
                '/models - Показать все модели\n'
                '/balance - Проверить баланс\n'
                '/help - Эта справка\n\n'
                '❓ <b>Нужна помощь?</b>\n'
                'Нажмите "❓ Как это работает?" для интерактивного туториала!'
            )
        else:
            help_text = (
                '📋 <b>ДОСТУПНЫЕ КОМАНДЫ</b>\n\n'
                '━━━━━━━━━━━━━━━━━━━━\n\n'
                '🔹 <b>Основные:</b>\n'
                '/start - Главное меню\n'
                '/models - Показать модели\n'
                '/balance - Проверить баланс\n'
                '/generate - Начать генерацию\n'
                '/help - Справка\n\n'
            )
            
            if user_id == ADMIN_ID:
                help_text += (
                    '👑 <b>Административные:</b>\n'
                    '/search - Поиск в базе знаний\n'
                    '/add - Добавление знаний\n'
                    '/payments - Просмотр платежей\n'
                    '/block_user - Заблокировать пользователя\n'
                    '/unblock_user - Разблокировать пользователя\n'
                    '/user_balance - Баланс пользователя\n\n'
                )
            
            help_text += (
                '💡 <b>Как использовать:</b>\n'
                '1. Выберите модель из меню\n'
                '2. Введите промпт (описание)\n'
                '3. Выберите параметры через кнопки\n'
                '4. Подтвердите генерацию\n'
                '5. Получите результат!\n\n'
                '📚 <b>Полезные функции:</b>\n'
                '• "📚 Мои генерации" - просмотр истории\n'
                '• "🔄 Повторить" - создать с теми же параметрами\n'
                '• "💳 Пополнить" - пополнение баланса'
            )
        
        keyboard = []
        if is_new:
            keyboard.append([InlineKeyboardButton("❓ Как это работает?", callback_data="tutorial_start")])
        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
        
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
        
        if data == "referral_info":
        # Show referral information
        referral_link = get_user_referral_link(user_id)
        referrals_count = len(get_user_referrals(user_id))
        remaining_free = get_user_free_generations_remaining(user_id)
        
        referral_text = (
            f'🎁 <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b> 🎁\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'💡 <b>КАК ЭТО РАБОТАЕТ:</b>\n\n'
            f'1️⃣ Пригласи друга по вашей ссылке\n'
            f'2️⃣ Он зарегистрируется через бота\n'
            f'3️⃣ Вы получите <b>+{REFERRAL_BONUS_GENERATIONS} бесплатных генераций</b>!\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'📊 <b>ВАША СТАТИСТИКА:</b>\n'
            f'• Приглашено друзей: <b>{referrals_count}</b>\n'
            f'• Получено бонусов: <b>{referrals_count * REFERRAL_BONUS_GENERATIONS}</b> генераций\n'
            f'• Доступно бесплатно: <b>{remaining_free}</b> генераций\n\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            f'🔗 <b>ВАША РЕФЕРАЛЬНАЯ ССЫЛКА:</b>\n\n'
            f'<code>{referral_link}</code>\n\n'
            f'💬 <b>Отправьте эту ссылку другу!</b>\n'
            f'После его регистрации вы получите бонус автоматически.'
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Скопировать ссылку", url=referral_link)],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            referral_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
        
        if data == "my_generations":
        # Show user's generation history
        history = get_user_generations_history(user_id, limit=20)
        
        if not history:
            keyboard = [[InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "📚 <b>Мои генерации</b>\n\n"
                "❌ У вас пока нет сохраненных генераций.\n\n"
                "💡 После создания контента все ваши работы будут сохранены здесь.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
        
        # Show first generation with navigation
        from datetime import datetime
        
        gen = history[0]
        timestamp = gen.get('timestamp', 0)
        if timestamp:
            date_str = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')
        else:
            date_str = 'Неизвестно'
        
        model_name = gen.get('model_name', gen.get('model_id', 'Unknown'))
        result_urls = gen.get('result_urls', [])
        price = gen.get('price', 0)
        is_free = gen.get('is_free', False)
        
        history_text = (
            f"📚 <b>Мои генерации</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>Всего:</b> {len(history)} генераций\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎨 <b>Генерация #{gen.get('id', 1)}</b>\n"
            f"📅 <b>Дата:</b> {date_str}\n"
            f"🤖 <b>Модель:</b> {model_name}\n"
            f"💰 <b>Стоимость:</b> {'🎁 Бесплатно' if is_free else f'{price:.2f} ₽'}\n"
            f"📦 <b>Результатов:</b> {len(result_urls)}\n\n"
        )
        
        if len(history) > 1:
            history_text += f"💡 <b>Показана последняя генерация</b>\n"
            history_text += f"Используйте кнопки для навигации\n\n"
        
        keyboard = []
        
        # Navigation buttons if more than 1 generation
        if len(history) > 1:
            keyboard.append([
                InlineKeyboardButton("◀️ Предыдущая", callback_data=f"gen_history:{gen.get('id', 1)}:prev"),
                InlineKeyboardButton("Следующая ▶️", callback_data=f"gen_history:{gen.get('id', 1)}:next")
            ])
        
        # Action buttons
        if result_urls:
            keyboard.append([
                InlineKeyboardButton("👁️ Показать результат", callback_data=f"gen_view:{gen.get('id', 1)}")
            ])
            keyboard.append([
                InlineKeyboardButton("🔄 Повторить", callback_data=f"gen_repeat:{gen.get('id', 1)}")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
        
        await query.edit_message_text(
            history_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END
        
        if data.startswith("gen_view:"):
        # View specific generation result
        gen_id = int(data.split(":")[1])
        gen = get_generation_by_id(user_id, gen_id)
        
        if not gen:
            await query.answer("❌ Генерация не найдена", show_alert=True)
            return ConversationHandler.END
        
        result_urls = gen.get('result_urls', [])
        if not result_urls:
            await query.answer("❌ Результаты не найдены", show_alert=True)
            return ConversationHandler.END
        
        # Send media
        for i, url in enumerate(result_urls[:5]):
            try:
                async with aiohttp.ClientSession() as session_http:
                    async with session_http.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            media_data = await resp.read()
                            
                            is_last = (i == len(result_urls[:5]) - 1)
                            is_video = gen.get('model_id', '') in ['sora-2-text-to-video', 'sora-watermark-remover', 'kling-2.6/image-to-video', 'kling-2.6/text-to-video', 'kling/v2-5-turbo-text-to-video-pro', 'kling/v2-5-turbo-image-to-video-pro', 'wan/2-5-image-to-video', 'wan/2-5-text-to-video', 'wan/2-2-animate-move', 'wan/2-2-animate-replace', 'hailuo/02-text-to-video-pro', 'hailuo/02-image-to-video-pro', 'hailuo/02-text-to-video-standard', 'hailuo/02-image-to-video-standard']
                            
                            keyboard = []
                            if is_last:
                                keyboard = [
                                    [InlineKeyboardButton("◀️ Назад к истории", callback_data="my_generations")],
                                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
                                ]
                            
                            if is_video:
                                video_file = io.BytesIO(media_data)
                                video_file.name = f"generated_video_{i+1}.mp4"
                                await context.bot.send_video(
                                    chat_id=update.effective_chat.id,
                                    video=video_file,
                                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                                )
                            else:
                                photo_file = io.BytesIO(media_data)
                                photo_file.name = f"generated_image_{i+1}.png"
                                await context.bot.send_photo(
                                    chat_id=update.effective_chat.id,
                                    photo=photo_file,
                                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                                )
            except Exception as e:
                logger.error(f"Error sending generation result: {e}")
        
        await query.answer("✅ Результаты отправлены")
        return ConversationHandler.END
        
        if data.startswith("gen_repeat:"):
        # Repeat generation with same parameters
        gen_id = int(data.split(":")[1])
        gen = get_generation_by_id(user_id, gen_id)
        
        if not gen:
            await query.answer("❌ Генерация не найдена", show_alert=True)
            return ConversationHandler.END
        
        # Restore session from history
        model_id = gen.get('model_id')
        params = gen.get('params', {})
        model_info = get_model_by_id(model_id)
        
        if not model_info:
            await query.answer("❌ Модель не найдена", show_alert=True)
            return ConversationHandler.END
        
        user_sessions[user_id] = {
            'model_id': model_id,
            'model_info': model_info,
            'params': params.copy(),
            'properties': model_info.get('input_params', {}),
            'required': []
        }
        
        # Go directly to confirmation
        await query.answer("✅ Параметры восстановлены")
        await query.edit_message_text(
            "🔄 <b>Повторная генерация</b>\n\n"
            f"Модель: <b>{model_info.get('name', model_id)}</b>\n"
            f"Параметры восстановлены из истории.\n\n"
            "Подтвердите генерацию:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Генерировать", callback_data="confirm_generate")],
                [InlineKeyboardButton("◀️ Назад к истории", callback_data="my_generations")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
            ]),
            parse_mode='HTML'
        )
        return CONFIRMING_GENERATION
        
        if data.startswith("gen_history:"):
        # Navigate through generation history
        parts = data.split(":")
        if len(parts) < 3:
            await query.answer("❌ Ошибка навигации", show_alert=True)
            return ConversationHandler.END
        
        current_gen_id = int(parts[1])
        direction = parts[2]  # prev or next
        
        history = get_user_generations_history(user_id, limit=100)
        if not history:
            await query.answer("❌ История пуста", show_alert=True)
            return ConversationHandler.END
        
        # Find current generation index
        current_index = -1
        for i, gen in enumerate(history):
            if gen.get('id') == current_gen_id:
                current_index = i
                break
        
        if current_index == -1:
            await query.answer("❌ Генерация не найдена", show_alert=True)
            return ConversationHandler.END
        
        # Navigate
        if direction == 'prev' and current_index < len(history) - 1:
            new_index = current_index + 1
        elif direction == 'next' and current_index > 0:
            new_index = current_index - 1
        else:
            await query.answer("⚠️ Это первая/последняя генерация", show_alert=True)
            return ConversationHandler.END
        
        gen = history[new_index]
        from datetime import datetime
        
        timestamp = gen.get('timestamp', 0)
        if timestamp:
            date_str = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')
        else:
            date_str = 'Неизвестно'
        
        model_name = gen.get('model_name', gen.get('model_id', 'Unknown'))
        result_urls = gen.get('result_urls', [])
        price = gen.get('price', 0)
        is_free = gen.get('is_free', False)
        
        history_text = (
            f"📚 <b>Мои генерации</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>Всего:</b> {len(history)} генераций\n"
            f"📍 <b>Показана:</b> {new_index + 1} из {len(history)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎨 <b>Генерация #{gen.get('id', 1)}</b>\n"
            f"📅 <b>Дата:</b> {date_str}\n"
            f"🤖 <b>Модель:</b> {model_name}\n"
            f"💰 <b>Стоимость:</b> {'🎁 Бесплатно' if is_free else f'{price:.2f} ₽'}\n"
            f"📦 <b>Результатов:</b> {len(result_urls)}\n\n"
        )
        
        keyboard = []
        
        # Navigation buttons
        keyboard.append([
            InlineKeyboardButton("◀️ Предыдущая", callback_data=f"gen_history:{gen.get('id', 1)}:prev"),
            InlineKeyboardButton("Следующая ▶️", callback_data=f"gen_history:{gen.get('id', 1)}:next")
        ])
        
        # Action buttons
        if result_urls:
            keyboard.append([
                InlineKeyboardButton("👁️ Показать результат", callback_data=f"gen_view:{gen.get('id', 1)}")
            ])
            keyboard.append([
                InlineKeyboardButton("🔄 Повторить", callback_data=f"gen_repeat:{gen.get('id', 1)}")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
        
        await query.edit_message_text(
            history_text,
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
        elif model_id == "topaz/image-upscale":
            default_params = {"upscale_factor": "1"}  # Cheapest option (1x = ≤2K)
        
        min_price = calculate_price_rub(model_id, default_params, is_admin)
        price_text = get_model_price_text(model_id, default_params, is_admin, user_id)
        
        # Check for free generations for z-image
        is_free_available = is_free_generation_available(user_id, model_id)
        remaining_free = get_user_free_generations_remaining(user_id) if model_id == FREE_MODEL_ID else 0
        
        # Calculate how many generations available
        if is_admin:
            available_count = "Безлимит"
        elif is_free_available:
            # For z-image with free generations, show free count
            available_count = f"🎁 {remaining_free} бесплатно в день"
        elif user_balance >= min_price:
            available_count = int(user_balance / min_price)
        else:
            available_count = 0
        
        # Show model info with premium formatting
        model_name = model_info.get('name', model_id)
        model_emoji = model_info.get('emoji', '🤖')
        model_desc = model_info.get('description', '')
        model_category = model_info.get('category', 'Общее')
        
        # Check if new user for hints
        is_new = is_new_user(user_id)
        
        # Premium formatted model info
        model_info_text = (
            f"✨ <b>ПРЕМИУМ МОДЕЛЬ</b> ✨\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{model_emoji} <b>{model_name}</b>\n"
            f"📁 <b>Категория:</b> {model_category}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 <b>Описание:</b>\n"
            f"<i>{model_desc}</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        # Format price text properly (remove duplicate emoji and formatting)
        price_display = price_text
        if price_text.startswith("💰"):
            price_display = price_text.replace("💰", "").strip()
        # Remove HTML tags if present but keep the content
        import re
        price_display = re.sub(r'<b>(.*?)</b>', r'\1', price_display)
        price_display = price_display.strip()
        
        model_info_text += f"💰 <b>Стоимость:</b> {price_display}\n"
        
        # Add hint for new users
        if is_new and model_id == FREE_MODEL_ID:
            model_info_text += (
                f"\n💡 <b>Отлично для начала!</b>\n"
                f"Эта модель бесплатна для первых {FREE_GENERATIONS_PER_DAY} генераций в день.\n"
                f"Просто опишите, что хотите создать, и нажмите \"Генерировать\"!\n\n"
            )
        
        if is_admin:
            model_info_text += (
                f"✅ <b>Доступ:</b> <b>Безлимит</b>\n"
                f"👑 <b>Статус:</b> Администратор\n\n"
            )
        else:
            if is_free_available:
                model_info_text += (
                    f"🎁 <b>Бесплатно:</b> {remaining_free}/{FREE_GENERATIONS_PER_DAY} в день\n"
                )
                if user_balance >= min_price:
                    paid_count = int(user_balance / min_price)
                    model_info_text += f"💳 <b>Платных:</b> {paid_count} генераций\n"
                model_info_text += f"💵 <b>Баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n\n"
            elif available_count > 0:
                model_info_text += (
                    f"✅ <b>Доступно:</b> {available_count} генераций\n"
                    f"💵 <b>Баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n\n"
                )
            else:
                # Not enough balance - show warning
                model_info_text += (
                    f"\n❌ <b>Недостаточно средств</b>\n\n"
                    f"💵 <b>Ваш баланс:</b> {format_price_rub(user_balance, is_admin)} ₽\n"
                    f"💰 <b>Требуется:</b> {format_price_rub(min_price, is_admin)} ₽\n\n"
                    f"💡 Пополните баланс для генерации"
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
        
        # Check balance before starting generation (but allow free generations)
        if not is_admin and not is_free_available and user_balance < min_price:
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
    
    # If we get here and no handler matched, log and return END
    except Exception as e:
        logger.error(f"Error in button_callback for data '{data}': {e}", exc_info=True)
        try:
            await query.answer("❌ Произошла ошибка. Попробуйте еще раз или используйте /start", show_alert=True)
        except:
            pass
        return ConversationHandler.END
    
    # Fallback - should never reach here if all handlers work correctly
    logger.warning(f"Unhandled callback data: {data} from user {user_id}")
    try:
        await query.answer("❌ Неизвестная команда. Используйте /start", show_alert=True)
    except:
        pass
    return ConversationHandler.END


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
                
                param_desc = param_info.get('description', '')
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
                    text=f"📝 <b>Выберите {param_name}:</b>\n\n{param_desc}\n\nПо умолчанию: {'Да' if default_value else 'Нет'}",
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
                
                param_desc = param_info.get('description', '')
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
                param_desc = param_info.get('description', '')
                max_length = param_info.get('max_length')
                max_text = f"\n\nМаксимум {max_length} символов." if max_length else ""
                
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
    
    # Handle broadcast message
    if user_id == ADMIN_ID and user_id in user_sessions and user_sessions[user_id].get('waiting_for') == 'broadcast_message':
        import time
        from datetime import datetime
        
        # Get message content
        message_text = None
        message_photo = None
        
        if update.message.text:
            message_text = update.message.text
        elif update.message.caption:
            message_text = update.message.caption
        
        if update.message.photo:
            message_photo = update.message.photo[-1]
        
        if not message_text and not message_photo:
            await update.message.reply_text(
                "❌ <b>Ошибка</b>\n\n"
                "Отправьте текст или изображение для рассылки.\n\n"
                "Или нажмите /cancel для отмены.",
                parse_mode='HTML'
            )
            return WAITING_BROADCAST_MESSAGE
        
        # Get all users
        all_users = get_all_users()
        total_users = len(all_users)
        
        if total_users == 0:
            await update.message.reply_text(
                "❌ <b>Нет пользователей для рассылки</b>\n\n"
                "В базе нет пользователей.",
                parse_mode='HTML'
            )
            if user_id in user_sessions:
                del user_sessions[user_id]['waiting_for']
            return ConversationHandler.END
        
        # Create broadcast record
        broadcast_data = {
            'id': len(get_broadcasts()) + 1,
            'message': message_text or '[Изображение]',
            'created_at': int(time.time()),
            'created_by': user_id,
            'total_users': total_users,
            'sent': 0,
            'delivered': 0,
            'failed': 0,
            'user_ids': []
        }
        
        broadcast_id = save_broadcast(broadcast_data)
        
        # Confirm and start sending
        await update.message.reply_text(
            f"📢 <b>Рассылка создана!</b>\n\n"
            f"👥 <b>Получателей:</b> {total_users}\n"
            f"📝 <b>Сообщение:</b> {message_text[:50] + '...' if message_text and len(message_text) > 50 else message_text or '[Изображение]'}\n\n"
            f"⏳ Начинаю отправку...",
            parse_mode='HTML'
        )
        
        # Clear waiting state
        if user_id in user_sessions:
            del user_sessions[user_id]['waiting_for']
        
        # Start broadcast in background
        asyncio.create_task(send_broadcast(context, broadcast_id, all_users, message_text, message_photo))
        
        return ConversationHandler.END
    
    # Handle payment screenshot
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
                
                await query.edit_message_text(
                    error_text,
                    parse_mode='HTML'
                )
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
        # Prepare params for API (convert image_input to appropriate parameter name if needed)
        api_params = params.copy()
        if model_id == "seedream/4.5-edit" and 'image_input' in api_params:
            # Convert image_input to image_urls for seedream/4.5-edit
            api_params['image_urls'] = api_params.pop('image_input')
        elif model_id == "kling-2.6/image-to-video" and 'image_input' in api_params:
            # Convert image_input to image_urls for kling-2.6/image-to-video
            api_params['image_urls'] = api_params.pop('image_input')
        elif model_id == "flux-2/pro-image-to-image" and 'image_input' in api_params:
            # Convert image_input to input_urls for flux-2/pro-image-to-image
            api_params['input_urls'] = api_params.pop('image_input')
        elif model_id == "flux-2/flex-image-to-image" and 'image_input' in api_params:
            # Convert image_input to input_urls for flux-2/flex-image-to-image
            api_params['input_urls'] = api_params.pop('image_input')
        elif model_id == "topaz/image-upscale" and 'image_input' in api_params:
            # Convert image_input to image_url for topaz/image-upscale (single image, not array)
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]  # Take first image
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "kling/v2-5-turbo-image-to-video-pro" and 'image_input' in api_params:
            # Convert image_input to image_url for kling/v2-5-turbo-image-to-video-pro
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]  # Take first image
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "wan/2-5-image-to-video" and 'image_input' in api_params:
            # Convert image_input to image_url for wan/2-5-image-to-video
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]  # Take first image
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "hailuo/02-image-to-video-pro" and 'image_input' in api_params:
            # Convert image_input to image_url for hailuo/02-image-to-video-pro
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]  # Take first image
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "hailuo/02-image-to-video-standard" and 'image_input' in api_params:
            # Convert image_input to image_url for hailuo/02-image-to-video-standard
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]  # Take first image
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "bytedance/seedream-v4-edit" and 'image_input' in api_params:
            # Convert image_input to image_urls for bytedance/seedream-v4-edit
            api_params['image_urls'] = api_params.pop('image_input')
        elif model_id == "topaz/video-upscale" and 'video_input' in api_params:
            # Convert video_input to video_url for topaz/video-upscale
            video_input = api_params.pop('video_input')
            if isinstance(video_input, list) and len(video_input) > 0:
                api_params['video_url'] = video_input[0]  # Take first video
            elif isinstance(video_input, str):
                api_params['video_url'] = video_input
        elif model_id == "wan/2-2-animate-move" or model_id == "wan/2-2-animate-replace":
            # Convert video_input and image_input for wan/2-2-animate models
            if 'video_input' in api_params:
                video_input = api_params.pop('video_input')
                if isinstance(video_input, list) and len(video_input) > 0:
                    api_params['video_url'] = video_input[0]
                elif isinstance(video_input, str):
                    api_params['video_url'] = video_input
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
        elif model_id == "kling/v1-avatar-standard" or model_id == "kling/ai-avatar-v1-pro":
            # Convert image_input and audio_input for kling avatar models
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
            if 'audio_input' in api_params:
                audio_input = api_params.pop('audio_input')
                if isinstance(audio_input, list) and len(audio_input) > 0:
                    api_params['audio_url'] = audio_input[0]
                elif isinstance(audio_input, str):
                    api_params['audio_url'] = audio_input
        elif model_id == "infinitalk/from-audio":
            # Convert image_input and audio_input for infinitalk/from-audio
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
            if 'audio_input' in api_params:
                audio_input = api_params.pop('audio_input')
                if isinstance(audio_input, list) and len(audio_input) > 0:
                    api_params['audio_url'] = audio_input[0]
                elif isinstance(audio_input, str):
                    api_params['audio_url'] = audio_input
        elif model_id == "recraft/remove-background" and 'image_input' in api_params:
            # Convert image_input to image for recraft/remove-background
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image'] = image_input
        elif model_id == "recraft/crisp-upscale" and 'image_input' in api_params:
            # Convert image_input to image for recraft/crisp-upscale
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image'] = image_input
        elif model_id == "ideogram/v3-reframe" and 'image_input' in api_params:
            # Convert image_input to image_url for ideogram/v3-reframe
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "ideogram/v3-edit":
            # Convert image_input and mask_input for ideogram/v3-edit
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
            if 'mask_input' in api_params:
                mask_input = api_params.pop('mask_input')
                if isinstance(mask_input, list) and len(mask_input) > 0:
                    api_params['mask_url'] = mask_input[0]
                elif isinstance(mask_input, str):
                    api_params['mask_url'] = mask_input
        elif model_id == "ideogram/v3-remix":
            # Convert image_input to image_url for ideogram/v3-remix
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
        elif model_id == "bytedance/v1-pro-fast-image-to-video":
            # Convert image_input to image_url for bytedance/v1-pro-fast-image-to-video
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
        elif model_id == "kling/v2-1-master-image-to-video" or model_id == "kling/v2-1-standard" or model_id == "kling/v2-1-pro":
            # Convert image_input to image_url for kling/v2-1 models
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
        elif model_id == "wan/2-2-a14b-image-to-video-turbo":
            # Convert image_input to image_url for wan/2-2-a14b-image-to-video-turbo
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
        elif model_id == "wan/2-2-a14b-speech-to-video-turbo":
            # Convert image_input and audio_input for wan/2-2-a14b-speech-to-video-turbo
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
            if 'audio_input' in api_params:
                audio_input = api_params.pop('audio_input')
                if isinstance(audio_input, list) and len(audio_input) > 0:
                    api_params['audio_url'] = audio_input[0]
                elif isinstance(audio_input, str):
                    api_params['audio_url'] = audio_input
        elif model_id == "qwen/image-to-image" and 'image_input' in api_params:
            # Convert image_input to image_url for qwen/image-to-image
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "qwen/image-edit" and 'image_input' in api_params:
            # Convert image_input to image_url for qwen/image-edit
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "ideogram/character-edit":
            # Convert image_input, mask_input, and reference_image_input for ideogram/character-edit
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
            if 'mask_input' in api_params:
                mask_input = api_params.pop('mask_input')
                if isinstance(mask_input, list) and len(mask_input) > 0:
                    api_params['mask_url'] = mask_input[0]
                elif isinstance(mask_input, str):
                    api_params['mask_url'] = mask_input
            if 'reference_image_input' in api_params:
                reference_image_input = api_params.pop('reference_image_input')
                if isinstance(reference_image_input, list):
                    api_params['reference_image_urls'] = reference_image_input
                elif isinstance(reference_image_input, str):
                    api_params['reference_image_urls'] = [reference_image_input]
        elif model_id == "ideogram/character-remix":
            # Convert image_input and reference_image_input for ideogram/character-remix
            if 'image_input' in api_params:
                image_input = api_params.pop('image_input')
                if isinstance(image_input, list) and len(image_input) > 0:
                    api_params['image_url'] = image_input[0]
                elif isinstance(image_input, str):
                    api_params['image_url'] = image_input
            if 'reference_image_input' in api_params:
                reference_image_input = api_params.pop('reference_image_input')
                if isinstance(reference_image_input, list):
                    api_params['reference_image_urls'] = reference_image_input
                elif isinstance(reference_image_input, str):
                    api_params['reference_image_urls'] = [reference_image_input]
        elif model_id == "ideogram/character":
            # Convert reference_image_input for ideogram/character
            if 'reference_image_input' in api_params:
                reference_image_input = api_params.pop('reference_image_input')
                if isinstance(reference_image_input, list):
                    api_params['reference_image_urls'] = reference_image_input
                elif isinstance(reference_image_input, str):
                    api_params['reference_image_urls'] = [reference_image_input]
        
        # Create task (for async models like z-image)
        result = await kie.create_task(model_id, api_params)
        
        if result.get('ok'):
            task_id = result.get('taskId')
            
            # Store task ID for polling
            session['task_id'] = task_id
            session['poll_attempts'] = 0
            session['max_poll_attempts'] = 60  # Poll for up to 5 minutes (60 * 5 seconds)
            session['is_free_generation'] = is_free  # Store if this is a free generation
            
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
                    is_free = session.get('is_free_generation', False)
                    
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
                            subtract_user_balance(user_id, price)
                
                # Task completed successfully
                result_json = status_result.get('resultJson', '{}')
                last_message = None
                try:
                    result_data = json.loads(result_json)
                    
                    # Determine if this is a video model
                    is_video_model = model_id in ['sora-2-text-to-video', 'sora-watermark-remover', 'kling-2.6/image-to-video', 'kling-2.6/text-to-video', 'kling/v2-5-turbo-text-to-video-pro', 'kling/v2-5-turbo-image-to-video-pro', 'wan/2-5-image-to-video', 'wan/2-5-text-to-video', 'wan/2-2-animate-move', 'wan/2-2-animate-replace', 'hailuo/02-text-to-video-pro', 'hailuo/02-image-to-video-pro', 'hailuo/02-text-to-video-standard', 'hailuo/02-image-to-video-standard', 'topaz/video-upscale', 'kling/v1-avatar-standard', 'kling/ai-avatar-v1-pro', 'infinitalk/from-audio', 'wan/2-2-a14b-speech-to-video-turbo', 'bytedance/v1-pro-fast-image-to-video', 'kling/v2-1-master-image-to-video', 'kling/v2-1-standard', 'kling/v2-1-pro', 'kling/v2-1-master-text-to-video', 'wan/2-2-a14b-text-to-video-turbo', 'wan/2-2-a14b-image-to-video-turbo']
                    
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
                    
                    # Save to history
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
                    
                    # Prepare buttons for last message
                    keyboard = [
                        [InlineKeyboardButton("📚 Мои генерации", callback_data="my_generations")],
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
    
    # Get user balance
    user_balance = get_user_balance(user_id)
    
    # Check if limited admin
    is_limited_admin = is_admin(user_id) and not is_main_admin
    balance_str = f"{user_balance:.2f}".rstrip('0').rstrip('.')
    
    if is_limited_admin:
        # Limited admin - show limit info
        limit = get_admin_limit(user_id)
        spent = get_admin_spent(user_id)
        remaining = get_admin_remaining(user_id)
        keyboard = [
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
        ]
        
        await update.message.reply_text(
            f'👑 <b>Админ с лимитом</b>\n\n'
            f'💳 <b>Лимит:</b> {limit:.2f} ₽\n'
            f'💸 <b>Потрачено:</b> {spent:.2f} ₽\n'
            f'✅ <b>Осталось:</b> {remaining:.2f} ₽\n\n'
            f'💰 <b>Баланс пользователя:</b> {balance_str} ₽',
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    elif is_main_admin:
        # Main admin sees both user balance and KIE credits
        try:
            result = await kie.get_credits()
            if result.get('ok'):
                credits = result.get('credits', 0)
                credits_rub = credits * CREDIT_TO_USD * USD_TO_RUB
                credits_rub_str = f"{credits_rub:.2f}".rstrip('0').rstrip('.')
                keyboard = [
                    [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
                    [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
                ]
                
                await update.message.reply_text(
                    f'💳 <b>Ваш баланс:</b> {balance_str} ₽\n\n'
                    f'🔧 <b>API баланс:</b> {credits_rub_str} ₽\n'
                    f'<i>({credits} кредитов)</i>',
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(
                    f'💳 <b>Ваш баланс:</b> {balance_str} ₽\n\n'
                    f'⚠️ API баланс недоступен',
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Error checking KIE balance: {e}")
            await update.message.reply_text(
                f'💳 <b>Ваш баланс:</b> {balance_str} ₽\n\n'
                    f'⚠️ API баланс недоступен',
                parse_mode='HTML'
            )
    else:
        # Regular user sees only their balance
        # Check for free generations
        remaining_free = get_user_free_generations_remaining(user_id)
        free_info = ""
        if remaining_free > 0:
            free_info = f"\n\n🎁 <b>Бесплатные генерации:</b> {remaining_free}/{FREE_GENERATIONS_PER_DAY} в день (модель Z-Image)"
        
        keyboard = [
            [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup_balance")],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
        ]
        
        await update.message.reply_text(
            f'💳 <b>Баланс:</b> {balance_str} ₽{free_info}\n\n'
            f'Доступно для генерации контента.',
            reply_markup=InlineKeyboardMarkup(keyboard),
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
                    response = f'Вопрос: {question}\n\nОшибка API: {kie_resp.get("error")}'
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
    global storage, kie
    
    # CRITICAL: Start HTTP server FIRST for Render port check
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health' or self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"ok","service":"telegram-bot"}')
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Suppress HTTP server logs
    
    def start_health_server():
        port = int(os.getenv('PORT', 10000))
        try:
            server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
            logger.info(f"✅ Health check server started on port {port}")
            server.serve_forever()
        except Exception as e:
            logger.error(f"❌ Failed to start health server: {e}")
            import traceback
            traceback.print_exc()
    
    # Start health check server IMMEDIATELY in background thread
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    logger.info("🚀 Health check server thread started")
    
    # Give server time to bind to port (critical for Render)
    import time
    time.sleep(2)
    logger.info("✅ Port should be open now")
    
    # Initialize storage and KIE client here (not at import time to avoid blocking)
    if storage is None:
        storage = KnowledgeStorage()
    if kie is None:
        kie = get_client()
    
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
            CallbackQueryHandler(button_callback, pattern='^gen_type:'),
            CallbackQueryHandler(button_callback, pattern='^check_balance$'),
            CallbackQueryHandler(button_callback, pattern='^help_menu$'),
            CallbackQueryHandler(button_callback, pattern='^support_contact$'),
            CallbackQueryHandler(button_callback, pattern='^select_model:'),
            CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
            CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
            CallbackQueryHandler(button_callback, pattern='^admin_search$'),
            CallbackQueryHandler(button_callback, pattern='^admin_add$'),
            CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
            CallbackQueryHandler(button_callback, pattern='^admin_broadcast$'),
            CallbackQueryHandler(button_callback, pattern='^admin_create_broadcast$'),
            CallbackQueryHandler(button_callback, pattern='^admin_broadcast_stats$'),
            CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
            CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
            CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
            CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
            CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
            CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
            CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
            CallbackQueryHandler(button_callback, pattern='^referral_info$'),
            CallbackQueryHandler(button_callback, pattern='^generate_again$'),
            CallbackQueryHandler(button_callback, pattern='^my_generations$'),
            CallbackQueryHandler(button_callback, pattern='^gen_view:'),
            CallbackQueryHandler(button_callback, pattern='^gen_repeat:'),
            CallbackQueryHandler(button_callback, pattern='^gen_history:'),
            CallbackQueryHandler(button_callback, pattern='^tutorial_start$'),
            CallbackQueryHandler(button_callback, pattern='^tutorial_step'),
            CallbackQueryHandler(button_callback, pattern='^tutorial_complete$')
        ],
        states={
            SELECTING_MODEL: [
                CallbackQueryHandler(button_callback, pattern='^select_model:'),
                CallbackQueryHandler(button_callback, pattern='^show_models$'),
                CallbackQueryHandler(button_callback, pattern='^category:'),
                CallbackQueryHandler(button_callback, pattern='^all_models$'),
                CallbackQueryHandler(button_callback, pattern='^gen_type:'),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^check_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
                CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
                CallbackQueryHandler(button_callback, pattern='^referral_info$'),
                CallbackQueryHandler(button_callback, pattern='^help_menu$'),
                CallbackQueryHandler(button_callback, pattern='^support_contact$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^my_generations$'),
                CallbackQueryHandler(button_callback, pattern='^gen_view:'),
                CallbackQueryHandler(button_callback, pattern='^gen_repeat:'),
                CallbackQueryHandler(button_callback, pattern='^gen_history:'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_start$'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_step'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_complete$'),
                CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
                CallbackQueryHandler(button_callback, pattern='^admin_search$'),
                CallbackQueryHandler(button_callback, pattern='^admin_add$'),
                CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_create_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
                CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
                CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            CONFIRMING_GENERATION: [
                CallbackQueryHandler(confirm_generation, pattern='^confirm_generate$'),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^check_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
                CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
                CallbackQueryHandler(button_callback, pattern='^referral_info$'),
                CallbackQueryHandler(button_callback, pattern='^help_menu$'),
                CallbackQueryHandler(button_callback, pattern='^support_contact$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^my_generations$'),
                CallbackQueryHandler(button_callback, pattern='^gen_view:'),
                CallbackQueryHandler(button_callback, pattern='^gen_repeat:'),
                CallbackQueryHandler(button_callback, pattern='^gen_history:'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_start$'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_step'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_complete$'),
                CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
                CallbackQueryHandler(button_callback, pattern='^admin_search$'),
                CallbackQueryHandler(button_callback, pattern='^admin_add$'),
                CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_create_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
                CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
                CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
                CallbackQueryHandler(button_callback, pattern='^select_model:'),
                CallbackQueryHandler(button_callback, pattern='^gen_type:'),
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
                CallbackQueryHandler(button_callback, pattern='^check_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
                CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
                CallbackQueryHandler(button_callback, pattern='^referral_info$'),
                CallbackQueryHandler(button_callback, pattern='^help_menu$'),
                CallbackQueryHandler(button_callback, pattern='^support_contact$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^my_generations$'),
                CallbackQueryHandler(button_callback, pattern='^gen_view:'),
                CallbackQueryHandler(button_callback, pattern='^gen_repeat:'),
                CallbackQueryHandler(button_callback, pattern='^gen_history:'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_start$'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_step'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_complete$'),
                CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
                CallbackQueryHandler(button_callback, pattern='^admin_search$'),
                CallbackQueryHandler(button_callback, pattern='^admin_add$'),
                CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_create_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
                CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
                CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
                CallbackQueryHandler(button_callback, pattern='^select_model:'),
                CallbackQueryHandler(button_callback, pattern='^gen_type:'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            SELECTING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
                CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
                CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^check_balance$'),
                CallbackQueryHandler(button_callback, pattern='^referral_info$'),
                CallbackQueryHandler(button_callback, pattern='^help_menu$'),
                CallbackQueryHandler(button_callback, pattern='^support_contact$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^my_generations$'),
                CallbackQueryHandler(button_callback, pattern='^gen_view:'),
                CallbackQueryHandler(button_callback, pattern='^gen_repeat:'),
                CallbackQueryHandler(button_callback, pattern='^gen_history:'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_start$'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_step'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_complete$'),
                CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
                CallbackQueryHandler(button_callback, pattern='^admin_search$'),
                CallbackQueryHandler(button_callback, pattern='^admin_add$'),
                CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_create_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
                CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
                CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
                CallbackQueryHandler(button_callback, pattern='^select_model:'),
                CallbackQueryHandler(button_callback, pattern='^gen_type:'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            WAITING_PAYMENT_SCREENSHOT: [
                MessageHandler(filters.PHOTO, input_parameters),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^check_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
                CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
                CallbackQueryHandler(button_callback, pattern='^referral_info$'),
                CallbackQueryHandler(button_callback, pattern='^help_menu$'),
                CallbackQueryHandler(button_callback, pattern='^support_contact$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^my_generations$'),
                CallbackQueryHandler(button_callback, pattern='^gen_view:'),
                CallbackQueryHandler(button_callback, pattern='^gen_repeat:'),
                CallbackQueryHandler(button_callback, pattern='^gen_history:'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_start$'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_step'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_complete$'),
                CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
                CallbackQueryHandler(button_callback, pattern='^admin_search$'),
                CallbackQueryHandler(button_callback, pattern='^admin_add$'),
                CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_create_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
                CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
                CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
                CallbackQueryHandler(button_callback, pattern='^select_model:'),
                CallbackQueryHandler(button_callback, pattern='^gen_type:'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            ADMIN_TEST_OCR: [
                MessageHandler(filters.PHOTO, input_parameters),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^check_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
                CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
                CallbackQueryHandler(button_callback, pattern='^referral_info$'),
                CallbackQueryHandler(button_callback, pattern='^help_menu$'),
                CallbackQueryHandler(button_callback, pattern='^support_contact$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^my_generations$'),
                CallbackQueryHandler(button_callback, pattern='^gen_view:'),
                CallbackQueryHandler(button_callback, pattern='^gen_repeat:'),
                CallbackQueryHandler(button_callback, pattern='^gen_history:'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_start$'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_step'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_complete$'),
                CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
                CallbackQueryHandler(button_callback, pattern='^admin_search$'),
                CallbackQueryHandler(button_callback, pattern='^admin_add$'),
                CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_create_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
                CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
                CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
                CallbackQueryHandler(button_callback, pattern='^select_model:'),
                CallbackQueryHandler(button_callback, pattern='^gen_type:'),
                CallbackQueryHandler(button_callback, pattern='^cancel$')
            ],
            WAITING_BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_parameters),
                MessageHandler(filters.PHOTO, input_parameters),
                CallbackQueryHandler(button_callback, pattern='^back_to_menu$'),
                CallbackQueryHandler(button_callback, pattern='^check_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_balance$'),
                CallbackQueryHandler(button_callback, pattern='^topup_amount:'),
                CallbackQueryHandler(button_callback, pattern='^topup_custom$'),
                CallbackQueryHandler(button_callback, pattern='^referral_info$'),
                CallbackQueryHandler(button_callback, pattern='^help_menu$'),
                CallbackQueryHandler(button_callback, pattern='^support_contact$'),
                CallbackQueryHandler(button_callback, pattern='^generate_again$'),
                CallbackQueryHandler(button_callback, pattern='^my_generations$'),
                CallbackQueryHandler(button_callback, pattern='^gen_view:'),
                CallbackQueryHandler(button_callback, pattern='^gen_repeat:'),
                CallbackQueryHandler(button_callback, pattern='^gen_history:'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_start$'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_step'),
                CallbackQueryHandler(button_callback, pattern='^tutorial_complete$'),
                CallbackQueryHandler(button_callback, pattern='^admin_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_settings$'),
                CallbackQueryHandler(button_callback, pattern='^admin_search$'),
                CallbackQueryHandler(button_callback, pattern='^admin_add$'),
                CallbackQueryHandler(button_callback, pattern='^admin_promocodes$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_create_broadcast$'),
                CallbackQueryHandler(button_callback, pattern='^admin_broadcast_stats$'),
                CallbackQueryHandler(button_callback, pattern='^admin_test_ocr$'),
                CallbackQueryHandler(button_callback, pattern='^admin_user_mode$'),
                CallbackQueryHandler(button_callback, pattern='^admin_back_to_admin$'),
                CallbackQueryHandler(button_callback, pattern='^select_model:'),
                CallbackQueryHandler(button_callback, pattern='^gen_type:'),
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
        if update.effective_user.id != ADMIN_ID:
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
    # Add error handler for better debugging
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a telegram message to notify the developer."""
        logger.error("Exception while handling an update:", exc_info=context.error)
        
        # Try to send error message to user if update is available
        if update and isinstance(update, Update):
            if update.callback_query:
                try:
                    await update.callback_query.answer(
                        "❌ Произошла ошибка. Попробуйте еще раз или используйте /start",
                        show_alert=True
                    )
                except:
                    pass
            elif update.message:
                try:
                    await update.message.reply_text(
                        "❌ Произошла ошибка. Попробуйте еще раз или используйте /start"
                    )
                except:
                    pass
    
    application.add_error_handler(error_handler)
    
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
    
    # HTTP server already started at the beginning of main()
    # Run the bot
    logger.info("Bot starting...")
    
    # Wait a bit to let any previous instance finish
    import time
    import asyncio
    logger.info("Waiting 5 seconds to avoid conflicts with previous instance...")
    time.sleep(5)
    
    # Try to clear pending updates manually before starting
    async def clear_updates():
        try:
            async with application:
                # Delete webhook if exists
                await application.bot.delete_webhook(drop_pending_updates=True)
                logger.info("Cleared webhook and pending updates")
        except Exception as e:
            logger.warning(f"Could not clear updates: {e}")
    
    # Run the clearing in a separate event loop
    try:
        asyncio.run(clear_updates())
    except Exception as e:
        logger.warning(f"Could not clear updates: {e}")
    
    max_retries = 5
    retry_delay = 15
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} to start bot...")
            # Drop pending updates to avoid conflicts with other bot instances
            application.run_polling(
                drop_pending_updates=True
            )
            # If we get here, bot started successfully
            break
        except Exception as e:
            error_msg = str(e)
            if "Conflict" in error_msg or "terminated by other getUpdates" in error_msg:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️  Conflict detected! Another bot instance may be running.")
                    logger.info(f"Waiting {retry_delay} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay)
                    # Try to clear updates again
                    try:
                        asyncio.run(clear_updates())
                    except:
                        pass
                    retry_delay = min(retry_delay + 5, 30)  # Increase delay but cap at 30s
                    continue
                else:
                    logger.error("❌ Conflict: Another bot instance is already running!")
                    logger.error("Please stop the other instance before starting this one.")
                    logger.error("On Render: Check if there are multiple services running with the same bot token.")
                    logger.error("Or wait a few minutes and the old instance should stop automatically.")
                    # Don't raise - let it retry on next deploy
                    time.sleep(60)  # Wait a minute before exiting
                    raise
            else:
                logger.error(f"❌ Bot crashed: {e}")
                import traceback
                traceback.print_exc()
                raise


if __name__ == '__main__':
    main()



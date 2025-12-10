"""
Скрипт для генерации полного списка доступных нейросетей с ценами
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Константы для расчета цен
CREDIT_TO_USD = 0.005  # 1 credit = $0.005
USD_TO_RUB = 6.95 / 0.09  # 1 USD = 77.2222... RUB

# Импортируем модели
from kie_models import KIE_MODELS, get_generation_types, get_models_by_generation_type

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
        base_credits = 6.5
    elif model_id == "sora-watermark-remover":
        base_credits = 10
    elif model_id == "sora-2-text-to-video":
        base_credits = 30
    elif model_id == "kling-2.6/image-to-video" or model_id == "kling-2.6/text-to-video":
        duration = params.get("duration", "5")
        sound = params.get("sound", False)
        if duration == "5":
            base_credits = 110 if sound else 55
        else:  # duration == "10"
            base_credits = 220 if sound else 110
    elif model_id == "kling/v2-5-turbo-text-to-video-pro" or model_id == "kling/v2-5-turbo-image-to-video-pro":
        duration = params.get("duration", "5")
        base_credits = 84 if duration == "10" else 42
    elif model_id == "wan/2-5-image-to-video" or model_id == "wan/2-5-text-to-video":
        duration = int(params.get("duration", "5"))
        resolution = params.get("resolution", "720p")
        base_credits = (20 if resolution == "1080p" else 12) * duration
    elif model_id == "wan/2-2-animate-move" or model_id == "wan/2-2-animate-replace":
        resolution = params.get("resolution", "480p")
        default_duration = 5
        if resolution == "720p":
            base_credits = 12.5 * default_duration
        elif resolution == "580p":
            base_credits = 9.5 * default_duration
        else:  # 480p
            base_credits = 6 * default_duration
    elif model_id == "hailuo/02-text-to-video-pro" or model_id == "hailuo/02-image-to-video-pro":
        base_credits = 57
    elif model_id == "hailuo/02-image-to-video-standard":
        resolution = params.get("resolution", "768P")
        duration = int(params.get("duration", "6"))
        base_credits = (5 if resolution == "768P" else 2) * duration
    elif model_id == "hailuo/02-text-to-video-standard":
        duration = int(params.get("duration", "6"))
        base_credits = 5 * duration
    elif model_id == "topaz/video-upscale":
        default_duration = 5
        base_credits = 12 * default_duration
    elif model_id == "kling/v1-avatar-standard":
        default_duration = 5
        base_credits = 8 * default_duration
    elif model_id == "kling/ai-avatar-v1-pro":
        default_duration = 5
        base_credits = 16 * default_duration
    elif model_id == "bytedance/seedream-v4-text-to-image" or model_id == "bytedance/seedream-v4-edit":
        max_images = params.get("max_images", 1)
        base_credits = 5 * max_images
    elif model_id == "infinitalk/from-audio":
        resolution = params.get("resolution", "480p")
        default_duration = 5
        base_credits = (12 if resolution == "720p" else 3) * default_duration
    elif model_id == "recraft/remove-background":
        base_credits = 1
    elif model_id == "recraft/crisp-upscale":
        base_credits = 0.5
    elif model_id in ["ideogram/v3-reframe", "ideogram/v3-text-to-image", "ideogram/v3-edit", "ideogram/v3-remix"]:
        rendering_speed = params.get("rendering_speed", "BALANCED")
        num_images = int(params.get("num_images", "1"))
        if rendering_speed == "TURBO":
            credits_per_image = 3.5
        elif rendering_speed == "QUALITY":
            credits_per_image = 10
        else:  # BALANCED
            credits_per_image = 7
        base_credits = credits_per_image * num_images
    elif model_id == "wan/2-2-a14b-speech-to-video-turbo":
        resolution = params.get("resolution", "480p")
        default_duration = 5
        if resolution == "720p":
            base_credits = 24 * default_duration
        elif resolution == "580p":
            base_credits = 18 * default_duration
        else:  # 480p
            base_credits = 12 * default_duration
    elif model_id in ["wan/2-2-a14b-text-to-video-turbo", "wan/2-2-a14b-image-to-video-turbo"]:
        resolution = params.get("resolution", "720p")
        default_duration = 5
        if resolution == "720p":
            base_credits = 16 * default_duration
        elif resolution == "580p":
            base_credits = 12 * default_duration
        else:  # 480p
            base_credits = 8 * default_duration
    elif model_id == "bytedance/seedream":
        base_credits = 3.5
    elif model_id == "qwen/text-to-image":
        image_size = params.get("image_size", "square_hd")
        mp_map = {
            "square": 0.26,
            "square_hd": 1.05,
            "portrait_4_3": 0.79,
            "portrait_16_9": 1.84,
            "landscape_4_3": 0.79,
            "landscape_16_9": 1.84
        }
        megapixels = mp_map.get(image_size, 1.05)
        base_credits = 4 * megapixels
    elif model_id == "qwen/image-to-image":
        base_credits = 4
    elif model_id == "qwen/image-edit":
        image_size = params.get("image_size", "landscape_4_3")
        num_images = int(params.get("num_images", "1"))
        mp_map = {
            "square": 0.26,
            "square_hd": 1.05,
            "portrait_4_3": 0.79,
            "portrait_16_9": 1.84,
            "landscape_4_3": 0.79,
            "landscape_16_9": 1.84
        }
        megapixels = mp_map.get(image_size, 0.79)
        base_credits = 6 * megapixels * num_images
    elif model_id == "google/imagen4-ultra":
        base_credits = 12
    elif model_id == "google/imagen4-fast":
        num_images = int(params.get("num_images", "1"))
        base_credits = 4 * num_images
    elif model_id == "google/imagen4":
        num_images = int(params.get("num_images", "1"))
        base_credits = 8 * num_images
    elif model_id in ["ideogram/character-edit", "ideogram/character-remix", "ideogram/character"]:
        rendering_speed = params.get("rendering_speed", "BALANCED")
        num_images = int(params.get("num_images", "1"))
        if rendering_speed == "TURBO":
            credits_per_image = 12
        elif rendering_speed == "QUALITY":
            credits_per_image = 24
        else:  # BALANCED
            credits_per_image = 18
        base_credits = credits_per_image * num_images
    elif model_id in ["flux-2/pro-image-to-image", "flux-2/pro-text-to-image"]:
        resolution = params.get("resolution", "1K")
        base_credits = 7 if resolution == "2K" else 5
    elif model_id in ["flux-2/flex-image-to-image", "flux-2/flex-text-to-image"]:
        resolution = params.get("resolution", "1K")
        base_credits = 24 if resolution == "2K" else 14
    elif model_id == "topaz/image-upscale":
        upscale_factor = params.get("upscale_factor", "2")
        if upscale_factor == "8":
            base_credits = 40
        elif upscale_factor in ["2", "4"]:
            base_credits = 20
        else:  # upscale_factor == "1"
            base_credits = 10
    elif model_id in ["bytedance/v1-lite-text-to-video", "bytedance/v1-lite-image-to-video"]:
        # ByteDance V1 Lite pricing: 8 credits per second
        default_duration = 5
        base_credits = 8 * default_duration
    elif model_id in ["bytedance/v1-pro-text-to-video", "bytedance/v1-pro-fast-image-to-video"]:
        # ByteDance V1 Pro pricing: 12 credits per second
        default_duration = 5
        base_credits = 12 * default_duration
    elif model_id in ["kling/v2-1-master-image-to-video", "kling/v2-1-master-text-to-video"]:
        # Kling V2.1 Master pricing: 20 credits per second
        default_duration = 5
        base_credits = 20 * default_duration
    elif model_id == "kling/v2-1-standard":
        # Kling V2.1 Standard pricing: 10 credits per second
        default_duration = 5
        base_credits = 10 * default_duration
    elif model_id == "kling/v2-1-pro":
        # Kling V2.1 Pro pricing: 15 credits per second
        default_duration = 5
        base_credits = 15 * default_duration
    else:
        base_credits = 1.0
    
    # Convert credits to USD, then to RUB
    price_usd = base_credits * CREDIT_TO_USD
    price_rub = price_usd * USD_TO_RUB
    
    # For regular users, multiply by 2
    if not is_admin:
        price_rub *= 2
    
    return price_rub


def get_default_params(model_id: str) -> dict:
    """Get default parameters for a model."""
    params = {}
    
    if model_id == "nano-banana-pro":
        params["resolution"] = "1K"
    elif model_id in ["seedream/4.5-text-to-image", "seedream/4.5-edit"]:
        params["quality"] = "basic"
    elif model_id in ["kling-2.6/image-to-video", "kling-2.6/text-to-video"]:
        params["duration"] = "5"
        params["sound"] = False
    elif model_id in ["kling/v2-5-turbo-text-to-video-pro", "kling/v2-5-turbo-image-to-video-pro"]:
        params["duration"] = "5"
    elif model_id in ["wan/2-5-image-to-video", "wan/2-5-text-to-video"]:
        params["duration"] = "5"
        params["resolution"] = "720p"
    elif model_id in ["wan/2-2-animate-move", "wan/2-2-animate-replace"]:
        params["resolution"] = "480p"
    elif model_id == "hailuo/02-image-to-video-standard":
        params["resolution"] = "768P"
        params["duration"] = "6"
    elif model_id == "hailuo/02-text-to-video-standard":
        params["duration"] = "6"
    elif model_id in ["ideogram/v3-reframe", "ideogram/v3-text-to-image", "ideogram/v3-edit", "ideogram/v3-remix"]:
        params["rendering_speed"] = "BALANCED"
        params["num_images"] = "1"
    elif model_id in ["ideogram/character-edit", "ideogram/character-remix", "ideogram/character"]:
        params["rendering_speed"] = "BALANCED"
        params["num_images"] = "1"
    elif model_id in ["flux-2/pro-image-to-image", "flux-2/pro-text-to-image", "flux-2/flex-image-to-image", "flux-2/flex-text-to-image"]:
        params["resolution"] = "1K"
    elif model_id == "topaz/image-upscale":
        params["upscale_factor"] = "2"
    elif model_id == "qwen/text-to-image":
        params["image_size"] = "square_hd"
    elif model_id == "qwen/image-edit":
        params["image_size"] = "landscape_4_3"
        params["num_images"] = "1"
    elif model_id in ["google/imagen4-fast", "google/imagen4"]:
        params["num_images"] = "1"
    elif model_id == "infinitalk/from-audio":
        params["resolution"] = "480p"
    elif model_id in ["wan/2-2-a14b-speech-to-video-turbo", "wan/2-2-a14b-text-to-video-turbo", "wan/2-2-a14b-image-to-video-turbo"]:
        params["resolution"] = "720p"
    elif model_id in ["bytedance/seedream-v4-text-to-image", "bytedance/seedream-v4-edit"]:
        params["max_images"] = 1
    
    return params


def generate_models_list():
    """Generate a complete list of all models with prices."""
    
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("ПОЛНЫЙ СПИСОК ДОСТУПНЫХ НЕЙРОСЕТЕЙ")
    output_lines.append("=" * 80)
    output_lines.append("")
    output_lines.append(f"Всего моделей: {len(KIE_MODELS)}")
    output_lines.append("")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    # Группируем по типам генерации
    generation_types = get_generation_types()
    
    for gen_type in generation_types:
        models = get_models_by_generation_type(gen_type)
        if not models:
            continue
        
        gen_info = {
            "text-to-video": "🎬 ГЕНЕРАЦИЯ ВИДЕО ИЗ ТЕКСТА",
            "image-to-video": "🎥 ГЕНЕРАЦИЯ ВИДЕО ИЗ ИЗОБРАЖЕНИЯ",
            "speech-to-video": "🎤 ГЕНЕРАЦИЯ ВИДЕО ИЗ АУДИО",
            "lip-sync": "👄 СИНХРОНИЗАЦИЯ ГУБ (AVATAR)",
            "text-to-image": "🖼️ ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ ИЗ ТЕКСТА",
            "image-to-image": "🔄 ТРАНСФОРМАЦИЯ ИЗОБРАЖЕНИЙ",
            "image-editing": "✏️ РЕДАКТИРОВАНИЕ ИЗОБРАЖЕНИЙ",
            "video-editing": "🎞️ РЕДАКТИРОВАНИЕ ВИДЕО"
        }
        
        output_lines.append("")
        output_lines.append("=" * 80)
        output_lines.append(gen_info.get(gen_type, gen_type.upper()))
        output_lines.append("=" * 80)
        output_lines.append("")
        
        for model in models:
            model_id = model['id']
            model_name = model['name']
            model_emoji = model.get('emoji', '🤖')
            model_desc = model.get('description', '')
            
            # Получаем дефолтные параметры
            default_params = get_default_params(model_id)
            
            # Рассчитываем цены
            price_admin = calculate_price_rub(model_id, default_params, is_admin=True)
            price_user = calculate_price_rub(model_id, default_params, is_admin=False)
            
            output_lines.append(f"{model_emoji} {model_name}")
            output_lines.append(f"   ID: {model_id}")
            output_lines.append(f"   Описание: {model_desc}")
            output_lines.append(f"   💰 Цена для админа: {price_admin:.2f} ₽")
            output_lines.append(f"   💰 Цена для пользователя: {price_user:.2f} ₽")
            
            # Добавляем информацию о параметрах, влияющих на цену
            if model_id == "nano-banana-pro":
                price_1k = calculate_price_rub(model_id, {"resolution": "1K"}, True)
                price_4k = calculate_price_rub(model_id, {"resolution": "4K"}, True)
                output_lines.append(f"   📊 Варианты: 1K/2K = {price_1k:.2f} ₽ (админ), 4K = {price_4k:.2f} ₽ (админ)")
            elif model_id in ["kling-2.6/image-to-video", "kling-2.6/text-to-video"]:
                price_5s = calculate_price_rub(model_id, {"duration": "5", "sound": False}, True)
                price_10s = calculate_price_rub(model_id, {"duration": "10", "sound": False}, True)
                price_5s_audio = calculate_price_rub(model_id, {"duration": "5", "sound": True}, True)
                price_10s_audio = calculate_price_rub(model_id, {"duration": "10", "sound": True}, True)
                output_lines.append(f"   📊 Варианты: 5с без звука = {price_5s:.2f} ₽, 10с без звука = {price_10s:.2f} ₽")
                output_lines.append(f"               5с со звуком = {price_5s_audio:.2f} ₽, 10с со звуком = {price_10s_audio:.2f} ₽")
            elif model_id in ["ideogram/v3-text-to-image", "ideogram/v3-edit", "ideogram/v3-remix"]:
                price_turbo = calculate_price_rub(model_id, {"rendering_speed": "TURBO"}, True)
                price_balanced = calculate_price_rub(model_id, {"rendering_speed": "BALANCED"}, True)
                price_quality = calculate_price_rub(model_id, {"rendering_speed": "QUALITY"}, True)
                output_lines.append(f"   📊 Варианты: TURBO = {price_turbo:.2f} ₽, BALANCED = {price_balanced:.2f} ₽, QUALITY = {price_quality:.2f} ₽ (админ)")
            
            output_lines.append("")
    
    output_lines.append("")
    output_lines.append("=" * 80)
    output_lines.append("ПРИМЕЧАНИЯ")
    output_lines.append("=" * 80)
    output_lines.append("")
    output_lines.append("• Цены указаны в рублях (₽)")
    output_lines.append("• Для пользователей цены в 2 раза выше, чем для админов")
    output_lines.append("• Админы имеют безлимитный доступ (цены указаны для справки)")
    output_lines.append("• Некоторые модели имеют переменные цены в зависимости от параметров")
    output_lines.append("• Для видео моделей цена может зависеть от длительности и разрешения")
    output_lines.append("")
    output_lines.append("=" * 80)
    
    return "\n".join(output_lines)


if __name__ == "__main__":
    try:
        content = generate_models_list()
        output_file = "СПИСОК_НЕЙРОСЕТЕЙ_И_ЦЕНЫ.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Файл '{output_file}' успешно создан!")
        print(f"📊 Всего моделей: {len(KIE_MODELS)}")
    except Exception as e:
        print(f"❌ Ошибка при создании файла: {e}")
        import traceback
        traceback.print_exc()


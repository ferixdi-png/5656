"""
Валидация входных данных для модели ideogram/v3-text-to-image
"""

def validate_ideogram_v3_text_to_image_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели ideogram/v3-text-to-image
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors)
    """
    errors = []
    
    # 1. Проверка prompt (обязательный)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 5000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка rendering_speed (опциональный, enum)
    # Модель ожидает: ["TURBO", "BALANCED", "QUALITY"]
    # Форма может передавать: "Turbo", "Balanced", "Quality"
    valid_rendering_speeds = ["TURBO", "BALANCED", "QUALITY"]
    if 'rendering_speed' in data and data['rendering_speed']:
        rendering_speed = str(data['rendering_speed']).upper()
        if rendering_speed not in valid_rendering_speeds:
            errors.append(f"[ERROR] Параметр 'rendering_speed' имеет недопустимое значение: '{data['rendering_speed']}'. Допустимые значения: {', '.join(valid_rendering_speeds)}")
    
    # 3. Проверка style (опциональный, enum)
    # Модель ожидает: ["AUTO", "GENERAL", "REALISTIC", "DESIGN"]
    # Форма может передавать: "Auto", "General", "Realistic", "Design"
    valid_styles = ["AUTO", "GENERAL", "REALISTIC", "DESIGN"]
    if 'style' in data and data['style']:
        style = str(data['style']).upper()
        if style not in valid_styles:
            errors.append(f"[ERROR] Параметр 'style' имеет недопустимое значение: '{data['style']}'. Допустимые значения: {', '.join(valid_styles)}")
    
    # 4. Проверка expand_prompt (опциональный, boolean)
    if 'expand_prompt' in data and data['expand_prompt'] is not None:
        expand_prompt = data['expand_prompt']
        if not isinstance(expand_prompt, bool):
            # Попытка конвертации строки в boolean
            if isinstance(expand_prompt, str):
                if expand_prompt.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[ERROR] Параметр 'expand_prompt' должен быть boolean (true/false), получено: {expand_prompt}")
            else:
                errors.append(f"[ERROR] Параметр 'expand_prompt' должен быть boolean, получено: {type(expand_prompt).__name__}")
    
    # 5. Проверка image_size (опциональный, enum)
    # Модель ожидает: ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
    # Форма может передавать: "Square", "Square HD", "Portrait 3:4", "Portrait 9:16", "Landscape 4:3", "Landscape 16:9"
    valid_image_sizes = ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
    # Маппинг значений формы в значения API
    image_size_mapping = {
        "square": "square",
        "square hd": "square_hd",
        "portrait 3:4": "portrait_4_3",
        "portrait 9:16": "portrait_16_9",
        "landscape 4:3": "landscape_4_3",
        "landscape 16:9": "landscape_16_9"
    }
    
    if 'image_size' in data and data['image_size']:
        image_size = str(data['image_size']).lower()
        # Нормализуем значение
        normalized_size = image_size_mapping.get(image_size, image_size.replace(" ", "_").replace(":", "_"))
        if normalized_size not in valid_image_sizes:
            errors.append(f"[ERROR] Параметр 'image_size' имеет недопустимое значение: '{data['image_size']}'. Допустимые значения: {', '.join(valid_image_sizes)}")
    
    # 6. Проверка num_images (опциональный, enum как string)
    valid_num_images = ["1", "2", "3", "4"]
    if 'num_images' in data and data['num_images']:
        num_images = str(data['num_images'])  # Модель ожидает string
        if num_images not in valid_num_images:
            errors.append(f"[ERROR] Параметр 'num_images' имеет недопустимое значение: '{num_images}'. Допустимые значения: {', '.join(valid_num_images)}")
    
    # 7. Проверка seed (опциональный, integer)
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Seed может быть любым целым числом (нет ограничений в модели)
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть целым числом, получено: {data['seed']}")
    
    # 8. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 5000)")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A cinematic photograph of a tranquil lakeside at twilight, viewed from a slight elevation. In the center, a cluster of softly glowing reeds and water lilies emit a gentle, golden light, their reflections shimmering on the calm surface. The elegant neon-style white text 'Kie.ai' hovers just above the water, subtly illuminated and harmonizing with the natural glow. Surrounding willows and drifting mist frame the scene, creating a serene yet magical atmosphere, with warm highlights contrasting against the cool blues of the evening sky.",
    "rendering_speed": "",  # Не указан - будет использован default "BALANCED"
    "style": "",  # Не указан - будет использован default "AUTO"
    "expand_prompt": None,  # Не указан - будет использован default True
    "image_size": "",  # Не указан - будет использован default "square_hd"
    "num_images": "1",  # В модели это string
    "seed": "",  # Не указан - опциональный
    "negative_prompt": ""  # Не указан - опциональный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для ideogram/v3-text-to-image")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: {test_data['prompt'][:100]}... ({len(test_data['prompt'])} символов)")
    print(f"  rendering_speed: '{test_data['rendering_speed']}' (не указан - будет использован default 'BALANCED')")
    print(f"  style: '{test_data['style']}' (не указан - будет использован default 'AUTO')")
    print(f"  expand_prompt: {test_data['expand_prompt']} (не указан - будет использован default True)")
    print(f"  image_size: '{test_data['image_size']}' (не указан - будет использован default 'square_hd')")
    print(f"  num_images: '{test_data['num_images']}'")
    print(f"  seed: '{test_data['seed']}' (не указан - опциональный)")
    print(f"  negative_prompt: '{test_data['negative_prompt']}' (не указан - опциональный)")
    print()
    
    is_valid, errors = validate_ideogram_v3_text_to_image_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        if test_data.get('rendering_speed'):
            print(f"  - rendering_speed: '{test_data['rendering_speed']}' - валидное значение [OK]")
        else:
            print(f"  - rendering_speed: не указан, будет использован default 'BALANCED' [OK]")
        if test_data.get('style'):
            print(f"  - style: '{test_data['style']}' - валидное значение [OK]")
        else:
            print(f"  - style: не указан, будет использован default 'AUTO' [OK]")
        print(f"  - expand_prompt: опциональный, не указан - будет использован default True [OK]")
        if test_data.get('image_size'):
            print(f"  - image_size: '{test_data['image_size']}' - валидное значение [OK]")
        else:
            print(f"  - image_size: не указан, будет использован default 'square_hd' [OK]")
        print(f"  - num_images: '{test_data['num_images']}' - валидное значение [OK]")
        if test_data.get('seed'):
            try:
                seed_val = int(test_data['seed'])
                print(f"  - seed: {seed_val} - валидное значение [OK]")
            except:
                print(f"  - seed: '{test_data['seed']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - seed: опциональный, не указан [OK]")
        print(f"  - negative_prompt: опциональный, не указан [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - rendering_speed влияет на цену: TURBO (3.5 кредита), BALANCED (7 кредитов), QUALITY (10 кредитов)")
        print("  - image_size имеет специальные значения: square, square_hd, portrait_4_3, portrait_16_9, landscape_4_3, landscape_16_9")
        print("  - expand_prompt (MagicPrompt) по умолчанию включен (True)")
    else:
        print("[ERROR] ОБНАРУЖЕНЫ ОШИБКИ:")
        print()
        for error in errors:
            print(f"  {error}")
    
    print()
    print("=" * 60)
    
    # Дополнительная проверка: формат для API
    print()
    print("[API] Формат данных для отправки в API:")
    api_data = {}
    
    # prompt - обязательный
    api_data['prompt'] = test_data['prompt']
    
    # rendering_speed - опциональный, но можно указать default
    if test_data.get('rendering_speed'):
        rendering_speed = str(test_data['rendering_speed']).upper()
        api_data['rendering_speed'] = rendering_speed
    else:
        api_data['rendering_speed'] = "BALANCED"  # default
    
    # style - опциональный, но можно указать default
    if test_data.get('style'):
        style = str(test_data['style']).upper()
        api_data['style'] = style
    else:
        api_data['style'] = "AUTO"  # default
    
    # expand_prompt - только если указан
    if test_data.get('expand_prompt') is not None:
        api_data['expand_prompt'] = bool(test_data['expand_prompt'])
    # Иначе не включаем (будет использован default True)
    
    # image_size - опциональный, но можно указать default
    if test_data.get('image_size'):
        image_size = str(test_data['image_size']).lower()
        # Нормализуем значение
        image_size_mapping = {
            "square": "square",
            "square hd": "square_hd",
            "portrait 3:4": "portrait_4_3",
            "portrait 9:16": "portrait_16_9",
            "landscape 4:3": "landscape_4_3",
            "landscape 16:9": "landscape_16_9"
        }
        normalized_size = image_size_mapping.get(image_size, image_size.replace(" ", "_").replace(":", "_"))
        api_data['image_size'] = normalized_size
    else:
        api_data['image_size'] = "square_hd"  # default
    
    # num_images - опциональный, но можно указать default
    if test_data.get('num_images'):
        api_data['num_images'] = test_data['num_images']
    else:
        api_data['num_images'] = "1"  # default
    
    # seed - только если указан (как integer!)
    if test_data.get('seed'):
        try:
            api_data['seed'] = int(test_data['seed'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный seed
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




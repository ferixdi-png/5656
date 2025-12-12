"""
Валидация входных данных для модели ideogram/character-remix
"""

def validate_ideogram_character_remix_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели ideogram/character-remix
    
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
    
    # 2. Проверка image_input/image_url (обязательный)
    # Модель ожидает image_input как массив, но пользователь может передать image_url
    image_input = None
    if 'image_input' in data:
        image_input = data['image_input']
    elif 'image_url' in data:
        # Конвертируем image_url в image_input (массив)
        image_input = [data['image_url']] if data['image_url'] else None
    
    if not image_input:
        errors.append("[ERROR] Параметр 'image_input' или 'image_url' обязателен и не может быть пустым")
    else:
        # Проверяем, что это массив
        if not isinstance(image_input, list):
            errors.append("[ERROR] Параметр 'image_input' должен быть массивом (списком)")
        elif len(image_input) == 0:
            errors.append("[ERROR] Параметр 'image_input' не может быть пустым массивом")
        elif len(image_input) > 1:
            errors.append("[ERROR] Параметр 'image_input' должен содержать только 1 изображение (максимум 1 элемент)")
        else:
            # Проверяем, что это строка (URL)
            if not isinstance(image_input[0], str) or not image_input[0]:
                errors.append("[ERROR] URL изображения должен быть непустой строкой")
    
    # 3. Проверка reference_image_input/reference_image_urls (обязательный)
    # Модель ожидает reference_image_input как массив, но пользователь может передать reference_image_urls
    reference_image_input = None
    if 'reference_image_input' in data:
        reference_image_input = data['reference_image_input']
    elif 'reference_image_urls' in data:
        # Конвертируем reference_image_urls в reference_image_input (массив)
        if isinstance(data['reference_image_urls'], list):
            # Берем только первый элемент (поддерживается только 1 изображение)
            reference_image_input = [data['reference_image_urls'][0]] if len(data['reference_image_urls']) > 0 and data['reference_image_urls'][0] else None
        elif data['reference_image_urls']:
            # Если это строка, конвертируем в массив
            reference_image_input = [data['reference_image_urls']]
    
    if not reference_image_input:
        errors.append("[ERROR] Параметр 'reference_image_input' или 'reference_image_urls' обязателен и не может быть пустым")
    else:
        # Проверяем, что это массив
        if not isinstance(reference_image_input, list):
            errors.append("[ERROR] Параметр 'reference_image_input' должен быть массивом (списком)")
        elif len(reference_image_input) == 0:
            errors.append("[ERROR] Параметр 'reference_image_input' не может быть пустым массивом")
        elif len(reference_image_input) > 1:
            errors.append("[WARNING] Параметр 'reference_image_input' должен содержать только 1 изображение. Остальные будут проигнорированы")
        else:
            # Проверяем, что это строка (URL)
            if not isinstance(reference_image_input[0], str) or not reference_image_input[0]:
                errors.append("[ERROR] URL референсного изображения должен быть непустой строкой")
    
    # 4. Проверка rendering_speed (опциональный, enum)
    # Модель ожидает: ["TURBO", "BALANCED", "QUALITY"]
    valid_rendering_speeds = ["TURBO", "BALANCED", "QUALITY"]
    if 'rendering_speed' in data and data['rendering_speed']:
        rendering_speed = str(data['rendering_speed']).upper()
        if rendering_speed not in valid_rendering_speeds:
            errors.append(f"[ERROR] Параметр 'rendering_speed' имеет недопустимое значение: '{data['rendering_speed']}'. Допустимые значения: {', '.join(valid_rendering_speeds)}")
    
    # 5. Проверка style (опциональный, enum)
    # Модель ожидает: ["AUTO", "REALISTIC", "FICTION"]
    valid_styles = ["AUTO", "REALISTIC", "FICTION"]
    if 'style' in data and data['style']:
        style = str(data['style']).upper()
        if style not in valid_styles:
            errors.append(f"[ERROR] Параметр 'style' имеет недопустимое значение: '{data['style']}'. Допустимые значения: {', '.join(valid_styles)}")
    
    # 6. Проверка expand_prompt (опциональный, boolean)
    if 'expand_prompt' in data and data['expand_prompt'] is not None:
        expand_prompt = data['expand_prompt']
        if not isinstance(expand_prompt, bool):
            # Попытка конвертации строки в boolean
            if isinstance(expand_prompt, str):
                if expand_prompt.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[ERROR] Параметр 'expand_prompt' должен быть boolean (true/false), получено: {expand_prompt}")
            else:
                errors.append(f"[ERROR] Параметр 'expand_prompt' должен быть boolean, получено: {type(expand_prompt).__name__}")
    
    # 7. Проверка image_size (опциональный, enum)
    # Модель ожидает: ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
    # Форма может передавать: "Square HD", "Square", "Portrait 3:4", "Portrait 9:16", "Landscape 4:3", "Landscape 16:9"
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
    
    # 8. Проверка num_images (опциональный, enum как string)
    valid_num_images = ["1", "2", "3", "4"]
    if 'num_images' in data and data['num_images']:
        num_images = str(data['num_images'])  # Модель ожидает string
        if num_images not in valid_num_images:
            errors.append(f"[ERROR] Параметр 'num_images' имеет недопустимое значение: '{num_images}'. Допустимые значения: {', '.join(valid_num_images)}")
    
    # 9. Проверка strength (опциональный, number)
    # ВАЖНО: В модели это float от 0.1 до 1 с шагом 0.1
    if 'strength' in data and data['strength']:
        try:
            # Обработка запятой как разделителя десятичных (0,8 -> 0.8)
            strength_str = str(data['strength']).replace(',', '.')
            strength = float(strength_str)
            if strength < 0.1 or strength > 1:
                errors.append(f"[ERROR] Параметр 'strength' должен быть в диапазоне от 0.1 до 1, получено: {strength}")
            else:
                # Проверяем шаг 0.1 (округление до 1 знака после запятой)
                rounded = round(strength, 1)
                if abs(strength - rounded) > 0.01:
                    errors.append(f"[WARNING] Параметр 'strength' должен иметь шаг 0.1, получено: {strength}. Будет округлено до {rounded}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'strength' должен быть числом (0.1-1), получено: {data['strength']}")
    
    # 10. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 500)")
    
    # 11. Проверка seed (опциональный, integer) - если указан в форме
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Seed может быть любым целым числом (нет ограничений в модели)
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть целым числом, получено: {data['seed']}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A fisheye lens selfie photograph taken at night on an urban street. The image is circular with a black border and shows a person wearing dark sunglasses and a black jacket, holding a silver digital camera up to capture the reflection. The background shows a row of shuttered storefronts with red neon lighting visible in the upper portion. The street is empty and dark, with street lights creating a warm glow along the sidewalk. The fisheye effect creates a curved, distorted perspective that bends the straight lines of the street and buildings. The lighting is predominantly red and dark, creating a moody urban atmosphere. The person's reflection shows long dark hair and is positioned in the center of the circular frame. Multiple storefront shutters are visible in the background, creating a repeating pattern of horizontal lines. The overall composition has a cinematic quality with strong contrast between the dark street and the illuminated storefronts above.",
    "image_url": "Upload successfully",  # Это будет URL после загрузки
    "reference_image_urls": ["File 1"],  # Массив с референсными изображениями (поддерживается только 1)
    "rendering_speed": "",  # Не указан - будет использован default "BALANCED"
    "style": "",  # Не указан - будет использован default "AUTO"
    "expand_prompt": None,  # Не указан - будет использован default True
    "image_size": "Square HD",  # Указан
    "num_images": "1",  # В модели это string
    "seed": "",  # Не указан - опциональный
    "strength": "0,8",  # Указан с запятой (нужно конвертировать в 0.8)
    "negative_prompt": ""  # Не указан - опциональный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для ideogram/character-remix")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  reference_image_urls: {test_data['reference_image_urls']}")
    print(f"  rendering_speed: '{test_data['rendering_speed']}' (не указан - будет использован default 'BALANCED')")
    print(f"  style: '{test_data['style']}' (не указан - будет использован default 'AUTO')")
    print(f"  expand_prompt: {test_data['expand_prompt']} (не указан - будет использован default True)")
    print(f"  image_size: '{test_data['image_size']}'")
    print(f"  num_images: '{test_data['num_images']}'")
    print(f"  seed: '{test_data['seed']}' (не указан - опциональный)")
    print(f"  strength: '{test_data['strength']}'")
    print(f"  negative_prompt: '{test_data['negative_prompt']}' (не указан - опциональный)")
    print()
    
    is_valid, errors = validate_ideogram_character_remix_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        print(f"  - image_url: будет конвертирован в image_input (массив) [OK]")
        print(f"  - reference_image_urls: будет конвертирован в reference_image_input (массив) [OK]")
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
            image_size_normalized = str(test_data['image_size']).lower().replace(" ", "_").replace(":", "_")
            print(f"  - image_size: '{test_data['image_size']}' -> нормализовано в '{image_size_normalized}' [OK]")
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
        if test_data.get('strength'):
            try:
                strength_str = str(test_data['strength']).replace(',', '.')
                strength_val = float(strength_str)
                print(f"  - strength: '{test_data['strength']}' -> конвертировано в {strength_val} [OK]")
            except:
                print(f"  - strength: '{test_data['strength']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - strength: опциональный, не указан [OK]")
        print(f"  - negative_prompt: опциональный, не указан [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image_input (массив с URL изображения) для ремикса")
        print("  - Требуется reference_image_input (массив с референсными изображениями, поддерживается только 1)")
        print("  - rendering_speed влияет на цену: TURBO (12 кредитов), BALANCED (18 кредитов), QUALITY (24 кредита)")
        print("  - expand_prompt (MagicPrompt) по умолчанию включен (True)")
        print("  - strength определяет силу влияния исходного изображения (0.1-1, шаг 0.1, default: 0.8)")
        print("  - Референсные изображения должны быть в формате JPEG, PNG или WebP (макс. 10MB)")
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
    
    # image_input - обязательный (конвертируем image_url в массив)
    if 'image_url' in test_data and test_data['image_url']:
        api_data['image_input'] = [test_data['image_url']]
    elif 'image_input' in test_data:
        api_data['image_input'] = test_data['image_input']
    
    # reference_image_input - обязательный (конвертируем reference_image_urls в массив)
    if 'reference_image_urls' in test_data and test_data['reference_image_urls']:
        if isinstance(test_data['reference_image_urls'], list):
            # Берем только первый элемент (поддерживается только 1 изображение)
            if len(test_data['reference_image_urls']) > 0 and test_data['reference_image_urls'][0]:
                api_data['reference_image_input'] = [test_data['reference_image_urls'][0]]
        elif test_data['reference_image_urls']:
            api_data['reference_image_input'] = [test_data['reference_image_urls']]
    elif 'reference_image_input' in test_data:
        api_data['reference_image_input'] = test_data['reference_image_input']
    
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
    
    # strength - только если указан (как number!)
    if test_data.get('strength'):
        try:
            strength_str = str(test_data['strength']).replace(',', '.')
            strength_val = float(strength_str)
            # Округляем до 1 знака после запятой (шаг 0.1)
            api_data['strength'] = round(strength_val, 1)
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный strength
    else:
        api_data['strength'] = 0.8  # default
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    
    # seed - только если указан (как integer!)
    if test_data.get('seed'):
        try:
            api_data['seed'] = int(test_data['seed'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный seed
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))





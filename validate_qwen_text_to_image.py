"""
Валидация входных данных для модели qwen/text-to-image
"""

def validate_qwen_text_to_image_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели qwen/text-to-image
    
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
    
    # 2. Проверка image_size (опциональный, enum)
    # Модель ожидает: ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
    # Форма может передавать: "Square HD", "Square", "Portrait 3:4", и т.д.
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
    
    # 3. Проверка num_inference_steps (опциональный, number)
    # ВАЖНО: В модели это integer от 2 до 250
    if 'num_inference_steps' in data and data['num_inference_steps']:
        try:
            num_inference_steps = int(data['num_inference_steps'])
            if num_inference_steps < 2 or num_inference_steps > 250:
                errors.append(f"[ERROR] Параметр 'num_inference_steps' должен быть в диапазоне от 2 до 250, получено: {num_inference_steps}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'num_inference_steps' должен быть целым числом (2-250), получено: {data['num_inference_steps']}")
    
    # 4. Проверка seed (опциональный, integer)
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Seed может быть любым целым числом (нет ограничений в модели)
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть целым числом, получено: {data['seed']}")
    
    # 5. Проверка guidance_scale (опциональный, number)
    # ВАЖНО: В модели это float от 0 до 20 с шагом 0.1
    if 'guidance_scale' in data and data['guidance_scale']:
        try:
            # Обработка запятой как разделителя десятичных (2,5 -> 2.5)
            guidance_scale_str = str(data['guidance_scale']).replace(',', '.')
            guidance_scale = float(guidance_scale_str)
            if guidance_scale < 0 or guidance_scale > 20:
                errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть в диапазоне от 0 до 20, получено: {guidance_scale}")
            else:
                # Проверяем шаг 0.1 (округление до 1 знака после запятой)
                rounded = round(guidance_scale, 1)
                if abs(guidance_scale - rounded) > 0.01:
                    errors.append(f"[WARNING] Параметр 'guidance_scale' должен иметь шаг 0.1, получено: {guidance_scale}. Будет округлено до {rounded}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть числом (0-20), получено: {data['guidance_scale']}")
    
    # 6. Проверка enable_safety_checker (опциональный, boolean)
    if 'enable_safety_checker' in data and data['enable_safety_checker'] is not None:
        enable_safety_checker = data['enable_safety_checker']
        if not isinstance(enable_safety_checker, bool):
            # Попытка конвертации строки в boolean
            if isinstance(enable_safety_checker, str):
                if enable_safety_checker.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[ERROR] Параметр 'enable_safety_checker' должен быть boolean (true/false), получено: {enable_safety_checker}")
            else:
                errors.append(f"[ERROR] Параметр 'enable_safety_checker' должен быть boolean, получено: {type(enable_safety_checker).__name__}")
    
    # 7. Проверка output_format (опциональный, enum)
    # Модель ожидает: ["png", "jpeg"] (в нижнем регистре)
    # Форма может передавать: "PNG", "JPEG"
    valid_output_formats = ["png", "jpeg"]
    if 'output_format' in data and data['output_format']:
        output_format = str(data['output_format']).strip().lower()
        # Маппинг jpg -> jpeg
        if output_format == "jpg":
            output_format = "jpeg"
        if output_format not in valid_output_formats:
            errors.append(f"[ERROR] Параметр 'output_format' имеет недопустимое значение: '{data['output_format']}'. Допустимые значения: {', '.join(valid_output_formats)}")
    
    # 8. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 500)")
    
    # 9. Проверка acceleration (опциональный, enum)
    # Модель ожидает: ["none", "regular", "high"]
    # Форма может передавать: "None", "Regular", "High"
    valid_accelerations = ["none", "regular", "high"]
    if 'acceleration' in data and data['acceleration']:
        acceleration = str(data['acceleration']).lower()
        if acceleration not in valid_accelerations:
            errors.append(f"[ERROR] Параметр 'acceleration' имеет недопустимое значение: '{data['acceleration']}'. Допустимые значения: {', '.join(valid_accelerations)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A vibrant, colorful scene at a lively amusement park during the day, featuring a cheerful young girl (around 10-12 years old) with a bright smile, wearing a colorful t-shirt and shorts, standing in the foreground. She's holding a cotton candy in one hand and pointing excitedly toward the background. Behind her, a large, eye-catching amusement park sign reads 'Kie AI' in bold, playful neon letters with a futuristic yet whimsical design, glowing in bright colors like pink, blue, and yellow. The background includes classic amusement park elements: a Ferris wheel, roller coaster tracks looping in the sky, colorful balloons, and a bustling crowd. The atmosphere is joyful, sunny, and energetic, with vivid colors and a sense of fun.",
    "image_size": "Square HD",  # Указан
    "num_inference_steps": "30",  # Указан
    "seed": "",  # Не указан - опциональный
    "guidance_scale": "2,5",  # Указан с запятой (нужно конвертировать в 2.5)
    "enable_safety_checker": None,  # Не указан - будет использован default True
    "output_format": "PNG",  # Указан
    "negative_prompt": "",  # Не указан - опциональный
    "acceleration": ""  # Не указан - будет использован default "none"
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для qwen/text-to-image")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_size: '{test_data['image_size']}'")
    print(f"  num_inference_steps: '{test_data['num_inference_steps']}'")
    print(f"  seed: '{test_data['seed']}' (не указан - опциональный)")
    print(f"  guidance_scale: '{test_data['guidance_scale']}'")
    print(f"  enable_safety_checker: {test_data['enable_safety_checker']} (не указан - будет использован default True)")
    print(f"  output_format: '{test_data['output_format']}'")
    print(f"  negative_prompt: '{test_data['negative_prompt']}' (не указан - опциональный)")
    print(f"  acceleration: '{test_data['acceleration']}' (не указан - будет использован default 'none')")
    print()
    
    is_valid, errors = validate_qwen_text_to_image_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        if test_data.get('image_size'):
            image_size_normalized = str(test_data['image_size']).lower().replace(" ", "_").replace(":", "_")
            print(f"  - image_size: '{test_data['image_size']}' -> нормализовано в '{image_size_normalized}' [OK]")
        else:
            print(f"  - image_size: опциональный, не указан - будет использован default 'square_hd' [OK]")
        if test_data.get('num_inference_steps'):
            try:
                steps_val = int(test_data['num_inference_steps'])
                print(f"  - num_inference_steps: {steps_val} - валидное значение [OK]")
            except:
                print(f"  - num_inference_steps: '{test_data['num_inference_steps']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - num_inference_steps: опциональный, не указан - будет использован default 30 [OK]")
        if test_data.get('seed'):
            try:
                seed_val = int(test_data['seed'])
                print(f"  - seed: {seed_val} - валидное значение [OK]")
            except:
                print(f"  - seed: '{test_data['seed']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - seed: опциональный, не указан [OK]")
        if test_data.get('guidance_scale'):
            try:
                guidance_str = str(test_data['guidance_scale']).replace(',', '.')
                guidance_val = float(guidance_str)
                print(f"  - guidance_scale: '{test_data['guidance_scale']}' -> конвертировано в {guidance_val} [OK]")
            except:
                print(f"  - guidance_scale: '{test_data['guidance_scale']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - guidance_scale: опциональный, не указан - будет использован default 2.5 [OK]")
        if test_data.get('enable_safety_checker') is not None:
            print(f"  - enable_safety_checker: {test_data['enable_safety_checker']} - валидное значение [OK]")
        else:
            print(f"  - enable_safety_checker: опциональный, не указан - будет использован default True [OK]")
        if test_data.get('output_format'):
            output_format_normalized = str(test_data['output_format']).strip().lower()
            if output_format_normalized == "jpg":
                output_format_normalized = "jpeg"
            print(f"  - output_format: '{test_data['output_format']}' -> нормализовано в '{output_format_normalized}' [OK]")
        else:
            print(f"  - output_format: опциональный, не указан - будет использован default 'png' [OK]")
        if test_data.get('negative_prompt'):
            print(f"  - negative_prompt: {len(test_data['negative_prompt'])} символов (лимит: 500) [OK]")
        else:
            print(f"  - negative_prompt: опциональный, не указан [OK]")
        if test_data.get('acceleration'):
            acceleration_normalized = str(test_data['acceleration']).lower()
            print(f"  - acceleration: '{test_data['acceleration']}' -> нормализовано в '{acceleration_normalized}' [OK]")
        else:
            print(f"  - acceleration: опциональный, не указан - будет использован default 'none' [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание для генерации изображения, макс. 5000 символов)")
        print("  - image_size определяет размер генерируемого изображения (default: square_hd)")
        print("  - num_inference_steps определяет качество генерации (2-250, default: 30)")
        print("  - guidance_scale определяет, насколько близко модель следует промпту (0-20, шаг 0.1, default: 2.5)")
        print("  - enable_safety_checker по умолчанию включен (True)")
        print("  - output_format определяет формат выходного изображения (png/jpeg, default: png)")
        print("  - acceleration влияет на скорость генерации: none (без ускорения), regular (баланс), high (высокая скорость, рекомендуется для изображений без текста)")
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
    
    # num_inference_steps - только если указан (как integer!)
    if test_data.get('num_inference_steps'):
        try:
            api_data['num_inference_steps'] = int(test_data['num_inference_steps'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный num_inference_steps
    else:
        api_data['num_inference_steps'] = 30  # default
    
    # seed - только если указан (как integer!)
    if test_data.get('seed'):
        try:
            api_data['seed'] = int(test_data['seed'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный seed
    
    # guidance_scale - только если указан (как number!)
    if test_data.get('guidance_scale'):
        try:
            guidance_scale_str = str(test_data['guidance_scale']).replace(',', '.')
            guidance_scale_val = float(guidance_scale_str)
            # Округляем до 1 знака после запятой (шаг 0.1)
            api_data['guidance_scale'] = round(guidance_scale_val, 1)
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный guidance_scale
    else:
        api_data['guidance_scale'] = 2.5  # default
    
    # enable_safety_checker - только если указан
    if test_data.get('enable_safety_checker') is not None:
        api_data['enable_safety_checker'] = bool(test_data['enable_safety_checker'])
    # Иначе не включаем (будет использован default True)
    
    # output_format - опциональный, но можно указать default
    if test_data.get('output_format'):
        output_format = str(test_data['output_format']).strip().lower()
        # Маппинг jpg -> jpeg
        if output_format == "jpg":
            output_format = "jpeg"
        api_data['output_format'] = output_format
    else:
        api_data['output_format'] = "png"  # default
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    
    # acceleration - опциональный, но можно указать default
    if test_data.get('acceleration'):
        acceleration = str(test_data['acceleration']).lower()
        api_data['acceleration'] = acceleration
    else:
        api_data['acceleration'] = "none"  # default
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))


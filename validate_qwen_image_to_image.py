"""
Валидация входных данных для модели qwen/image-to-image
"""

def validate_qwen_image_to_image_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели qwen/image-to-image
    
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
    
    # 3. Проверка strength (опциональный, number)
    # ВАЖНО: В модели это float от 0 до 1 с шагом 0.01
    if 'strength' in data and data['strength']:
        try:
            # Обработка запятой как разделителя десятичных (0,8 -> 0.8)
            strength_str = str(data['strength']).replace(',', '.')
            strength = float(strength_str)
            if strength < 0 or strength > 1:
                errors.append(f"[ERROR] Параметр 'strength' должен быть в диапазоне от 0 до 1, получено: {strength}")
            else:
                # Проверяем шаг 0.01 (округление до 2 знаков после запятой)
                rounded = round(strength, 2)
                if abs(strength - rounded) > 0.001:
                    errors.append(f"[WARNING] Параметр 'strength' должен иметь шаг 0.01, получено: {strength}. Будет округлено до {rounded}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'strength' должен быть числом (0-1), получено: {data['strength']}")
    
    # 4. Проверка output_format (опциональный, enum)
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
    
    # 5. Проверка acceleration (опциональный, enum)
    # Модель ожидает: ["none", "regular", "high"]
    # Форма может передавать: "None", "Regular", "High"
    valid_accelerations = ["none", "regular", "high"]
    if 'acceleration' in data and data['acceleration']:
        acceleration = str(data['acceleration']).lower()
        if acceleration not in valid_accelerations:
            errors.append(f"[ERROR] Параметр 'acceleration' имеет недопустимое значение: '{data['acceleration']}'. Допустимые значения: {', '.join(valid_accelerations)}")
    
    # 6. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 500)")
    
    # 7. Проверка seed (опциональный, integer)
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Seed может быть любым целым числом (нет ограничений в модели)
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть целым числом, получено: {data['seed']}")
    
    # 8. Проверка num_inference_steps (опциональный, number)
    # ВАЖНО: В модели это integer от 2 до 250
    if 'num_inference_steps' in data and data['num_inference_steps']:
        try:
            num_inference_steps = int(data['num_inference_steps'])
            if num_inference_steps < 2 or num_inference_steps > 250:
                errors.append(f"[ERROR] Параметр 'num_inference_steps' должен быть в диапазоне от 2 до 250, получено: {num_inference_steps}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'num_inference_steps' должен быть целым числом (2-250), получено: {data['num_inference_steps']}")
    
    # 9. Проверка guidance_scale (опциональный, number)
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
    
    # 10. Проверка enable_safety_checker (опциональный, boolean)
    if 'enable_safety_checker' in data and data['enable_safety_checker'] is not None:
        enable_safety_checker = data['enable_safety_checker']
        if not isinstance(enable_safety_checker, bool):
            # Попытка конвертации строки в boolean
            if isinstance(enable_safety_checker, str):
                if enable_safety_checker.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[ERROR] Параметр 'enable_safety_checker' должен быть boolean (true/false), получено: {enable_safety_checker}")
            else:
                errors.append(f"[ERROR] Параметр 'enable_safety_checker' должен быть boolean, получено: {type(enable_safety_checker).__name__}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Enter your image generation prompt...",  # Плейсхолдер, но обязательный
    "image_url": "Click to upload or drag and drop",  # Это будет URL после загрузки
    "strength": "0,8",  # Указан с запятой (нужно конвертировать в 0.8)
    "output_format": "PNG",  # Указан
    "acceleration": "",  # Не указан - будет использован default "none"
    "negative_prompt": "blurry, ugly",  # Указан
    "seed": "",  # Не указан - опциональный
    "num_inference_steps": "30",  # Указан
    "guidance_scale": "2,5",  # Указан с запятой (нужно конвертировать в 2.5)
    "enable_safety_checker": None  # Не указан - будет использован default True
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для qwen/image-to-image")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt']}' ({len(test_data['prompt'])} символов)")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  strength: '{test_data['strength']}'")
    print(f"  output_format: '{test_data['output_format']}'")
    print(f"  acceleration: '{test_data['acceleration']}' (не указан - будет использован default 'none')")
    print(f"  negative_prompt: '{test_data['negative_prompt']}'")
    print(f"  seed: '{test_data['seed']}' (не указан - опциональный)")
    print(f"  num_inference_steps: '{test_data['num_inference_steps']}'")
    print(f"  guidance_scale: '{test_data['guidance_scale']}'")
    print(f"  enable_safety_checker: {test_data['enable_safety_checker']} (не указан - будет использован default True)")
    print()
    
    is_valid, errors = validate_qwen_image_to_image_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        print(f"  - image_url: будет конвертирован в image_input (массив) [OK]")
        if test_data.get('strength'):
            try:
                strength_str = str(test_data['strength']).replace(',', '.')
                strength_val = float(strength_str)
                print(f"  - strength: '{test_data['strength']}' -> конвертировано в {strength_val} [OK]")
            except:
                print(f"  - strength: '{test_data['strength']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - strength: опциональный, не указан - будет использован default 0.8 [OK]")
        if test_data.get('output_format'):
            output_format_normalized = str(test_data['output_format']).strip().lower()
            if output_format_normalized == "jpg":
                output_format_normalized = "jpeg"
            print(f"  - output_format: '{test_data['output_format']}' -> нормализовано в '{output_format_normalized}' [OK]")
        else:
            print(f"  - output_format: опциональный, не указан - будет использован default 'png' [OK]")
        if test_data.get('acceleration'):
            acceleration_normalized = str(test_data['acceleration']).lower()
            print(f"  - acceleration: '{test_data['acceleration']}' -> нормализовано в '{acceleration_normalized}' [OK]")
        else:
            print(f"  - acceleration: опциональный, не указан - будет использован default 'none' [OK]")
        if test_data.get('negative_prompt'):
            print(f"  - negative_prompt: {len(test_data['negative_prompt'])} символов (лимит: 500) [OK]")
        else:
            print(f"  - negative_prompt: опциональный, не указан [OK]")
        if test_data.get('seed'):
            try:
                seed_val = int(test_data['seed'])
                print(f"  - seed: {seed_val} - валидное значение [OK]")
            except:
                print(f"  - seed: '{test_data['seed']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - seed: опциональный, не указан [OK]")
        if test_data.get('num_inference_steps'):
            try:
                steps_val = int(test_data['num_inference_steps'])
                print(f"  - num_inference_steps: {steps_val} - валидное значение [OK]")
            except:
                print(f"  - num_inference_steps: '{test_data['num_inference_steps']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - num_inference_steps: опциональный, не указан - будет использован default 30 [OK]")
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
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание для генерации изображения, макс. 5000 символов)")
        print("  - Требуется image_input (массив с URL референсного изображения, 1 изображение)")
        print("  - strength определяет силу денойзинга (0-1, шаг 0.01, default: 0.8)")
        print("  - output_format определяет формат выходного изображения (png/jpeg, default: png)")
        print("  - acceleration влияет на скорость генерации: none (без ускорения), regular (баланс), high (высокая скорость, рекомендуется для изображений без текста)")
        print("  - num_inference_steps определяет качество генерации (2-250, default: 30)")
        print("  - guidance_scale определяет, насколько близко модель следует промпту (0-20, шаг 0.1, default: 2.5)")
        print("  - enable_safety_checker по умолчанию включен (True)")
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
    
    # strength - только если указан (как number!)
    if test_data.get('strength'):
        try:
            strength_str = str(test_data['strength']).replace(',', '.')
            strength_val = float(strength_str)
            # Округляем до 2 знаков после запятой (шаг 0.01)
            api_data['strength'] = round(strength_val, 2)
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный strength
    else:
        api_data['strength'] = 0.8  # default
    
    # output_format - опциональный, но можно указать default
    if test_data.get('output_format'):
        output_format = str(test_data['output_format']).strip().lower()
        # Маппинг jpg -> jpeg
        if output_format == "jpg":
            output_format = "jpeg"
        api_data['output_format'] = output_format
    else:
        api_data['output_format'] = "png"  # default
    
    # acceleration - опциональный, но можно указать default
    if test_data.get('acceleration'):
        acceleration = str(test_data['acceleration']).lower()
        api_data['acceleration'] = acceleration
    else:
        api_data['acceleration'] = "none"  # default
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    
    # seed - только если указан (как integer!)
    if test_data.get('seed'):
        try:
            api_data['seed'] = int(test_data['seed'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный seed
    
    # num_inference_steps - только если указан (как integer!)
    if test_data.get('num_inference_steps'):
        try:
            api_data['num_inference_steps'] = int(test_data['num_inference_steps'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный num_inference_steps
    else:
        api_data['num_inference_steps'] = 30  # default
    
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
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))


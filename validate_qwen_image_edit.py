"""
Валидация входных данных для модели qwen/image-edit
"""

def validate_qwen_image_edit_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели qwen/image-edit
    
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
        if len(prompt) > 2000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 2000)")
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
    
    # 3. Проверка acceleration (опциональный, enum)
    # Модель ожидает: ["none", "regular", "high"]
    # Форма может передавать: "None", "Regular", "High"
    valid_accelerations = ["none", "regular", "high"]
    if 'acceleration' in data and data['acceleration']:
        acceleration = str(data['acceleration']).lower()
        if acceleration not in valid_accelerations:
            errors.append(f"[ERROR] Параметр 'acceleration' имеет недопустимое значение: '{data['acceleration']}'. Допустимые значения: {', '.join(valid_accelerations)}")
    
    # 4. Проверка image_size (опциональный, enum)
    # Модель ожидает: ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
    # Форма может передавать: "Landscape 4:3", "Square", "Portrait 3:4", и т.д.
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
    
    # 5. Проверка num_inference_steps (опциональный, number)
    # ВАЖНО: В модели это integer от 2 до 49
    if 'num_inference_steps' in data and data['num_inference_steps']:
        try:
            num_inference_steps = int(data['num_inference_steps'])
            if num_inference_steps < 2 or num_inference_steps > 49:
                errors.append(f"[ERROR] Параметр 'num_inference_steps' должен быть в диапазоне от 2 до 49, получено: {num_inference_steps}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'num_inference_steps' должен быть целым числом (2-49), получено: {data['num_inference_steps']}")
    
    # 6. Проверка seed (опциональный, integer)
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Seed может быть любым целым числом (нет ограничений в модели)
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть целым числом, получено: {data['seed']}")
    
    # 7. Проверка guidance_scale (опциональный, number)
    # ВАЖНО: В модели это float от 0 до 20 с шагом 0.1
    if 'guidance_scale' in data and data['guidance_scale']:
        try:
            guidance_scale = float(data['guidance_scale'])
            if guidance_scale < 0 or guidance_scale > 20:
                errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть в диапазоне от 0 до 20, получено: {guidance_scale}")
            else:
                # Проверяем шаг 0.1 (округление до 1 знака после запятой)
                rounded = round(guidance_scale, 1)
                if abs(guidance_scale - rounded) > 0.01:
                    errors.append(f"[WARNING] Параметр 'guidance_scale' должен иметь шаг 0.1, получено: {guidance_scale}. Будет округлено до {rounded}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть числом (0-20), получено: {data['guidance_scale']}")
    
    # 8. Проверка sync_mode (опциональный, boolean)
    # ПРИМЕЧАНИЕ: В описании модели sync_mode не указан, но форма может его передавать
    if 'sync_mode' in data and data['sync_mode'] is not None:
        sync_mode = data['sync_mode']
        if not isinstance(sync_mode, bool):
            # Попытка конвертации строки в boolean
            if isinstance(sync_mode, str):
                if sync_mode.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[WARNING] Параметр 'sync_mode' должен быть boolean (true/false), получено: {sync_mode}. Параметр не поддерживается моделью и будет проигнорирован")
            else:
                errors.append(f"[WARNING] Параметр 'sync_mode' должен быть boolean, получено: {type(sync_mode).__name__}. Параметр не поддерживается моделью и будет проигнорирован")
    
    # 9. Проверка num_images (опциональный, enum как string)
    valid_num_images = ["1", "2", "3", "4"]
    if 'num_images' in data and data['num_images']:
        num_images = str(data['num_images'])  # Модель ожидает string
        if num_images not in valid_num_images:
            errors.append(f"[ERROR] Параметр 'num_images' имеет недопустимое значение: '{num_images}'. Допустимые значения: {', '.join(valid_num_images)}")
    
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
    
    # 11. Проверка output_format (опциональный, enum)
    # Модель ожидает: ["jpeg", "png"]
    # Форма может передавать: "JPEG", "PNG"
    valid_output_formats = ["jpeg", "png"]
    if 'output_format' in data and data['output_format']:
        output_format = str(data['output_format']).lower()
        if output_format not in valid_output_formats:
            errors.append(f"[ERROR] Параметр 'output_format' имеет недопустимое значение: '{data['output_format']}'. Допустимые значения: {', '.join(valid_output_formats)}")
    
    # 12. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 500)")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "make the soda can a dark green and brown gradient",
    "image_url": "Upload successfully",  # Это будет URL после загрузки
    "acceleration": "",  # Не указан - будет использован default "none"
    "image_size": "Landscape 4:3",  # Указан
    "num_inference_steps": "25",  # Указан
    "seed": "",  # Не указан - опциональный
    "guidance_scale": "4",  # Указан
    "sync_mode": None,  # Не указан - опциональный (и не поддерживается моделью)
    "num_images": "1",  # В модели это string
    "enable_safety_checker": None,  # Не указан - будет использован default True
    "output_format": "JPEG",  # Указан
    "negative_prompt": "blurry, ugly"  # Указан
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для qwen/image-edit")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt']}' ({len(test_data['prompt'])} символов)")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  acceleration: '{test_data['acceleration']}' (не указан - будет использован default 'none')")
    print(f"  image_size: '{test_data['image_size']}'")
    print(f"  num_inference_steps: '{test_data['num_inference_steps']}'")
    print(f"  seed: '{test_data['seed']}' (не указан - опциональный)")
    print(f"  guidance_scale: '{test_data['guidance_scale']}'")
    print(f"  sync_mode: {test_data['sync_mode']} (не указан - опциональный, не поддерживается моделью)")
    print(f"  num_images: '{test_data['num_images']}'")
    print(f"  enable_safety_checker: {test_data['enable_safety_checker']} (не указан - будет использован default True)")
    print(f"  output_format: '{test_data['output_format']}'")
    print(f"  negative_prompt: '{test_data['negative_prompt']}'")
    print()
    
    is_valid, errors = validate_qwen_image_edit_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 2000) [OK]")
        print(f"  - image_url: будет конвертирован в image_input (массив) [OK]")
        if test_data.get('acceleration'):
            print(f"  - acceleration: '{test_data['acceleration']}' -> нормализовано в '{str(test_data['acceleration']).lower()}' [OK]")
        else:
            print(f"  - acceleration: не указан, будет использован default 'none' [OK]")
        if test_data.get('image_size'):
            image_size_normalized = str(test_data['image_size']).lower().replace(" ", "_").replace(":", "_")
            print(f"  - image_size: '{test_data['image_size']}' -> нормализовано в '{image_size_normalized}' [OK]")
        else:
            print(f"  - image_size: не указан, будет использован default 'landscape_4_3' [OK]")
        if test_data.get('num_inference_steps'):
            try:
                steps_val = int(test_data['num_inference_steps'])
                print(f"  - num_inference_steps: {steps_val} - валидное значение [OK]")
            except:
                print(f"  - num_inference_steps: '{test_data['num_inference_steps']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - num_inference_steps: опциональный, не указан [OK]")
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
                guidance_val = float(test_data['guidance_scale'])
                print(f"  - guidance_scale: {guidance_val} - валидное значение [OK]")
            except:
                print(f"  - guidance_scale: '{test_data['guidance_scale']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - guidance_scale: опциональный, не указан [OK]")
        if test_data.get('sync_mode') is not None:
            print(f"  - sync_mode: '{test_data['sync_mode']}' - параметр не поддерживается моделью, будет проигнорирован [WARNING]")
        else:
            print(f"  - sync_mode: опциональный, не указан [OK]")
        print(f"  - num_images: '{test_data['num_images']}' - валидное значение [OK]")
        if test_data.get('enable_safety_checker') is not None:
            print(f"  - enable_safety_checker: {test_data['enable_safety_checker']} - валидное значение [OK]")
        else:
            print(f"  - enable_safety_checker: опциональный, не указан - будет использован default True [OK]")
        if test_data.get('output_format'):
            output_format_normalized = str(test_data['output_format']).lower()
            print(f"  - output_format: '{test_data['output_format']}' -> нормализовано в '{output_format_normalized}' [OK]")
        else:
            print(f"  - output_format: опциональный, не указан - будет использован default 'png' [OK]")
        if test_data.get('negative_prompt'):
            print(f"  - negative_prompt: {len(test_data['negative_prompt'])} символов (лимит: 500) [OK]")
        else:
            print(f"  - negative_prompt: опциональный, не указан [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image_input (массив с URL изображения) для редактирования")
        print("  - acceleration влияет на скорость генерации: none (без ускорения), regular (баланс), high (высокая скорость)")
        print("  - num_inference_steps определяет качество генерации (2-49, default: 30)")
        print("  - guidance_scale определяет, насколько близко модель следует промпту (0-20, шаг 0.1, default: 4)")
        print("  - enable_safety_checker по умолчанию включен (True)")
        print("  - output_format определяет формат выходного изображения (jpeg/png, default: png)")
        print("  - Параметр 'sync_mode' не поддерживается моделью и будет проигнорирован, если указан")
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
    
    # acceleration - опциональный, но можно указать default
    if test_data.get('acceleration'):
        acceleration = str(test_data['acceleration']).lower()
        api_data['acceleration'] = acceleration
    else:
        api_data['acceleration'] = "none"  # default
    
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
        api_data['image_size'] = "landscape_4_3"  # default
    
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
            guidance_scale_val = float(test_data['guidance_scale'])
            # Округляем до 1 знака после запятой (шаг 0.1)
            api_data['guidance_scale'] = round(guidance_scale_val, 1)
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный guidance_scale
    else:
        api_data['guidance_scale'] = 4  # default
    
    # sync_mode - НЕ включаем, так как модель его не поддерживает
    
    # num_images - опциональный, но можно указать default
    if test_data.get('num_images'):
        api_data['num_images'] = test_data['num_images']
    else:
        api_data['num_images'] = "1"  # default
    
    # enable_safety_checker - только если указан
    if test_data.get('enable_safety_checker') is not None:
        api_data['enable_safety_checker'] = bool(test_data['enable_safety_checker'])
    # Иначе не включаем (будет использован default True)
    
    # output_format - опциональный, но можно указать default
    if test_data.get('output_format'):
        output_format = str(test_data['output_format']).lower()
        api_data['output_format'] = output_format
    else:
        api_data['output_format'] = "png"  # default
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    else:
        api_data['negative_prompt'] = " "  # default (пробел)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))


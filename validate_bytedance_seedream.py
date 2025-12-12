"""
Валидация входных данных для модели bytedance/seedream
"""

def validate_bytedance_seedream_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели bytedance/seedream
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 5000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
        elif len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 5000)")
    
    # 2. Проверка image_size (опциональный, enum)
    # Форма может передавать "Square HD", нужно нормализовать в "square_hd"
    valid_image_sizes = ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
    image_size_mapping = {
        "square hd": "square_hd",
        "squarehd": "square_hd",
        "square hd": "square_hd",
        "Square HD": "square_hd",
        "SQUARE HD": "square_hd",
        "portrait 4:3": "portrait_4_3",
        "portrait 16:9": "portrait_16_9",
        "landscape 4:3": "landscape_4_3",
        "landscape 16:9": "landscape_16_9"
    }
    
    if 'image_size' in data and data['image_size']:
        image_size = str(data['image_size']).strip()
        # Нормализуем: lowercase и заменяем пробелы/двоеточия на подчеркивания
        image_size_normalized = image_size.lower().replace(' ', '_').replace(':', '_')
        # Проверяем маппинг для специальных случаев
        if image_size in image_size_mapping:
            image_size_normalized = image_size_mapping[image_size]
        elif image_size_normalized in image_size_mapping:
            image_size_normalized = image_size_mapping[image_size_normalized]
        
        if image_size_normalized not in valid_image_sizes:
            errors.append(f"[ERROR] Параметр 'image_size' имеет недопустимое значение: '{data['image_size']}'. Допустимые значения: {', '.join(valid_image_sizes)} (или 'Square HD' для 'square_hd')")
    
    # 3. Проверка guidance_scale (опциональный, число 1-10, шаг 0.1, default: 2.5)
    # Форма может передавать "2,5" с запятой, нужно нормализовать в 2.5
    if 'guidance_scale' in data and data['guidance_scale'] is not None:
        guidance_scale = data['guidance_scale']
        try:
            # Преобразуем в float
            if isinstance(guidance_scale, str):
                guidance_scale_str = guidance_scale.strip()
                # Заменяем запятую на точку для десятичного разделителя
                if ',' in guidance_scale_str:
                    guidance_scale_str = guidance_scale_str.replace(',', '.')
                guidance_scale_float = float(guidance_scale_str)
            elif isinstance(guidance_scale, (int, float)):
                guidance_scale_float = float(guidance_scale)
            else:
                errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть числом, получено: {type(guidance_scale).__name__}")
                guidance_scale_float = None
            
            if guidance_scale_float is not None:
                if guidance_scale_float < 1 or guidance_scale_float > 10:
                    errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть в диапазоне от 1 до 10, получено: {guidance_scale_float}")
                # Проверяем, что значение соответствует шагу 0.1 (с небольшой погрешностью)
                rounded = round(guidance_scale_float * 10) / 10
                if abs(guidance_scale_float - rounded) > 0.01:
                    warnings.append(f"[WARNING] Параметр 'guidance_scale' рекомендуется использовать с шагом 0.1, получено: {guidance_scale_float}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть числом от 1 до 10, получено: {data['guidance_scale']}")
    
    # 4. Проверка enable_safety_checker (опциональный, boolean, default: True)
    if 'enable_safety_checker' in data and data['enable_safety_checker'] is not None:
        enable_safety_checker = data['enable_safety_checker']
        # Преобразуем строки "true"/"false" в boolean
        if isinstance(enable_safety_checker, str):
            enable_safety_checker_str = enable_safety_checker.strip().lower()
            if enable_safety_checker_str in ['true', '1', 'yes', 'on']:
                enable_safety_checker = True
            elif enable_safety_checker_str in ['false', '0', 'no', 'off']:
                enable_safety_checker = False
            else:
                errors.append(f"[ERROR] Параметр 'enable_safety_checker' должен быть boolean (true/false), получено: '{enable_safety_checker}'")
        elif not isinstance(enable_safety_checker, bool):
            errors.append(f"[ERROR] Параметр 'enable_safety_checker' должен быть boolean, получено: {type(enable_safety_checker).__name__}")
    
    # 5. Проверка seed (опциональный, число)
    if 'seed' in data and data['seed'] is not None:
        seed_str = str(data['seed']).strip()
        # Проверяем на placeholder
        if seed_str.lower() in ['enter number...', 'enter seed number...', 'enter seed...', '']:
            warnings.append(f"[WARNING] Параметр 'seed' содержит placeholder: '{seed_str}'. Если нужен seed, укажите число")
        else:
            try:
                seed = int(seed_str)
                # Обычно seed может быть любым целым числом, но проверим на разумные пределы
                if seed < 0 or seed > 2147483647:  # Максимальное значение для 32-bit signed int
                    warnings.append(f"[WARNING] Параметр 'seed' имеет необычное значение: {seed}. Обычно seed находится в диапазоне 0-2147483647")
            except ValueError:
                errors.append(f"[ERROR] Параметр 'seed' должен быть числом, получено: '{seed_str}'")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits() -> float:
    """
    Вычисляет цену в кредитах
    
    Returns:
        float: Цена в кредитах (фиксированная)
    """
    # 3.5 кредита за изображение (фиксированная цена, не зависит от параметров)
    return 3.5


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A 2D flat art style campsite poster with the text \"Kie AI Seedream 3.0 API\". The scene includes mountains, brown tents under a sunny sky, a rabbit, a deer, some birds, green grass, and a flowing river, all illustrated in clean vector art.",  # Обязательный
    "image_size": "Square HD",  # Опциональный (форма передает "Square HD", нужно нормализовать в "square_hd")
    "guidance_scale": "2,5",  # Опциональный (форма может передавать "2,5" с запятой, нужно нормализовать в 2.5)
    "seed": "Enter number...",  # Опциональный (может быть placeholder)
    "enable_safety_checker": True  # Опциональный (boolean, default: True)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для bytedance/seedream")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data.get('prompt', '')}' ({len(test_data.get('prompt', ''))} символов)")
    print(f"  image_size: '{test_data.get('image_size', 'square_hd')}'")
    print(f"  guidance_scale: '{test_data.get('guidance_scale', '2.5')}'")
    print(f"  seed: '{test_data.get('seed', '')}'")
    print(f"  enable_safety_checker: {test_data.get('enable_safety_checker', True)}")
    print()
    
    is_valid, errors, warnings = validate_bytedance_seedream_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        prompt = test_data.get('prompt', '')
        print(f"  - prompt: {len(prompt)} символов (лимит: до 5000) [OK]")
        
        # Обрабатываем image_size
        if 'image_size' in test_data and test_data['image_size']:
            image_size = str(test_data['image_size']).strip()
            image_size_normalized = image_size.lower().replace(' ', '_').replace(':', '_')
            if image_size == "Square HD":
                image_size_normalized = "square_hd"
            print(f"  - image_size: '{image_size}' -> нормализовано в '{image_size_normalized}' [OK]")
        else:
            print(f"  - image_size: не указан, используется значение по умолчанию 'square_hd' [OK]")
        
        # Обрабатываем guidance_scale
        if 'guidance_scale' in test_data and test_data['guidance_scale'] is not None:
            guidance_scale = test_data['guidance_scale']
            if isinstance(guidance_scale, str):
                guidance_scale_str = guidance_scale.strip().replace(',', '.')
                guidance_scale_float = float(guidance_scale_str)
            else:
                guidance_scale_float = float(guidance_scale)
            print(f"  - guidance_scale: '{test_data.get('guidance_scale', '2.5')}' -> нормализовано в {guidance_scale_float} [OK]")
        else:
            print(f"  - guidance_scale: не указан, используется значение по умолчанию 2.5 [OK]")
        
        # Обрабатываем enable_safety_checker
        if 'enable_safety_checker' in test_data and test_data['enable_safety_checker'] is not None:
            enable_safety_checker = test_data['enable_safety_checker']
            if isinstance(enable_safety_checker, str):
                enable_safety_checker = enable_safety_checker.strip().lower() in ['true', '1', 'yes', 'on']
            print(f"  - enable_safety_checker: {test_data.get('enable_safety_checker', True)} -> нормализовано в {enable_safety_checker} [OK]")
        else:
            print(f"  - enable_safety_checker: не указан, используется значение по умолчанию True [OK]")
        
        # Обрабатываем seed
        if 'seed' in test_data and test_data['seed']:
            seed_str = str(test_data['seed']).strip()
            if seed_str.lower() in ['enter number...', 'enter seed number...', 'enter seed...', '']:
                print(f"  - seed: '{seed_str}' (placeholder, опциональный) [WARNING]")
            else:
                try:
                    seed = int(seed_str)
                    print(f"  - seed: '{seed_str}' -> нормализовано в {seed} [OK]")
                except ValueError:
                    print(f"  - seed: '{seed_str}' [ERROR]")
        else:
            print(f"  - seed: не указан (опциональный) [OK]")
        
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание для генерации изображения, до 5000 символов)")
        print("  - Опционально image_size (размер изображения, соотношение сторон, по умолчанию 'square_hd')")
        print("  - Опционально guidance_scale (контроль соответствия промпту: 1-10, шаг 0.1, по умолчанию 2.5)")
        print("  - Опционально enable_safety_checker (включение проверщика безопасности, по умолчанию True)")
        print("  - Опционально seed (случайное число для контроля генерации)")
        print("  - Цена фиксированная: 3.5 кредита за изображение (не зависит от параметров)")
        print()
        print("[PRICING] Ценообразование:")
        price = calculate_price_credits()
        print(f"  - Цена: {price} кредитов")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * prompt не влияет на цену")
        print(f"    * image_size не влияет на цену")
        print(f"    * guidance_scale не влияет на цену")
        print(f"    * enable_safety_checker не влияет на цену")
        print(f"    * seed не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Цена: 3.5 кредита за изображение (фиксированная)")
        print("    * Цена не зависит от разрешения или других параметров")
        print("    * Все параметры влияют только на качество и стиль генерации, но не на цену")
    else:
        print("[ERROR] ОБНАРУЖЕНЫ ОШИБКИ:")
        print()
        for error in errors:
            print(f"  {error}")
        if warnings:
            print()
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
    
    print()
    print("=" * 60)
    
    # Дополнительная проверка: формат для API
    print()
    print("[API] Формат данных для отправки в API:")
    api_data = {}
    
    # prompt - обязательный
    prompt = test_data.get('prompt', '')
    if prompt:
        api_data['prompt'] = prompt
    
    # image_size - опциональный (нормализуем)
    if 'image_size' in test_data and test_data['image_size']:
        image_size = str(test_data['image_size']).strip()
        image_size_normalized = image_size.lower().replace(' ', '_').replace(':', '_')
        if image_size == "Square HD":
            image_size_normalized = "square_hd"
        valid_image_sizes = ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
        if image_size_normalized in valid_image_sizes:
            api_data['image_size'] = image_size_normalized
    
    # guidance_scale - опциональный (нормализуем, заменяем запятую на точку)
    if 'guidance_scale' in test_data and test_data['guidance_scale'] is not None:
        guidance_scale = test_data['guidance_scale']
        try:
            if isinstance(guidance_scale, str):
                guidance_scale_str = guidance_scale.strip().replace(',', '.')
                guidance_scale_float = float(guidance_scale_str)
            else:
                guidance_scale_float = float(guidance_scale)
            if 1 <= guidance_scale_float <= 10:
                api_data['guidance_scale'] = guidance_scale_float
        except (ValueError, TypeError):
            pass
    
    # enable_safety_checker - опциональный (преобразуем в boolean)
    if 'enable_safety_checker' in test_data and test_data['enable_safety_checker'] is not None:
        enable_safety_checker = test_data['enable_safety_checker']
        if isinstance(enable_safety_checker, str):
            enable_safety_checker = enable_safety_checker.strip().lower() in ['true', '1', 'yes', 'on']
        if isinstance(enable_safety_checker, bool):
            api_data['enable_safety_checker'] = enable_safety_checker
    
    # seed - опциональный (преобразуем в число, если не placeholder)
    if 'seed' in test_data and test_data['seed']:
        seed_str = str(test_data['seed']).strip()
        if seed_str.lower() not in ['enter number...', 'enter seed number...', 'enter seed...', '']:
            try:
                seed = int(seed_str)
                api_data['seed'] = seed
            except ValueError:
                pass
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))





"""
Валидация входных данных для модели bytedance/seedream-v4-text-to-image
"""

def validate_bytedance_seedream_v4_text_to_image_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели bytedance/seedream-v4-text-to-image
    
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
    valid_image_sizes = ["square", "square_hd", "portrait_4_3", "portrait_3_2", "portrait_16_9", 
                         "landscape_4_3", "landscape_3_2", "landscape_16_9", "landscape_21_9"]
    image_size_mapping = {
        "square hd": "square_hd",
        "squarehd": "square_hd",
        "square hd": "square_hd",
        "Square HD": "square_hd",
        "SQUARE HD": "square_hd",
        "portrait 4:3": "portrait_4_3",
        "portrait 3:2": "portrait_3_2",
        "portrait 16:9": "portrait_16_9",
        "landscape 4:3": "landscape_4_3",
        "landscape 3:2": "landscape_3_2",
        "landscape 16:9": "landscape_16_9",
        "landscape 21:9": "landscape_21_9"
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
    
    # 3. Проверка image_resolution (опциональный, enum: "1K", "2K", "4K")
    valid_resolutions = ["1K", "2K", "4K"]
    
    if 'image_resolution' in data and data['image_resolution']:
        image_resolution = str(data['image_resolution']).strip().upper()
        # Убеждаемся, что есть суффикс "K"
        if not image_resolution.endswith('K'):
            # Пытаемся добавить "K" если это просто число
            try:
                num = int(image_resolution)
                image_resolution = f"{num}K"
            except ValueError:
                pass
        
        if image_resolution not in valid_resolutions:
            errors.append(f"[ERROR] Параметр 'image_resolution' имеет недопустимое значение: '{data['image_resolution']}'. Допустимые значения: {', '.join(valid_resolutions)}")
    
    # 4. Проверка max_images (опциональный, число 1-6)
    if 'max_images' in data and data['max_images'] is not None:
        try:
            max_images = int(data['max_images'])
            if max_images < 1 or max_images > 6:
                errors.append(f"[ERROR] Параметр 'max_images' должен быть в диапазоне от 1 до 6, получено: {max_images}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'max_images' должен быть числом от 1 до 6, получено: {data['max_images']}")
    
    # 5. Проверка seed (опциональный, число)
    if 'seed' in data and data['seed'] is not None:
        seed_str = str(data['seed']).strip()
        # Проверяем на placeholder
        if seed_str.lower() in ['enter seed number...', 'enter seed...', '']:
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


def calculate_price_credits(max_images: int = 1) -> int:
    """
    Вычисляет цену в кредитах на основе количества изображений
    
    Args:
        max_images: Количество изображений (1-6)
        
    Returns:
        int: Цена в кредитах
    """
    # Ограничиваем до 6 изображений
    if max_images > 6:
        max_images = 6
    if max_images < 1:
        max_images = 1
    
    # 5 кредитов за изображение
    return 5 * max_images


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Draw the following system of binary linear equations and the corresponding solution steps on the blackboard: 5x + 2y = 26; 2x -y = 5.",  # Обязательный
    "image_size": "Square HD",  # Опциональный (форма передает "Square HD", нужно нормализовать в "square_hd")
    "image_resolution": "1K",  # Опциональный (enum: "1K", "2K", "4K")
    "max_images": "1",  # Опциональный (число 1-6, может быть строкой)
    "seed": "Enter seed number..."  # Опциональный (может быть placeholder)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для bytedance/seedream-v4-text-to-image")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data.get('prompt', '')}' ({len(test_data.get('prompt', ''))} символов)")
    print(f"  image_size: '{test_data.get('image_size', 'square_hd')}'")
    print(f"  image_resolution: '{test_data.get('image_resolution', '1K')}'")
    print(f"  max_images: '{test_data.get('max_images', '1')}'")
    print(f"  seed: '{test_data.get('seed', '')}'")
    print()
    
    is_valid, errors, warnings = validate_bytedance_seedream_v4_text_to_image_input(test_data)
    
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
        
        # Обрабатываем image_resolution
        if 'image_resolution' in test_data and test_data['image_resolution']:
            image_resolution = str(test_data['image_resolution']).strip().upper()
            if not image_resolution.endswith('K'):
                try:
                    num = int(image_resolution)
                    image_resolution = f"{num}K"
                except ValueError:
                    pass
            print(f"  - image_resolution: '{test_data.get('image_resolution', '1K')}' -> нормализовано в '{image_resolution}' [OK]")
        else:
            print(f"  - image_resolution: не указан, используется значение по умолчанию '1K' [OK]")
        
        # Обрабатываем max_images
        if 'max_images' in test_data and test_data['max_images'] is not None:
            try:
                max_images = int(test_data['max_images'])
                print(f"  - max_images: '{test_data.get('max_images', '1')}' -> нормализовано в {max_images} [OK]")
            except (ValueError, TypeError):
                print(f"  - max_images: '{test_data.get('max_images', '1')}' [ERROR]")
        else:
            print(f"  - max_images: не указан, используется значение по умолчанию 1 [OK]")
        
        # Обрабатываем seed
        if 'seed' in test_data and test_data['seed']:
            seed_str = str(test_data['seed']).strip()
            if seed_str.lower() in ['enter seed number...', 'enter seed...', '']:
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
        print("  - Опционально image_resolution (разрешение: 1K, 2K, 4K, по умолчанию '1K')")
        print("  - Опционально max_images (количество изображений: 1-6, по умолчанию 1)")
        print("  - Опционально seed (случайное число для контроля генерации)")
        print("  - Цена не зависит от разрешения, определяется только количеством изображений")
        print()
        print("[PRICING] Ценообразование:")
        max_images = int(test_data.get('max_images', 1)) if test_data.get('max_images') else 1
        price = calculate_price_credits(max_images)
        print(f"  - Цена (для {max_images} изображения/изображений): {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * max_images (5 кредитов за изображение, 1-6 изображений)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * prompt не влияет на цену")
        print(f"    * image_size не влияет на цену")
        print(f"    * image_resolution не влияет на цену")
        print(f"    * seed не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Цена: 5 кредитов за изображение")
        print("    * Цена не зависит от разрешения (image_size и image_resolution)")
        print("    * Примеры:")
        print("      * 1 изображение: 5 кредитов (5 кредитов × 1)")
        print("      * 2 изображения: 10 кредитов (5 кредитов × 2)")
        print("      * 3 изображения: 15 кредитов (5 кредитов × 3)")
        print("      * 6 изображений: 30 кредитов (5 кредитов × 6)")
        print("    * Важно: max_images должно совпадать с количеством изображений, указанным в промпте")
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
        valid_image_sizes = ["square", "square_hd", "portrait_4_3", "portrait_3_2", "portrait_16_9", 
                             "landscape_4_3", "landscape_3_2", "landscape_16_9", "landscape_21_9"]
        if image_size_normalized in valid_image_sizes:
            api_data['image_size'] = image_size_normalized
    
    # image_resolution - опциональный (нормализуем)
    if 'image_resolution' in test_data and test_data['image_resolution']:
        image_resolution = str(test_data['image_resolution']).strip().upper()
        if not image_resolution.endswith('K'):
            try:
                num = int(image_resolution)
                image_resolution = f"{num}K"
            except ValueError:
                pass
        if image_resolution in ["1K", "2K", "4K"]:
            api_data['image_resolution'] = image_resolution
    
    # max_images - опциональный (преобразуем в число)
    if 'max_images' in test_data and test_data['max_images'] is not None:
        try:
            max_images = int(test_data['max_images'])
            if 1 <= max_images <= 6:
                api_data['max_images'] = max_images
        except (ValueError, TypeError):
            pass
    
    # seed - опциональный (преобразуем в число, если не placeholder)
    if 'seed' in test_data and test_data['seed']:
        seed_str = str(test_data['seed']).strip()
        if seed_str.lower() not in ['enter seed number...', 'enter seed...', '']:
            try:
                seed = int(seed_str)
                api_data['seed'] = seed
            except ValueError:
                pass
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




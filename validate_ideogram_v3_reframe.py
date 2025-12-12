"""
Валидация входных данных для модели ideogram/v3-reframe
"""

def validate_ideogram_v3_reframe_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели ideogram/v3-reframe
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка image_url или image_input (обязательный, один URL)
    # Форма может передавать image_url, но API ожидает image_input (массив) или image_url
    image_url = None
    if 'image_url' in data and data['image_url']:
        image_url = str(data['image_url']).strip()
        # Проверяем на placeholder
        if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
            warnings.append(f"[WARNING] Параметр 'image_url' содержит placeholder: '{image_url}'. Убедитесь, что это валидный URL изображения")
    elif 'image_input' in data and data['image_input']:
        # Если передан image_input (массив или строка)
        image_input = data['image_input']
        if isinstance(image_input, list):
            if len(image_input) == 0:
                errors.append("[ERROR] Параметр 'image_input' не может быть пустым массивом")
            elif len(image_input) > 1:
                errors.append(f"[ERROR] Параметр 'image_input' должен содержать только 1 URL, получено: {len(image_input)}")
            else:
                image_url = str(image_input[0]).strip()
                if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
                    warnings.append(f"[WARNING] Параметр 'image_input' содержит placeholder: '{image_url}'. Убедитесь, что это валидный URL изображения")
        elif isinstance(image_input, str):
            image_url = image_input.strip()
            if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
                warnings.append(f"[WARNING] Параметр 'image_input' содержит placeholder: '{image_url}'. Убедитесь, что это валидный URL изображения")
        else:
            errors.append(f"[ERROR] Параметр 'image_input' должен быть строкой или массивом строк, получено: {type(image_input).__name__}")
    else:
        errors.append("[ERROR] Параметр 'image_url' или 'image_input' обязателен и не может быть пустым")
    
    # 2. Проверка image_size (обязательный, enum)
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
    
    if 'image_size' not in data or not data['image_size']:
        errors.append("[ERROR] Параметр 'image_size' обязателен и не может быть пустым")
    else:
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
    
    # 3. Проверка rendering_speed (опциональный, enum: "TURBO", "BALANCED", "QUALITY", default: "BALANCED")
    # Форма может передавать "Turbo", "Balanced", "Quality" -> нужно нормализовать в uppercase
    valid_rendering_speeds = ["TURBO", "BALANCED", "QUALITY"]
    rendering_speed_mapping = {
        "turbo": "TURBO",
        "balanced": "BALANCED",
        "quality": "QUALITY",
        "Turbo": "TURBO",
        "Balanced": "BALANCED",
        "Quality": "QUALITY"
    }
    
    if 'rendering_speed' in data and data['rendering_speed']:
        rendering_speed = str(data['rendering_speed']).strip()
        rendering_speed_upper = rendering_speed.upper()
        
        # Проверяем маппинг
        if rendering_speed in rendering_speed_mapping:
            rendering_speed_normalized = rendering_speed_mapping[rendering_speed]
        elif rendering_speed_upper in rendering_speed_mapping:
            rendering_speed_normalized = rendering_speed_mapping[rendering_speed_upper]
        elif rendering_speed_upper in valid_rendering_speeds:
            rendering_speed_normalized = rendering_speed_upper
        else:
            errors.append(f"[ERROR] Параметр 'rendering_speed' имеет недопустимое значение: '{data['rendering_speed']}'. Допустимые значения: {', '.join(valid_rendering_speeds)} (или 'Turbo', 'Balanced', 'Quality')")
    
    # 4. Проверка style (опциональный, enum: "AUTO", "GENERAL", "REALISTIC", "DESIGN", default: "AUTO")
    # Форма может передавать "Auto", "General", "Realistic", "Design" -> нужно нормализовать в uppercase
    valid_styles = ["AUTO", "GENERAL", "REALISTIC", "DESIGN"]
    style_mapping = {
        "auto": "AUTO",
        "general": "GENERAL",
        "realistic": "REALISTIC",
        "design": "DESIGN",
        "Auto": "AUTO",
        "General": "GENERAL",
        "Realistic": "REALISTIC",
        "Design": "DESIGN"
    }
    
    if 'style' in data and data['style']:
        style = str(data['style']).strip()
        style_upper = style.upper()
        
        # Проверяем маппинг
        if style in style_mapping:
            style_normalized = style_mapping[style]
        elif style_upper in style_mapping:
            style_normalized = style_mapping[style_upper]
        elif style_upper in valid_styles:
            style_normalized = style_upper
        else:
            errors.append(f"[ERROR] Параметр 'style' имеет недопустимое значение: '{data['style']}'. Допустимые значения: {', '.join(valid_styles)} (или 'Auto', 'General', 'Realistic', 'Design')")
    
    # 5. Проверка num_images (опциональный, число 1-4, default: 1)
    if 'num_images' in data and data['num_images'] is not None:
        try:
            num_images = int(data['num_images'])
            if num_images < 1 or num_images > 4:
                errors.append(f"[ERROR] Параметр 'num_images' должен быть в диапазоне от 1 до 4, получено: {num_images}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'num_images' должен быть числом от 1 до 4, получено: {data['num_images']}")
    
    # 6. Проверка seed (опциональный, число)
    if 'seed' in data and data['seed'] is not None:
        try:
            seed = int(data['seed'])
            # Обычно seed может быть любым целым числом, но проверим на разумные пределы
            if seed < 0 or seed > 2147483647:  # Максимальное значение для 32-bit signed int
                warnings.append(f"[WARNING] Параметр 'seed' имеет необычное значение: {seed}. Обычно seed находится в диапазоне 0-2147483647")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть числом, получено: '{data['seed']}'")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(rendering_speed: str = "BALANCED", num_images: int = 1) -> float:
    """
    Вычисляет цену в кредитах на основе rendering_speed и num_images
    
    Args:
        rendering_speed: Скорость рендеринга ("TURBO", "BALANCED", "QUALITY")
        num_images: Количество изображений (1-4)
        
    Returns:
        float: Цена в кредитах
    """
    # Нормализуем rendering_speed
    rendering_speed = str(rendering_speed).strip().upper()
    if rendering_speed == "TURBO":
        credits_per_image = 3.5
    elif rendering_speed == "QUALITY":
        credits_per_image = 10.0
    else:  # BALANCED (по умолчанию)
        credits_per_image = 7.0
    
    # Ограничиваем num_images
    if num_images < 1:
        num_images = 1
    if num_images > 4:
        num_images = 4
    
    return credits_per_image * num_images


# Тестовые данные из запроса пользователя
test_data = {
    "image_url": "Upload successfully",  # Обязательный (форма передает image_url, но может быть placeholder)
    "image_size": "Square HD",  # Обязательный (форма передает "Square HD", нужно нормализовать в "square_hd")
    "rendering_speed": "Turbo",  # Опциональный (форма передает "Turbo", нужно нормализовать в "TURBO")
    "style": "Auto",  # Опциональный (форма передает "Auto", нужно нормализовать в "AUTO")
    "num_images": "1",  # Опциональный (число 1-4, может быть строкой, default: 1)
    "seed": "0"  # Опциональный (число)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для ideogram/v3-reframe")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    # Проверяем image_url или image_input
    if 'image_url' in test_data:
        print(f"  image_url: '{test_data['image_url']}'")
    elif 'image_input' in test_data:
        print(f"  image_input: {test_data['image_input']}")
    print(f"  image_size: '{test_data.get('image_size', 'square_hd')}'")
    print(f"  rendering_speed: '{test_data.get('rendering_speed', 'BALANCED')}'")
    print(f"  style: '{test_data.get('style', 'AUTO')}'")
    print(f"  num_images: '{test_data.get('num_images', '1')}'")
    print(f"  seed: '{test_data.get('seed', '')}'")
    print()
    
    is_valid, errors, warnings = validate_ideogram_v3_reframe_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        # Обрабатываем image_url или image_input
        if 'image_url' in test_data:
            image_url = str(test_data['image_url']).strip()
            if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - image_url: '{image_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - image_url: '{image_url}' [OK]")
        elif 'image_input' in test_data:
            image_input = test_data['image_input']
            if isinstance(image_input, list) and len(image_input) > 0:
                image_url = str(image_input[0]).strip()
            else:
                image_url = str(image_input).strip()
            if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - image_input: '{image_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - image_input: '{image_url}' [OK]")
        
        # Обрабатываем image_size
        if 'image_size' in test_data and test_data['image_size']:
            image_size = str(test_data['image_size']).strip()
            image_size_normalized = image_size.lower().replace(' ', '_').replace(':', '_')
            if image_size == "Square HD":
                image_size_normalized = "square_hd"
            print(f"  - image_size: '{image_size}' -> нормализовано в '{image_size_normalized}' [OK]")
        else:
            print(f"  - image_size: не указан, используется значение по умолчанию 'square_hd' [OK]")
        
        # Обрабатываем rendering_speed
        if 'rendering_speed' in test_data and test_data['rendering_speed']:
            rendering_speed = str(test_data['rendering_speed']).strip()
            rendering_speed_normalized = rendering_speed.upper()
            if rendering_speed == "Turbo":
                rendering_speed_normalized = "TURBO"
            elif rendering_speed == "Balanced":
                rendering_speed_normalized = "BALANCED"
            elif rendering_speed == "Quality":
                rendering_speed_normalized = "QUALITY"
            print(f"  - rendering_speed: '{rendering_speed}' -> нормализовано в '{rendering_speed_normalized}' [OK]")
        else:
            print(f"  - rendering_speed: не указан, используется значение по умолчанию 'BALANCED' [OK]")
        
        # Обрабатываем style
        if 'style' in test_data and test_data['style']:
            style = str(test_data['style']).strip()
            style_normalized = style.upper()
            if style == "Auto":
                style_normalized = "AUTO"
            elif style == "General":
                style_normalized = "GENERAL"
            elif style == "Realistic":
                style_normalized = "REALISTIC"
            elif style == "Design":
                style_normalized = "DESIGN"
            print(f"  - style: '{style}' -> нормализовано в '{style_normalized}' [OK]")
        else:
            print(f"  - style: не указан, используется значение по умолчанию 'AUTO' [OK]")
        
        # Обрабатываем num_images
        if 'num_images' in test_data and test_data['num_images'] is not None:
            try:
                num_images = int(test_data['num_images'])
                print(f"  - num_images: '{test_data.get('num_images', '1')}' -> нормализовано в {num_images} [OK]")
            except (ValueError, TypeError):
                print(f"  - num_images: '{test_data.get('num_images', '1')}' [ERROR]")
        else:
            print(f"  - num_images: не указан, используется значение по умолчанию 1 [OK]")
        
        # Обрабатываем seed
        if 'seed' in test_data and test_data['seed'] is not None:
            try:
                seed = int(test_data['seed'])
                print(f"  - seed: '{test_data.get('seed', '')}' -> нормализовано в {seed} [OK]")
            except ValueError:
                print(f"  - seed: '{test_data.get('seed', '')}' [ERROR]")
        else:
            print(f"  - seed: не указан (опциональный) [OK]")
        
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image_url или image_input (URL изображения для изменения кадра, 1 изображение)")
        print("  - Требуется image_size (разрешение для рефреймированного изображения, по умолчанию 'square_hd')")
        print("  - Опционально rendering_speed (скорость рендеринга: TURBO, BALANCED, QUALITY, по умолчанию 'BALANCED')")
        print("  - Опционально style (тип стиля: AUTO, GENERAL, REALISTIC, DESIGN, по умолчанию 'AUTO')")
        print("  - Опционально num_images (количество изображений: 1-4, по умолчанию 1)")
        print("  - Опционально seed (случайное число для контроля генерации)")
        print("  - Цена зависит от rendering_speed и num_images")
        print()
        print("[PRICING] Ценообразование:")
        rendering_speed = str(test_data.get('rendering_speed', 'BALANCED')).strip().upper()
        if rendering_speed == "TURBO":
            rendering_speed_normalized = "TURBO"
        elif rendering_speed == "QUALITY":
            rendering_speed_normalized = "QUALITY"
        else:
            rendering_speed_normalized = "BALANCED"
        num_images = int(test_data.get('num_images', 1)) if test_data.get('num_images') else 1
        price = calculate_price_credits(rendering_speed_normalized, num_images)
        print(f"  - Цена (для {num_images} изображения/изображений, {rendering_speed_normalized}): {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * rendering_speed (TURBO: 3.5 кредита/изображение, BALANCED: 7 кредитов/изображение, QUALITY: 10 кредитов/изображение)")
        print(f"    * num_images (цена умножается на количество изображений)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * image_url/image_input не влияет на цену")
        print(f"    * image_size не влияет на цену")
        print(f"    * style не влияет на цену")
        print(f"    * seed не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Цена зависит от rendering_speed и num_images")
        print("    * Таблица цен за изображение:")
        print("      * TURBO: 3.5 кредита за изображение")
        print("      * BALANCED: 7 кредитов за изображение")
        print("      * QUALITY: 10 кредитов за изображение")
        print("    * Примеры:")
        print("      * 1 изображение, TURBO: 3.5 кредитов (3.5 × 1)")
        print("      * 1 изображение, BALANCED: 7 кредитов (7 × 1)")
        print("      * 1 изображение, QUALITY: 10 кредитов (10 × 1)")
        print("      * 2 изображения, TURBO: 7 кредитов (3.5 × 2)")
        print("      * 2 изображения, BALANCED: 14 кредитов (7 × 2)")
        print("      * 2 изображения, QUALITY: 20 кредитов (10 × 2)")
        print("      * 4 изображения, TURBO: 14 кредитов (3.5 × 4)")
        print("      * 4 изображения, BALANCED: 28 кредитов (7 × 4)")
        print("      * 4 изображения, QUALITY: 40 кредитов (10 × 4)")
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
    
    # image_url или image_input - обязательный
    # API ожидает image_url (строка) или image_input (массив)
    if 'image_url' in test_data:
        image_url = str(test_data['image_url']).strip()
        if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
            api_data['image_url'] = image_url
    elif 'image_input' in test_data:
        image_input = test_data['image_input']
        if isinstance(image_input, list):
            if len(image_input) > 0:
                image_url = str(image_input[0]).strip()
                if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                    api_data['image_url'] = image_url
        elif isinstance(image_input, str):
            image_url = image_input.strip()
            if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                api_data['image_url'] = image_url
    
    # image_size - обязательный (нормализуем)
    if 'image_size' in test_data and test_data['image_size']:
        image_size = str(test_data['image_size']).strip()
        image_size_normalized = image_size.lower().replace(' ', '_').replace(':', '_')
        if image_size == "Square HD":
            image_size_normalized = "square_hd"
        valid_image_sizes = ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
        if image_size_normalized in valid_image_sizes:
            api_data['image_size'] = image_size_normalized
    
    # rendering_speed - опциональный (нормализуем в uppercase)
    if 'rendering_speed' in test_data and test_data['rendering_speed']:
        rendering_speed = str(test_data['rendering_speed']).strip().upper()
        if rendering_speed == "TURBO" or rendering_speed == "TURB":
            rendering_speed = "TURBO"
        elif rendering_speed == "BALANCED" or rendering_speed == "BALANCE" or rendering_speed == "BAL":
            rendering_speed = "BALANCED"
        elif rendering_speed == "QUALITY" or rendering_speed == "QUAL" or rendering_speed == "HIGH":
            rendering_speed = "QUALITY"
        if rendering_speed in ["TURBO", "BALANCED", "QUALITY"]:
            api_data['rendering_speed'] = rendering_speed
    
    # style - опциональный (нормализуем в uppercase)
    if 'style' in test_data and test_data['style']:
        style = str(test_data['style']).strip().upper()
        if style in ["AUTO", "GENERAL", "REALISTIC", "DESIGN"]:
            api_data['style'] = style
    
    # num_images - опциональный (преобразуем в число)
    if 'num_images' in test_data and test_data['num_images'] is not None:
        try:
            num_images = int(test_data['num_images'])
            if 1 <= num_images <= 4:
                api_data['num_images'] = num_images
        except (ValueError, TypeError):
            pass
    
    # seed - опциональный (преобразуем в число)
    if 'seed' in test_data and test_data['seed'] is not None:
        try:
            seed = int(test_data['seed'])
            api_data['seed'] = seed
        except ValueError:
            pass
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))





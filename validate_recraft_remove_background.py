"""
Валидация входных данных для модели recraft/remove-background
"""

def validate_recraft_remove_background_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели recraft/remove-background
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка image или image_input (обязательный, один URL)
    # Форма может передавать image, но API ожидает image_input (массив) или image
    image_url = None
    if 'image' in data and data['image']:
        image_url = str(data['image']).strip()
        # Проверяем на placeholder
        if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
            warnings.append(f"[WARNING] Параметр 'image' содержит placeholder: '{image_url}'. Убедитесь, что это валидный URL изображения")
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
        errors.append("[ERROR] Параметр 'image' или 'image_input' обязателен и не может быть пустым")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits() -> int:
    """
    Вычисляет цену в кредитах
    
    Returns:
        int: Цена в кредитах (бесплатно)
    """
    # Бесплатно и безлимитно для пользователей
    return 0


# Тестовые данные из запроса пользователя
test_data = {
    "image": "Upload successfully"  # Обязательный (форма передает image, но может быть placeholder)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для recraft/remove-background")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    # Проверяем image или image_input
    if 'image' in test_data:
        print(f"  image: '{test_data['image']}'")
    elif 'image_input' in test_data:
        print(f"  image_input: {test_data['image_input']}")
    print()
    
    is_valid, errors, warnings = validate_recraft_remove_background_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        # Обрабатываем image или image_input
        if 'image' in test_data:
            image_url = str(test_data['image']).strip()
            if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - image: '{image_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - image: '{image_url}' [OK]")
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
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image или image_input (URL изображения для удаления фона, 1 изображение)")
        print("  - Поддерживаемые форматы: PNG, JPG, WEBP")
        print("  - Ограничения: макс. 5MB, макс. 16MP, макс. размер 4096px, мин. размер 256px")
        print("  - Бесплатно и безлимитно для пользователей")
        print()
        print("[PRICING] Ценообразование:")
        price = calculate_price_credits()
        print(f"  - Цена: {price} кредитов (бесплатно)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * image/image_input не влияет на цену (но требуется валидный URL)")
        print()
        print("  - Информация о цене:")
        print("    * Цена: Бесплатно (0 кредитов)")
        print("    * Безлимитное использование для всех пользователей")
        print("    * Цена не зависит от размера, разрешения или других параметров изображения")
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
    
    # image или image_input - обязательный
    # API ожидает image (строка) или image_input (массив)
    if 'image' in test_data:
        image_url = str(test_data['image']).strip()
        if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
            api_data['image'] = image_url
    elif 'image_input' in test_data:
        image_input = test_data['image_input']
        if isinstance(image_input, list):
            if len(image_input) > 0:
                image_url = str(image_input[0]).strip()
                if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                    api_data['image'] = image_url
        elif isinstance(image_input, str):
            image_url = image_input.strip()
            if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                api_data['image'] = image_url
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




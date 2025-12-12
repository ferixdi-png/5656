"""
Валидация входных данных для модели flux-2/flex-text-to-image
"""

def validate_flux_2_flex_text_to_image_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели flux-2/flex-text-to-image
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, от 3 до 5000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) < 3:
            errors.append(f"[ERROR] Параметр 'prompt' слишком короткий: {len(prompt)} символов (минимум 3)")
        elif len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 5000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка aspect_ratio (обязательный, enum)
    # Модель ожидает: ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"]
    # Форма может передавать: "1:1 (Square)" -> нужно извлечь "1:1"
    valid_aspect_ratios = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"]
    
    if 'aspect_ratio' not in data or not data['aspect_ratio']:
        errors.append("[ERROR] Параметр 'aspect_ratio' обязателен и не может быть пустым")
    else:
        aspect_ratio = str(data['aspect_ratio']).strip()
        # Извлекаем только соотношение сторон, если есть дополнительные символы (например, "1:1 (Square)")
        if ' ' in aspect_ratio:
            aspect_ratio = aspect_ratio.split()[0]
        aspect_ratio = aspect_ratio.strip()
        
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 3. Проверка resolution (обязательный, enum)
    # Модель ожидает: ["1K", "2K"]
    valid_resolutions = ["1K", "2K"]
    
    if 'resolution' not in data or not data['resolution']:
        errors.append("[ERROR] Параметр 'resolution' обязателен и не может быть пустым")
    else:
        resolution = str(data['resolution']).strip().upper()
        if resolution not in valid_resolutions:
            errors.append(f"[ERROR] Параметр 'resolution' имеет недопустимое значение: '{data['resolution']}'. Допустимые значения: {', '.join(valid_resolutions)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(resolution: str) -> int:
    """
    Вычисляет цену в кредитах на основе параметра resolution
    
    Args:
        resolution: Разрешение изображения ("1K" или "2K")
        
    Returns:
        int: Цена в кредитах
    """
    resolution = str(resolution).strip().upper()
    if resolution == "2K":
        return 24  # 2K
    else:  # 1K
        return 14  # 1K


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A humanoid figure with a vintage television set for a head, featuring a green-tinted screen displaying a `Hello FLUX.2` writing in ASCII font. The figure is wearing a yellow raincoat, and there are various wires and components attached to the television. The background is cloudy and indistinct, suggesting an outdoor setting",
    "aspect_ratio": "1:1 (Square)",  # Обязательный (форма может передавать с дополнительным текстом)
    "resolution": "1K"  # Обязательный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для flux-2/flex-text-to-image")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}'")
    print(f"  resolution: '{test_data['resolution']}'")
    print()
    
    is_valid, errors, warnings = validate_flux_2_flex_text_to_image_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 3-5000) [OK]")
        
        aspect_ratio = str(test_data['aspect_ratio']).strip()
        if ' ' in aspect_ratio:
            aspect_ratio_normalized = aspect_ratio.split()[0]
        else:
            aspect_ratio_normalized = aspect_ratio
        print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' -> нормализовано в '{aspect_ratio_normalized}' [OK]")
        
        resolution = str(test_data['resolution']).strip().upper()
        print(f"  - resolution: '{test_data['resolution']}' -> нормализовано в '{resolution}' [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемого изображения, от 3 до 5000 символов)")
        print("  - Требуется aspect_ratio (соотношение сторон: 1:1, 4:3, 3:4, 16:9, 9:16, 3:2, 2:3, auto)")
        print("  - Требуется resolution (разрешение выходного изображения: 1K или 2K)")
        print()
        print("[PRICING] Ценообразование:")
        resolution = str(test_data.get('resolution', '1K')).strip().upper()
        price = calculate_price_credits(resolution)
        print(f"  - Текущая цена: {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * resolution='{resolution}'")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * aspect_ratio не влияет на цену")
        print()
        print("  - Таблица цен:")
        print("    * 1K: 14 кредитов (выше, чем Pro версия: 5 кредитов)")
        print("    * 2K: 24 кредита (выше, чем Pro версия: 7 кредитов)")
        print("  - ВНИМАНИЕ: Flex версия дороже Pro версии, но имеет расширенные возможности")
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
    api_data['prompt'] = test_data['prompt']
    
    # aspect_ratio - обязательный (извлекаем только соотношение сторон)
    aspect_ratio = str(test_data['aspect_ratio']).strip()
    if ' ' in aspect_ratio:
        aspect_ratio = aspect_ratio.split()[0]
    api_data['aspect_ratio'] = aspect_ratio.strip()
    
    # resolution - обязательный (нормализуем в верхний регистр)
    resolution = str(test_data['resolution']).strip().upper()
    api_data['resolution'] = resolution
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))





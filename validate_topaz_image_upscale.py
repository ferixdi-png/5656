"""
Валидация входных данных для модели topaz/image-upscale
"""

def validate_topaz_image_upscale_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели topaz/image-upscale
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка image_url/image_input (обязательный, один URL)
    # Модель ожидает image_url, но форма может передавать image_input
    # В bot_kie.py image_input конвертируется в image_url (берется первый элемент, если массив)
    image_url = None
    if 'image_url' in data:
        image_url = data['image_url']
    elif 'image_input' in data:
        image_input = data['image_input']
        # Если это массив, берем первый элемент
        if isinstance(image_input, list):
            if len(image_input) > 0:
                image_url = image_input[0]
            else:
                errors.append("[ERROR] Параметр 'image_input' не может быть пустым массивом")
        else:
            image_url = image_input
    
    if not image_url:
        errors.append("[ERROR] Параметр 'image_url' (или 'image_input') обязателен и не может быть пустым")
    else:
        image_url_str = str(image_url).strip()
        if not image_url_str:
            errors.append("[ERROR] Параметр 'image_url' не может быть пустым")
        # Базовая проверка формата URL (должен начинаться с http:// или https://)
        elif not (image_url_str.startswith('http://') or image_url_str.startswith('https://')):
            # Предупреждение для placeholder значений
            if image_url_str.lower().startswith('file') or 'upload' in image_url_str.lower() or 'click' in image_url_str.lower() or 'preview' in image_url_str.lower():
                warnings.append(f"[WARNING] URL изображения может иметь неверный формат: '{image_url_str[:50]}...' (должен начинаться с http:// или https://). Это может быть placeholder, который будет заменен на реальный URL.")
            else:
                warnings.append(f"[WARNING] URL изображения может иметь неверный формат: '{image_url_str[:50]}...' (должен начинаться с http:// или https://)")
    
    # 2. Проверка upscale_factor (обязательный, enum)
    # Модель ожидает: ["1", "2", "4", "8"]
    # Форма может передавать: "1x", "2x", "4x", "8x" -> нужно убрать "x"
    valid_upscale_factors = ["1", "2", "4", "8"]
    
    if 'upscale_factor' not in data or not data['upscale_factor']:
        errors.append("[ERROR] Параметр 'upscale_factor' обязателен и не может быть пустым")
    else:
        upscale_factor = str(data['upscale_factor']).strip().lower()
        # Убираем "x" в конце, если есть (например, "1x" -> "1")
        if upscale_factor.endswith('x'):
            upscale_factor = upscale_factor[:-1].strip()
        
        if upscale_factor not in valid_upscale_factors:
            errors.append(f"[ERROR] Параметр 'upscale_factor' имеет недопустимое значение: '{data['upscale_factor']}'. Допустимые значения: {', '.join(valid_upscale_factors)} (или с суффиксом 'x': 1x, 2x, 4x, 8x)")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(upscale_factor: str) -> int:
    """
    Вычисляет цену в кредитах на основе параметра upscale_factor
    
    Args:
        upscale_factor: Коэффициент увеличения ("1", "2", "4" или "8")
        
    Returns:
        int: Цена в кредитах
    """
    upscale_factor = str(upscale_factor).strip().lower()
    # Убираем "x" в конце, если есть
    if upscale_factor.endswith('x'):
        upscale_factor = upscale_factor[:-1].strip()
    
    if upscale_factor == "8":
        return 40  # 8K
    elif upscale_factor in ["2", "4"]:
        return 20  # 4K
    else:  # upscale_factor == "1"
        return 10  # ≤2K


# Тестовые данные из запроса пользователя
test_data = {
    "image_url": "Upload successfully",  # Это будет заменено на реальный URL после загрузки
    "upscale_factor": "1x"  # Обязательный (форма может передавать с суффиксом "x")
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для topaz/image-upscale")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  upscale_factor: '{test_data['upscale_factor']}'")
    print()
    
    is_valid, errors, warnings = validate_topaz_image_upscale_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - image_url: '{test_data['image_url']}' [OK]")
        
        upscale_factor = str(test_data['upscale_factor']).strip().lower()
        if upscale_factor.endswith('x'):
            upscale_factor_normalized = upscale_factor[:-1].strip()
        else:
            upscale_factor_normalized = upscale_factor
        print(f"  - upscale_factor: '{test_data['upscale_factor']}' -> нормализовано в '{upscale_factor_normalized}' [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image_url (URL изображения для увеличения разрешения)")
        print("  - Требуется upscale_factor (коэффициент увеличения: 1, 2, 4 или 8, можно с суффиксом 'x')")
        print()
        print("[PRICING] Ценообразование:")
        upscale_factor = str(test_data.get('upscale_factor', '1')).strip().lower()
        if upscale_factor.endswith('x'):
            upscale_factor = upscale_factor[:-1].strip()
        price = calculate_price_credits(upscale_factor)
        print(f"  - Текущая цена: {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * upscale_factor='{upscale_factor}'")
        print()
        print("  - Таблица цен:")
        print("    * 1x (≤2K): 10 кредитов")
        print("    * 2x (4K): 20 кредитов")
        print("    * 4x (4K): 20 кредитов")
        print("    * 8x (8K): 40 кредитов")
        print("  - ВНИМАНИЕ: 2x и 4x имеют одинаковую цену (20 кредитов)")
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
    
    # image_url - обязательный (конвертируем image_input в image_url, если нужно)
    image_url = test_data.get('image_url') or test_data.get('image_input')
    if isinstance(image_url, list) and len(image_url) > 0:
        image_url = image_url[0]
    api_data['image_url'] = str(image_url).strip()
    
    # upscale_factor - обязательный (нормализуем, убирая "x")
    upscale_factor = str(test_data['upscale_factor']).strip().lower()
    if upscale_factor.endswith('x'):
        upscale_factor = upscale_factor[:-1].strip()
    api_data['upscale_factor'] = upscale_factor
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))


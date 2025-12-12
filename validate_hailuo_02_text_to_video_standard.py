"""
Валидация входных данных для модели hailuo/02-text-to-video-standard
"""

def validate_hailuo_02_text_to_video_standard_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели hailuo/02-text-to-video-standard
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 1500 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
        elif len(prompt) > 1500:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 1500)")
    
    # 2. Проверка duration (опциональный, enum: "6" или "10")
    # Форма может передавать: "6 seconds" -> нужно извлечь "6"
    valid_durations = ["6", "10"]
    
    if 'duration' in data and data['duration']:
        duration = str(data['duration']).strip().lower()
        # Убираем "s" или "seconds" в конце, если есть
        if duration.endswith('seconds'):
            duration = duration[:-7].strip()
        elif duration.endswith('s'):
            duration = duration[:-1].strip()
        
        if duration not in valid_durations:
            errors.append(f"[ERROR] Параметр 'duration' имеет недопустимое значение: '{data['duration']}'. Допустимые значения: {', '.join(valid_durations)} (или с суффиксом 's'/'seconds': 6s, 10s, 6 seconds, 10 seconds)")
    
    # 3. Проверка prompt_optimizer (опциональный, boolean)
    if 'prompt_optimizer' in data and data['prompt_optimizer'] is not None:
        prompt_optimizer = data['prompt_optimizer']
        # Конвертируем строку в boolean, если нужно
        if isinstance(prompt_optimizer, str):
            prompt_optimizer_str = prompt_optimizer.strip().lower()
            if prompt_optimizer_str not in ['true', 'false', '1', '0', 'yes', 'no']:
                errors.append(f"[ERROR] Параметр 'prompt_optimizer' должен быть boolean (true/false), получено: '{prompt_optimizer}'")
        elif not isinstance(prompt_optimizer, bool):
            errors.append(f"[ERROR] Параметр 'prompt_optimizer' должен быть boolean, получено: {type(prompt_optimizer).__name__}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(duration: str) -> int:
    """
    Вычисляет цену в кредитах на основе параметра duration
    
    Args:
        duration: Длительность видео ("6" или "10")
        
    Returns:
        int: Цена в кредитах
    """
    duration = str(duration).strip().lower()
    # Убираем "s" или "seconds" в конце, если есть
    if duration.endswith('seconds'):
        duration = duration[:-7].strip()
    elif duration.endswith('s'):
        duration = duration[:-1].strip()
    
    duration_int = int(duration) if duration.isdigit() else 6
    
    # Фиксированное разрешение 768P: 5 кредитов за секунду
    return 5 * duration_int


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A llama and a raccoon battle it out in an intense table tennis match, inside a roaring Olympic stadium. Slow-mo, wild angles, full comedy mode.",
    "duration": "6 seconds",  # Опциональный (форма может передавать с суффиксом "seconds")
    "prompt_optimizer": True  # Опциональный (boolean, по умолчанию True)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для hailuo/02-text-to-video-standard")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  duration: '{test_data.get('duration', '6')}'")
    print(f"  prompt_optimizer: {test_data.get('prompt_optimizer', True)}")
    print()
    
    is_valid, errors, warnings = validate_hailuo_02_text_to_video_standard_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: до 1500) [OK]")
        
        duration = str(test_data.get('duration', '6')).strip().lower()
        if duration.endswith('seconds'):
            duration_normalized = duration[:-7].strip()
        elif duration.endswith('s'):
            duration_normalized = duration[:-1].strip()
        else:
            duration_normalized = duration
        print(f"  - duration: '{test_data.get('duration', '6')}' -> нормализовано в '{duration_normalized}' [OK]")
        
        prompt_optimizer = test_data.get('prompt_optimizer', True)
        print(f"  - prompt_optimizer: {prompt_optimizer} [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемого видео, до 1500 символов)")
        print("  - Опционально duration (длительность: 6 или 10 секунд, по умолчанию 6)")
        print("  - Опционально prompt_optimizer (использовать оптимизатор промпта модели, по умолчанию True)")
        print("  - Модель генерирует видео с фиксированным разрешением 768P")
        print()
        print("[PRICING] Ценообразование:")
        duration = str(test_data.get('duration', '6')).strip().lower()
        if duration.endswith('seconds'):
            duration = duration[:-7].strip()
        elif duration.endswith('s'):
            duration = duration[:-1].strip()
        price = calculate_price_credits(duration)
        print(f"  - Текущая цена: {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * duration='{duration}'")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * prompt не влияет на цену")
        print(f"    * prompt_optimizer не влияет на цену")
        print()
        print("  - Таблица цен (фиксированное разрешение 768P):")
        print("    * 6s: 30 кредитов (5 кредитов/сек × 6)")
        print("    * 10s: 50 кредитов (5 кредитов/сек × 10)")
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
    
    # duration - опциональный (нормализуем, убирая "s"/"seconds")
    duration = str(test_data.get('duration', '6')).strip().lower()
    if duration.endswith('seconds'):
        duration = duration[:-7].strip()
    elif duration.endswith('s'):
        duration = duration[:-1].strip()
    api_data['duration'] = duration
    
    # prompt_optimizer - опциональный (конвертируем в boolean)
    if test_data.get('prompt_optimizer') is not None:
        prompt_optimizer = test_data['prompt_optimizer']
        if isinstance(prompt_optimizer, str):
            prompt_optimizer = prompt_optimizer.strip().lower()
            api_data['prompt_optimizer'] = prompt_optimizer in ['true', '1', 'yes']
        else:
            api_data['prompt_optimizer'] = bool(prompt_optimizer)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




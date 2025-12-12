"""
Валидация входных данных для модели hailuo/02-text-to-video-pro
"""

def validate_hailuo_02_text_to_video_pro_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели hailuo/02-text-to-video-pro
    
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
    
    # 2. Проверка prompt_optimizer (опциональный, boolean)
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


def calculate_price_credits() -> int:
    """
    Вычисляет цену в кредитах для модели hailuo/02-text-to-video-pro
    
    Returns:
        int: Цена в кредитах (фиксированная: 57 кредитов за 6-секундное 1080p видео)
    """
    # Фиксированная цена: 9.5 кредитов/сек × 6 секунд = 57 кредитов
    return 57


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "High top angle wide mid close-up tracking shot, flying very fast two meters high over prehistoric ferns and moss-covered ground, dominated by a real young boy (pink t-shirt, pink shorts, white shoes, white long socks), with his back to the camera, body stretched out, gliding smoothly forward, flying in the air, casting a clear shadow on the terrain below. His legs and body are high above the surface, his feet not touching the ground, soaring in a Superman pose. The background is a vast Jurassic valley, filled with dense, ancient jungle vegetation and towering cycads. In the distance, rugged volcanic mountains rise with a winding path cutting through. Massive, slow-moving sauropods graze far off on the horizon. Large, fluffy white clouds float in the vibrant blue sky. Strong dynamic motion blur adds a vivid sense of high-speed flight and deep cinematic perspective. Realistic image –raw.",
    "prompt_optimizer": True  # Опциональный (boolean, по умолчанию True)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для hailuo/02-text-to-video-pro")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  prompt_optimizer: {test_data.get('prompt_optimizer', True)}")
    print()
    
    is_valid, errors, warnings = validate_hailuo_02_text_to_video_pro_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: до 1500) [OK]")
        
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
        print("  - Опционально prompt_optimizer (использовать оптимизатор промпта модели, по умолчанию True)")
        print("  - Модель генерирует 6-секундное 1080p видео")
        print()
        print("[PRICING] Ценообразование:")
        price = calculate_price_credits()
        print(f"  - Текущая цена: {price} кредитов (фиксированная)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * prompt не влияет на цену")
        print(f"    * prompt_optimizer не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Фиксированная цена: 57 кредитов за 6-секундное 1080p видео")
        print("    * Расчет: 9.5 кредитов/сек × 6 секунд = 57 кредитов")
        print("    * Все генерации имеют одинаковую цену независимо от параметров")
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


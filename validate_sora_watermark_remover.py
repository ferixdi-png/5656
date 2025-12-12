"""
Валидация входных данных для модели sora-watermark-remover
"""

def validate_sora_watermark_remover_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели sora-watermark-remover
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка video_url (обязательный, макс. 500 символов, должен начинаться с sora.chatgpt.com)
    if 'video_url' not in data or not data['video_url']:
        errors.append("[ERROR] Параметр 'video_url' обязателен и не может быть пустым")
    else:
        video_url = str(data['video_url']).strip()
        if len(video_url) == 0:
            errors.append("[ERROR] Параметр 'video_url' не может быть пустым")
        elif len(video_url) > 500:
            errors.append(f"[ERROR] Параметр 'video_url' слишком длинный: {len(video_url)} символов (максимум 500)")
        else:
            # Проверяем, что URL начинается с sora.chatgpt.com
            if not video_url.startswith('https://sora.chatgpt.com/') and not video_url.startswith('http://sora.chatgpt.com/'):
                errors.append(f"[ERROR] Параметр 'video_url' должен быть публично доступной ссылкой от OpenAI, начинающейся с 'sora.chatgpt.com'. Получено: '{video_url[:50]}...'")
            elif not video_url.startswith('https://'):
                warnings.append(f"[WARNING] Рекомендуется использовать HTTPS для 'video_url': '{video_url[:50]}...'")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# Тестовые данные из запроса пользователя
test_data = {
    "video_url": "https://sora.chatgpt.com/p/s_68e83bd7eee88191be79d2ba7158516f"
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для sora-watermark-remover")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  video_url: '{test_data['video_url']}'")
    print()
    
    is_valid, errors, warnings = validate_sora_watermark_remover_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - video_url: '{test_data['video_url']}' - валидный URL от OpenAI [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется video_url (публично доступная ссылка на видео Sora 2 от OpenAI)")
        print("  - URL должен начинаться с 'sora.chatgpt.com'")
        print("  - Максимальная длина URL: 500 символов")
        print()
        print("[PRICING] Ценообразование:")
        print("  - Цена: 10 кредитов за использование (фиксированная)")
        print("  - Цена не зависит от параметров (нет дополнительных параметров)")
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
    
    # video_url - обязательный
    api_data['video_url'] = str(test_data['video_url']).strip()
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




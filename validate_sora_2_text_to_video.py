"""
Валидация входных данных для модели sora-2-text-to-video
"""

def validate_sora_2_text_to_video_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели sora-2-text-to-video
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 10000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) > 10000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 10000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка aspect_ratio (опциональный, enum)
    # Модель ожидает: ["portrait", "landscape"]
    # Форма может передавать: "Portrait", "Landscape"
    valid_aspect_ratios = ["portrait", "landscape"]
    
    if 'aspect_ratio' in data and data['aspect_ratio']:
        aspect_ratio = str(data['aspect_ratio']).strip().lower()
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 3. Проверка n_frames (опциональный, enum)
    # Модель ожидает: ["10", "15"]
    # Форма может передавать: "10s", "15s" (с суффиксом "s")
    valid_n_frames = ["10", "15"]
    
    if 'n_frames' in data and data['n_frames']:
        n_frames = str(data['n_frames']).strip()
        # Удаляем суффикс "s" если есть
        if n_frames.lower().endswith('s'):
            n_frames = n_frames[:-1].strip()
        
        if n_frames not in valid_n_frames:
            errors.append(f"[ERROR] Параметр 'n_frames' имеет недопустимое значение: '{data['n_frames']}'. Допустимые значения: '10', '15' (или '10s', '15s')")
    
    # 4. Проверка remove_watermark (опциональный, boolean)
    if 'remove_watermark' in data and data['remove_watermark'] is not None:
        remove_watermark = data['remove_watermark']
        if not isinstance(remove_watermark, bool):
            # Попытка конвертировать строку в boolean
            if isinstance(remove_watermark, str):
                remove_watermark_str = str(remove_watermark).strip().lower()
                if remove_watermark_str in ['true', '1', 'yes', 'on']:
                    # Это будет нормализовано в True
                    pass
                elif remove_watermark_str in ['false', '0', 'no', 'off', '']:
                    # Это будет нормализовано в False
                    pass
                else:
                    warnings.append(f"[WARNING] Параметр 'remove_watermark' имеет нестандартное значение: '{remove_watermark}'. Ожидается boolean (true/false)")
            else:
                errors.append(f"[ERROR] Параметр 'remove_watermark' должен быть boolean (true/false), получено: {type(remove_watermark).__name__}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A professor stands at the front of a lively classroom, enthusiastically giving a lecture. On the blackboard behind him are colorful chalk diagrams. With an animated gesture, he declares to the students: \"Sora 2 is now available on Kie AI, making it easier than ever to create stunning videos.\" The students listen attentively, some smiling and taking notes.",
    "aspect_ratio": "Portrait",  # Опциональный
    "n_frames": "10s",  # Опциональный (может быть "10s" или "15s")
    "remove_watermark": True  # Опциональный, boolean
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для sora-2-text-to-video")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  aspect_ratio: '{test_data.get('aspect_ratio', 'не указан')}'")
    print(f"  n_frames: '{test_data.get('n_frames', 'не указан')}'")
    print(f"  remove_watermark: {test_data.get('remove_watermark', 'не указан')}")
    print()
    
    is_valid, errors, warnings = validate_sora_2_text_to_video_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 10000) [OK]")
        
        aspect_ratio = test_data.get('aspect_ratio')
        if aspect_ratio:
            aspect_ratio_normalized = str(aspect_ratio).strip().lower()
            print(f"  - aspect_ratio: '{aspect_ratio}' -> нормализовано в '{aspect_ratio_normalized}' [OK]")
        else:
            print(f"  - aspect_ratio: не указан, будет использовано значение по умолчанию 'landscape' [OK]")
        
        n_frames = test_data.get('n_frames')
        if n_frames:
            n_frames_normalized = str(n_frames).strip()
            if n_frames_normalized.lower().endswith('s'):
                n_frames_normalized = n_frames_normalized[:-1].strip()
            print(f"  - n_frames: '{n_frames}' -> нормализовано в '{n_frames_normalized}' [OK]")
        else:
            print(f"  - n_frames: не указан, будет использовано значение по умолчанию '10' [OK]")
        
        remove_watermark = test_data.get('remove_watermark')
        if remove_watermark is not None:
            print(f"  - remove_watermark: {remove_watermark} [OK]")
        else:
            print(f"  - remove_watermark: не указан, будет использовано значение по умолчанию True [OK]")
        
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемого видео, макс. 10000 символов)")
        print("  - aspect_ratio: опциональный (portrait/landscape, по умолчанию: landscape)")
        print("  - n_frames: опциональный (10/15 секунд, по умолчанию: 10)")
        print("  - remove_watermark: опциональный (boolean, по умолчанию: true)")
        print()
        print("[PRICING] Ценообразование:")
        print("  - Цена: 30 кредитов за видео (фиксированная)")
        print("  - Цена НЕ зависит от параметров:")
        print("    * aspect_ratio не влияет на цену")
        print("    * n_frames (10s/15s) не влияет на цену")
        print("    * remove_watermark не влияет на цену")
        print("  - ВНИМАНИЕ: Цена фиксирована независимо от длительности видео")
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
    
    # aspect_ratio - опциональный (нормализуем в нижний регистр)
    if 'aspect_ratio' in test_data and test_data['aspect_ratio']:
        aspect_ratio = str(test_data['aspect_ratio']).strip().lower()
        api_data['aspect_ratio'] = aspect_ratio
    
    # n_frames - опциональный (удаляем суффикс "s" если есть)
    if 'n_frames' in test_data and test_data['n_frames']:
        n_frames = str(test_data['n_frames']).strip()
        if n_frames.lower().endswith('s'):
            n_frames = n_frames[:-1].strip()
        api_data['n_frames'] = n_frames
    
    # remove_watermark - опциональный (boolean)
    if 'remove_watermark' in test_data and test_data['remove_watermark'] is not None:
        remove_watermark = test_data['remove_watermark']
        if isinstance(remove_watermark, str):
            remove_watermark_str = str(remove_watermark).strip().lower()
            remove_watermark = remove_watermark_str in ['true', '1', 'yes', 'on']
        api_data['remove_watermark'] = bool(remove_watermark)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




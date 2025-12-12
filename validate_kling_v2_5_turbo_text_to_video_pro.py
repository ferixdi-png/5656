"""
Валидация входных данных для модели kling/v2-5-turbo-text-to-video-pro
"""

def validate_kling_v2_5_turbo_text_to_video_pro_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели kling/v2-5-turbo-text-to-video-pro
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 2500 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
        elif len(prompt) > 2500:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 2500)")
    
    # 2. Проверка duration (опциональный, enum: "5" или "10")
    # Форма может передавать: "5 seconds" -> нужно извлечь "5"
    valid_durations = ["5", "10"]
    
    if 'duration' in data and data['duration']:
        duration = str(data['duration']).strip().lower()
        # Убираем "s" или "seconds" в конце, если есть
        if duration.endswith('seconds'):
            duration = duration[:-7].strip()
        elif duration.endswith('s'):
            duration = duration[:-1].strip()
        
        if duration not in valid_durations:
            errors.append(f"[ERROR] Параметр 'duration' имеет недопустимое значение: '{data['duration']}'. Допустимые значения: {', '.join(valid_durations)} (или с суффиксом 's'/'seconds': 5s, 10s, 5 seconds, 10 seconds)")
    
    # 3. Проверка aspect_ratio (опциональный, enum)
    valid_aspect_ratios = ["16:9", "9:16", "1:1"]
    
    if 'aspect_ratio' in data and data['aspect_ratio']:
        aspect_ratio = str(data['aspect_ratio']).strip()
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 4. Проверка negative_prompt (опциональный, макс. 2500 символов)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 2500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 2500)")
    
    # 5. Проверка cfg_scale (опциональный, число от 0 до 1)
    # Форма может передавать: "0,5" (запятая) -> нужно нормализовать в 0.5
    if 'cfg_scale' in data and data['cfg_scale'] is not None:
        cfg_scale = data['cfg_scale']
        try:
            # Конвертируем строку в float, обрабатывая запятую и точку как разделитель
            if isinstance(cfg_scale, str):
                cfg_scale_str = cfg_scale.strip().replace(',', '.')
                cfg_scale_float = float(cfg_scale_str)
            elif isinstance(cfg_scale, (int, float)):
                cfg_scale_float = float(cfg_scale)
            else:
                errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть числом, получено: {type(cfg_scale).__name__}")
                cfg_scale_float = None
            
            if cfg_scale_float is not None:
                if cfg_scale_float < 0 or cfg_scale_float > 1:
                    errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть в диапазоне от 0 до 1, получено: {cfg_scale_float}")
        except ValueError:
            errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть числом, получено: '{cfg_scale}'")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(duration: str) -> int:
    """
    Вычисляет цену в кредитах на основе параметра duration
    
    Args:
        duration: Длительность видео ("5" или "10")
        
    Returns:
        int: Цена в кредитах
    """
    duration = str(duration).strip().lower()
    # Убираем "s" или "seconds" в конце, если есть
    if duration.endswith('seconds'):
        duration = duration[:-7].strip()
    elif duration.endswith('s'):
        duration = duration[:-1].strip()
    
    if duration == "10":
        return 84  # 10s
    else:  # duration == "5" (по умолчанию)
        return 42  # 5s


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Real-time playback. Wide shot of a ruined city: collapsed towers, fires blazing, storm clouds with lightning. Camera drops fast from the sky over burning streets and tilted buildings. Smoke and dust fill the air. A lone hero walks out of the ruins, silhouetted by fire. Camera shifts front: his face is dirty with dust and sweat, eyes firm, a faint smile. Wind blows, debris rises. Extreme close-up: his eyes reflect the approaching enemy. Music and drums hit. Final wide shot: fire forms a blazing halo behind him — reborn in flames with epic cinematic vibe.",
    "duration": "5 seconds",  # Опциональный (форма может передавать с суффиксом "seconds")
    "aspect_ratio": "16:9",  # Опциональный
    "negative_prompt": "blur, distort, and low quality",  # Опциональный
    "cfg_scale": "0,5"  # Опциональный (форма может передавать с запятой вместо точки)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для kling/v2-5-turbo-text-to-video-pro")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  duration: '{test_data.get('duration', '5')}'")
    print(f"  aspect_ratio: '{test_data.get('aspect_ratio', '16:9')}'")
    print(f"  negative_prompt: '{test_data.get('negative_prompt', '')}' ({len(test_data.get('negative_prompt', ''))} символов)")
    print(f"  cfg_scale: '{test_data.get('cfg_scale', '0.5')}'")
    print()
    
    is_valid, errors, warnings = validate_kling_v2_5_turbo_text_to_video_pro_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: до 2500) [OK]")
        
        duration = str(test_data.get('duration', '5')).strip().lower()
        if duration.endswith('seconds'):
            duration_normalized = duration[:-7].strip()
        elif duration.endswith('s'):
            duration_normalized = duration[:-1].strip()
        else:
            duration_normalized = duration
        print(f"  - duration: '{test_data.get('duration', '5')}' -> нормализовано в '{duration_normalized}' [OK]")
        
        aspect_ratio = test_data.get('aspect_ratio', '16:9')
        print(f"  - aspect_ratio: '{aspect_ratio}' [OK]")
        
        negative_prompt = test_data.get('negative_prompt', '')
        if negative_prompt:
            print(f"  - negative_prompt: {len(negative_prompt)} символов (лимит: до 2500) [OK]")
        else:
            print(f"  - negative_prompt: не указан (опциональный) [OK]")
        
        cfg_scale = test_data.get('cfg_scale')
        if cfg_scale is not None:
            cfg_scale_str = str(cfg_scale).strip().replace(',', '.')
            cfg_scale_float = float(cfg_scale_str)
            print(f"  - cfg_scale: '{cfg_scale}' -> нормализовано в {cfg_scale_float} [OK]")
        else:
            print(f"  - cfg_scale: не указан (опциональный, по умолчанию 0.5) [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемого видео, до 2500 символов)")
        print("  - Опционально duration (длительность: 5 или 10 секунд, по умолчанию 5)")
        print("  - Опционально aspect_ratio (соотношение сторон: 16:9, 9:16, 1:1, по умолчанию 16:9)")
        print("  - Опционально negative_prompt (что избегать в видео, до 2500 символов)")
        print("  - Опционально cfg_scale (CFG scale, число от 0 до 1, по умолчанию 0.5)")
        print()
        print("[PRICING] Ценообразование:")
        duration = str(test_data.get('duration', '5')).strip().lower()
        if duration.endswith('seconds'):
            duration = duration[:-7].strip()
        elif duration.endswith('s'):
            duration = duration[:-1].strip()
        price = calculate_price_credits(duration)
        print(f"  - Текущая цена: {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * duration='{duration}'")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * aspect_ratio не влияет на цену")
        print(f"    * negative_prompt не влияет на цену")
        print(f"    * cfg_scale не влияет на цену")
        print()
        print("  - Таблица цен:")
        print("    * 5s: 42 кредита")
        print("    * 10s: 84 кредита")
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
    duration = str(test_data.get('duration', '5')).strip().lower()
    if duration.endswith('seconds'):
        duration = duration[:-7].strip()
    elif duration.endswith('s'):
        duration = duration[:-1].strip()
    api_data['duration'] = duration
    
    # aspect_ratio - опциональный
    if test_data.get('aspect_ratio'):
        api_data['aspect_ratio'] = str(test_data['aspect_ratio']).strip()
    
    # negative_prompt - опциональный
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = str(test_data['negative_prompt']).strip()
    
    # cfg_scale - опциональный (нормализуем, заменяя запятую на точку)
    if test_data.get('cfg_scale') is not None:
        cfg_scale = test_data['cfg_scale']
        if isinstance(cfg_scale, str):
            cfg_scale_str = cfg_scale.strip().replace(',', '.')
            api_data['cfg_scale'] = float(cfg_scale_str)
        else:
            api_data['cfg_scale'] = float(cfg_scale)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




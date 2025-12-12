"""
Валидация входных данных для модели wan/2-2-a14b-text-to-video-turbo
"""

def validate_wan_a14b_text_to_video_turbo_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели wan/2-2-a14b-text-to-video-turbo
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors)
    """
    errors = []
    
    # 1. Проверка prompt (обязательный)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 5000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка resolution (опциональный, enum)
    valid_resolutions = ["480p", "580p", "720p"]
    if 'resolution' in data and data['resolution']:
        resolution = str(data['resolution'])
        if resolution not in valid_resolutions:
            errors.append(f"[ERROR] Параметр 'resolution' имеет недопустимое значение: '{resolution}'. Допустимые значения: {', '.join(valid_resolutions)}")
    
    # 3. Проверка aspect_ratio (опциональный, enum)
    valid_aspect_ratios = ["16:9", "9:16", "1:1"]
    if 'aspect_ratio' in data and data['aspect_ratio']:
        aspect_ratio = str(data['aspect_ratio'])
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{aspect_ratio}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 4. Проверка enable_prompt_expansion (опциональный, boolean)
    if 'enable_prompt_expansion' in data and data['enable_prompt_expansion'] is not None:
        enable_expansion = data['enable_prompt_expansion']
        if not isinstance(enable_expansion, bool):
            # Попытка конвертации строки в boolean
            if isinstance(enable_expansion, str):
                if enable_expansion.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[ERROR] Параметр 'enable_prompt_expansion' должен быть boolean (true/false), получено: {enable_expansion}")
            else:
                errors.append(f"[ERROR] Параметр 'enable_prompt_expansion' должен быть boolean, получено: {type(enable_expansion).__name__}")
    
    # 5. Проверка seed (опциональный, number)
    if 'seed' in data and data['seed'] is not None:
        try:
            seed = float(data['seed'])
            seed_int = int(seed)
            if seed_int < 0:
                errors.append(f"[ERROR] Параметр 'seed' должен быть неотрицательным числом, получено: {seed_int}")
            elif seed_int > 2147483647:
                errors.append(f"[ERROR] Параметр 'seed' должен быть не больше 2147483647, получено: {seed_int}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть числом, получено: {data['seed']}")
    
    # 6. Проверка acceleration (опциональный, enum)
    valid_accelerations = ["none", "regular"]
    if 'acceleration' in data and data['acceleration']:
        acceleration = str(data['acceleration'])
        if acceleration not in valid_accelerations:
            errors.append(f"[ERROR] Параметр 'acceleration' имеет недопустимое значение: '{acceleration}'. Допустимые значения: {', '.join(valid_accelerations)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Drone shot, fast traversal, starting inside a cracked, frosty circular pipe. The camera bursts upward through the pipe to reveal a vast polar landscape bathed in golden sunrise light. Workers in orange suits operate steaming machinery. The camera tilts up, revealing the scene from the perspective of a rising hot air balloon. It continues ascending into a glowing sky, the balloon trailing steam and displaying the letters \"KIE AI\" as it rises into breathtaking polar majesty.",
    "resolution": "",  # Не указан - будет использован default "720p"
    "aspect_ratio": "",  # Не указан - будет использован default "16:9"
    "enable_prompt_expansion": None,  # Не указан - будет использован default False
    "seed": "0",  # Указан как строка "0", нужно конвертировать в число
    "acceleration": ""  # Не указан - будет использован default "none"
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для wan/2-2-a14b-text-to-video-turbo")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: {test_data['prompt'][:100]}... ({len(test_data['prompt'])} символов)")
    print(f"  resolution: '{test_data['resolution']}' (не указан - будет использован default '720p')")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}' (не указан - будет использован default '16:9')")
    print(f"  enable_prompt_expansion: {test_data['enable_prompt_expansion']} (не указан - будет использован default False)")
    print(f"  seed: '{test_data['seed']}'")
    print(f"  acceleration: '{test_data['acceleration']}' (не указан - будет использован default 'none')")
    print()
    
    is_valid, errors = validate_wan_a14b_text_to_video_turbo_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        if test_data.get('resolution'):
            print(f"  - resolution: '{test_data['resolution']}' - валидное значение [OK]")
        else:
            print(f"  - resolution: не указан, будет использован default '720p' [OK]")
        if test_data.get('aspect_ratio'):
            print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        else:
            print(f"  - aspect_ratio: не указан, будет использован default '16:9' [OK]")
        print(f"  - enable_prompt_expansion: опциональный, не указан - будет использован default False [OK]")
        if test_data.get('seed'):
            try:
                seed_val = int(test_data['seed'])
                print(f"  - seed: {seed_val} - валидное значение (диапазон: 0-2147483647) [OK]")
            except:
                print(f"  - seed: '{test_data['seed']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - seed: опциональный, не указан [OK]")
        if test_data.get('acceleration'):
            print(f"  - acceleration: '{test_data['acceleration']}' - валидное значение [OK]")
        else:
            print(f"  - acceleration: не указан, будет использован default 'none' [OK]")
    else:
        print("[ERROR] ОБНАРУЖЕНЫ ОШИБКИ:")
        print()
        for error in errors:
            print(f"  {error}")
    
    print()
    print("=" * 60)
    
    # Дополнительная проверка: формат для API
    print()
    print("[API] Формат данных для отправки в API:")
    api_data = {}
    
    # prompt - обязательный
    api_data['prompt'] = test_data['prompt']
    
    # resolution - опциональный, но можно указать default
    if test_data.get('resolution'):
        api_data['resolution'] = test_data['resolution']
    else:
        api_data['resolution'] = "720p"  # default
    
    # aspect_ratio - опциональный, но можно указать default
    if test_data.get('aspect_ratio'):
        api_data['aspect_ratio'] = test_data['aspect_ratio']
    else:
        api_data['aspect_ratio'] = "16:9"  # default
    
    # enable_prompt_expansion - только если указан
    if test_data.get('enable_prompt_expansion') is not None:
        api_data['enable_prompt_expansion'] = bool(test_data['enable_prompt_expansion'])
    # Иначе не включаем (будет использован default False)
    
    # seed - только если указан (как number!)
    if test_data.get('seed'):
        try:
            api_data['seed'] = int(test_data['seed'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный seed
    
    # acceleration - опциональный, но можно указать default
    if test_data.get('acceleration'):
        api_data['acceleration'] = test_data['acceleration']
    else:
        api_data['acceleration'] = "none"  # default
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))


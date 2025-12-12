"""
Валидация входных данных для модели wan/2-2-a14b-speech-to-video-turbo
"""

def validate_wan_2_2_a14b_speech_to_video_turbo_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели wan/2-2-a14b-speech-to-video-turbo
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, строка, макс. 5000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt']).strip()
        if not prompt:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустой строкой")
        elif len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' превышает максимальную длину 5000 символов, получено: {len(prompt)}")
        elif prompt.lower() in ['enter your prompt...', 'enter your prompt here...', 'enter number...']:
            warnings.append(f"[WARNING] Параметр 'prompt' содержит placeholder: '{prompt}'. Убедитесь, что это валидный промпт")
    
    # 2. Проверка image_url или image_input (обязательный, один URL)
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
    
    # 3. Проверка audio_url или audio_input (обязательный, один URL)
    # Форма может передавать audio_url, но API ожидает audio_input (массив) или audio_url
    audio_url = None
    if 'audio_url' in data and data['audio_url']:
        audio_url = str(data['audio_url']).strip()
        # Проверяем на placeholder
        if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
            warnings.append(f"[WARNING] Параметр 'audio_url' содержит placeholder: '{audio_url}'. Убедитесь, что это валидный URL аудиофайла")
    elif 'audio_input' in data and data['audio_input']:
        # Если передан audio_input (массив или строка)
        audio_input = data['audio_input']
        if isinstance(audio_input, list):
            if len(audio_input) == 0:
                errors.append("[ERROR] Параметр 'audio_input' не может быть пустым массивом")
            elif len(audio_input) > 1:
                errors.append(f"[ERROR] Параметр 'audio_input' должен содержать только 1 URL, получено: {len(audio_input)}")
            else:
                audio_url = str(audio_input[0]).strip()
                if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
                    warnings.append(f"[WARNING] Параметр 'audio_input' содержит placeholder: '{audio_url}'. Убедитесь, что это валидный URL аудиофайла")
        elif isinstance(audio_input, str):
            audio_url = audio_input.strip()
            if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
                warnings.append(f"[WARNING] Параметр 'audio_input' содержит placeholder: '{audio_url}'. Убедитесь, что это валидный URL аудиофайла")
        else:
            errors.append(f"[ERROR] Параметр 'audio_input' должен быть строкой или массивом строк, получено: {type(audio_input).__name__}")
    else:
        errors.append("[ERROR] Параметр 'audio_url' или 'audio_input' обязателен и не может быть пустым")
    
    # 4. Проверка num_frames (опциональный, число 40-120, должно быть кратно 4, default: 80)
    if 'num_frames' in data and data['num_frames'] is not None:
        try:
            num_frames = int(data['num_frames'])
            if num_frames < 40 or num_frames > 120:
                errors.append(f"[ERROR] Параметр 'num_frames' должен быть в диапазоне от 40 до 120, получено: {num_frames}")
            elif num_frames % 4 != 0:
                errors.append(f"[ERROR] Параметр 'num_frames' должен быть кратен 4, получено: {num_frames}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'num_frames' должен быть числом от 40 до 120 (кратным 4), получено: '{data['num_frames']}'")
    
    # 5. Проверка frames_per_second (опциональный, число 4-60, default: 16)
    if 'frames_per_second' in data and data['frames_per_second'] is not None:
        try:
            frames_per_second = int(data['frames_per_second'])
            if frames_per_second < 4 or frames_per_second > 60:
                errors.append(f"[ERROR] Параметр 'frames_per_second' должен быть в диапазоне от 4 до 60, получено: {frames_per_second}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'frames_per_second' должен быть числом от 4 до 60, получено: '{data['frames_per_second']}'")
    
    # 6. Проверка resolution (опциональный, enum: "480p", "580p", "720p", default: "480p")
    valid_resolutions = ["480p", "580p", "720p"]
    if 'resolution' in data and data['resolution']:
        resolution = str(data['resolution']).strip().lower()
        if resolution not in valid_resolutions:
            errors.append(f"[ERROR] Параметр 'resolution' имеет недопустимое значение: '{data['resolution']}'. Допустимые значения: {', '.join(valid_resolutions)}")
    
    # 7. Проверка negative_prompt (опциональный, строка, макс. 500 символов)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt']).strip()
        if len(negative_prompt) > 500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' превышает максимальную длину 500 символов, получено: {len(negative_prompt)}")
        elif negative_prompt.lower() in ['enter negative prompt...', 'enter content to avoid in the video...', 'describe what you want to avoid in the video...']:
            warnings.append(f"[WARNING] Параметр 'negative_prompt' содержит placeholder: '{negative_prompt}'. Убедитесь, что это валидный негативный промпт")
    
    # 8. Проверка seed (опциональный, число)
    if 'seed' in data and data['seed'] is not None:
        try:
            seed = int(data['seed'])
            # Обычно seed может быть любым целым числом, но проверим на разумные пределы
            if seed < 0 or seed > 2147483647:  # Максимальное значение для 32-bit signed int
                warnings.append(f"[WARNING] Параметр 'seed' имеет необычное значение: {seed}. Обычно seed находится в диапазоне 0-2147483647")
        except (ValueError, TypeError):
            if str(data['seed']).strip().lower() not in ['enter number...', 'enter seed number...', '']:
                errors.append(f"[ERROR] Параметр 'seed' должен быть числом, получено: '{data['seed']}'")
    
    # 9. Проверка num_inference_steps (опциональный, число 2-40, default: 27)
    if 'num_inference_steps' in data and data['num_inference_steps'] is not None:
        try:
            num_inference_steps = int(data['num_inference_steps'])
            if num_inference_steps < 2 or num_inference_steps > 40:
                errors.append(f"[ERROR] Параметр 'num_inference_steps' должен быть в диапазоне от 2 до 40, получено: {num_inference_steps}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'num_inference_steps' должен быть числом от 2 до 40, получено: '{data['num_inference_steps']}'")
    
    # 10. Проверка guidance_scale (опциональный, число 1-10, шаг 0.1, default: 3.5)
    # Форма может передавать "3,5" (с запятой), нужно нормализовать в 3.5
    if 'guidance_scale' in data and data['guidance_scale'] is not None:
        try:
            guidance_scale_str = str(data['guidance_scale']).strip()
            # Заменяем запятую на точку для float
            guidance_scale_str = guidance_scale_str.replace(',', '.')
            guidance_scale = float(guidance_scale_str)
            if guidance_scale < 1.0 or guidance_scale > 10.0:
                errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть в диапазоне от 1.0 до 10.0, получено: {guidance_scale}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'guidance_scale' должен быть числом от 1.0 до 10.0, получено: '{data['guidance_scale']}'")
    
    # 11. Проверка shift (опциональный, число 1.0-10.0, шаг 0.1, default: 5)
    if 'shift' in data and data['shift'] is not None:
        try:
            shift_str = str(data['shift']).strip()
            # Заменяем запятую на точку для float
            shift_str = shift_str.replace(',', '.')
            shift = float(shift_str)
            if shift < 1.0 or shift > 10.0:
                errors.append(f"[ERROR] Параметр 'shift' должен быть в диапазоне от 1.0 до 10.0, получено: {shift}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'shift' должен быть числом от 1.0 до 10.0, получено: '{data['shift']}'")
    
    # 12. Проверка enable_safety_checker (опциональный, boolean, default: True)
    if 'enable_safety_checker' in data and data['enable_safety_checker'] is not None:
        enable_safety_checker = data['enable_safety_checker']
        if not isinstance(enable_safety_checker, bool):
            # Пытаемся преобразовать строку в boolean
            enable_safety_checker_str = str(enable_safety_checker).strip().lower()
            if enable_safety_checker_str not in ['true', 'false', '1', '0', 'yes', 'no']:
                warnings.append(f"[WARNING] Параметр 'enable_safety_checker' должен быть boolean (true/false), получено: '{data['enable_safety_checker']}'. Будет интерпретировано как {enable_safety_checker_str in ['true', '1', 'yes']}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(resolution: str = "480p", duration_seconds: float = 5.0) -> float:
    """
    Вычисляет цену в кредитах на основе resolution и длительности аудио
    
    Args:
        resolution: Разрешение видео ("480p", "580p", "720p")
        duration_seconds: Длительность аудио в секундах (определяется длиной аудиофайла)
        
    Returns:
        float: Цена в кредитах
    """
    # Нормализуем resolution
    resolution = str(resolution).strip().lower()
    
    # Определяем цену за секунду
    if resolution == "720p":
        credits_per_second = 24.0
    elif resolution == "580p":
        credits_per_second = 18.0
    else:  # 480p (по умолчанию)
        credits_per_second = 12.0
    
    # Ограничиваем длительность (минимум 1 секунда)
    if duration_seconds < 1.0:
        duration_seconds = 1.0
    
    return credits_per_second * duration_seconds


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "The lady is talking",  # Обязательный (строка, макс. 5000 символов)
    "image_url": "Upload successfully",  # Обязательный (форма передает image_url, но может быть placeholder)
    "audio_url": "Upload successfully",  # Обязательный (форма передает audio_url, но может быть placeholder)
    "num_frames": "80",  # Опциональный (число 40-120, должно быть кратно 4, default: 80)
    "frames_per_second": "16",  # Опциональный (число 4-60, default: 16)
    "resolution": "480p",  # Опциональный (enum: "480p", "580p", "720p", default: "480p")
    "negative_prompt": "Enter negative prompt...",  # Опциональный (строка, макс. 500 символов)
    "seed": "Enter number...",  # Опциональный (число)
    "num_inference_steps": "27",  # Опциональный (число 2-40, default: 27)
    "guidance_scale": "3,5",  # Опциональный (число 1-10, шаг 0.1, default: 3.5) - форма передает "3,5" (с запятой)
    "shift": "5",  # Опциональный (число 1.0-10.0, шаг 0.1, default: 5)
    "enable_safety_checker": True  # Опциональный (boolean, default: True)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для wan/2-2-a14b-speech-to-video-turbo")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data.get('prompt', '')}'")
    # Проверяем image_url или image_input
    if 'image_url' in test_data:
        print(f"  image_url: '{test_data['image_url']}'")
    elif 'image_input' in test_data:
        print(f"  image_input: {test_data['image_input']}")
    # Проверяем audio_url или audio_input
    if 'audio_url' in test_data:
        print(f"  audio_url: '{test_data['audio_url']}'")
    elif 'audio_input' in test_data:
        print(f"  audio_input: {test_data['audio_input']}")
    print(f"  num_frames: '{test_data.get('num_frames', '80')}'")
    print(f"  frames_per_second: '{test_data.get('frames_per_second', '16')}'")
    print(f"  resolution: '{test_data.get('resolution', '480p')}'")
    print(f"  negative_prompt: '{test_data.get('negative_prompt', '')}'")
    print(f"  seed: '{test_data.get('seed', '')}'")
    print(f"  num_inference_steps: '{test_data.get('num_inference_steps', '27')}'")
    print(f"  guidance_scale: '{test_data.get('guidance_scale', '3.5')}'")
    print(f"  shift: '{test_data.get('shift', '5')}'")
    print(f"  enable_safety_checker: '{test_data.get('enable_safety_checker', 'True')}'")
    print()
    
    is_valid, errors, warnings = validate_wan_2_2_a14b_speech_to_video_turbo_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        # Обрабатываем prompt
        if 'prompt' in test_data and test_data['prompt']:
            prompt = str(test_data['prompt']).strip()
            if prompt.lower() in ['enter your prompt...', 'enter your prompt here...', 'enter number...']:
                print(f"  - prompt: '{prompt}' (placeholder, требуется валидный промпт) [WARNING]")
            else:
                print(f"  - prompt: '{prompt}' (длина: {len(prompt)} символов) [OK]")
        
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
        
        # Обрабатываем audio_url или audio_input
        if 'audio_url' in test_data:
            audio_url = str(test_data['audio_url']).strip()
            if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - audio_url: '{audio_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - audio_url: '{audio_url}' [OK]")
        elif 'audio_input' in test_data:
            audio_input = test_data['audio_input']
            if isinstance(audio_input, list) and len(audio_input) > 0:
                audio_url = str(audio_input[0]).strip()
            else:
                audio_url = str(audio_input).strip()
            if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - audio_input: '{audio_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - audio_input: '{audio_url}' [OK]")
        
        # Обрабатываем num_frames
        if 'num_frames' in test_data and test_data['num_frames'] is not None:
            try:
                num_frames = int(test_data['num_frames'])
                print(f"  - num_frames: '{test_data.get('num_frames', '80')}' -> нормализовано в {num_frames} [OK]")
            except (ValueError, TypeError):
                print(f"  - num_frames: '{test_data.get('num_frames', '80')}' [ERROR]")
        else:
            print(f"  - num_frames: не указан, используется значение по умолчанию 80 [OK]")
        
        # Обрабатываем frames_per_second
        if 'frames_per_second' in test_data and test_data['frames_per_second'] is not None:
            try:
                frames_per_second = int(test_data['frames_per_second'])
                print(f"  - frames_per_second: '{test_data.get('frames_per_second', '16')}' -> нормализовано в {frames_per_second} [OK]")
            except (ValueError, TypeError):
                print(f"  - frames_per_second: '{test_data.get('frames_per_second', '16')}' [ERROR]")
        else:
            print(f"  - frames_per_second: не указан, используется значение по умолчанию 16 [OK]")
        
        # Обрабатываем resolution
        if 'resolution' in test_data and test_data['resolution']:
            resolution = str(test_data['resolution']).strip().lower()
            print(f"  - resolution: '{test_data.get('resolution', '480p')}' -> нормализовано в '{resolution}' [OK]")
        else:
            print(f"  - resolution: не указан, используется значение по умолчанию '480p' [OK]")
        
        # Обрабатываем negative_prompt
        if 'negative_prompt' in test_data and test_data['negative_prompt']:
            negative_prompt = str(test_data['negative_prompt']).strip()
            if negative_prompt.lower() in ['enter negative prompt...', 'enter content to avoid in the video...', 'describe what you want to avoid in the video...']:
                print(f"  - negative_prompt: '{negative_prompt}' (placeholder, опциональный) [WARNING]")
            else:
                print(f"  - negative_prompt: '{negative_prompt}' (длина: {len(negative_prompt)} символов) [OK]")
        else:
            print(f"  - negative_prompt: не указан (опциональный) [OK]")
        
        # Обрабатываем seed
        if 'seed' in test_data and test_data['seed'] is not None:
            seed_str = str(test_data['seed']).strip()
            if seed_str.lower() in ['enter number...', 'enter seed number...', '']:
                print(f"  - seed: '{seed_str}' (placeholder, опциональный) [WARNING]")
            else:
                try:
                    seed = int(seed_str)
                    print(f"  - seed: '{seed_str}' -> нормализовано в {seed} [OK]")
                except ValueError:
                    print(f"  - seed: '{seed_str}' [ERROR]")
        else:
            print(f"  - seed: не указан (опциональный) [OK]")
        
        # Обрабатываем num_inference_steps
        if 'num_inference_steps' in test_data and test_data['num_inference_steps'] is not None:
            try:
                num_inference_steps = int(test_data['num_inference_steps'])
                print(f"  - num_inference_steps: '{test_data.get('num_inference_steps', '27')}' -> нормализовано в {num_inference_steps} [OK]")
            except (ValueError, TypeError):
                print(f"  - num_inference_steps: '{test_data.get('num_inference_steps', '27')}' [ERROR]")
        else:
            print(f"  - num_inference_steps: не указан, используется значение по умолчанию 27 [OK]")
        
        # Обрабатываем guidance_scale
        if 'guidance_scale' in test_data and test_data['guidance_scale'] is not None:
            try:
                guidance_scale_str = str(test_data['guidance_scale']).strip().replace(',', '.')
                guidance_scale = float(guidance_scale_str)
                print(f"  - guidance_scale: '{test_data.get('guidance_scale', '3.5')}' -> нормализовано в {guidance_scale} [OK]")
            except (ValueError, TypeError):
                print(f"  - guidance_scale: '{test_data.get('guidance_scale', '3.5')}' [ERROR]")
        else:
            print(f"  - guidance_scale: не указан, используется значение по умолчанию 3.5 [OK]")
        
        # Обрабатываем shift
        if 'shift' in test_data and test_data['shift'] is not None:
            try:
                shift_str = str(test_data['shift']).strip().replace(',', '.')
                shift = float(shift_str)
                print(f"  - shift: '{test_data.get('shift', '5')}' -> нормализовано в {shift} [OK]")
            except (ValueError, TypeError):
                print(f"  - shift: '{test_data.get('shift', '5')}' [ERROR]")
        else:
            print(f"  - shift: не указан, используется значение по умолчанию 5.0 [OK]")
        
        # Обрабатываем enable_safety_checker
        if 'enable_safety_checker' in test_data and test_data['enable_safety_checker'] is not None:
            enable_safety_checker = test_data['enable_safety_checker']
            if isinstance(enable_safety_checker, bool):
                print(f"  - enable_safety_checker: {enable_safety_checker} [OK]")
            else:
                enable_safety_checker_str = str(enable_safety_checker).strip().lower()
                print(f"  - enable_safety_checker: '{enable_safety_checker}' -> интерпретировано как {enable_safety_checker_str in ['true', '1', 'yes']} [OK]")
        else:
            print(f"  - enable_safety_checker: не указан, используется значение по умолчанию True [OK]")
        
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовый промпт для генерации видео, макс. 5000 символов)")
        print("  - Требуется image_url или image_input (URL изображения, 1 изображение)")
        print("  - Требуется audio_url или audio_input (URL аудиофайла, 1 файл)")
        print("  - Опционально num_frames (количество кадров: 40-120, должно быть кратно 4, по умолчанию 80)")
        print("  - Опционально frames_per_second (кадров в секунду: 4-60, по умолчанию 16)")
        print("  - Опционально resolution (разрешение: 480p, 580p, 720p, по умолчанию 480p)")
        print("  - Опционально negative_prompt (негативный промпт, макс. 500 символов)")
        print("  - Опционально seed (случайное число для контроля генерации)")
        print("  - Опционально num_inference_steps (количество шагов вывода: 2-40, по умолчанию 27)")
        print("  - Опционально guidance_scale (классификатор-free guidance scale: 1-10, шаг 0.1, по умолчанию 3.5)")
        print("  - Опционально shift (значение сдвига: 1.0-10.0, шаг 0.1, по умолчанию 5.0)")
        print("  - Опционально enable_safety_checker (проверка безопасности: true/false, по умолчанию true)")
        print("  - Цена зависит от resolution и длительности аудио")
        print()
        print("[PRICING] Ценообразование:")
        resolution = str(test_data.get('resolution', '480p')).strip().lower()
        # Для расчета цены используем дефолтную длительность 5 секунд (как в bot_kie.py)
        # В реальности длительность определяется длиной аудиофайла
        duration_seconds = 5.0  # Дефолтная длительность для примера
        price = calculate_price_credits(resolution, duration_seconds)
        print(f"  - Цена (для {duration_seconds} секунд, {resolution}): {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * resolution (480p: 12 кредитов/сек, 580p: 18 кредитов/сек, 720p: 24 кредита/сек)")
        print(f"    * длительность аудио (цена умножается на длительность в секундах)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * prompt не влияет на цену")
        print(f"    * image_url/image_input не влияет на цену")
        print(f"    * audio_url/audio_input не влияет на цену (но определяет длительность)")
        print(f"    * num_frames не влияет на цену")
        print(f"    * frames_per_second не влияет на цену")
        print(f"    * negative_prompt не влияет на цену")
        print(f"    * seed не влияет на цену")
        print(f"    * num_inference_steps не влияет на цену")
        print(f"    * guidance_scale не влияет на цену")
        print(f"    * shift не влияет на цену")
        print(f"    * enable_safety_checker не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Цена зависит от resolution и длительности аудио")
        print("    * Длительность определяется длиной аудиофайла")
        print("    * Таблица цен за секунду:")
        print("      * 480p: 12 кредитов за секунду")
        print("      * 580p: 18 кредитов за секунду")
        print("      * 720p: 24 кредита за секунду")
        print("    * Примеры (для дефолтной длительности 5 секунд):")
        print("      * 5 секунд, 480p: 60 кредитов (12 × 5)")
        print("      * 5 секунд, 580p: 90 кредитов (18 × 5)")
        print("      * 5 секунд, 720p: 120 кредитов (24 × 5)")
        print("    * Примеры (для других длительностей):")
        print("      * 10 секунд, 480p: 120 кредитов (12 × 10)")
        print("      * 10 секунд, 580p: 180 кредитов (18 × 10)")
        print("      * 10 секунд, 720p: 240 кредитов (24 × 10)")
        print("      * 3 секунды, 480p: 36 кредитов (12 × 3)")
        print("      * 3 секунды, 580p: 54 кредита (18 × 3)")
        print("      * 3 секунды, 720p: 72 кредита (24 × 3)")
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
    if 'prompt' in test_data and test_data['prompt']:
        prompt = str(test_data['prompt']).strip()
        if prompt.lower() not in ['enter your prompt...', 'enter your prompt here...', 'enter number...']:
            api_data['prompt'] = prompt
    
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
    
    # audio_url или audio_input - обязательный
    # API ожидает audio_url (строка) или audio_input (массив)
    if 'audio_url' in test_data:
        audio_url = str(test_data['audio_url']).strip()
        if audio_url.lower() not in ['upload successfully', 'file 1', 'preview']:
            api_data['audio_url'] = audio_url
    elif 'audio_input' in test_data:
        audio_input = test_data['audio_input']
        if isinstance(audio_input, list):
            if len(audio_input) > 0:
                audio_url = str(audio_input[0]).strip()
                if audio_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                    api_data['audio_url'] = audio_url
        elif isinstance(audio_input, str):
            audio_url = audio_input.strip()
            if audio_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                api_data['audio_url'] = audio_url
    
    # num_frames - опциональный (преобразуем в число)
    if 'num_frames' in test_data and test_data['num_frames'] is not None:
        try:
            num_frames = int(test_data['num_frames'])
            if 40 <= num_frames <= 120 and num_frames % 4 == 0:
                api_data['num_frames'] = num_frames
        except (ValueError, TypeError):
            pass
    
    # frames_per_second - опциональный (преобразуем в число)
    if 'frames_per_second' in test_data and test_data['frames_per_second'] is not None:
        try:
            frames_per_second = int(test_data['frames_per_second'])
            if 4 <= frames_per_second <= 60:
                api_data['frames_per_second'] = frames_per_second
        except (ValueError, TypeError):
            pass
    
    # resolution - опциональный (нормализуем в lowercase)
    if 'resolution' in test_data and test_data['resolution']:
        resolution = str(test_data['resolution']).strip().lower()
        if resolution in ["480p", "580p", "720p"]:
            api_data['resolution'] = resolution
    
    # negative_prompt - опциональный
    if 'negative_prompt' in test_data and test_data['negative_prompt']:
        negative_prompt = str(test_data['negative_prompt']).strip()
        if negative_prompt.lower() not in ['enter negative prompt...', 'enter content to avoid in the video...', 'describe what you want to avoid in the video...']:
            api_data['negative_prompt'] = negative_prompt
    
    # seed - опциональный (преобразуем в число)
    if 'seed' in test_data and test_data['seed'] is not None:
        seed_str = str(test_data['seed']).strip()
        if seed_str.lower() not in ['enter number...', 'enter seed number...', '']:
            try:
                seed = int(seed_str)
                api_data['seed'] = seed
            except ValueError:
                pass
    
    # num_inference_steps - опциональный (преобразуем в число)
    if 'num_inference_steps' in test_data and test_data['num_inference_steps'] is not None:
        try:
            num_inference_steps = int(test_data['num_inference_steps'])
            if 2 <= num_inference_steps <= 40:
                api_data['num_inference_steps'] = num_inference_steps
        except (ValueError, TypeError):
            pass
    
    # guidance_scale - опциональный (преобразуем в float, заменяем запятую на точку)
    if 'guidance_scale' in test_data and test_data['guidance_scale'] is not None:
        try:
            guidance_scale_str = str(test_data['guidance_scale']).strip().replace(',', '.')
            guidance_scale = float(guidance_scale_str)
            if 1.0 <= guidance_scale <= 10.0:
                api_data['guidance_scale'] = guidance_scale
        except (ValueError, TypeError):
            pass
    
    # shift - опциональный (преобразуем в float, заменяем запятую на точку)
    if 'shift' in test_data and test_data['shift'] is not None:
        try:
            shift_str = str(test_data['shift']).strip().replace(',', '.')
            shift = float(shift_str)
            if 1.0 <= shift <= 10.0:
                api_data['shift'] = shift
        except (ValueError, TypeError):
            pass
    
    # enable_safety_checker - опциональный (преобразуем в boolean)
    if 'enable_safety_checker' in test_data and test_data['enable_safety_checker'] is not None:
        enable_safety_checker = test_data['enable_safety_checker']
        if isinstance(enable_safety_checker, bool):
            api_data['enable_safety_checker'] = enable_safety_checker
        else:
            enable_safety_checker_str = str(enable_safety_checker).strip().lower()
            api_data['enable_safety_checker'] = enable_safety_checker_str in ['true', '1', 'yes']
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




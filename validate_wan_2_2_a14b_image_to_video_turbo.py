"""
Валидация входных данных для модели wan/2-2-a14b-image-to-video-turbo
"""

def validate_wan_2_2_a14b_image_to_video_turbo_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели wan/2-2-a14b-image-to-video-turbo
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка image_url или image_input (обязательный, один URL)
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
    
    # 2. Проверка prompt (обязательный, макс. 5000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
        elif len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 5000)")
    
    # 3. Проверка resolution (опциональный, enum: "480p", "580p" или "720p")
    valid_resolutions = ["480p", "580p", "720p"]
    
    if 'resolution' in data and data['resolution']:
        resolution = str(data['resolution']).strip().lower()
        # Убеждаемся, что есть суффикс "p"
        if not resolution.endswith('p'):
            resolution = resolution + 'p'
        
        if resolution not in valid_resolutions:
            errors.append(f"[ERROR] Параметр 'resolution' имеет недопустимое значение: '{data['resolution']}'. Допустимые значения: {', '.join(valid_resolutions)}")
    
    # 4. Проверка aspect_ratio (опциональный, enum: "auto", "16:9", "9:16", "1:1")
    # Форма может передавать "Auto" -> нужно нормализовать в "auto"
    valid_aspect_ratios = ["auto", "16:9", "9:16", "1:1"]
    
    if 'aspect_ratio' in data and data['aspect_ratio']:
        aspect_ratio = str(data['aspect_ratio']).strip().lower()
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)} (или 'Auto' для автоматического определения)")
    
    # 5. Проверка enable_prompt_expansion (опциональный, boolean)
    if 'enable_prompt_expansion' in data and data['enable_prompt_expansion'] is not None:
        enable_prompt_expansion = data['enable_prompt_expansion']
        # Конвертируем строку в boolean, если нужно
        if isinstance(enable_prompt_expansion, str):
            enable_prompt_expansion_str = enable_prompt_expansion.strip().lower()
            if enable_prompt_expansion_str not in ['true', 'false', '1', '0', 'yes', 'no']:
                errors.append(f"[ERROR] Параметр 'enable_prompt_expansion' должен быть boolean (true/false), получено: '{enable_prompt_expansion}'")
        elif not isinstance(enable_prompt_expansion, bool):
            errors.append(f"[ERROR] Параметр 'enable_prompt_expansion' должен быть boolean, получено: {type(enable_prompt_expansion).__name__}")
    
    # 6. Проверка seed (опциональный, целое число от 0 до 2147483647)
    if 'seed' in data and data['seed'] is not None:
        seed = data['seed']
        try:
            # Конвертируем в целое число
            if isinstance(seed, str):
                seed_str = seed.strip()
                # Убираем десятичную часть, если есть
                if '.' in seed_str:
                    seed_str = seed_str.split('.')[0]
                seed_int = int(seed_str)
            elif isinstance(seed, (int, float)):
                seed_int = int(seed)
            else:
                errors.append(f"[ERROR] Параметр 'seed' должен быть числом (целым), получено: {type(seed).__name__}")
                seed_int = None
            
            if seed_int is not None:
                if seed_int < 0 or seed_int > 2147483647:
                    errors.append(f"[ERROR] Параметр 'seed' должен быть в диапазоне от 0 до 2147483647, получено: {seed_int}")
        except ValueError:
            errors.append(f"[ERROR] Параметр 'seed' должен быть числом (целым), получено: '{seed}'")
    
    # 7. Проверка acceleration (опциональный, enum: "none" или "regular")
    # Форма может передавать "None" или "Regular" -> нужно нормализовать в "none" или "regular"
    valid_accelerations = ["none", "regular"]
    
    if 'acceleration' in data and data['acceleration']:
        acceleration = str(data['acceleration']).strip().lower()
        if acceleration not in valid_accelerations:
            errors.append(f"[ERROR] Параметр 'acceleration' имеет недопустимое значение: '{data['acceleration']}'. Допустимые значения: {', '.join(valid_accelerations)} (или 'None'/'Regular' в форме)")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(resolution: str, duration: int = 5) -> int:
    """
    Вычисляет цену в кредитах на основе параметра resolution
    
    Args:
        resolution: Разрешение видео ("480p", "580p" или "720p")
        duration: Длительность видео в секундах (по умолчанию 5 секунд)
        
    Returns:
        int: Цена в кредитах
    """
    resolution = str(resolution).strip().lower()
    # Убеждаемся, что есть суффикс "p"
    if not resolution.endswith('p'):
        resolution = resolution + 'p'
    
    # Цена за секунду в зависимости от разрешения
    if resolution == "720p":
        credits_per_second = 16
    elif resolution == "580p":
        credits_per_second = 12
    else:  # 480p
        credits_per_second = 8
    
    return credits_per_second * duration


# Тестовые данные из запроса пользователя
test_data = {
    "image_url": "Upload successfully",  # Обязательный (форма передает image_url, но может быть placeholder)
    "prompt": "Overcast lighting, medium lens, soft lighting, low contrast lighting, edge lighting, low angle shot, desaturated colors, medium close-up shot, clean single shot, cool colors, center composition.The camera captures a low-angle close-up of a Western man outdoors, sharply dressed in a black coat over a gray sweater, white shirt, and black tie. His gaze is fixed on the lens as he advances. In the background, a brown building looms, its windows glowing with warm, yellow light above a dark doorway. As the camera pushes in, a blurred black object on the right side of the frame drifts back and forth, partially obscuring the view against a dark, nighttime background.",
    "resolution": "720p",  # Опциональный
    "aspect_ratio": "Auto",  # Опциональный (форма передает "Auto", нужно нормализовать в "auto")
    "enable_prompt_expansion": False,  # Опциональный (boolean)
    "seed": 0,  # Опциональный (число)
    "acceleration": "None"  # Опциональный (форма передает "None", нужно нормализовать в "none")
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для wan/2-2-a14b-image-to-video-turbo")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    # Проверяем image_url или image_input
    if 'image_url' in test_data:
        print(f"  image_url: '{test_data['image_url']}'")
    elif 'image_input' in test_data:
        print(f"  image_input: {test_data['image_input']}")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  resolution: '{test_data.get('resolution', '720p')}'")
    print(f"  aspect_ratio: '{test_data.get('aspect_ratio', 'auto')}'")
    print(f"  enable_prompt_expansion: {test_data.get('enable_prompt_expansion', False)}")
    print(f"  seed: {test_data.get('seed', 'не указан')}")
    print(f"  acceleration: '{test_data.get('acceleration', 'none')}'")
    print()
    
    is_valid, errors, warnings = validate_wan_2_2_a14b_image_to_video_turbo_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
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
            print(f"  - image_input: '{image_url}' [OK]")
        
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: до 5000) [OK]")
        
        resolution = str(test_data.get('resolution', '720p')).strip().lower()
        if not resolution.endswith('p'):
            resolution = resolution + 'p'
        print(f"  - resolution: '{test_data.get('resolution', '720p')}' -> нормализовано в '{resolution}' [OK]")
        
        aspect_ratio = str(test_data.get('aspect_ratio', 'auto')).strip().lower()
        print(f"  - aspect_ratio: '{test_data.get('aspect_ratio', 'auto')}' -> нормализовано в '{aspect_ratio}' [OK]")
        
        enable_prompt_expansion = test_data.get('enable_prompt_expansion', False)
        print(f"  - enable_prompt_expansion: {enable_prompt_expansion} [OK]")
        
        seed = test_data.get('seed')
        if seed is not None:
            print(f"  - seed: {seed} [OK]")
        else:
            print(f"  - seed: не указан (опциональный) [OK]")
        
        acceleration = str(test_data.get('acceleration', 'none')).strip().lower()
        print(f"  - acceleration: '{test_data.get('acceleration', 'none')}' -> нормализовано в '{acceleration}' [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image_url или image_input (URL входного изображения, 1 изображение)")
        print("  - Требуется prompt (текстовый промпт для генерации видео, до 5000 символов)")
        print("  - Опционально resolution (разрешение: 480p, 580p или 720p, по умолчанию 720p)")
        print("  - Опционально aspect_ratio (соотношение сторон: auto, 16:9, 9:16, 1:1, по умолчанию auto)")
        print("  - Опционально enable_prompt_expansion (включить расширение промпта с помощью LLM, по умолчанию False)")
        print("  - Опционально seed (случайное число для воспроизводимости, от 0 до 2147483647)")
        print("  - Опционально acceleration (уровень ускорения: none или regular, по умолчанию none)")
        print()
        print("[PRICING] Ценообразование:")
        resolution = str(test_data.get('resolution', '720p')).strip().lower()
        if not resolution.endswith('p'):
            resolution = resolution + 'p'
        # Примечание: длительность видео фиксирована (5 секунд) или определяется автоматически моделью
        default_duration = 5  # Фиксированная длительность для расчета цены
        price = calculate_price_credits(resolution, default_duration)
        print(f"  - Текущая цена: {price} кредитов (при длительности {default_duration} секунд)")
        print(f"  - Параметры влияют на цену:")
        print(f"    * resolution='{resolution}'")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * image_url/image_input не влияет на цену")
        print(f"    * prompt не влияет на цену")
        print(f"    * aspect_ratio не влияет на цену")
        print(f"    * enable_prompt_expansion не влияет на цену")
        print(f"    * seed не влияет на цену")
        print(f"    * acceleration не влияет на цену")
        print()
        print("  - Таблица цен (при длительности 5 секунд):")
        print("    * 480p: 40 кредитов (8 кредитов/сек × 5)")
        print("    * 580p: 60 кредитов (12 кредитов/сек × 5)")
        print("    * 720p: 80 кредитов (16 кредитов/сек × 5)")
        print("  - ВНИМАНИЕ: Длительность видео фиксирована (5 секунд) или определяется автоматически моделью")
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
    
    # prompt - обязательный
    api_data['prompt'] = test_data['prompt']
    
    # resolution - опциональный (нормализуем, добавляя "p" если нужно)
    resolution = str(test_data.get('resolution', '720p')).strip().lower()
    if not resolution.endswith('p'):
        resolution = resolution + 'p'
    api_data['resolution'] = resolution
    
    # aspect_ratio - опциональный (нормализуем "Auto" в "auto")
    if test_data.get('aspect_ratio'):
        aspect_ratio = str(test_data['aspect_ratio']).strip().lower()
        api_data['aspect_ratio'] = aspect_ratio
    
    # enable_prompt_expansion - опциональный (конвертируем в boolean)
    if test_data.get('enable_prompt_expansion') is not None:
        enable_prompt_expansion = test_data['enable_prompt_expansion']
        if isinstance(enable_prompt_expansion, str):
            enable_prompt_expansion = enable_prompt_expansion.strip().lower()
            api_data['enable_prompt_expansion'] = enable_prompt_expansion in ['true', '1', 'yes']
        else:
            api_data['enable_prompt_expansion'] = bool(enable_prompt_expansion)
    
    # seed - опциональный (конвертируем в целое число)
    if test_data.get('seed') is not None:
        seed = test_data['seed']
        if isinstance(seed, str):
            seed_str = seed.strip()
            if '.' in seed_str:
                seed_str = seed_str.split('.')[0]
            api_data['seed'] = int(seed_str)
        else:
            api_data['seed'] = int(seed)
    
    # acceleration - опциональный (нормализуем "None"/"Regular" в "none"/"regular")
    if test_data.get('acceleration'):
        acceleration = str(test_data['acceleration']).strip().lower()
        api_data['acceleration'] = acceleration
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))


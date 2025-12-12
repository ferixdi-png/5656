"""
Валидация входных данных для модели elevenlabs/speech-to-text
"""

def validate_elevenlabs_speech_to_text_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели elevenlabs/speech-to-text
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка audio_url (обязательный, строка, URL аудиофайла)
    if 'audio_url' not in data or not data['audio_url']:
        errors.append("[ERROR] Параметр 'audio_url' обязателен и не может быть пустым")
    else:
        audio_url = str(data['audio_url']).strip()
        if not audio_url:
            errors.append("[ERROR] Параметр 'audio_url' не может быть пустой строкой")
        elif audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
            warnings.append(f"[WARNING] Параметр 'audio_url' содержит placeholder: '{audio_url}'. Убедитесь, что это валидный URL аудиофайла")
    
    # 2. Проверка language_code (опциональный, строка, макс. 500 символов, default: "ru")
    if 'language_code' in data and data['language_code']:
        language_code = str(data['language_code']).strip()
        if len(language_code) > 500:
            errors.append(f"[ERROR] Параметр 'language_code' превышает максимальную длину 500 символов, получено: {len(language_code)}")
    
    # 3. Проверка tag_audio_events (опциональный, boolean, default: False)
    if 'tag_audio_events' in data and data['tag_audio_events'] is not None:
        tag_audio_events = data['tag_audio_events']
        if not isinstance(tag_audio_events, bool):
            # Пытаемся преобразовать строку в boolean
            tag_audio_events_str = str(tag_audio_events).strip().lower()
            if tag_audio_events_str not in ['true', 'false', '1', '0', 'yes', 'no']:
                warnings.append(f"[WARNING] Параметр 'tag_audio_events' должен быть boolean (true/false), получено: '{data['tag_audio_events']}'. Будет интерпретировано как {tag_audio_events_str in ['true', '1', 'yes']}")
    
    # 4. Проверка diarize (опциональный, boolean, default: False)
    if 'diarize' in data and data['diarize'] is not None:
        diarize = data['diarize']
        if not isinstance(diarize, bool):
            # Пытаемся преобразовать строку в boolean
            diarize_str = str(diarize).strip().lower()
            if diarize_str not in ['true', 'false', '1', '0', 'yes', 'no']:
                warnings.append(f"[WARNING] Параметр 'diarize' должен быть boolean (true/false), получено: '{data['diarize']}'. Будет интерпретировано как {diarize_str in ['true', '1', 'yes']}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(duration_minutes: float = 1.0) -> float:
    """
    Вычисляет цену в кредитах на основе длительности аудио
    
    Args:
        duration_minutes: Длительность аудио в минутах (определяется длиной аудиофайла)
        
    Returns:
        float: Цена в кредитах
    """
    # Цена: 3.5 кредитов за минуту
    credits_per_minute = 3.5
    
    # Ограничиваем длительность (минимум 0.1 минуты)
    if duration_minutes < 0.1:
        duration_minutes = 0.1
    
    return credits_per_minute * duration_minutes


# Тестовые данные из запроса пользователя
test_data = {
    "audio_url": "Upload successfully",  # Обязательный (форма передает audio_url, но может быть placeholder)
    "language_code": "eng",  # Опциональный (строка, макс. 500 символов, default: "ru")
    "tag_audio_events": None,  # Опциональный (boolean, default: False) - в форме есть чекбокс, но не указано значение
    "diarize": None  # Опциональный (boolean, default: False) - в форме есть чекбокс, но не указано значение
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для elevenlabs/speech-to-text")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  audio_url: '{test_data.get('audio_url', '')}'")
    print(f"  language_code: '{test_data.get('language_code', 'ru')}'")
    print(f"  tag_audio_events: '{test_data.get('tag_audio_events', 'False')}'")
    print(f"  diarize: '{test_data.get('diarize', 'False')}'")
    print()
    
    is_valid, errors, warnings = validate_elevenlabs_speech_to_text_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        # Обрабатываем audio_url
        if 'audio_url' in test_data and test_data['audio_url']:
            audio_url = str(test_data['audio_url']).strip()
            if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - audio_url: '{audio_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - audio_url: '{audio_url}' [OK]")
        
        # Обрабатываем language_code
        if 'language_code' in test_data and test_data['language_code']:
            language_code = str(test_data['language_code']).strip()
            print(f"  - language_code: '{language_code}' (длина: {len(language_code)} символов) [OK]")
        else:
            print(f"  - language_code: не указан, используется значение по умолчанию 'ru' [OK]")
        
        # Обрабатываем tag_audio_events
        if 'tag_audio_events' in test_data and test_data['tag_audio_events'] is not None:
            tag_audio_events = test_data['tag_audio_events']
            if isinstance(tag_audio_events, bool):
                print(f"  - tag_audio_events: {tag_audio_events} [OK]")
            else:
                tag_audio_events_str = str(tag_audio_events).strip().lower()
                print(f"  - tag_audio_events: '{tag_audio_events}' -> интерпретировано как {tag_audio_events_str in ['true', '1', 'yes']} [OK]")
        else:
            print(f"  - tag_audio_events: не указан, используется значение по умолчанию False [OK]")
        
        # Обрабатываем diarize
        if 'diarize' in test_data and test_data['diarize'] is not None:
            diarize = test_data['diarize']
            if isinstance(diarize, bool):
                print(f"  - diarize: {diarize} [OK]")
            else:
                diarize_str = str(diarize).strip().lower()
                print(f"  - diarize: '{diarize}' -> интерпретировано как {diarize_str in ['true', '1', 'yes']} [OK]")
        else:
            print(f"  - diarize: не указан, используется значение по умолчанию False [OK]")
        
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется audio_url (URL аудиофайла для транскрибации)")
        print("  - Опционально language_code (код языка аудио, макс. 500 символов, по умолчанию 'ru')")
        print("  - Опционально tag_audio_events (тегировать аудио-события: true/false, по умолчанию false)")
        print("  - Опционально diarize (разделять говорящих: true/false, по умолчанию false)")
        print("  - Поддерживаемые форматы: audio/mpeg, audio/wav, audio/x-wav, audio/aac, audio/mp4, audio/ogg")
        print("  - Максимальный размер файла: 200.0MB")
        print("  - Цена зависит от длительности аудио")
        print()
        print("[PRICING] Ценообразование:")
        # Для расчета цены используем дефолтную длительность 1 минуту (как в bot_kie.py)
        # В реальности длительность определяется длиной аудиофайла
        duration_minutes = 1.0  # Дефолтная длительность для примера
        price = calculate_price_credits(duration_minutes)
        print(f"  - Цена (для {duration_minutes} минуты/минут): {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * длительность аудио (цена умножается на длительность в минутах)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * audio_url не влияет на цену (но определяет длительность)")
        print(f"    * language_code не влияет на цену")
        print(f"    * tag_audio_events не влияет на цену")
        print(f"    * diarize не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Цена зависит от длительности аудио")
        print("    * Длительность определяется длиной аудиофайла")
        print("    * Таблица цен:")
        print("      * 3.5 кредитов за минуту")
        print("    * Примеры:")
        print("      * 1 минута: 3.5 кредитов (3.5 × 1)")
        print("      * 2 минуты: 7 кредитов (3.5 × 2)")
        print("      * 5 минут: 17.5 кредитов (3.5 × 5)")
        print("      * 10 минут: 35 кредитов (3.5 × 10)")
        print("      * 0.5 минуты (30 секунд): 1.75 кредита (3.5 × 0.5)")
        print("      * 3 минуты: 10.5 кредитов (3.5 × 3)")
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
    
    # audio_url - обязательный
    if 'audio_url' in test_data and test_data['audio_url']:
        audio_url = str(test_data['audio_url']).strip()
        if audio_url.lower() not in ['upload successfully', 'file 1', 'preview']:
            api_data['audio_url'] = audio_url
    
    # language_code - опциональный
    if 'language_code' in test_data and test_data['language_code']:
        language_code = str(test_data['language_code']).strip()
        if language_code:
            api_data['language_code'] = language_code
    
    # tag_audio_events - опциональный (преобразуем в boolean)
    if 'tag_audio_events' in test_data and test_data['tag_audio_events'] is not None:
        tag_audio_events = test_data['tag_audio_events']
        if isinstance(tag_audio_events, bool):
            api_data['tag_audio_events'] = tag_audio_events
        else:
            tag_audio_events_str = str(tag_audio_events).strip().lower()
            api_data['tag_audio_events'] = tag_audio_events_str in ['true', '1', 'yes']
    
    # diarize - опциональный (преобразуем в boolean)
    if 'diarize' in test_data and test_data['diarize'] is not None:
        diarize = test_data['diarize']
        if isinstance(diarize, bool):
            api_data['diarize'] = diarize
        else:
            diarize_str = str(diarize).strip().lower()
            api_data['diarize'] = diarize_str in ['true', '1', 'yes']
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




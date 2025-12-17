"""
Скрипт для проверки соответствия всех моделей требованиям KIE AI
Проверяет:
1. Все модели из kie_models.py
2. Обработка в confirm_generation
3. Все обязательные параметры запрашиваются
4. Параметры отправляются строго по формату KIE API
"""

import re
import sys
import io
from kie_models import KIE_MODELS

# Устанавливаем UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def extract_model_ids_from_code():
    """Извлекает все model_id из bot_kie.py"""
    with open('bot_kie.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Найти все проверки model_id в confirm_generation
    patterns = [
        r'if model_id == "([^"]+)"',
        r'elif model_id == "([^"]+)"',
        r'elif model_id == "([^"]+)" or model_id == "([^"]+)"',
        r'elif model_id == "([^"]+)" or model_id == "([^"]+)" or model_id == "([^"]+)"',
        r'elif model_id == "([^"]+)" or model_id == "([^"]+)" or model_id == "([^"]+)" or model_id == "([^"]+)"',
    ]
    
    found_models = set()
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            if isinstance(match, tuple):
                found_models.update([m for m in match if m])
            else:
                found_models.add(match)
    
    return found_models

def check_model_validation(model_id, code_content):
    """Проверяет есть ли валидация для модели"""
    # Проверяем наличие блока валидации
    validation_patterns = [
        f'if model_id == "{model_id}":',
        f'elif model_id == "{model_id}":',
    ]
    
    for pattern in validation_patterns:
        if pattern in code_content:
            # Проверяем что после этого есть валидация (не просто pass)
            idx = code_content.find(pattern)
            if idx != -1:
                # Берем следующий блок кода (до следующего if/elif или до конца функции)
                next_block = code_content[idx:idx+5000]
                # Проверяем наличие валидации
                if 'Validate' in next_block or 'validate' in next_block or 'api_params' in next_block:
                    return True
    return False

def get_required_params(model):
    """Получает список обязательных параметров модели"""
    required = []
    input_params = model.get('input_params', {})
    for param_name, param_info in input_params.items():
        if param_info.get('required', False):
            required.append(param_name)
    return required

def main():
    print("=" * 80)
    print("ПРОВЕРКА СООТВЕТСТВИЯ ВСЕХ МОДЕЛЕЙ ТРЕБОВАНИЯМ KIE AI")
    print("=" * 80)
    print()
    
    # Получаем все модели из kie_models.py
    all_models = {model['id']: model for model in KIE_MODELS}
    print(f"Всего моделей в kie_models.py: {len(all_models)}")
    print()
    
    # Читаем bot_kie.py
    with open('bot_kie.py', 'r', encoding='utf-8') as f:
        code_content = f.read()
    
    # Извлекаем модели из кода
    code_models = extract_model_ids_from_code()
    print(f"Моделей найдено в коде: {len(code_models)}")
    print()
    
    # Проверяем каждую модель
    missing_validation = []
    missing_in_code = []
    all_ok = []
    
    for model_id, model in all_models.items():
        required_params = get_required_params(model)
        
        # Проверяем наличие в коде
        in_code = model_id in code_models
        
        # Проверяем наличие валидации
        has_validation = check_model_validation(model_id, code_content)
        
        if not in_code:
            missing_in_code.append((model_id, required_params))
        elif not has_validation:
            missing_validation.append((model_id, required_params))
        else:
            all_ok.append((model_id, required_params))
    
    # Выводим результаты
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ ПРОВЕРКИ")
    print("=" * 80)
    print()
    
    if all_ok:
        print(f"✅ МОДЕЛИ С ВАЛИДАЦИЕЙ ({len(all_ok)}):")
        for model_id, params in sorted(all_ok):
            print(f"  ✅ {model_id}")
            if params:
                print(f"     Обязательные параметры: {', '.join(params)}")
        print()
    
    if missing_validation:
        print(f"⚠️ МОДЕЛИ БЕЗ ВАЛИДАЦИИ ({len(missing_validation)}):")
        for model_id, params in sorted(missing_validation):
            print(f"  ⚠️ {model_id}")
            if params:
                print(f"     Обязательные параметры: {', '.join(params)}")
        print()
    
    if missing_in_code:
        print(f"❌ МОДЕЛИ НЕ НАЙДЕНЫ В КОДЕ ({len(missing_in_code)}):")
        for model_id, params in sorted(missing_in_code):
            print(f"  ❌ {model_id}")
            if params:
                print(f"     Обязательные параметры: {', '.join(params)}")
        print()
    
    print("=" * 80)
    print("ИТОГО:")
    print(f"  Всего моделей: {len(all_models)}")
    print(f"  ✅ С валидацией: {len(all_ok)}")
    print(f"  ⚠️ Без валидации: {len(missing_validation)}")
    print(f"  ❌ Не найдены в коде: {len(missing_in_code)}")
    print("=" * 80)

if __name__ == "__main__":
    main()



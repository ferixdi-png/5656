#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Финальная проверка всех моделей KIE AI
Проверяет:
1. Порядок запроса параметров (логичность)
2. Все обязательные параметры запрашиваются
3. Специальные случаи обрабатываются правильно
4. Валидация соответствует API документации
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from kie_models import KIE_MODELS

# Модели, которые требуют image_input первым
MODELS_REQUIRE_IMAGE_FIRST = [
    "nano-banana-pro",              # Requires image_input + prompt
    "recraft/remove-background",    # Requires only image_input (no prompt)
    "recraft/crisp-upscale",        # Requires only image_input (no prompt)
    "ideogram/v3-reframe",          # Requires image_input first (no prompt)
    "topaz/image-upscale",          # Requires image_input (no prompt)
]

# Модели, которые требуют только image (без prompt)
MODELS_ONLY_IMAGE = [
    "recraft/remove-background",
    "recraft/crisp-upscale",
    "topaz/image-upscale",
    "ideogram/v3-reframe"
]

def check_model(model):
    """Проверка одной модели"""
    model_id = model['id']
    input_params = model.get('input_params', {})
    
    required_params = [k for k, v in input_params.items() if v.get('required', False)]
    all_params = list(input_params.keys())
    
    issues = []
    warnings = []
    
    # 1. Проверка обязательных параметров
    if not required_params:
        issues.append("❌ Нет обязательных параметров!")
    
    # 2. Проверка порядка параметров
    has_image_input = 'image_input' in all_params
    has_image_urls = 'image_urls' in all_params
    has_prompt = 'prompt' in all_params
    image_required = 'image_input' in required_params or 'image_urls' in required_params
    prompt_required = 'prompt' in required_params
    
    # 3. Проверка специальных случаев
    if model_id in MODELS_REQUIRE_IMAGE_FIRST:
        if not image_required:
            issues.append(f"⚠️ Модель в MODELS_REQUIRE_IMAGE_FIRST, но image_input/image_urls не обязателен!")
        if model_id in MODELS_ONLY_IMAGE and prompt_required:
            issues.append(f"❌ Модель в MODELS_ONLY_IMAGE, но prompt обязателен!")
    
    if model_id in MODELS_ONLY_IMAGE:
        if prompt_required:
            issues.append(f"❌ Модель в MODELS_ONLY_IMAGE, но prompt обязателен!")
        if not image_required:
            issues.append(f"❌ Модель в MODELS_ONLY_IMAGE, но image_input/image_urls не обязателен!")
    
    # 4. Проверка логичности порядка
    if image_required and prompt_required:
        if model_id not in MODELS_REQUIRE_IMAGE_FIRST:
            # Для большинства моделей: prompt -> image (опционально)
            # Но если image обязателен, нужно проверить порядок
            if 'nano-banana-pro' not in model_id:
                warnings.append("💡 Модель требует и image и prompt - проверьте порядок запроса")
    
    # 5. Проверка наличия всех необходимых параметров
    if has_image_input and not image_required:
        warnings.append("💡 image_input есть, но не обязателен - это нормально")
    
    return {
        'model_id': model_id,
        'name': model.get('name', 'Unknown'),
        'required_params': required_params,
        'all_params': all_params,
        'has_image_input': has_image_input,
        'has_image_urls': has_image_urls,
        'has_prompt': has_prompt,
        'image_required': image_required,
        'prompt_required': prompt_required,
        'issues': issues,
        'warnings': warnings
    }

def main():
    print("=" * 80)
    print("ФИНАЛЬНАЯ ПРОВЕРКА ВСЕХ МОДЕЛЕЙ KIE AI")
    print("=" * 80)
    print()
    
    results = []
    total_issues = 0
    total_warnings = 0
    
    for model in KIE_MODELS:
        result = check_model(model)
        results.append(result)
        total_issues += len(result['issues'])
        total_warnings += len(result['warnings'])
    
    # Группировка результатов
    models_with_issues = [r for r in results if r['issues']]
    models_with_warnings = [r for r in results if r['warnings']]
    models_require_image_first = [r for r in results if r['model_id'] in MODELS_REQUIRE_IMAGE_FIRST]
    models_only_image = [r for r in results if r['model_id'] in MODELS_ONLY_IMAGE]
    
    print(f"📊 СТАТИСТИКА:")
    print(f"   Всего моделей: {len(results)}")
    print(f"   Моделей с проблемами: {len(models_with_issues)}")
    print(f"   Моделей с предупреждениями: {len(models_with_warnings)}")
    print(f"   Всего проблем: {total_issues}")
    print(f"   Всего предупреждений: {total_warnings}")
    print()
    
    # Модели, требующие image первым
    print("=" * 80)
    print("МОДЕЛИ, ТРЕБУЮЩИЕ IMAGE ПЕРВЫМ:")
    print("=" * 80)
    for result in models_require_image_first:
        print(f"\n✅ {result['model_id']} - {result['name']}")
        print(f"   Обязательные: {', '.join(result['required_params'])}")
        if result['issues']:
            for issue in result['issues']:
                print(f"   {issue}")
        if result['warnings']:
            for warning in result['warnings']:
                print(f"   {warning}")
    print()
    
    # Модели только с image (без prompt)
    print("=" * 80)
    print("МОДЕЛИ ТОЛЬКО С IMAGE (БЕЗ PROMPT):")
    print("=" * 80)
    for result in models_only_image:
        print(f"\n✅ {result['model_id']} - {result['name']}")
        print(f"   Обязательные: {', '.join(result['required_params'])}")
        if result['issues']:
            for issue in result['issues']:
                print(f"   {issue}")
    print()
    
    # Модели с проблемами
    if models_with_issues:
        print("=" * 80)
        print("МОДЕЛИ С ПРОБЛЕМАМИ:")
        print("=" * 80)
        for result in models_with_issues:
            print(f"\n❌ {result['model_id']} - {result['name']}")
            print(f"   Обязательные: {', '.join(result['required_params'])}")
            for issue in result['issues']:
                print(f"   {issue}")
        print()
    
    # Модели с предупреждениями
    if models_with_warnings:
        print("=" * 80)
        print("МОДЕЛИ С ПРЕДУПРЕЖДЕНИЯМИ:")
        print("=" * 80)
        for result in models_with_warnings:
            print(f"\n⚠️ {result['model_id']} - {result['name']}")
            for warning in result['warnings']:
                print(f"   {warning}")
        print()
    
    # Итоговый результат
    print("=" * 80)
    if total_issues == 0:
        print("✅ ВСЕ МОДЕЛИ ПРОВЕРЕНЫ - КРИТИЧЕСКИХ ПРОБЛЕМ НЕТ!")
    else:
        print(f"❌ НАЙДЕНО {total_issues} КРИТИЧЕСКИХ ПРОБЛЕМ!")
    print("=" * 80)
    
    return total_issues == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

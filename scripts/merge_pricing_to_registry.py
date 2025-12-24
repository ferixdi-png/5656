#!/usr/bin/env python3
"""
Мерж pricing в KIE_SOURCE_OF_TRUTH.json
Добавляет цены из artifacts/pricing_table.json
"""

import json
from pathlib import Path
from typing import Dict


def load_pricing() -> Dict:
    """Загружаем pricing table"""
    pricing_file = Path("artifacts/pricing_table.json")
    with open(pricing_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Создаем mapping model_id -> pricing
    pricing_map = {}
    for model in data['models']:
        model_id = model['model_id']
        pricing_map[model_id] = {
            "credits_per_gen": model.get('price_usd', 0) * 200,  # 1 USD = 200 credits
            "usd_per_gen": model['price_usd'],
            "rub_per_gen": model['price_rub'],
            "is_free": model.get('is_free', False),
            "rank": model['rank']
        }
    
    return pricing_map


def merge_pricing_into_registry():
    """Мерж pricing в registry"""
    
    # Загружаем registry
    registry_file = Path("models/KIE_SOURCE_OF_TRUTH.json")
    with open(registry_file, 'r', encoding='utf-8') as f:
        registry = json.load(f)
    
    # Загружаем pricing
    pricing_map = load_pricing()
    
    print("=" * 80)
    print("💰 MERGING PRICING INTO REGISTRY")
    print("=" * 80)
    print(f"\nRegistry models: {len(registry['models'])}")
    print(f"Pricing models: {len(pricing_map)}")
    
    # Мерж
    matched = 0
    unmatched = []
    
    for model_id, model_data in registry['models'].items():
        # Проверяем точное совпадение
        if model_id in pricing_map:
            model_data['pricing'] = pricing_map[model_id]
            matched += 1
        else:
            # Пробуем нормализацию
            # Убираем version suffixes и пробуем снова
            normalized_id = model_id.split('/')[0] + '/' + model_id.split('/')[1].split('-')[0]
            
            if normalized_id in pricing_map:
                model_data['pricing'] = pricing_map[normalized_id]
                matched += 1
            else:
                unmatched.append(model_id)
    
    print(f"\n✅ Matched: {matched}")
    print(f"⚠️  Unmatched: {len(unmatched)}")
    
    if unmatched:
        print(f"\nUnmatched models (first 10):")
        for mid in unmatched[:10]:
            print(f"  - {mid}")
    
    # Сохраняем обновленный registry
    with open(registry_file, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Registry updated: {registry_file}")
    
    # Статистика
    with_pricing = sum(1 for m in registry['models'].values() if m.get('pricing'))
    free_count = sum(1 for m in registry['models'].values() if m.get('pricing', {}).get('is_free'))
    
    print(f"\n📊 Final stats:")
    print(f"   - Models with pricing: {with_pricing}/{len(registry['models'])}")
    print(f"   - Free models: {free_count}")
    print(f"   - Paid models: {with_pricing - free_count}")


if __name__ == "__main__":
    merge_pricing_into_registry()

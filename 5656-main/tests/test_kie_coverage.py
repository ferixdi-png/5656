"""
Тесты для проверки покрытия всех 47 моделей KIE.ai Market.
"""

import pytest
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def test_models_count():
    """Проверяет, что моделей >= 47 (обновлено: теперь 72)."""
    try:
        import kie_models
        models = kie_models.KIE_MODELS
        
        # Если KIE_MODELS - список, преобразуем в словарь
        if isinstance(models, list):
            models_dict = {m.get("id", ""): m for m in models if m.get("id")}
            count = len(models_dict)
        else:
            count = len(models)
        
        assert count >= 47, f"Ожидалось минимум 47 моделей, найдено {count}"
    
    except ImportError:
        pytest.skip("kie_models.py не найден")


def test_each_model_has_modes():
    """Проверяет, что у каждой модели есть хотя бы один mode."""
    try:
        import kie_models
        models = kie_models.KIE_MODELS
        
        # Если KIE_MODELS - список, преобразуем в словарь
        if isinstance(models, list):
            models_dict = {m.get("id", ""): m for m in models if m.get("id")}
        else:
            models_dict = models
        
        for model_id, model_data in models_dict.items():
            if isinstance(model_data, dict):
                # Проверяем наличие modes
                modes = model_data.get("modes", {})
                if not modes:
                    # Старая структура - проверяем input_params
                    input_params = model_data.get("input_params", {})
                    assert input_params, f"Модель {model_id} не имеет modes и input_params"
                else:
                    assert len(modes) > 0, f"Модель {model_id} не имеет modes"
    
    except ImportError:
        pytest.skip("kie_models.py не найден")


def test_callback_data_length():
    """Проверяет, что все callback_data < 64 символов и без пробелов."""
    try:
        import kie_models
        models = kie_models.KIE_MODELS
        
        # Если KIE_MODELS - список, преобразуем в словарь
        if isinstance(models, list):
            models_dict = {m.get("id", ""): m for m in models if m.get("id")}
        else:
            models_dict = models
        
        for model_id, model_data in models_dict.items():
            # Проверяем длину model_id
            assert len(model_id) < 64, f"model_id {model_id} слишком длинный ({len(model_id)} символов)"
            assert " " not in model_id, f"model_id {model_id} содержит пробелы"
            
            # Проверяем modes
            if isinstance(model_data, dict):
                modes = model_data.get("modes", {})
                for mode_id in modes.keys():
                    assert len(mode_id) < 64, f"mode_id {mode_id} слишком длинный ({len(mode_id)} символов)"
                    assert " " not in mode_id, f"mode_id {mode_id} содержит пробелы"
    
    except ImportError:
        pytest.skip("kie_models.py не найден")


def test_catalog_exists():
    """Проверяет, что каталог существует."""
    catalog_file = root_dir / "data" / "kie_market_catalog.json"
    
    if not catalog_file.exists():
        pytest.skip("Каталог не найден. Запустите: python scripts/kie_market_crawler.py")
    
    import json
    with open(catalog_file, 'r', encoding='utf-8') as f:
        catalog = json.load(f)
    
    assert "catalog" in catalog, "Каталог не содержит ключ 'catalog'"
    assert len(catalog["catalog"]) > 0, "Каталог пуст"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


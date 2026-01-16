"""
Tests for model registry validation (YAML/JSON catalogs).
"""
from app.models import yaml_registry
from app.ui import marketing_menu


def test_validate_registry_models_skips_invalid_entries():
    models_dict = {
        "good_model": {"model_id": "good_model", "category": "image"},
        "missing_category": {"model_id": "missing_category"},
        "bad_category": {"model_id": "bad_category", "category": "unknown"},
        "non_dict": "oops",
    }

    validated = marketing_menu._validate_registry_models(models_dict)

    assert len(validated) == 1
    assert validated[0]["model_id"] == "good_model"


def test_validate_yaml_models_skips_invalid_entries():
    models_dict = {
        "valid": {"model_type": "text_to_image", "input": {"prompt": {"type": "string"}}},
        "no_type": {"input": {"prompt": {"type": "string"}}},
        "no_input": {"model_type": "text_to_image"},
        "bad_category": {"model_type": "text_to_image", "input": {"prompt": {"type": "string"}}, "category": "bad"},
    }

    validated = yaml_registry._validate_yaml_models(models_dict)

    assert list(validated.keys()) == ["valid"]

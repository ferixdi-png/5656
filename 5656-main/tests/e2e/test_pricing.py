"""
E2E tests for parameterized pricing integration.
"""

import pytest
from decimal import Decimal
from pathlib import Path

from app.pricing.parameterized import ParameterizedPricing, calculate_price_rub


@pytest.fixture
def pricing_engine():
    """Create pricing engine instance."""
    return ParameterizedPricing()


def test_pricing_engine_loads(pricing_engine):
    """Test that pricing engine loads pricing data."""
    assert pricing_engine._pricing_data is not None
    assert "models" in pricing_engine._pricing_data


def test_get_price_exact_match(pricing_engine):
    """Test getting price with exact parameter match."""
    model_id = "bytedance/seedance-1.5-pro"
    params = {
        "duration": "12s",
        "resolution": "720p",
        "audio": "WITH"
    }
    
    price = pricing_engine.get_price(model_id, params, io_type="video")
    
    assert price is not None
    assert isinstance(price, Decimal)
    assert price > 0


def test_get_price_fallback(pricing_engine):
    """Test getting price with fallback logic."""
    model_id = "bytedance/seedance-1.5-pro"
    params = {
        "duration": "10s",  # Not exact match, should use fallback
        "resolution": "720p",
        "audio": "WITH"
    }
    
    price = pricing_engine.get_price(model_id, params, io_type="video")
    
    # Should find nearest match (12s or 8s)
    assert price is not None
    assert isinstance(price, Decimal)
    assert price > 0


def test_get_price_no_match(pricing_engine):
    """Test getting price for model not in pricing data."""
    model_id = "nonexistent/model"
    params = {"duration": "12s"}
    
    price = pricing_engine.get_price(model_id, params)
    
    assert price is None


def test_format_price_display(pricing_engine):
    """Test price display formatting."""
    model_id = "bytedance/seedance-1.5-pro"
    params = {
        "duration": "12s",
        "resolution": "720p",
        "audio": "WITH"
    }
    
    display = pricing_engine.format_price_display(model_id, params, io_type="video")
    
    assert "Модель:" in display
    assert "Параметры:" in display
    assert "Цена:" in display
    assert "₽" in display


def test_calculate_price_rub_function():
    """Test global calculate_price_rub function."""
    model_id = "bytedance/seedance-1.5-pro"
    params = {
        "duration": "12s",
        "resolution": "720p",
        "audio": "WITH"
    }
    
    price = calculate_price_rub(model_id, params, io_type="video")
    
    assert price is not None
    assert isinstance(price, Decimal)


def test_pricing_integration_with_payments_module():
    """Test that pricing integrates with app.payments.pricing module."""
    from app.payments.pricing import calculate_kie_cost
    
    model = {
        "model_id": "bytedance/seedance-1.5-pro",
        "category": "video"
    }
    user_inputs = {
        "duration": "12s",
        "resolution": "720p",
        "audio": "WITH",
        "prompt": "test"
    }
    
    # Should use parameterized pricing
    cost = calculate_kie_cost(model, user_inputs)
    
    assert cost > 0
    assert isinstance(cost, float)


def test_pricing_json_exists():
    """Test that pricing JSON file exists and is valid."""
    pricing_path = Path(__file__).parent.parent.parent / "pricing" / "KIE_PRICING_RUB.json"
    
    assert pricing_path.exists(), f"Pricing file not found: {pricing_path}"
    
    import json
    with open(pricing_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    assert "models" in data
    assert len(data["models"]) > 0




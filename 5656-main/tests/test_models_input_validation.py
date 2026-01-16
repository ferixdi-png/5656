"""
Tests: UX validation for required model input fields.
"""
import pytest


def test_field_prompt_generation():
    """Test that field prompts are generated for all input types."""
    from bot.handlers.flow import _field_prompt
    
    # Test prompt field (most common)
    prompt = _field_prompt("prompt", {"type": "string", "description": "What to generate"})
    assert "Опишите" in prompt or "✍️" in prompt, "Prompt should be human-friendly"
    
    # Test URL field
    url_prompt = _field_prompt("image_url", {"type": "url"})
    assert "ссылку" in url_prompt or "🔗" in url_prompt, "URL field should explain linking"
    
    # Test file field
    file_prompt = _field_prompt("image", {"type": "file"})
    assert "Загрузьте" in file_prompt or "📎" in file_prompt, "File field should explain uploading"


def test_field_validation_required():
    """Test that required fields are validated before generation."""
    from bot.handlers.flow import _validate_field_value
    from app.kie.validator import ModelContractError
    
    # Valid input
    _validate_field_value("hello world", {"type": "string", "max_length": 100}, "text")
    
    # Invalid: too long
    with pytest.raises(ModelContractError):
        _validate_field_value("x" * 101, {"type": "string", "max_length": 100}, "text")
    
    # Invalid enum
    with pytest.raises(ModelContractError):
        _validate_field_value("invalid", {"type": "string", "enum": ["a", "b"]}, "choice")


def test_input_context_tracks_required_optional():
    """Test that InputContext tracks which fields are required vs optional."""
    from bot.handlers.flow import InputContext
    
    ctx = InputContext(
        model_id="test_model",
        required_fields=["prompt", "image_size"],
        optional_fields=["style", "quality"],
        properties={},
        collected={},
    )
    
    assert len(ctx.required_fields) == 2
    assert len(ctx.optional_fields) == 2
    assert not ctx.collecting_optional, "Should start with required fields"

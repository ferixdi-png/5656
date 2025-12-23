import pytest

from bot.flow.input_wizard import InputWizard, WizardStep
from app.kie.validator import ModelContractError


def test_wizard_enforces_enum():
    model = {
        "model_id": "test_model",
        "input_schema": {
            "required": ["tone"],
            "properties": {
                "tone": {"type": "string", "enum": ["calm", "bold"]}
            },
        },
    }
    wizard = InputWizard(model)
    step = wizard.steps()[0]
    with pytest.raises(ModelContractError):
        wizard.validate("other", step)


def test_wizard_max_length():
    model = {
        "model_id": "test_model",
        "input_schema": {
            "required": ["prompt"],
            "properties": {
                "prompt": {"type": "string", "max_length": 5}
            },
        },
    }
    wizard = InputWizard(model)
    step = wizard.steps()[0]
    with pytest.raises(ModelContractError):
        wizard.validate("toolong", step)


def test_wizard_coerce_number():
    model = {
        "model_id": "test_model",
        "input_schema": {
            "required": ["count"],
            "properties": {
                "count": {"type": "integer"}
            },
        },
    }
    wizard = InputWizard(model)
    step = wizard.steps()[0]
    value = wizard.coerce("3", step.spec)
    assert value == 3
    wizard.validate(value, step)


def test_wizard_expects_url():
    model = {
        "model_id": "test_model",
        "input_schema": {
            "required": ["image_url"],
            "properties": {
                "image_url": {"type": "url"}
            },
        },
    }
    wizard = InputWizard(model)
    step = wizard.steps()[0]
    assert InputWizard.expects_url(step)

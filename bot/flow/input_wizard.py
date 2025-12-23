"""Input wizard for model-driven parameter collection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from app.kie.contract import build_create_task_payload
from app.kie.validator import ModelContractError, validate_input_type
from bot.ui import presenter


@dataclass
class WizardStep:
    name: str
    spec: Dict[str, Any]
    label: str
    help_text: str


class InputWizard:
    """Builds steps and validates user inputs for a model schema."""

    def __init__(self, model: Dict[str, Any]):
        self.model = model
        input_schema = model.get("input_schema", {})
        self.required_fields: List[str] = input_schema.get("required", [])
        self.properties: Dict[str, Any] = input_schema.get("properties", {})

    def steps(self) -> List[WizardStep]:
        steps = []
        for field in self.required_fields:
            spec = self.properties.get(field, {})
            steps.append(
                WizardStep(
                    name=field,
                    spec=spec,
                    label=presenter.friendly_param(field),
                    help_text=presenter.param_hint(field, spec),
                )
            )
        return steps

    def prompt(self, step: WizardStep) -> str:
        field_type = step.spec.get("type", "string")
        max_length = step.spec.get("max_length")
        if step.spec.get("enum"):
            return f"Выберите значение для <b>{step.label}</b>:"
        if field_type in {"file", "file_id", "file_url"}:
            return f"Отправьте файл для <b>{step.label}</b>:"
        if field_type in {"url", "link", "source_url"}:
            return f"Отправьте ссылку для <b>{step.label}</b> (http/https):"
        if max_length:
            return f"Введите значение для <b>{step.label}</b> (до {max_length} символов):"
        return f"Введите значение для <b>{step.label}</b>:"

    def coerce(self, value: Any, spec: Dict[str, Any]) -> Any:
        field_type = spec.get("type", "string")
        if field_type in {"integer", "int"}:
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        if field_type in {"number", "float"}:
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        if field_type in {"boolean", "bool"}:
            if isinstance(value, str):
                return value.lower() in {"true", "1", "yes", "on"}
            return bool(value)
        return value

    def validate(self, value: Any, step: WizardStep) -> None:
        field_type = step.spec.get("type", "string")
        validate_input_type(value, field_type, step.name)
        enum_values = step.spec.get("enum")
        if enum_values and value not in enum_values:
            raise ModelContractError(
                f"Поле '{step.label}' должно быть одним из {enum_values}"
            )
        if field_type in {"string", "text", "prompt", "input", "message"}:
            max_length = step.spec.get("max_length")
            if max_length and isinstance(value, str) and len(value) > max_length:
                raise ModelContractError(
                    f"Поле '{step.label}' должно быть не длиннее {max_length} символов"
                )
        minimum = step.spec.get("minimum")
        maximum = step.spec.get("maximum")
        if minimum is not None or maximum is not None:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                return
            if minimum is not None and numeric_value < minimum:
                raise ModelContractError(
                    f"Поле '{step.label}' должно быть >= {minimum}"
                )
            if maximum is not None and numeric_value > maximum:
                raise ModelContractError(
                    f"Поле '{step.label}' должно быть <= {maximum}"
                )

    def normalize_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return build_create_task_payload(self.model, inputs)

    @staticmethod
    def expects_file(step: WizardStep) -> bool:
        return step.spec.get("type") in {"file", "file_id", "file_url"}

    @staticmethod
    def expects_url(step: WizardStep) -> bool:
        return step.spec.get("type") in {"url", "link", "source_url"}

    @staticmethod
    def expects_enum(step: WizardStep) -> bool:
        return bool(step.spec.get("enum"))

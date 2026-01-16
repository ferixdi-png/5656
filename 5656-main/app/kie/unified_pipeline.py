"""
Unified Model Pipeline - standardized flow for ALL models.

Contract:
- prompt always required
- other params defaulted if defined, otherwise collected via minimal UI
- standardized confirmation screen
- standardized task create/poll/result delivery
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from app.kie.builder import load_source_of_truth
from app.kie.validator import validate_input_type, ModelContractError

logger = logging.getLogger(__name__)


@dataclass
class ModelSpec:
    """Model specification from SSOT."""
    model_id: str
    name: str
    category: str
    input_schema: Dict[str, Any]
    price_usd: float
    output_type: str
    enabled: bool = True


@dataclass
class ParameterCollection:
    """Collected parameters for generation."""
    prompt: str  # Always required
    other_params: Dict[str, Any]  # Optional parameters with defaults applied


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    success: bool
    task_id: Optional[str] = None
    result_urls: List[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class UnifiedModelPipeline:
    """
    Unified pipeline for all models.
    
    Steps:
    1. resolve_model(model_id) -> ModelSpec
    2. get_schema(model_id) -> input_schema with RU labels, defaults, constraints
    3. collect_params_stepwise(...) -> ParameterCollection
    4. apply_defaults(...) -> fills missing fields except prompt
    5. validate(...) -> list of human-readable RU errors
    6. confirm_screen(...) -> shows summary
    7. submit_job(...) -> builds KIE payload, creates task
    8. poll_and_deliver(...) -> consistent delivery + history record
    """
    
    def __init__(self):
        self._sot_cache: Optional[Dict[str, Any]] = None
    
    def _get_source_of_truth(self) -> Dict[str, Any]:
        """Get source of truth, with caching."""
        if self._sot_cache is None:
            self._sot_cache = load_source_of_truth()
        return self._sot_cache
    
    def resolve_model(self, model_id: str) -> Optional[ModelSpec]:
        """
        Resolve model from SSOT.
        
        Args:
            model_id: Model identifier
            
        Returns:
            ModelSpec if found, None otherwise
        """
        try:
            sot = self._get_source_of_truth()
            models = sot.get("models", {})
            
            # Support both dict and list formats
            if isinstance(models, dict):
                model = models.get(model_id)
            elif isinstance(models, list):
                model = next((m for m in models if m.get("model_id") == model_id), None)
            else:
                return None
            
            if not model:
                return None
            
            return ModelSpec(
                model_id=model.get("model_id", model_id),
                name=model.get("name", model_id),
                category=model.get("category", ""),
                input_schema=model.get("input_schema", {}),
                price_usd=float(model.get("price", 0)),
                output_type=model.get("output_type", "url"),
                enabled=model.get("enabled", True)
            )
        except Exception as e:
            logger.error(f"Failed to resolve model {model_id}: {e}", exc_info=True)
            return None
    
    def get_schema(self, model_id: str) -> Dict[str, Any]:
        """
        Get input schema with RU labels, defaults, constraints.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Input schema with normalized structure
        """
        model = self.resolve_model(model_id)
        if not model:
            return {}
        
        schema = model.input_schema
        
        # Normalize schema structure
        # Support both flat and nested formats
        if 'properties' in schema:
            # Nested format (already normalized)
            return schema
        else:
            # Flat format - convert to nested
            properties = schema
            required = [k for k, v in properties.items() if v.get('required', False)]
            optional = [k for k in properties.keys() if k not in required]
            
            return {
                "properties": properties,
                "required": required,
                "optional": optional
            }
    
    def apply_defaults(self, schema: Dict[str, Any], collected: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply defaults for missing optional fields.
        
        Args:
            schema: Input schema
            collected: Already collected parameters
            
        Returns:
            Parameters with defaults applied (except prompt)
        """
        result = collected.copy()
        properties = schema.get("properties", {})
        
        for field_name, field_spec in properties.items():
            # Skip prompt - it's always required
            if field_name == "prompt":
                continue
            
            # Skip if already collected
            if field_name in result:
                continue
            
            # Apply default if exists
            if "default" in field_spec:
                result[field_name] = field_spec["default"]
            elif field_spec.get("type") == "boolean" and field_spec.get("default") is None:
                # Boolean defaults to False if not specified
                result[field_name] = False
        
        return result
    
    def validate(self, model_id: str, params: Dict[str, Any]) -> List[str]:
        """
        Validate parameters against schema.
        
        Args:
            model_id: Model identifier
            params: Parameters to validate
            
        Returns:
            List of human-readable RU error messages (empty if valid)
        """
        errors = []
        model = self.resolve_model(model_id)
        if not model:
            errors.append(f"Модель {model_id} не найдена")
            return errors
        
        schema = self.get_schema(model_id)
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Check required fields
        for field_name in required:
            if field_name not in params or not params[field_name]:
                field_label = properties.get(field_name, {}).get("label_ru", field_name)
                errors.append(f"Поле '{field_label}' обязательно для заполнения")
        
        # Validate field types and constraints
        for field_name, field_value in params.items():
            if field_name not in properties:
                continue  # Unknown field, skip validation
            
            field_spec = properties[field_name]
            field_type = field_spec.get("type", "string")
            
            try:
                # Type validation
                if field_type == "integer" and not isinstance(field_value, int):
                    try:
                        int(field_value)
                    except (ValueError, TypeError):
                        errors.append(f"Поле '{field_name}' должно быть числом")
                
                elif field_type == "number" and not isinstance(field_value, (int, float)):
                    try:
                        float(field_value)
                    except (ValueError, TypeError):
                        errors.append(f"Поле '{field_name}' должно быть числом")
                
                elif field_type == "boolean" and not isinstance(field_value, bool):
                    errors.append(f"Поле '{field_name}' должно быть true или false")
                
                # Enum validation
                if "enum" in field_spec:
                    if field_value not in field_spec["enum"]:
                        errors.append(f"Поле '{field_name}' должно быть одним из: {', '.join(field_spec['enum'])}")
                
                # Range validation
                if "minimum" in field_spec and field_value < field_spec["minimum"]:
                    errors.append(f"Поле '{field_name}' должно быть не менее {field_spec['minimum']}")
                if "maximum" in field_spec and field_value > field_spec["maximum"]:
                    errors.append(f"Поле '{field_name}' должно быть не более {field_spec['maximum']}")
            
            except Exception as e:
                logger.warning(f"Validation error for {field_name}: {e}")
                # Don't add error for validation exceptions - just log
        
        return errors
    
    def build_kie_payload(self, model_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build KIE API payload from parameters.
        
        Args:
            model_id: Model identifier
            params: Collected parameters
            
        Returns:
            KIE API payload
        """
        # Base payload structure
        payload = {
            "model": model_id,
            "input": {}
        }
        
        # Add all parameters to input
        for key, value in params.items():
            payload["input"][key] = value
        
        return payload
    
    def format_confirmation_text(
        self,
        model: ModelSpec,
        params: Dict[str, Any],
        price_rub: float
    ) -> str:
        """
        Format confirmation screen text.
        
        Args:
            model: Model specification
            params: Collected parameters
            price_rub: Price in RUB
            
        Returns:
            Formatted confirmation text
        """
        from app.payments.pricing import format_price_rub
        
        lines = [
            f"🔍 <b>Проверьте заказ</b>\n",
            f"<b>Модель:</b> {model.name}\n",
        ]
        
        # Show prompt (truncated to 300 chars)
        prompt = params.get("prompt", "")
        if prompt:
            prompt_display = prompt[:300] + "..." if len(prompt) > 300 else prompt
            lines.append(f"<b>Задача:</b> {prompt_display}\n")
        
        # Show key params (top 6 non-prompt params)
        key_params = []
        for key, value in params.items():
            if key != "prompt" and len(key_params) < 6:
                key_params.append(f"• {key}: {value}")
        
        if key_params:
            lines.append("\n<b>Параметры:</b>")
            lines.extend(key_params)
        
        lines.extend([
            f"\n💰 <b>Стоимость:</b> {format_price_rub(price_rub)}",
            f"⏱ <b>Ожидание:</b> ~10-30 сек",
        ])
        
        return "\n".join(lines)


# Global pipeline instance
_pipeline_instance: Optional[UnifiedModelPipeline] = None


def get_unified_pipeline() -> UnifiedModelPipeline:
    """Get global unified pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = UnifiedModelPipeline()
    return _pipeline_instance


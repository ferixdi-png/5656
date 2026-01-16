#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Payload Builder - строит корректные payloads для KIE API по schema.

Features:
- Type coercion (string -> int, etc.)
- Range clamping (min/max)
- Enum validation
- Required field checks
- Default values
- Schema-driven validation
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PayloadBuilderError(Exception):
    """Payload building error."""
    pass


class PayloadBuilder:
    """Builds and validates payloads for KIE models."""
    
    def __init__(self, model_id: str, schema: Dict[str, Any]):
        """
        Initialize payload builder.
        
        Args:
            model_id: Model identifier
            schema: Input schema (from kie_models.yaml)
        """
        self.model_id = model_id
        self.schema = schema
    
    def build_payload(
        self,
        user_inputs: Dict[str, Any],
        defaults: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Build payload from user inputs.
        
        Args:
            user_inputs: User-provided inputs
            defaults: Default values for optional fields
        
        Returns:
            (payload, errors)
        """
        payload = {}
        errors = []
        defaults = defaults or {}
        
        # Process each field in schema
        for field_name, field_spec in self.schema.items():
            if not isinstance(field_spec, dict):
                continue
            
            field_type = field_spec.get('type')
            required = field_spec.get('required', False)
            
            # Get value (user input > default > None)
            value = user_inputs.get(field_name, defaults.get(field_name))
            
            # Check required fields
            if required and value is None:
                errors.append(f"Required field '{field_name}' missing")
                continue
            
            # Skip optional fields with no value
            if not required and value is None:
                continue
            
            # Validate and coerce value
            try:
                validated_value = self._validate_field(
                    field_name, value, field_spec
                )
                payload[field_name] = validated_value
            except ValueError as e:
                errors.append(f"Field '{field_name}': {e}")
        
        return payload, errors
    
    def _validate_field(
        self,
        field_name: str,
        value: Any,
        field_spec: Dict[str, Any]
    ) -> Any:
        """
        Validate and coerce field value.
        
        Args:
            field_name: Field name
            value: Raw value
            field_spec: Field specification from schema
        
        Returns:
            Validated and coerced value
        
        Raises:
            ValueError: If validation fails
        """
        field_type = field_spec.get('type')
        
        # Type coercion and validation
        if field_type == 'string':
            return self._validate_string(value, field_spec)
        elif field_type in ('integer', 'number', 'float'):
            return self._validate_number(value, field_spec, field_type)
        elif field_type == 'boolean':
            return self._validate_boolean(value)
        elif field_type == 'enum':
            return self._validate_enum(value, field_spec)
        elif field_type == 'array':
            return self._validate_array(value, field_spec)
        elif field_type == 'object':
            return value  # Pass through for now
        else:
            raise ValueError(f"Unknown type: {field_type}")
    
    def _validate_string(self, value: Any, field_spec: Dict[str, Any]) -> str:
        """Validate string field."""
        # Coerce to string
        if not isinstance(value, str):
            value = str(value)
        
        # Check length constraints
        min_len = field_spec.get('min', field_spec.get('minLength', 0))
        max_len = field_spec.get('max', field_spec.get('maxLength'))
        
        if len(value) < min_len:
            raise ValueError(f"Too short (min: {min_len})")
        
        if max_len and len(value) > max_len:
            # Truncate instead of failing
            value = value[:max_len]
            logger.warning(f"Truncated string to {max_len} chars")
        
        return value
    
    def _validate_number(
        self,
        value: Any,
        field_spec: Dict[str, Any],
        field_type: str
    ) -> float:
        """Validate numeric field."""
        # Coerce to number
        try:
            if field_type == 'integer':
                value = int(float(value))  # Handle "123.0" -> 123
            else:
                value = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot convert to {field_type}")
        
        # Check range constraints
        min_val = field_spec.get('min', field_spec.get('minimum'))
        max_val = field_spec.get('max', field_spec.get('maximum'))
        
        if min_val is not None and value < min_val:
            value = min_val  # Clamp to min
            logger.warning(f"Clamped to min: {min_val}")
        
        if max_val is not None and value > max_val:
            value = max_val  # Clamp to max
            logger.warning(f"Clamped to max: {max_val}")
        
        return value
    
    def _validate_boolean(self, value: Any) -> bool:
        """Validate boolean field."""
        if isinstance(value, bool):
            return value
        
        # Coerce from string
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ('true', '1', 'yes', 'on'):
                return True
            elif value_lower in ('false', '0', 'no', 'off'):
                return False
        
        # Coerce from number
        if isinstance(value, (int, float)):
            return bool(value)
        
        raise ValueError(f"Cannot convert to boolean: {value}")
    
    def _validate_enum(self, value: Any, field_spec: Dict[str, Any]) -> Any:
        """Validate enum field."""
        valid_values = field_spec.get('values', [])
        
        if not valid_values:
            raise ValueError("Enum has no valid values")
        
        if value not in valid_values:
            raise ValueError(f"Not in enum: {value}. Valid: {valid_values}")
        
        return value
    
    def _validate_array(self, value: Any, field_spec: Dict[str, Any]) -> List[Any]:
        """Validate array field."""
        if not isinstance(value, list):
            # Try to coerce single value to array
            value = [value]
        
        item_type = field_spec.get('item_type', 'string')
        
        # Validate each item (simple validation)
        validated = []
        for item in value:
            if item_type == 'string' and not isinstance(item, str):
                item = str(item)
            validated.append(item)
        
        return validated
    
    def get_required_fields(self) -> List[str]:
        """Get list of required field names."""
        return [
            field_name
            for field_name, field_spec in self.schema.items()
            if isinstance(field_spec, dict) and field_spec.get('required', False)
        ]
    
    def get_optional_fields(self) -> List[str]:
        """Get list of optional field names."""
        return [
            field_name
            for field_name, field_spec in self.schema.items()
            if isinstance(field_spec, dict) and not field_spec.get('required', False)
        ]


def build_payload_for_model(
    model_id: str,
    schema: Dict[str, Any],
    user_inputs: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Convenience function to build payload.
    
    Args:
        model_id: Model identifier
        schema: Input schema
        user_inputs: User-provided inputs
        defaults: Default values
    
    Returns:
        (payload, errors)
    """
    builder = PayloadBuilder(model_id, schema)
    return builder.build_payload(user_inputs, defaults)


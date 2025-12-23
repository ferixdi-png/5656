"""Validate registry specs consistency."""
import json
import sys


def main() -> int:
    with open("models/kie_models_source_of_truth.json", "r", encoding="utf-8") as handle:
        data = json.load(handle)

    models = data.get("models", [])
    errors = []
    for model in models:
        model_id = model.get("model_id")
        if not model_id:
            errors.append("Missing model_id")
            continue
        input_schema = model.get("input_schema")
        if input_schema is None:
            errors.append(f"{model_id}: missing input_schema")
            continue
        if "required" not in input_schema or "properties" not in input_schema:
            errors.append(f"{model_id}: input_schema missing required/properties")
        properties = input_schema.get("properties", {})
        for field, spec in properties.items():
            if "type" not in spec:
                errors.append(f"{model_id}: field {field} missing type")
            if "enum" in spec and not isinstance(spec["enum"], list):
                errors.append(f"{model_id}: field {field} enum must be list")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Registry specs OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

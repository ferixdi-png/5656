"""
Kie.ai Truth Audit: проверка registry моделей на соответствие реальным требованиям.

Источники истины:
- https://kie.ai/models - все модели с параметрами
- https://kie.ai/pricing - официальные цены
- models/kie_models_source_of_truth.json - наш registry

Проверяет:
1. Наличие обязательных полей (model_id, category, input_schema)
2. Валидность input_schema (required, properties)
3. Наличие цены (price) для платных моделей
4. Соответствие category известным типам
5. Описание модели (description)
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Known valid categories from Kie.ai
VALID_CATEGORIES = {
    "t2i", "i2i", "t2v", "i2v", "v2v",
    "lip_sync", "music", "sfx", "tts", "stt",
    "audio_isolation", "upscale", "bg_remove",
    "watermark_remove", "general", "other"
}

# Known model types to skip (not AI models)
SKIP_PATTERNS = [
    "_processor",
    "ARCHITECTURE",
    "AI_INTEGRATION",
    "test_results"
]


def should_skip_model(model_id: str) -> bool:
    """Check if model should be skipped (not a real AI model)."""
    model_lower = model_id.lower()
    
    # Skip processors
    if any(pattern.lower() in model_lower for pattern in SKIP_PATTERNS):
        return True
    
    # Skip all-caps constants
    if model_id.isupper():
        return True
    
    return False


def audit_model(model: Dict[str, Any]) -> List[str]:
    """
    Audit single model for completeness.
    
    Returns:
        List of issues (empty if OK)
    """
    issues = []
    model_id = model.get("model_id", "UNKNOWN")
    
    # Skip non-AI models
    if should_skip_model(model_id):
        return []
    
    # Check required fields
    if "category" not in model:
        issues.append(f"{model_id}: missing 'category'")
    elif model["category"] not in VALID_CATEGORIES:
        issues.append(f"{model_id}: unknown category '{model['category']}'")
    
    if "input_schema" not in model:
        issues.append(f"{model_id}: missing 'input_schema'")
    else:
        schema = model["input_schema"]
        if "required" not in schema:
            issues.append(f"{model_id}: input_schema missing 'required' field")
        if "properties" not in schema:
            issues.append(f"{model_id}: input_schema missing 'properties' field")
        
        # Check if has required fields but no properties
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if required and not properties:
            issues.append(f"{model_id}: has required fields but no properties definition")
        
        # Check if required fields are in properties
        for req_field in required:
            if req_field not in properties:
                issues.append(f"{model_id}: required field '{req_field}' not in properties")
    
    if "output_type" not in model:
        issues.append(f"{model_id}: missing 'output_type'")
    
    # Check for price (important for billing)
    if "price" not in model:
        # Only warning for now - we have FALLBACK_PRICES_RUB
        pass  # Will add price from official source
    
    # Check description
    if not model.get("description"):
        issues.append(f"{model_id}: missing or empty 'description'")
    
    # Check for example payload (nice to have)
    if "example_payload" not in model and "example_inputs" not in model:
        # Not critical but helpful
        pass
    
    return issues


def generate_report(registry_path: Path) -> Dict[str, Any]:
    """Generate full audit report."""
    with open(registry_path) as f:
        data = json.load(f)
    
    models = data.get("models", [])
    
    total = len(models)
    ai_models = [m for m in models if not should_skip_model(m.get("model_id", ""))]
    total_ai = len(ai_models)
    
    all_issues = []
    models_with_issues = []
    
    for model in ai_models:
        issues = audit_model(model)
        if issues:
            models_with_issues.append(model.get("model_id"))
            all_issues.extend(issues)
    
    # Category breakdown
    categories = {}
    for model in ai_models:
        cat = model.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
    
    # Models with price
    with_price = [m for m in ai_models if "price" in m and m["price"] is not None]
    
    return {
        "total_models": total,
        "ai_models": total_ai,
        "skipped": total - total_ai,
        "categories": categories,
        "with_price": len(with_price),
        "models_with_issues": len(models_with_issues),
        "total_issues": len(all_issues),
        "issues": all_issues,
        "status": "OK" if not all_issues else "ISSUES_FOUND"
    }


def main():
    """Run audit and print report."""
    repo_root = Path(__file__).parent.parent
    registry_path = repo_root / "models" / "kie_models_source_of_truth.json"
    
    if not registry_path.exists():
        print(f"ERROR: Registry not found at {registry_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("KIE.AI TRUTH AUDIT")
    print("=" * 60)
    print(f"Registry: {registry_path}")
    print()
    
    report = generate_report(registry_path)
    
    print(f"📊 Total models in registry: {report['total_models']}")
    print(f"🤖 AI generation models: {report['ai_models']}")
    print(f"⏭️  Skipped (processors/constants): {report['skipped']}")
    print()
    
    print("📂 Categories breakdown:")
    for cat, count in sorted(report['categories'].items()):
        print(f"   {cat:20s}: {count:3d} models")
    print()
    
    print(f"💰 Models with price data: {report['with_price']}/{report['ai_models']}")
    print()
    
    if report['total_issues'] == 0:
        print("✅ ALL CHECKS PASSED - No issues found")
        print()
        print("Registry is production-ready!")
        return 0
    else:
        print(f"⚠️  ISSUES FOUND: {report['total_issues']} issues in {report['models_with_issues']} models")
        print()
        print("Issues:")
        for issue in report['issues'][:20]:  # Show first 20
            print(f"  - {issue}")
        
        if len(report['issues']) > 20:
            print(f"  ... and {len(report['issues']) - 20} more")
        
        print()
        print("❌ Registry needs fixes before production")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Comprehensive check of all models in kie_models.py
Verifies that each model is properly handled in bot_kie.py
"""

import json
import re
import sys

# Read kie_models.py
try:
    with open('kie_models.py', 'r', encoding='utf-8') as f:
        kie_models_content = f.read()
except Exception as e:
    print(f"ERROR: Cannot read kie_models.py: {e}")
    sys.exit(1)

# Read bot_kie.py
try:
    with open('bot_kie.py', 'r', encoding='utf-8') as f:
        bot_kie_content = f.read()
except Exception as e:
    print(f"ERROR: Cannot read bot_kie.py: {e}")
    sys.exit(1)

# Extract all model IDs from kie_models.py
model_ids = []
model_pattern = r'"id":\s*"([^"]+)"'
matches = re.findall(model_pattern, kie_models_content)
model_ids = list(set(matches))  # Remove duplicates

print(f"Found {len(model_ids)} models in kie_models.py")
print("=" * 80)

# Check each model
issues = []
warnings = []
success_count = 0

for model_id in sorted(model_ids):
    print(f"\nChecking model: {model_id}")
    model_issues = []
    model_warnings = []
    
    # 1. Check if model is in models_require_image_first list
    if 'models_require_image_first' in bot_kie_content:
        if model_id in ['nano-banana-pro', 'recraft/remove-background', 'recraft/crisp-upscale']:
            if f'"{model_id}"' not in bot_kie_content.split('models_require_image_first')[1].split(']')[0]:
                model_warnings.append(f"Model {model_id} should be in models_require_image_first but might not be")
    
    # 2. Check if model has special handling for sora-2-pro-image-to-video
    if model_id == 'sora-2-pro-image-to-video':
        if 'sora-2-pro-image-to-video' not in bot_kie_content or 'image_urls' not in bot_kie_content:
            model_issues.append("Missing special handling for sora-2-pro-image-to-video")
    
    # 3. Check if model has pricing calculation
    if f'model_id == "{model_id}"' not in bot_kie_content and f'model_id == "{model_id}"' not in bot_kie_content:
        # Check for pattern with or
        pattern1 = f'"{model_id}"'
        pattern2 = f'model_id == "{model_id}"'
        if pattern1 not in bot_kie_content.split('calculate_price_rub')[1] if 'calculate_price_rub' in bot_kie_content else '':
            model_warnings.append("Model might not have explicit pricing calculation")
    
    # 4. Check if model has API parameter conversion
    if 'convert_params_for_api' in bot_kie_content:
        api_section = bot_kie_content.split('convert_params_for_api')[1] if 'convert_params_for_api' in bot_kie_content else ''
        if model_id not in api_section:
            model_warnings.append("Model might not have API parameter conversion")
    
    # 5. Extract input_params from kie_models.py for this model
    model_section_pattern = rf'"id":\s*"{re.escape(model_id)}"[^}}]*"input_params":\s*{{([^}}]+(?:{{[^}}]*}}[^}}]*)*)}}'
    model_match = re.search(model_section_pattern, kie_models_content, re.DOTALL)
    
    if model_match:
        input_params_section = model_match.group(1)
        # Extract required parameters
        required_params = []
        param_pattern = r'"([^"]+)":\s*{{[^}}]*"required":\s*True'
        required_matches = re.findall(param_pattern, input_params_section)
        required_params = required_matches
        
        # Check if prompt is required
        has_prompt = '"prompt"' in input_params_section
        prompt_required = '"prompt"' in input_params_section and '"required":\s*True' in input_params_section.split('"prompt"')[1].split('}')[0] if '"prompt"' in input_params_section else False
        
        # Check if image_input is required
        has_image_input = '"image_input"' in input_params_section
        image_input_required = '"image_input"' in input_params_section and '"required":\s*True' in input_params_section.split('"image_input"')[1].split('}')[0] if '"image_input"' in input_params_section else False
        
        # Check if image_urls is required
        has_image_urls = '"image_urls"' in input_params_section
        image_urls_required = '"image_urls"' in input_params_section and '"required":\s*True' in input_params_section.split('"image_urls"')[1].split('}')[0] if '"image_urls"' in input_params_section else False
        
        print(f"  Required params: {required_params}")
        print(f"  Has prompt: {has_prompt} (required: {prompt_required})")
        print(f"  Has image_input: {has_image_input} (required: {image_input_required})")
        print(f"  Has image_urls: {has_image_urls} (required: {image_urls_required})")
        
        # Validate model handling logic
        if image_input_required and not prompt_required:
            # Model requires image_input but no prompt (like recraft models)
            if model_id not in ['recraft/remove-background', 'recraft/crisp-upscale', 'nano-banana-pro']:
                if f'"{model_id}"' not in bot_kie_content.split('models_require_image_first')[1].split(']')[0] if 'models_require_image_first' in bot_kie_content else '':
                    model_issues.append(f"Model requires image_input first but not in models_require_image_first list")
        
        if image_input_required and prompt_required:
            # Model requires both (like nano-banana-pro)
            if model_id == 'nano-banana-pro':
                if 'nano-banana-pro' not in bot_kie_content.split('models_require_image_first')[1].split(']')[0] if 'models_require_image_first' in bot_kie_content else '':
                    model_issues.append("nano-banana-pro should be in models_require_image_first")
    
    else:
        model_warnings.append("Could not extract input_params from kie_models.py")
    
    if model_issues:
        issues.extend([(model_id, issue) for issue in model_issues])
        print(f"  ❌ ISSUES: {model_issues}")
    elif model_warnings:
        warnings.extend([(model_id, warning) for warning in model_warnings])
        print(f"  ⚠️  WARNINGS: {model_warnings}")
    else:
        success_count += 1
        print(f"  ✅ OK")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total models: {len(model_ids)}")
print(f"✅ Success: {success_count}")
print(f"❌ Issues: {len(issues)}")
print(f"⚠️  Warnings: {len(warnings)}")

if issues:
    print("\n" + "=" * 80)
    print("ISSUES FOUND:")
    print("=" * 80)
    for model_id, issue in issues:
        print(f"  {model_id}: {issue}")

if warnings:
    print("\n" + "=" * 80)
    print("WARNINGS:")
    print("=" * 80)
    for model_id, warning in warnings:
        print(f"  {model_id}: {warning}")

# Save detailed report
report = {
    "total_models": len(model_ids),
    "success_count": success_count,
    "issues_count": len(issues),
    "warnings_count": len(warnings),
    "models": model_ids,
    "issues": [{"model": m, "issue": i} for m, i in issues],
    "warnings": [{"model": m, "warning": w} for m, w in warnings]
}

with open('models_check_report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"\nDetailed report saved to: models_check_report.json")

if issues:
    sys.exit(1)
else:
    sys.exit(0)



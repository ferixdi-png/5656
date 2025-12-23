#!/usr/bin/env python3
"""
Verify project invariants:
- source_of_truth is not empty
- UI count == registry count == source_of_truth count
- model_ids match across all sources
"""
import os
import json
import sys
from pathlib import Path
from typing import Set, Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_source_of_truth(file_path: str = "models/kie_models_source_of_truth.json") -> Dict:
    """Load source of truth file."""
    if not os.path.exists(file_path):
        logger.error(f"Source of truth file not found: {file_path}")
        return {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_ui_models() -> Set[str]:
    """Extract model_ids from UI (if exists)."""
    model_ids = set()
    
    ui_files = [
        "ui/models.json",
        "frontend/src/models.json",
        "web/models.json",
        "app/models.json",
    ]
    
    for ui_file in ui_files:
        if os.path.exists(ui_file):
            try:
                with open(ui_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                model_id = item.get('model_id') or item.get('id') or item.get('name')
                                if model_id:
                                    model_ids.add(str(model_id))
                    elif isinstance(data, dict):
                        if 'models' in data:
                            for item in data['models']:
                                if isinstance(item, dict):
                                    model_id = item.get('model_id') or item.get('id') or item.get('name')
                                    if model_id:
                                        model_ids.add(str(model_id))
            except Exception as e:
                logger.warning(f"Failed to load UI file {ui_file}: {e}")
    
    return model_ids


def get_registry_models() -> Set[str]:
    """Extract model_ids from registry (if exists)."""
    model_ids = set()
    
    registry_files = [
        "models/registry.json",
        "registry/models.json",
        "app/registry.json",
        "kie_full_api.json",
    ]
    
    for registry_file in registry_files:
        if os.path.exists(registry_file):
            try:
                with open(registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                model_id = item.get('model_id') or item.get('id') or item.get('name')
                                if model_id:
                                    model_ids.add(str(model_id))
                    elif isinstance(data, dict):
                        if 'models' in data:
                            for item in data['models']:
                                if isinstance(item, dict):
                                    model_id = item.get('model_id') or item.get('id') or item.get('name')
                                    if model_id:
                                        model_ids.add(str(model_id))
            except Exception as e:
                logger.warning(f"Failed to load registry file {registry_file}: {e}")
    
    return model_ids


def verify_project() -> bool:
    """Verify all project invariants."""
    errors = []
    warnings = []
    
    source_of_truth = load_source_of_truth()
    if not source_of_truth:
        errors.append("Source of truth file is missing or empty")
        return False
    
    source_models = source_of_truth.get('models', [])
    source_model_ids = {m['model_id'] for m in source_models if 'model_id' in m}
    
    if not source_model_ids:
        errors.append("Source of truth contains no models")
        return False
    
    logger.info(f"[OK] Source of truth: {len(source_model_ids)} models")
    
    ui_model_ids = get_ui_models()
    registry_model_ids = get_registry_models()
    
    logger.info(f"[INFO] UI models: {len(ui_model_ids)}")
    logger.info(f"[INFO] Registry models: {len(registry_model_ids)}")
    logger.info(f"[INFO] Source of truth models: {len(source_model_ids)}")
    
    if ui_model_ids and len(ui_model_ids) != len(source_model_ids):
        warnings.append(
            f"UI count ({len(ui_model_ids)}) != source_of_truth count ({len(source_model_ids)})"
        )
    
    if registry_model_ids and len(registry_model_ids) != len(source_model_ids):
        warnings.append(
            f"Registry count ({len(registry_model_ids)}) != source_of_truth count ({len(source_model_ids)})"
        )
    
    if ui_model_ids:
        ui_only = ui_model_ids - source_model_ids
        source_only = source_model_ids - ui_model_ids
        if ui_only:
            warnings.append(f"Models in UI but not in source_of_truth: {ui_only}")
        if source_only:
            warnings.append(f"Models in source_of_truth but not in UI: {source_only}")
    
    if registry_model_ids:
        registry_only = registry_model_ids - source_model_ids
        source_only = source_model_ids - registry_model_ids
        if registry_only:
            warnings.append(f"Models in registry but not in source_of_truth: {registry_only}")
        if source_only:
            warnings.append(f"Models in source_of_truth but not in registry: {source_only}")
    
    if errors:
        logger.error("[ERROR] ERRORS:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    if warnings:
        logger.warning("[WARNING] WARNINGS:")
        for warning in warnings:
            logger.warning(f"  - {warning}")
    else:
        logger.info("[OK] All invariants satisfied!")

    # Verify polling preflight uses deleteWebhook
    try:
        main_render_path = Path("main_render.py")
        if main_render_path.exists():
            content = main_render_path.read_text(encoding="utf-8")
            if "delete_webhook" not in content:
                errors.append("main_render.py missing delete_webhook preflight call")
        else:
            errors.append("main_render.py not found for preflight verification")
    except Exception as e:
        errors.append(f"Failed to verify preflight: {e}")

    if errors:
        logger.error("[ERROR] ERRORS:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    return True


if __name__ == "__main__":
    success = verify_project()
    sys.exit(0 if success else 1)

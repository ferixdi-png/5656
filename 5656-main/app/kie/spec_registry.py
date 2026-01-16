"""
Registry моделей KIE AI - единый источник правды.

Загружает модели ТОЛЬКО из сгенерированного registry файла,
который построен из документации docs/*_INTEGRATION.md.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class InputFieldSpec:
    """Спецификация поля входного параметра."""
    name: str
    type: str
    required: bool
    description: str = ""
    max_length: Optional[int] = None
    options: Optional[List[str]] = None
    default: Optional[Any] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None


@dataclass
class ModelSpecFromRegistry:
    """Спецификация модели из registry."""
    model_id: str
    create_endpoint: str
    record_endpoint: str
    input_schema: Dict[str, InputFieldSpec]
    output_media_type: str
    states: List[str]
    title_ru: Optional[str] = None
    description: Optional[str] = None
    # Menu display fields (with defaults)
    menu_title: Optional[str] = None  # Short title for button
    menu_subtitle: Optional[str] = None  # Subtitle/description for button
    menu_badge: Optional[str] = None  # Badge (e.g., "2K", "Видео", "Upscale")


class KIERegistry:
    """Registry моделей KIE AI."""
    
    def __init__(self, registry_data: Dict[str, Any]):
        """
        Инициализирует registry из данных.
        
        Args:
            registry_data: Данные registry (из JSON)
        """
        self._models: Dict[str, ModelSpecFromRegistry] = {}
        self._load_from_data(registry_data)
    
    def _load_from_data(self, data: Dict[str, Any]):
        """Загружает модели из данных registry."""
        models_data = data.get("models", {})
        
        for model_id, model_data in models_data.items():
            # Конвертируем input_schema
            input_schema = {}
            for field_name, field_data in model_data.get("input_schema", {}).items():
                input_schema[field_name] = InputFieldSpec(
                    name=field_data.get("name", field_name),
                    type=field_data.get("type", "string"),
                    required=field_data.get("required", False),
                    description=field_data.get("description", ""),
                    max_length=field_data.get("max_length"),
                    options=field_data.get("options"),
                    default=field_data.get("default"),
                    min_value=field_data.get("min_value"),
                    max_value=field_data.get("max_value"),
                    step=field_data.get("step"),
                )
            
            spec = ModelSpecFromRegistry(
                model_id=model_id,
                create_endpoint=model_data.get("create_endpoint", "POST https://api.kie.ai/api/v1/jobs/createTask"),
                record_endpoint=model_data.get("record_endpoint", "GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId={taskId}"),
                input_schema=input_schema,
                output_media_type=model_data.get("output_media_type", "media_urls"),
                states=model_data.get("states", ["waiting", "success", "fail"]),
                title_ru=model_data.get("title_ru"),
                description=model_data.get("description"),
                # Menu display fields (with defaults)
                menu_title=model_data.get("menu_title"),
                menu_subtitle=model_data.get("menu_subtitle"),
                menu_badge=model_data.get("menu_badge"),
            )
            
            self._models[model_id] = spec
    
    def get_model(self, model_id: str) -> Optional[ModelSpecFromRegistry]:
        """
        Получает спецификацию модели по ID.
        
        Args:
            model_id: ID модели (например, "google/imagen4")
        
        Returns:
            ModelSpecFromRegistry или None если модель не найдена
        """
        return self._models.get(model_id)
    
    def list_models(self) -> List[str]:
        """
        Возвращает список всех model_id в registry.
        
        Returns:
            Список model_id
        """
        return sorted(self._models.keys())
    
    def count(self) -> int:
        """Возвращает количество моделей в registry."""
        return len(self._models)
    
    def has_model(self, model_id: str) -> bool:
        """Проверяет наличие модели в registry."""
        return model_id in self._models
    
    def get_all_models(self) -> Dict[str, ModelSpecFromRegistry]:
        """Возвращает все модели."""
        return self._models.copy()


# Глобальный registry (singleton)
_registry: Optional[KIERegistry] = None


def load_registry(registry_path: Optional[Path] = None) -> KIERegistry:
    """
    Загружает registry из файла.
    
    Args:
        registry_path: Путь к файлу registry (по умолчанию models/kie_registry.generated.json)
    
    Returns:
        KIERegistry
    """
    global _registry
    
    if _registry is not None:
        return _registry
    
    if registry_path is None:
        # Ищем в корне проекта
        project_root = Path(__file__).parent.parent.parent
        registry_path = project_root / "models" / "kie_registry.generated.json"
    
    if not registry_path.exists():
        raise FileNotFoundError(
            f"Registry file not found: {registry_path}\n"
            f"Please run: python scripts/build_kie_registry.py"
        )
    
    try:
        registry_data = json.loads(registry_path.read_text(encoding='utf-8'))
    except Exception as e:
        raise ValueError(f"Failed to load registry from {registry_path}: {e}")
    
    _registry = KIERegistry(registry_data)
    logger.info(f"Loaded KIE Registry: {_registry.count()} models")
    
    return _registry


def get_registry() -> KIERegistry:
    """
    Получает глобальный registry (загружает если нужно).
    
    Returns:
        KIERegistry
    """
    global _registry
    
    if _registry is None:
        _registry = load_registry()
    
    return _registry


def reset_registry():
    """Сбрасывает глобальный registry (для тестов)."""
    global _registry
    _registry = None












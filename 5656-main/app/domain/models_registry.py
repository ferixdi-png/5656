"""
Models Registry - единый источник правды для всех моделей
Валидация: нет дублей, у каждой модели есть id, title, model_type, capabilities
Генерация меню строится из registry
"""

import logging
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class ModelRegistry:
    """Реестр всех моделей - единый источник правды"""
    
    def __init__(self):
        self._models: Dict[str, Dict[str, Any]] = {}
        self._models_by_type: Dict[str, List[str]] = {}
        self._categories: Set[str] = set()
        self._initialized = False
    
    def load_from_kie_models(self):
        """Загрузить модели из kie_models.py"""
        try:
            from kie_models import KIE_MODELS, get_categories, get_models_by_generation_type
            
            # Загружаем модели
            for model in KIE_MODELS:
                model_id = model.get('id')
                if not model_id:
                    logger.warning(f"[WARN] Model without id skipped: {model}")
                    continue
                
                # Нормализуем модель
                normalized = self._normalize_model(model)
                
                # Проверяем дубликаты
                if model_id in self._models:
                    logger.warning(f"[WARN] Duplicate model id: {model_id}")
                    continue
                
                self._models[model_id] = normalized
                
                # Индексируем по типу
                model_type = normalized.get('model_type', 'unknown')
                if model_type not in self._models_by_type:
                    self._models_by_type[model_type] = []
                self._models_by_type[model_type].append(model_id)
                
                # Индексируем категории
                category = normalized.get('category')
                if category:
                    self._categories.add(category)
            
            # Загружаем категории из kie_models
            try:
                categories = get_categories()
                for cat in categories:
                    self._categories.add(cat)
            except Exception:
                pass
            
            self._initialized = True
            logger.info(f"[OK] Models registry loaded: {len(self._models)} models, {len(self._models_by_type)} types")
            
        except ImportError as e:
            logger.error(f"[ERROR] Failed to import kie_models: {e}")
            raise
    
    def _normalize_model(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализовать модель для единообразного использования"""
        normalized = model.copy()
        
        # Обязательные поля
        model_id = normalized.get('id')
        if not model_id:
            raise ValueError("Model must have 'id'")
        
        # title (используем name если есть, иначе id)
        if 'title' not in normalized:
            normalized['title'] = normalized.get('name', model_id)
        
        # model_type (определяем из category или capabilities)
        if 'model_type' not in normalized:
            # Пробуем определить из category или других полей
            category = normalized.get('category', '').lower()
            if 'image' in category or 'фото' in category:
                normalized['model_type'] = 'text_to_image'  # Дефолт
            else:
                normalized['model_type'] = 'unknown'
        
        # capabilities (список возможностей модели)
        if 'capabilities' not in normalized:
            capabilities = []
            input_params = normalized.get('input_params', {})
            
            if 'prompt' in input_params:
                capabilities.append('text_input')
            if 'image_input' in input_params or 'image_urls' in input_params:
                capabilities.append('image_input')
            if 'video_input' in input_params or 'video_urls' in input_params:
                capabilities.append('video_input')
            if 'audio_input' in input_params or 'audio_urls' in input_params:
                capabilities.append('audio_input')
            
            normalized['capabilities'] = capabilities
        
        return normalized
    
    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Получить модель по ID"""
        if not self._initialized:
            self.load_from_kie_models()
        return self._models.get(model_id)
    
    def get_all_models(self) -> List[Dict[str, Any]]:
        """Получить все модели"""
        if not self._initialized:
            self.load_from_kie_models()
        return list(self._models.values())
    
    def get_models_by_type(self, model_type: str) -> List[Dict[str, Any]]:
        """Получить модели по типу"""
        if not self._initialized:
            self.load_from_kie_models()
        model_ids = self._models_by_type.get(model_type, [])
        return [self._models[mid] for mid in model_ids if mid in self._models]
    
    def get_categories(self) -> List[str]:
        """Получить список категорий"""
        if not self._initialized:
            self.load_from_kie_models()
        return sorted(list(self._categories))
    
    def get_models_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Получить модели по категории"""
        if not self._initialized:
            self.load_from_kie_models()
        return [m for m in self._models.values() if m.get('category') == category]
    
    def validate(self) -> List[str]:
        """Валидация registry: проверка на дубликаты и обязательные поля"""
        errors = []
        
        if not self._initialized:
            self.load_from_kie_models()
        
        # Проверяем обязательные поля
        for model_id, model in self._models.items():
            if not model.get('id'):
                errors.append(f"Model {model_id}: missing 'id'")
            if not model.get('title'):
                errors.append(f"Model {model_id}: missing 'title'")
            if not model.get('model_type'):
                errors.append(f"Model {model_id}: missing 'model_type'")
            if not model.get('capabilities'):
                errors.append(f"Model {model_id}: missing 'capabilities'")
        
        # Проверяем дубликаты (уже проверено при загрузке, но на всякий случай)
        seen_ids = set()
        for model_id in self._models.keys():
            if model_id in seen_ids:
                errors.append(f"Duplicate model id: {model_id}")
            seen_ids.add(model_id)
        
        return errors


# Singleton instance
_registry_instance: Optional[ModelRegistry] = None


def get_models_registry() -> ModelRegistry:
    """Получить registry (singleton)"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ModelRegistry()
    return _registry_instance



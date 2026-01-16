"""
Model registry module - single source of truth for KIE models
"""

from .registry import load_models, get_model_registry

__all__ = ['load_models', 'get_model_registry']

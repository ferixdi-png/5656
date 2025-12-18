"""
Модуль для управления профилями пользователей.
Сохраняет предпочтения и автоматически подставляет их при генерациях.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Файл для хранения профилей
PROFILES_FILE = Path("data/user_profiles.json")


def get_user_profile(user_id: int) -> Dict[str, Any]:
    """
    Получает профиль пользователя.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Словарь с профилем пользователя
    """
    try:
        if not PROFILES_FILE.exists():
            return create_default_profile(user_id)
        
        with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        
        user_key = str(user_id)
        if user_key in profiles:
            return profiles[user_key]
        else:
            return create_default_profile(user_id)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при получении профиля пользователя {user_id}: {e}", exc_info=True)
        return create_default_profile(user_id)


def create_default_profile(user_id: int) -> Dict[str, Any]:
    """
    Создает профиль по умолчанию для пользователя.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Профиль по умолчанию
    """
    return {
        'user_id': user_id,
        'preferences': {
            'default_resolution': '720p',
            'default_aspect_ratio': '16:9',
            'default_quality': 'medium',
            'preferred_models': [],
            'auto_apply_preferences': True
        },
        'settings': {
            'notifications_enabled': True,
            'auto_save_history': True,
            'show_preview': True
        },
        'created_at': None,
        'updated_at': None
    }


def save_user_profile(user_id: int, profile: Dict[str, Any]) -> bool:
    """
    Сохраняет профиль пользователя.
    
    Args:
        user_id: ID пользователя
        profile: Профиль для сохранения
    
    Returns:
        True, если профиль сохранен успешно
    """
    try:
        # Создаем директорию, если не существует
        PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем существующие профили
        if PROFILES_FILE.exists():
            with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
        else:
            profiles = {}
        
        # Обновляем профиль
        user_key = str(user_id)
        profile['updated_at'] = datetime.now().isoformat()
        if 'created_at' not in profile or not profile['created_at']:
            profile['created_at'] = datetime.now().isoformat()
        
        profiles[user_key] = profile
        
        # Сохраняем
        with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Профиль пользователя {user_id} сохранен")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении профиля пользователя {user_id}: {e}", exc_info=True)
        return False


def update_user_preferences(user_id: int, preferences: Dict[str, Any]) -> bool:
    """
    Обновляет предпочтения пользователя.
    
    Args:
        user_id: ID пользователя
        preferences: Новые предпочтения
    
    Returns:
        True, если предпочтения обновлены успешно
    """
    profile = get_user_profile(user_id)
    profile['preferences'].update(preferences)
    return save_user_profile(user_id, profile)


def get_user_default_parameters(user_id: int, model_id: str) -> Dict[str, Any]:
    """
    Получает параметры по умолчанию для пользователя на основе профиля.
    
    Args:
        user_id: ID пользователя
        model_id: ID модели
    
    Returns:
        Словарь с параметрами по умолчанию
    """
    profile = get_user_profile(user_id)
    prefs = profile.get('preferences', {})
    
    default_params = {}
    
    # Применяем предпочтения, если включена автоматическая подстановка
    if prefs.get('auto_apply_preferences', True):
        if 'default_resolution' in prefs:
            default_params['resolution'] = prefs['default_resolution']
        if 'default_aspect_ratio' in prefs:
            default_params['aspect_ratio'] = prefs['default_aspect_ratio']
        if 'default_quality' in prefs:
            default_params['quality'] = prefs['default_quality']
    
    # Получаем рекомендуемые параметры от AI
    try:
        from ai_parameter_optimizer import suggest_optimal_parameters
        ai_suggested = suggest_optimal_parameters(user_id, model_id)
        
        # Объединяем (приоритет у AI рекомендаций)
        default_params.update(ai_suggested)
    except ImportError:
        pass
    
    return default_params


def apply_user_profile_to_params(user_id: int, model_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Применяет профиль пользователя к параметрам генерации.
    
    Args:
        user_id: ID пользователя
        model_id: ID модели
        params: Текущие параметры
    
    Returns:
        Параметры с примененным профилем
    """
    profile = get_user_profile(user_id)
    prefs = profile.get('preferences', {})
    
    # Если автоматическое применение отключено, возвращаем параметры как есть
    if not prefs.get('auto_apply_preferences', True):
        return params
    
    # Получаем параметры по умолчанию
    default_params = get_user_default_parameters(user_id, model_id)
    
    # Объединяем: сначала дефолтные, потом текущие (приоритет у текущих)
    result = default_params.copy()
    result.update(params)
    
    return result


"""
Модуль для упрощения и оптимизации логики генерации.
"""

import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def validate_generation_params_unified(
    model_id: str,
    params: Dict[str, Any],
    model_schema: Dict[str, Any]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Унифицированная валидация параметров генерации.
    Объединяет все проверки в один блок.
    
    Args:
        model_id: ID модели
        params: Параметры для проверки
        model_schema: Схема модели
    
    Returns:
        (валидно, сообщение_об_ошибке, исправленные_параметры)
    """
    try:
        from input_validation import validate_generation_params
        
        is_valid, errors = validate_generation_params(model_id, params, model_schema)
        
        if not is_valid:
            error_message = "\n".join(errors)
            return False, error_message, params
        
        # Исправляем параметры (нормализация)
        corrected_params = params.copy()
        
        # Нормализация разрешения
        if 'resolution' in corrected_params:
            resolution = str(corrected_params['resolution']).lower()
            if '1080' in resolution:
                corrected_params['resolution'] = '1080p'
            elif '720' in resolution:
                corrected_params['resolution'] = '720p'
            elif '480' in resolution:
                corrected_params['resolution'] = '480p'
        
        # Нормализация aspect_ratio
        if 'aspect_ratio' in corrected_params:
            aspect_ratio = str(corrected_params['aspect_ratio']).lower()
            if '16:9' in aspect_ratio or '16/9' in aspect_ratio:
                corrected_params['aspect_ratio'] = '16:9'
            elif '1:1' in aspect_ratio or '1/1' in aspect_ratio:
                corrected_params['aspect_ratio'] = '1:1'
            elif '4:3' in aspect_ratio or '4/3' in aspect_ratio:
                corrected_params['aspect_ratio'] = '4:3'
        
        return True, None, corrected_params
        
    except Exception as e:
        logger.error(f"❌ Ошибка при валидации параметров: {e}", exc_info=True)
        return False, f"Ошибка валидации: {str(e)}", params


def prepare_generation_request(
    model_id: str,
    params: Dict[str, Any],
    user_id: int
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Подготавливает запрос на генерацию, объединяя все проверки.
    
    Args:
        model_id: ID модели
        params: Параметры генерации
        user_id: ID пользователя
    
    Returns:
        (подготовленные_параметры, сообщение_об_ошибке)
    """
    # Получаем схему модели
    try:
        from kie_models import get_model_by_id
        model_info = get_model_by_id(model_id)
        
        if not model_info:
            return params, f"Модель {model_id} не найдена"
        
        # Валидируем параметры
        is_valid, error_msg, corrected_params = validate_generation_params_unified(
            model_id,
            params,
            model_info
        )
        
        if not is_valid:
            return params, error_msg
        
        # Применяем профиль пользователя
        try:
            from user_profiles import apply_user_profile_to_params
            corrected_params = apply_user_profile_to_params(user_id, model_id, corrected_params)
        except ImportError:
            pass
        
        # Оптимизируем параметры
        try:
            from request_preprocessing import preprocess_request
            corrected_params = preprocess_request('create_task', corrected_params)
        except ImportError:
            pass
        
        return corrected_params, None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при подготовке запроса: {e}", exc_info=True)
        return params, f"Ошибка подготовки: {str(e)}"


def check_balance_with_bonuses(
    user_id: int,
    required_amount: float
) -> Tuple[bool, float, float, float]:
    """
    Проверяет баланс с учетом бонусов.
    Автоматически предлагает использовать бонусы.
    
    Args:
        user_id: ID пользователя
        required_amount: Требуемая сумма
    
    Returns:
        (достаточно, основной_баланс, бонусный_баланс, недостающая_сумма)
    """
    try:
        from db_optimization import get_user_balance_optimized
        from bonus_system import get_user_bonuses
        
        # Получаем балансы
        main_balance = get_user_balance_optimized(user_id)
        bonuses = get_user_bonuses(user_id)
        bonus_balance = bonuses.get('bonus_balance', 0.0)
        
        total_available = main_balance + bonus_balance
        
        if total_available >= required_amount:
            return True, main_balance, bonus_balance, 0.0
        else:
            needed = required_amount - total_available
            return False, main_balance, bonus_balance, needed
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке баланса: {e}", exc_info=True)
        return False, 0.0, 0.0, required_amount


def deduct_balance_with_bonuses(
    user_id: int,
    amount: float
) -> Tuple[bool, float, float]:
    """
    Списывает баланс с автоматическим использованием бонусов.
    
    Args:
        user_id: ID пользователя
        amount: Сумма для списания
    
    Returns:
        (успешно, списано_с_основного, списано_с_бонусов)
    """
    try:
        from db_optimization import get_user_balance_optimized, invalidate_balance_cache
        from bot_kie import set_user_balance
        from bonus_system import get_user_bonuses, use_bonus
        
        # Получаем балансы
        main_balance = get_user_balance_optimized(user_id)
        bonuses = get_user_bonuses(user_id)
        bonus_balance = bonuses.get('bonus_balance', 0.0)
        
        total_available = main_balance + bonus_balance
        
        if total_available < amount:
            return False, 0.0, 0.0
        
        # Сначала используем основной баланс
        deducted_main = min(main_balance, amount)
        remaining = amount - deducted_main
        
        # Затем используем бонусы
        deducted_bonus = min(bonus_balance, remaining)
        
        # Списываем основной баланс
        if deducted_main > 0:
            new_main_balance = main_balance - deducted_main
            set_user_balance(user_id, new_main_balance)
            invalidate_balance_cache(user_id)
        
        # Списываем бонусы
        if deducted_bonus > 0:
            use_bonus(user_id, deducted_bonus, f'Генерация')
        
        logger.info(
            f"✅ Списание баланса для пользователя {user_id}: "
            f"основной {deducted_main:.2f} ₽, бонусы {deducted_bonus:.2f} ₽"
        )
        
        return True, deducted_main, deducted_bonus
        
    except Exception as e:
        logger.error(f"❌ Ошибка при списании баланса: {e}", exc_info=True)
        return False, 0.0, 0.0


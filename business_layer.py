"""
Business Layer для проверки баланса, применения бонусов и списания средств.
"""

import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def check_balance_before_generation(
    user_id: int,
    required_price_rub: float
) -> Tuple[bool, float, float, Optional[str]]:
    """
    Проверяет баланс перед генерацией.
    
    Args:
        user_id: ID пользователя
        required_price_rub: Требуемая сумма в рублях
    
    Returns:
        (достаточно, основной_баланс, бонусный_баланс, сообщение_об_ошибке)
    """
    try:
        try:
            from db_optimization import get_user_balance_optimized
            main_balance = get_user_balance_optimized(user_id)
        except ImportError:
            from bot_kie import get_user_balance
            main_balance = get_user_balance(user_id)
        
        try:
            from bonus_system import get_user_bonuses
            bonuses = get_user_bonuses(user_id)
            bonus_balance = bonuses.get('bonus_balance', 0.0)
        except ImportError:
            bonus_balance = 0.0
        
        total_available = main_balance + bonus_balance
        
        if total_available >= required_price_rub:
            return True, main_balance, bonus_balance, None
        else:
            needed = required_price_rub - total_available
            error_msg = (
                f"Недостаточно средств. Требуется: {required_price_rub:.2f} ₽, "
                f"доступно: {total_available:.2f} ₽ (основной: {main_balance:.2f} ₽, "
                f"бонусы: {bonus_balance:.2f} ₽). Не хватает: {needed:.2f} ₽"
            )
            return False, main_balance, bonus_balance, error_msg
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке баланса: {e}", exc_info=True)
        return False, 0.0, 0.0, f"Ошибка проверки баланса: {str(e)}"


def apply_bonuses_if_available(
    user_id: int,
    required_price_rub: float
) -> Tuple[float, float, float]:
    """
    Применяет бонусы если доступны.
    
    Args:
        user_id: ID пользователя
        required_price_rub: Требуемая сумма
    
    Returns:
        (итоговая_цена, списано_с_основного, списано_с_бонусов)
    """
    try:
        try:
            from db_optimization import get_user_balance_optimized, invalidate_balance_cache
            main_balance = get_user_balance_optimized(user_id)
            invalidate_cache = invalidate_balance_cache
        except ImportError:
            from bot_kie import get_user_balance
            main_balance = get_user_balance(user_id)
            invalidate_cache = lambda uid: None
        
        from bot_kie import set_user_balance
        
        try:
            from bonus_system import get_user_bonuses, use_bonus
            bonuses = get_user_bonuses(user_id)
            bonus_balance = bonuses.get('bonus_balance', 0.0)
            use_bonus_func = use_bonus
        except ImportError:
            bonus_balance = 0.0
            use_bonus_func = lambda uid, amount, reason: None
        
        # Сначала используем основной баланс
        deducted_main = min(main_balance, required_price_rub)
        remaining = required_price_rub - deducted_main
        
        # Затем используем бонусы
        deducted_bonus = min(bonus_balance, remaining)
        
        # Списываем основной баланс
        if deducted_main > 0:
            new_main_balance = main_balance - deducted_main
            set_user_balance(user_id, new_main_balance)
            invalidate_cache(user_id)
        
        # Списываем бонусы
        if deducted_bonus > 0:
            use_bonus_func(user_id, deducted_bonus, 'Генерация')
        
        final_price = deducted_main + deducted_bonus
        
        logger.info(
            f"✅ Списание для пользователя {user_id}: "
            f"основной {deducted_main:.2f} ₽, бонусы {deducted_bonus:.2f} ₽"
        )
        
        return final_price, deducted_main, deducted_bonus
        
    except Exception as e:
        logger.error(f"❌ Ошибка при применении бонусов: {e}", exc_info=True)
        return 0.0, 0.0, 0.0


def deduct_balance_after_success(
    user_id: int,
    price_rub: float,
    is_admin: bool = False
) -> bool:
    """
    Списывает баланс после успешной генерации.
    
    Args:
        user_id: ID пользователя
        price_rub: Сумма для списания
        is_admin: Является ли пользователь админом
    
    Returns:
        True если списание успешно
    """
    try:
        from config_runtime import is_dry_run, is_test_mode
        
        # В TEST_MODE/DRY_RUN не списываем
        if is_dry_run() or is_test_mode():
            logger.info(f"🔧 DRY-RUN: Пропущено списание {price_rub} ₽ для пользователя {user_id}")
            return True
        
        if is_admin:
            # Для админов не списываем
            return True
        
        # Применяем бонусы и списываем
        final_price, deducted_main, deducted_bonus = apply_bonuses_if_available(
            user_id,
            price_rub
        )
        
        if final_price >= price_rub:
            return True
        else:
            logger.error(
                f"❌ Не удалось списать полную сумму: "
                f"требовалось {price_rub:.2f} ₽, списано {final_price:.2f} ₽"
            )
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при списании баланса: {e}", exc_info=True)
        return False


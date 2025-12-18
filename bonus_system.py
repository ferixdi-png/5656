"""
Модуль для системы бонусов и скидок.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Файл для хранения бонусов
BONUSES_FILE = Path("data/user_bonuses.json")


def get_user_bonuses(user_id: int) -> Dict[str, Any]:
    """
    Получает информацию о бонусах пользователя.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Словарь с информацией о бонусах
    """
    try:
        if not BONUSES_FILE.exists():
            return create_default_bonuses(user_id)
        
        with open(BONUSES_FILE, 'r', encoding='utf-8') as f:
            bonuses = json.load(f)
        
        user_key = str(user_id)
        if user_key in bonuses:
            return bonuses[user_key]
        else:
            return create_default_bonuses(user_id)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при получении бонусов пользователя {user_id}: {e}", exc_info=True)
        return create_default_bonuses(user_id)


def create_default_bonuses(user_id: int) -> Dict[str, Any]:
    """Создает структуру бонусов по умолчанию."""
    return {
        'user_id': user_id,
        'bonus_balance': 0.0,
        'bonus_points': 0,
        'total_earned': 0.0,
        'total_spent': 0.0,
        'promotions': [],
        'referral_bonuses': 0,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }


def save_user_bonuses(user_id: int, bonuses: Dict[str, Any]) -> bool:
    """Сохраняет бонусы пользователя."""
    try:
        BONUSES_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        if BONUSES_FILE.exists():
            with open(BONUSES_FILE, 'r', encoding='utf-8') as f:
                all_bonuses = json.load(f)
        else:
            all_bonuses = {}
        
        bonuses['updated_at'] = datetime.now().isoformat()
        all_bonuses[str(user_id)] = bonuses
        
        with open(BONUSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_bonuses, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении бонусов: {e}", exc_info=True)
        return False


def add_bonus(user_id: int, amount: float, reason: str = '') -> bool:
    """
    Добавляет бонус пользователю.
    
    Args:
        user_id: ID пользователя
        amount: Сумма бонуса
        reason: Причина начисления
    """
    bonuses = get_user_bonuses(user_id)
    bonuses['bonus_balance'] = bonuses.get('bonus_balance', 0.0) + amount
    bonuses['total_earned'] = bonuses.get('total_earned', 0.0) + amount
    
    if reason:
        if 'history' not in bonuses:
            bonuses['history'] = []
        bonuses['history'].append({
            'type': 'earned',
            'amount': amount,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })
    
    return save_user_bonuses(user_id, bonuses)


def use_bonus(user_id: int, amount: float, reason: str = '') -> bool:
    """
    Использует бонус пользователя.
    
    Args:
        user_id: ID пользователя
        amount: Сумма для списания
        reason: Причина списания
    """
    bonuses = get_user_bonuses(user_id)
    current_balance = bonuses.get('bonus_balance', 0.0)
    
    if current_balance < amount:
        return False
    
    bonuses['bonus_balance'] = current_balance - amount
    bonuses['total_spent'] = bonuses.get('total_spent', 0.0) + amount
    
    if reason:
        if 'history' not in bonuses:
            bonuses['history'] = []
        bonuses['history'].append({
            'type': 'spent',
            'amount': amount,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        })
    
    return save_user_bonuses(user_id, bonuses)


def apply_promotion(user_id: int, promotion_code: str) -> Dict[str, Any]:
    """
    Применяет промо-код или акцию.
    
    Args:
        user_id: ID пользователя
        promotion_code: Код промо-акции
    
    Returns:
        Результат применения промо-кода
    """
    # Проверяем промо-коды
    promotions = {
        'NEWUSER10': {'discount': 0.1, 'description': 'Скидка 10% для новых пользователей'},
        'FIRSTGEN': {'bonus': 50.0, 'description': '50 рублей бонусов на первую генерацию'},
        'WELCOME': {'discount': 0.15, 'description': 'Приветственная скидка 15%'},
        'SEASON2024': {'discount': 0.2, 'description': 'Сезонная скидка 20%'}
    }
    
    promotion = promotions.get(promotion_code.upper())
    if not promotion:
        return {
            'success': False,
            'message': 'Неверный промо-код'
        }
    
    bonuses = get_user_bonuses(user_id)
    
    # Проверяем, не использован ли уже этот промо-код
    used_promos = bonuses.get('promotions', [])
    if promotion_code.upper() in used_promos:
        return {
            'success': False,
            'message': 'Этот промо-код уже использован'
        }
    
    # Применяем промо-код
    used_promos.append(promotion_code.upper())
    bonuses['promotions'] = used_promos
    
    if 'discount' in promotion:
        # Сохраняем скидку в профиле
        bonuses['active_discount'] = {
            'code': promotion_code.upper(),
            'discount': promotion['discount'],
            'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
        }
    
    if 'bonus' in promotion:
        add_bonus(user_id, promotion['bonus'], f'Промо-код {promotion_code}')
    
    save_user_bonuses(user_id, bonuses)
    
    return {
        'success': True,
        'message': promotion['description'],
        'promotion': promotion
    }


def get_active_discount(user_id: int) -> Optional[float]:
    """
    Получает активную скидку пользователя.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Размер скидки (0.0-1.0) или None
    """
    bonuses = get_user_bonuses(user_id)
    active_discount = bonuses.get('active_discount')
    
    if not active_discount:
        return None
    
    # Проверяем срок действия
    expires_at = active_discount.get('expires_at')
    if expires_at:
        try:
            expires = datetime.fromisoformat(expires_at)
            if datetime.now() > expires:
                return None
        except:
            pass
    
    return active_discount.get('discount', 0.0)


def format_bonus_info(user_id: int, lang: str = 'ru') -> str:
    """
    Форматирует информацию о бонусах для пользователя.
    
    Args:
        user_id: ID пользователя
        lang: Язык
    
    Returns:
        Отформатированная информация о бонусах
    """
    bonuses = get_user_bonuses(user_id)
    bonus_balance = bonuses.get('bonus_balance', 0.0)
    active_discount = get_active_discount(user_id)
    
    if lang == 'ru':
        text = f"🎁 <b>Ваши бонусы:</b>\n\n"
        text += f"💰 <b>Бонусный баланс:</b> {bonus_balance:.2f} ₽\n"
        
        if active_discount:
            discount_percent = int(active_discount * 100)
            text += f"🎫 <b>Активная скидка:</b> {discount_percent}%\n"
        
        text += f"\n💡 <b>Как получить бонусы:</b>\n"
        text += f"• Пригласите друга: +50 ₽\n"
        text += f"• Оставьте отзыв: +10 ₽\n"
        text += f"• Используйте промо-коды\n"
    else:
        text = f"🎁 <b>Your Bonuses:</b>\n\n"
        text += f"💰 <b>Bonus Balance:</b> {bonus_balance:.2f} ₽\n"
        
        if active_discount:
            discount_percent = int(active_discount * 100)
            text += f"🎫 <b>Active Discount:</b> {discount_percent}%\n"
        
        text += f"\n💡 <b>How to Get Bonuses:</b>\n"
        text += f"• Invite a friend: +50 ₽\n"
        text += f"• Leave feedback: +10 ₽\n"
        text += f"• Use promo codes\n"
    
    return text


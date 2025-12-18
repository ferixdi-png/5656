"""
Модуль для прозрачного ценообразования и отображения цен пользователю.
Включает динамический пересчет цен, детализацию стоимости и подтверждение.
"""

import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)

# Курс валют (можно получать из API)
USD_TO_RUB_RATE = 100.0  # Примерный курс, должен обновляться


def calculate_detailed_price(
    model_id: str,
    params: Dict[str, Any],
    base_price_usd: float = 0.0,
    multiplier: float = 2.0
) -> Dict[str, Any]:
    """
    Рассчитывает детализированную цену с учетом всех параметров.
    
    Args:
        model_id: ID модели
        params: Параметры генерации
        base_price_usd: Базовая цена в USD от KIE AI
        multiplier: Множитель для цены (по умолчанию X2)
    
    Returns:
        Словарь с детализированной информацией о цене
    """
    # Базовая цена в рублях
    base_price_rub = base_price_usd * USD_TO_RUB_RATE * multiplier
    
    # Дополнительные наценки за параметры
    additional_costs = {}
    total_additional = 0.0
    
    # Наценка за разрешение
    resolution = params.get('resolution', '')
    if resolution:
        if '1080' in str(resolution) or '4k' in str(resolution).lower():
            additional_costs['resolution'] = {
                'name': 'Высокое разрешение',
                'amount': base_price_rub * 0.3,  # +30%
                'description': f'Разрешение {resolution}'
            }
            total_additional += additional_costs['resolution']['amount']
        elif '720' in str(resolution):
            additional_costs['resolution'] = {
                'name': 'Среднее разрешение',
                'amount': 0.0,
                'description': f'Разрешение {resolution}'
            }
        else:
            additional_costs['resolution'] = {
                'name': 'Базовое разрешение',
                'amount': 0.0,
                'description': f'Разрешение {resolution}'
            }
    
    # Наценка за длительность видео
    duration = params.get('duration')
    if duration:
        try:
            duration_sec = float(duration)
            if duration_sec > 10:
                # За каждую секунду свыше 10 секунд
                extra_seconds = duration_sec - 10
                additional_costs['duration'] = {
                    'name': 'Дополнительная длительность',
                    'amount': base_price_rub * 0.1 * (extra_seconds / 10),  # +10% за каждые 10 секунд
                    'description': f'{duration_sec} секунд (базовая цена за 10 сек)'
                }
                total_additional += additional_costs['duration']['amount']
            else:
                additional_costs['duration'] = {
                    'name': 'Базовая длительность',
                    'amount': 0.0,
                    'description': f'{duration_sec} секунд'
                }
        except (ValueError, TypeError):
            pass
    
    # Наценка за количество изображений
    num_images = params.get('num_images', 1)
    if num_images and isinstance(num_images, (int, str)):
        try:
            num = int(num_images)
            if num > 1:
                additional_costs['num_images'] = {
                    'name': 'Дополнительные изображения',
                    'amount': base_price_rub * (num - 1) * 0.8,  # 80% от базовой за каждое дополнительное
                    'description': f'{num} изображений'
                }
                total_additional += additional_costs['num_images']['amount']
        except (ValueError, TypeError):
            pass
    
    # Наценка за удаление водяного знака
    if params.get('remove_watermark', False):
        additional_costs['remove_watermark'] = {
            'name': 'Удаление водяного знака',
            'amount': base_price_rub * 0.5,  # +50%
            'description': 'Без водяного знака'
        }
        total_additional += additional_costs['remove_watermark']['amount']
    
    # Итоговая цена
    total_price = base_price_rub + total_additional
    
    return {
        'base_price_usd': base_price_usd,
        'base_price_rub': base_price_rub,
        'multiplier': multiplier,
        'additional_costs': additional_costs,
        'total_additional': total_additional,
        'total_price': total_price,
        'currency': 'RUB'
    }


def format_price_breakdown(price_info: Dict[str, Any], lang: str = 'ru') -> str:
    """
    Форматирует детализированную информацию о цене для пользователя.
    
    Args:
        price_info: Информация о цене от calculate_detailed_price
        lang: Язык
    
    Returns:
        Отформатированный текст с детализацией цены
    """
    if lang == 'ru':
        text = "💰 <b>Детализация стоимости:</b>\n\n"
        text += f"📊 <b>Базовая цена:</b> {price_info['base_price_rub']:.2f} ₽\n"
        
        if price_info['additional_costs']:
            text += "\n📝 <b>Дополнительные параметры:</b>\n"
            for key, cost_info in price_info['additional_costs'].items():
                if cost_info['amount'] > 0:
                    text += f"  • {cost_info['name']}: <b>+{cost_info['amount']:.2f}</b> ₽\n"
                    text += f"    ({cost_info['description']})\n"
        
        text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💵 <b>Итого:</b> <b>{price_info['total_price']:.2f}</b> ₽\n"
    else:
        text = "💰 <b>Price Breakdown:</b>\n\n"
        text += f"📊 <b>Base Price:</b> {price_info['base_price_rub']:.2f} ₽\n"
        
        if price_info['additional_costs']:
            text += "\n📝 <b>Additional Parameters:</b>\n"
            for key, cost_info in price_info['additional_costs'].items():
                if cost_info['amount'] > 0:
                    text += f"  • {cost_info['name']}: <b>+{cost_info['amount']:.2f}</b> ₽\n"
                    text += f"    ({cost_info['description']})\n"
        
        text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💵 <b>Total:</b> <b>{price_info['total_price']:.2f}</b> ₽\n"
    
    return text


def get_price_hint_for_parameter(param_name: str, param_value: Any, lang: str = 'ru') -> str:
    """
    Возвращает подсказку о влиянии параметра на цену.
    
    Args:
        param_name: Название параметра
        param_value: Значение параметра
        lang: Язык
    
    Returns:
        Подсказка о влиянии на цену
    """
    if lang == 'ru':
        hints = {
            'resolution': {
                '1080p': 'Высокое разрешение увеличивает стоимость на ~30%',
                '720p': 'Стандартное разрешение, без доплаты',
                '480p': 'Базовое разрешение, минимальная стоимость'
            },
            'duration': 'Каждые дополнительные 10 секунд увеличивают стоимость на ~10%',
            'num_images': 'Каждое дополнительное изображение стоит 80% от базовой цены',
            'remove_watermark': 'Удаление водяного знака увеличивает стоимость на 50%'
        }
    else:
        hints = {
            'resolution': {
                '1080p': 'High resolution increases cost by ~30%',
                '720p': 'Standard resolution, no extra charge',
                '480p': 'Basic resolution, minimum cost'
            },
            'duration': 'Each additional 10 seconds increases cost by ~10%',
            'num_images': 'Each additional image costs 80% of base price',
            'remove_watermark': 'Removing watermark increases cost by 50%'
        }
    
    if param_name in hints:
        if isinstance(hints[param_name], dict):
            return hints[param_name].get(str(param_value), '')
        else:
            return hints[param_name]
    
    return ''


def format_price_simple(price: float, lang: str = 'ru') -> str:
    """
    Форматирует простую цену для отображения.
    
    Args:
        price: Цена в рублях
        lang: Язык
    
    Returns:
        Отформатированная цена
    """
    price_str = f"{price:.2f}".rstrip('0').rstrip('.')
    
    if lang == 'ru':
        return f"{price_str} ₽"
    else:
        return f"{price_str} RUB"


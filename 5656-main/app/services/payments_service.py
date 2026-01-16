"""
Payments service - работа с платежами и курсами валют
БЕЗ зависимостей от bot_kie.py
"""

import logging
from typing import Optional
from app.storage import get_storage

logger = logging.getLogger(__name__)


# Константы для конвертации
CREDIT_TO_USD = 0.005  # 1 credit = $0.005
USD_TO_RUB_DEFAULT = 77.22  # 1 USD = 77.22 RUB (default)


def get_usd_to_rub_rate() -> float:
    """
    Получить курс USD к RUB
    Пока возвращает дефолтное значение, можно расширить для чтения из storage
    """
    # TODO: можно читать из storage если нужно динамическое обновление
    return USD_TO_RUB_DEFAULT


def set_usd_to_rub_rate(rate: float) -> None:
    """
    Установить курс USD к RUB
    Пока заглушка, можно расширить для сохранения в storage
    """
    # TODO: можно сохранять в storage если нужно динамическое обновление
    logger.info(f"USD to RUB rate set to {rate}")


def credit_to_rub(credits: float) -> float:
    """Конвертировать кредиты в рубли"""
    return credits * CREDIT_TO_USD * get_usd_to_rub_rate()


def rub_to_credit(rub: float) -> float:
    """Конвертировать рубли в кредиты"""
    return rub / (CREDIT_TO_USD * get_usd_to_rub_rate())



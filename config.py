"""
Централизованная система конфигурации
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class Settings:
    """Настройки бота"""
    
    def __init__(self):
        # Bot settings
        self.BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
        
        # Получаем ADMIN_ID с обработкой ошибок
        admin_id_str = os.getenv('ADMIN_ID', '6913446846')
        if admin_id_str and admin_id_str != 'your_admin_id_here':
            try:
                self.ADMIN_ID: int = int(admin_id_str)
            except (ValueError, TypeError):
                self.ADMIN_ID: int = 6913446846  # Default fallback
        else:
            self.ADMIN_ID: int = 6913446846  # Default fallback
        
        # Price conversion constants
        self.CREDIT_TO_USD: float = 0.005  # 1 credit = $0.005
        self.USD_TO_RUB: float = 77.2222  # 1 USD = 77.2222 RUB (calculated from 6.95 ₽ / $0.09)
        
        # Free generations
        self.FREE_GENERATIONS_PER_DAY: int = 5
        self.REFERRAL_BONUS_GENERATIONS: int = 5
        self.FREE_MODEL_ID: str = "z-image"
        
        # File paths
        self.BALANCES_FILE: str = "user_balances.json"
        self.USER_LANGUAGES_FILE: str = "user_languages.json"
        self.GIFT_CLAIMED_FILE: str = "gift_claimed.json"
        self.ADMIN_LIMITS_FILE: str = "admin_limits.json"
        self.PAYMENTS_FILE: str = "payments.json"
        self.BLOCKED_USERS_FILE: str = "blocked_users.json"
        self.FREE_GENERATIONS_FILE: str = "daily_free_generations.json"
        self.PROMOCODES_FILE: str = "promocodes.json"
        self.REFERRALS_FILE: str = "referrals.json"
        self.BROADCASTS_FILE: str = "broadcasts.json"
        self.GENERATIONS_HISTORY_FILE: str = "generations_history.json"
        
        # Payment settings
        self.PAYMENT_PHONE: Optional[str] = os.getenv('PAYMENT_PHONE')
        self.PAYMENT_BANK: Optional[str] = os.getenv('PAYMENT_BANK')
        self.PAYMENT_CARD_HOLDER: Optional[str] = os.getenv('PAYMENT_CARD_HOLDER')
        
        # Support settings
        self.SUPPORT_TELEGRAM: Optional[str] = os.getenv('SUPPORT_TELEGRAM')
        self.SUPPORT_TEXT: Optional[str] = os.getenv('SUPPORT_TEXT')
    
    def validate(self):
        """Валидация настроек"""
        errors = []
        
        if not self.BOT_TOKEN:
            errors.append("BOT_TOKEN не установлен")
        
        if not self.ADMIN_ID or self.ADMIN_ID == 0:
            errors.append("ADMIN_ID не установлен или неверный")
        
        if errors:
            raise ValueError(f"Ошибки конфигурации: {', '.join(errors)}")
        
        return True


# Создаем глобальный экземпляр настроек
settings = Settings()

# Валидируем при импорте
try:
    settings.validate()
except ValueError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Configuration validation warning: {e}")

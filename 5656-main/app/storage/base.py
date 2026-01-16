"""
Базовый интерфейс для storage (JSON или PostgreSQL)
Единый API для всех операций с данными пользователей
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime


class BaseStorage(ABC):
    """Базовый интерфейс для хранения данных пользователей"""
    
    # ==================== USER OPERATIONS ====================
    
    @abstractmethod
    async def ensure_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> None:
        """
        Ensure user exists in database (create if not exists, update if changed)
        CRITICAL: Call this BEFORE creating jobs to avoid FK violations
        
        Args:
            user_id: Telegram user ID
            username: Telegram username (optional)
            first_name: User first name (optional)
            last_name: User last name (optional)
        """
        pass
    
    @abstractmethod
    async def get_user(self, user_id: int, upsert: bool = True) -> Dict[str, Any]:
        """
        Получить данные пользователя (создать если не существует)
        
        Returns:
            {
                'user_id': int,
                'balance': float,
                'language': str,
                'gift_claimed': bool,
                'referrer_id': Optional[int],
                'created_at': datetime,
                'updated_at': datetime
            }
        """
        pass
    
    @abstractmethod
    async def get_user_balance(self, user_id: int) -> float:
        """Получить баланс пользователя в рублях"""
        pass
    
    @abstractmethod
    async def set_user_balance(self, user_id: int, amount: float) -> None:
        """Установить баланс пользователя в рублях"""
        pass
    
    @abstractmethod
    async def add_user_balance(self, user_id: int, amount: float) -> float:
        """Добавить к балансу пользователя, вернуть новый баланс"""
        pass
    
    @abstractmethod
    async def subtract_user_balance(self, user_id: int, amount: float) -> bool:
        """Вычесть из баланса пользователя. Возвращает True если успешно, False если недостаточно средств"""
        pass
    
    @abstractmethod
    async def get_user_language(self, user_id: int) -> str:
        """Получить язык пользователя (по умолчанию 'ru')"""
        pass
    
    @abstractmethod
    async def set_user_language(self, user_id: int, language: str) -> None:
        """Установить язык пользователя"""
        pass
    
    @abstractmethod
    async def has_claimed_gift(self, user_id: int) -> bool:
        """Проверить, получил ли пользователь подарок"""
        pass
    
    @abstractmethod
    async def set_gift_claimed(self, user_id: int) -> None:
        """Отметить, что пользователь получил подарок"""
        pass
    
    @abstractmethod
    async def get_user_free_generations_today(self, user_id: int) -> int:
        """Получить количество бесплатных генераций использованных сегодня"""
        pass
    
    @abstractmethod
    async def get_user_free_generations_remaining(self, user_id: int) -> int:
        """Получить оставшиеся бесплатные генерации на сегодня"""
        pass
    
    @abstractmethod
    async def increment_free_generations(self, user_id: int) -> None:
        """Увеличить счетчик бесплатных генераций на сегодня"""
        pass
    
    @abstractmethod
    async def get_admin_limit(self, user_id: int) -> float:
        """Получить лимит админа (inf для главного админа)"""
        pass
    
    @abstractmethod
    async def get_admin_spent(self, user_id: int) -> float:
        """Получить потраченную сумму админа"""
        pass
    
    @abstractmethod
    async def get_admin_remaining(self, user_id: int) -> float:
        """Получить оставшийся лимит админа"""
        pass
    
    # ==================== GENERATION JOBS ====================
    
    @abstractmethod
    async def add_generation_job(
        self,
        user_id: int,
        model_id: str,
        model_name: str,
        params: Dict[str, Any],
        price: float,
        task_id: Optional[str] = None,
        status: str = "queued"
    ) -> str:
        """
        Добавить задачу генерации
        
        Returns:
            job_id: str - ID задачи
        """
        pass
    
    @abstractmethod
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        result_urls: Optional[List[str]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Обновить статус задачи генерации"""
        pass
    
    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Получить задачу по ID"""
        pass

    @abstractmethod
    async def find_job_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Найти задачу по внешнему task_id (callback).

        Returns job dict or None when not found.
        """
        pass

    @abstractmethod
    async def get_undelivered_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get jobs that are done but not delivered to Telegram (for retry)."""
        pass

    @abstractmethod
    async def list_jobs(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Получить список задач с фильтрацией и пагинацией"""
        pass

    @abstractmethod
    async def add_generation_to_history(
        self,
        user_id: int,
        model_id: str,
        model_name: str,
        params: Dict[str, Any],
        result_urls: List[str],
        price: float,
        operation_id: Optional[str] = None,
    ) -> str:
        """Добавить генерацию в историю. Возвращает ID генерации"""
        pass
    
    @abstractmethod
    async def get_user_generations_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить историю генераций пользователя"""
        pass
    
    # ==================== PAYMENTS ====================
    
    @abstractmethod
    async def add_payment(
        self,
        user_id: int,
        amount: float,
        payment_method: str,
        payment_id: Optional[str] = None,
        screenshot_file_id: Optional[str] = None,
        status: str = "pending",
        idempotency_key: Optional[str] = None
    ) -> str:
        """
        Добавить платеж с поддержкой idempotency
        
        Args:
            idempotency_key: Ключ идемпотентности (request_id + user_id + model_id)
                           Если передан и платеж уже существует, возвращает существующий payment_id
        
        Returns:
            payment_id: str - ID платежа
        """
        pass
    
    @abstractmethod
    async def mark_payment_status(
        self,
        payment_id: str,
        status: str,
        admin_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> None:
        """
        Обновить статус платежа (pending -> approved/rejected)
        
        При статусе "cancelled" или "failed" автоматически откатывает резерв/списание баланса
        """
        pass
    
    @abstractmethod
    async def reserve_balance_for_generation(
        self,
        user_id: int,
        amount: float,
        model_id: str,
        task_id: str,
        idempotency_key: Optional[str] = None
    ) -> bool:
        """
        Резервирует баланс для генерации (idempotent)
        
        Args:
            idempotency_key: Ключ идемпотентности (task_id + user_id + model_id)
        
        Returns:
            True если резерв успешен, False если недостаточно средств или уже зарезервировано
        """
        pass
    
    @abstractmethod
    async def release_balance_reserve(
        self,
        user_id: int,
        task_id: str,
        model_id: str
    ) -> bool:
        """
        Освобождает зарезервированный баланс (при отмене/ошибке)
        
        Returns:
            True если резерв был освобожден, False если резерва не было
        """
        pass
    
    @abstractmethod
    async def commit_balance_reserve(
        self,
        user_id: int,
        task_id: str,
        model_id: str
    ) -> bool:
        """
        Подтверждает резерв баланса (списывает при успешной генерации)
        
        Returns:
            True если списание успешно, False если резерва не было
        """
        pass
    
    @abstractmethod
    async def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Получить платеж по ID"""
        pass
    
    @abstractmethod
    async def list_payments(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Получить список платежей (с фильтрацией)"""
        pass
    
    # ==================== REFERRALS ====================
    
    @abstractmethod
    async def set_referrer(self, user_id: int, referrer_id: int) -> None:
        """Установить реферера для пользователя"""
        pass
    
    @abstractmethod
    async def get_referrer(self, user_id: int) -> Optional[int]:
        """Получить ID реферера пользователя"""
        pass
    
    @abstractmethod
    async def get_referrals(self, referrer_id: int) -> List[int]:
        """Получить список рефералов реферера"""
        pass
    
    @abstractmethod
    async def add_referral_bonus(self, referrer_id: int, bonus_generations: int = 5) -> None:
        """Добавить бонусные генерации рефереру"""
        pass
    
    # ==================== FREE USAGE TRACKING ====================
    
    @abstractmethod
    async def log_free_usage(self, user_id: int, model_id: str, job_id: Optional[str] = None) -> None:
        """Log free model usage (for limit tracking)"""
        pass
    
    @abstractmethod
    async def get_daily_free_usage(self, user_id: int, model_id: str) -> int:
        """Get daily free usage count for a user and model"""
        pass
    
    @abstractmethod
    async def get_hourly_free_usage(self, user_id: int, model_id: str) -> int:
        """Get hourly free usage count for a user and model"""
        pass
    
    @abstractmethod
    async def delete_free_usage(self, user_id: int, model_id: str, job_id: str) -> None:
        """Delete a specific free usage record (used when generation fails)"""
        pass
    
    # ==================== UTILITY ====================
    
    @abstractmethod
    async def async_test_connection(self) -> bool:
        """
        Проверить подключение (async-friendly).
        
        ВАЖНО: Используется в runtime когда event loop уже запущен.
        """
        return True  # Base implementation - переопределяется в подклассах
    
    def test_connection(self) -> bool:
        """Проверить подключение (синхронно, для инициализации)"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Закрыть соединения (для cleanup)"""
        pass

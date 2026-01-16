"""
JSON storage implementation - хранение данных в JSON файлах
Атомарная запись (temp+rename), filelock для безопасности
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import aiofiles

from app.storage.base import BaseStorage
from app.storage.status import is_terminal_status, normalize_job_status

# Опциональный импорт filelock (мягкая деградация)
try:
    from filelock import FileLock, Timeout

    FILELOCK_AVAILABLE = True
except ImportError:
    FILELOCK_AVAILABLE = False
    pass

logger = logging.getLogger(__name__)


class JsonStorage(BaseStorage):
    """JSON storage implementation"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Файлы
        self.balances_file = self.data_dir / "user_balances.json"
        self.languages_file = self.data_dir / "user_languages.json"
        self.gift_claimed_file = self.data_dir / "gift_claimed.json"
        self.free_generations_file = self.data_dir / "daily_free_generations.json"
        self.admin_limits_file = self.data_dir / "admin_limits.json"
        self.generations_history_file = self.data_dir / "generations_history.json"
        self.payments_file = self.data_dir / "payments.json"
        self.referrals_file = self.data_dir / "referrals.json"
        self.jobs_file = self.data_dir / "generation_jobs.json"
        self.processed_transactions_file = self.data_dir / "processed_transactions.json"

        # Инициализируем файлы если их нет
        self._init_files()

    def _init_files(self):
        """Инициализирует JSON файлы если их нет"""
        files = [
            self.balances_file,
            self.languages_file,
            self.gift_claimed_file,
            self.free_generations_file,
            self.admin_limits_file,
            self.generations_history_file,
            self.payments_file,
            self.referrals_file,
            self.jobs_file,
            self.processed_transactions_file,
        ]
        for file in files:
            if not file.exists():
                try:
                    file.write_text("{}", encoding="utf-8")
                except Exception as e:
                    logger.error(f"Failed to create {file}: {e}")

    def _get_lock_file(self, file_path: Path) -> Path:
        """Получает путь к lock файлу"""
        return file_path.parent / f".{file_path.name}.lock"

    async def _load_json(self, file_path: Path) -> Dict[str, Any]:
        """Загружает JSON файл"""
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                if not content.strip():
                    return {}
                return json.loads(content)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {file_path}, returning empty dict")
            return {}
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return {}

    async def _save_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Сохраняет JSON файл атомарно (temp file + rename)"""
        if FILELOCK_AVAILABLE:
            lock_file = self._get_lock_file(file_path)
            lock = FileLock(lock_file, timeout=5)

            try:
                with lock:
                    # Создаем временный файл
                    temp_file = file_path.with_suffix(".tmp")
                    async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
                        await f.write(json.dumps(data, ensure_ascii=False, indent=2))

                    # Атомарно переименовываем
                    temp_file.replace(file_path)
            except Timeout:
                logger.error(f"Timeout acquiring lock for {file_path}")
                raise
            except Exception as e:
                logger.error(f"Error saving {file_path}: {e}")
                raise
        else:
            # Без filelock - просто сохраняем (риск race conditions, но работает)
            temp_file = file_path.with_suffix(".tmp")
            async with aiofiles.open(temp_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
            temp_file.replace(file_path)

    # ==================== USER OPERATIONS ====================
    
    async def ensure_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> None:
        """
        Ensure user exists (JSON storage doesn't enforce FK but keep API compatible)
        In JSON mode this is a no-op since we create users on-demand
        """
        # JSON storage creates users automatically in get_user with upsert=True
        # This method exists for API compatibility with PostgreSQL storage
        pass

    async def get_user(self, user_id: int, upsert: bool = True) -> Dict[str, Any]:
        """Получить данные пользователя"""
        balance = await self.get_user_balance(user_id)
        language = await self.get_user_language(user_id)
        gift_claimed = await self.has_claimed_gift(user_id)
        referrer_id = await self.get_referrer(user_id)

        return {
            "user_id": user_id,
            "balance": balance,
            "language": language,
            "gift_claimed": gift_claimed,
            "referrer_id": referrer_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    async def get_user_balance(self, user_id: int) -> float:
        """Получить баланс пользователя"""
        data = await self._load_json(self.balances_file)
        return float(data.get(str(user_id), 0.0))

    async def set_user_balance(self, user_id: int, amount: float) -> None:
        """Установить баланс пользователя"""
        data = await self._load_json(self.balances_file)
        data[str(user_id)] = amount
        await self._save_json(self.balances_file, data)

    async def add_user_balance(self, user_id: int, amount: float) -> float:
        """Добавить к балансу"""
        current = await self.get_user_balance(user_id)
        new_balance = current + amount
        await self.set_user_balance(user_id, new_balance)
        return new_balance

    async def subtract_user_balance(self, user_id: int, amount: float) -> bool:
        """Вычесть из баланса"""
        current = await self.get_user_balance(user_id)
        if current >= amount:
            await self.set_user_balance(user_id, current - amount)
            return True
        return False

    async def get_user_language(self, user_id: int) -> str:
        """Получить язык пользователя"""
        data = await self._load_json(self.languages_file)
        return data.get(str(user_id), "ru")

    async def set_user_language(self, user_id: int, language: str) -> None:
        """Установить язык пользователя"""
        data = await self._load_json(self.languages_file)
        data[str(user_id)] = language
        await self._save_json(self.languages_file, data)

    async def has_claimed_gift(self, user_id: int) -> bool:
        """Проверить получение подарка"""
        data = await self._load_json(self.gift_claimed_file)
        return data.get(str(user_id), False)

    async def set_gift_claimed(self, user_id: int) -> None:
        """Отметить получение подарка"""
        data = await self._load_json(self.gift_claimed_file)
        data[str(user_id)] = True
        await self._save_json(self.gift_claimed_file, data)

    async def get_user_free_generations_today(self, user_id: int) -> int:
        """Получить количество бесплатных генераций сегодня"""
        data = await self._load_json(self.free_generations_file)
        user_key = str(user_id)
        today = datetime.now().strftime("%Y-%m-%d")

        if user_key not in data:
            return 0

        user_data = data[user_key]
        if user_data.get("date") == today:
            return user_data.get("count", 0)
        return 0

    async def get_user_free_generations_remaining(self, user_id: int) -> int:
        """Получить оставшиеся бесплатные генерации"""
        from app.config import get_settings

        settings = get_settings()
        free_per_day = 5  # TODO: добавить в settings

        used = await self.get_user_free_generations_today(user_id)
        data = await self._load_json(self.free_generations_file)
        user_key = str(user_id)
        bonus = data.get(user_key, {}).get("bonus", 0)
        total_available = free_per_day + bonus
        return max(0, total_available - used)

    async def increment_free_generations(self, user_id: int) -> None:
        """Увеличить счетчик бесплатных генераций"""
        data = await self._load_json(self.free_generations_file)
        user_key = str(user_id)
        today = datetime.now().strftime("%Y-%m-%d")

        if user_key not in data:
            data[user_key] = {"date": today, "count": 0, "bonus": 0}

        user_data = data[user_key]
        if user_data.get("date") != today:
            user_data["date"] = today
            user_data["count"] = 0

        user_data["count"] = user_data.get("count", 0) + 1
        await self._save_json(self.free_generations_file, data)

    async def get_admin_limit(self, user_id: int) -> float:
        """Получить лимит админа"""
        from app.config import get_settings

        settings = get_settings()

        if user_id == settings.admin_id:
            return float("inf")

        data = await self._load_json(self.admin_limits_file)
        admin_data = data.get(str(user_id), {})
        return float(admin_data.get("limit", 100.0))

    async def get_admin_spent(self, user_id: int) -> float:
        """Получить потраченную сумму админа"""
        data = await self._load_json(self.admin_limits_file)
        admin_data = data.get(str(user_id), {})
        return float(admin_data.get("spent", 0.0))

    async def get_admin_remaining(self, user_id: int) -> float:
        """Получить оставшийся лимит админа"""
        limit = await self.get_admin_limit(user_id)
        if limit == float("inf"):
            return float("inf")
        spent = await self.get_admin_spent(user_id)
        return max(0.0, limit - spent)

    # ==================== GENERATION JOBS ====================

    async def add_generation_job(
        self,
        user_id: int,
        model_id: str,
        model_name: str,
        params: Dict[str, Any],
        price: float,
        task_id: Optional[str] = None,
        status: str = "queued",
    ) -> str:
        """Добавить задачу генерации"""
        job_id = task_id or str(uuid.uuid4())
        data = await self._load_json(self.jobs_file)
        normalized_status = normalize_job_status(status)

        job = {
            "job_id": job_id,
            "user_id": user_id,
            "model_id": model_id,
            "model_name": model_name,
            "params": params,
            "price": price,
            "status": normalized_status,
            "task_id": task_id,  # external_task_id от KIE
            "external_task_id": task_id,  # alias для совместимости
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "finished_at": None,
            "result_urls": [],
            "error_message": None,
        }

        data[job_id] = job
        await self._save_json(self.jobs_file, data)
        return job_id

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        result_urls: Optional[List[str]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Обновить статус задачи"""
        data = await self._load_json(self.jobs_file)
        if job_id not in data:
            raise ValueError(f"Job {job_id} not found")

        job = data[job_id]
        normalized_status = normalize_job_status(status)
        job["status"] = normalized_status
        job["updated_at"] = datetime.now().isoformat()
        if is_terminal_status(normalized_status) and not job.get("finished_at"):
            job["finished_at"] = datetime.now().isoformat()

        if result_urls is not None:
            job["result_urls"] = result_urls
        if error_message is not None:
            job["error_message"] = error_message

        await self._save_json(self.jobs_file, data)

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Получить задачу по ID"""
        data = await self._load_json(self.jobs_file)
        return data.get(job_id)

    async def find_job_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Найти задачу по внешнему task_id или совпадающему job_id."""
        data = await self._load_json(self.jobs_file)
        for job in data.values():
            if job.get("task_id") == task_id or job.get("external_task_id") == task_id or job.get("job_id") == task_id:
                return job
        return None

    async def get_undelivered_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get jobs that are done but not delivered (for retry)."""
        data = await self._load_json(self.jobs_file)
        undelivered = [
            job for job in data.values()
            if job.get('status') == 'done'
            and job.get('result_urls')
            and not job.get('delivered')
        ]
        # Sort by created_at
        undelivered.sort(key=lambda j: j.get('created_at', ''))
        return undelivered[:limit]

    async def list_jobs(
        self, user_id: Optional[int] = None, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Получить список задач"""
        data = await self._load_json(self.jobs_file)
        jobs = list(data.values())

        if user_id is not None:
            jobs = [j for j in jobs if j.get("user_id") == user_id]
        if status is not None:
            jobs = [j for j in jobs if j.get("status") == status]

        # Сортируем по created_at (новые первыми)
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return jobs[:limit]
    
    # ==================== ORPHAN CALLBACKS (PHASE 4 - JSON STUB) ====================
    
    async def _save_orphan_callback(self, task_id: str, payload: Dict[str, Any]) -> None:
        """Save orphan callback (JSON storage stub - no-op for compatibility)"""
        # In JSON mode we don't have proper orphan tracking
        # This is a no-op for API compatibility
        logger.debug(f"[JSON_STORAGE] Orphan callback saved (no-op): task_id={task_id}")
        pass
    
    async def _get_unprocessed_orphans(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get unprocessed orphans (JSON storage stub)"""
        return []
    
    async def _mark_orphan_processed(self, task_id: str, error: Optional[str] = None) -> None:
        """Mark orphan processed (JSON storage stub)"""
        pass

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
        """Добавить генерацию в историю"""
        gen_id = operation_id or str(uuid.uuid4())
        data = await self._load_json(self.generations_history_file)
        user_key = str(user_id)

        if user_key not in data:
            data[user_key] = []

        generation = {
            "id": gen_id,
            "model_id": model_id,
            "model_name": model_name,
            "params": params,
            "result_urls": result_urls,
            "price": price,
            "timestamp": datetime.now().isoformat(),
        }

        data[user_key].append(generation)
        # Ограничиваем историю последними 100 генерациями
        data[user_key] = data[user_key][-100:]

        await self._save_json(self.generations_history_file, data)
        return gen_id

    async def get_user_generations_history(
        self, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Получить историю генераций"""
        data = await self._load_json(self.generations_history_file)
        user_key = str(user_id)
        history = data.get(user_key, [])
        return history[-limit:]

    # ==================== PAYMENTS ====================

    async def add_payment(
        self,
        user_id: int,
        amount: float,
        payment_method: str,
        payment_id: Optional[str] = None,
        screenshot_file_id: Optional[str] = None,
        status: str = "pending",
        idempotency_key: Optional[str] = None,
    ) -> str:
        """Добавить платеж с поддержкой idempotency"""
        pay_id = payment_id or str(uuid.uuid4())
        data = await self._load_json(self.payments_file)

        # Если передан idempotency_key, проверяем существующий платеж
        if idempotency_key:
            for existing_payment in data.values():
                if existing_payment.get("idempotency_key") == idempotency_key:
                    return existing_payment["payment_id"]

        payment = {
            "payment_id": pay_id,
            "user_id": user_id,
            "amount": amount,
            "payment_method": payment_method,
            "screenshot_file_id": screenshot_file_id,
            "status": status,
            "idempotency_key": idempotency_key,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "admin_id": None,
            "notes": None,
        }

        data[pay_id] = payment
        await self._save_json(self.payments_file, data)
        return pay_id

    async def mark_payment_status(
        self,
        payment_id: str,
        status: str,
        admin_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Обновить статус платежа с автоматическим rollback при cancel/failed"""
        data = await self._load_json(self.payments_file)
        if payment_id not in data:
            raise ValueError(f"Payment {payment_id} not found")

        payment = data[payment_id]
        old_status = payment.get("status")
        payment["status"] = status
        payment["updated_at"] = datetime.now().isoformat()

        if admin_id is not None:
            payment["admin_id"] = admin_id
        if notes is not None:
            payment["notes"] = notes

        # Если платеж одобрен, добавляем баланс
        if status == "approved" and old_status != "approved":
            await self.add_user_balance(payment["user_id"], payment["amount"])

        # Если платеж отменен или провалился, освобождаем резервы (если были)
        if status in ("cancelled", "failed", "rejected"):
            reserves_data = await self._load_json(self.data_dir / "balance_reserves.json")
            user_id = payment["user_id"]
            for reserve_id, reserve in list(reserves_data.items()):
                if reserve.get("user_id") == user_id and reserve.get("status") == "reserved":
                    reserve["status"] = "released"
                    reserve["updated_at"] = datetime.now().isoformat()
                    # Возвращаем баланс
                    await self.add_user_balance(user_id, reserve["amount"])
            await self._save_json(self.data_dir / "balance_reserves.json", reserves_data)

        await self._save_json(self.payments_file, data)

    async def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Получить платеж по ID"""
        data = await self._load_json(self.payments_file)
        return data.get(payment_id)

    async def is_transaction_processed(self, transaction_id: str) -> bool:
        """Проверить, обработана ли транзакция (идемпотентность webhook)."""
        data = await self._load_json(self.processed_transactions_file)
        return bool(data.get(transaction_id))

    async def mark_transaction_processed(
        self,
        transaction_id: str,
        user_id: Optional[int] = None,
        amount: Optional[float] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Отметить транзакцию как обработанную. Возвращает True если новая запись.
        False если транзакция уже была отмечена ранее.
        """
        data = await self._load_json(self.processed_transactions_file)
        if transaction_id in data:
            return False
        data[transaction_id] = {
            "user_id": user_id,
            "amount": amount,
            "meta": meta or {},
            "processed_at": datetime.now().isoformat(),
        }
        await self._save_json(self.processed_transactions_file, data)
        return True

    async def list_payments(
        self, user_id: Optional[int] = None, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Получить список платежей"""
        data = await self._load_json(self.payments_file)
        payments = list(data.values())

        if user_id is not None:
            payments = [p for p in payments if p.get("user_id") == user_id]
        if status is not None:
            payments = [p for p in payments if p.get("status") == status]

        payments.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return payments[:limit]

    # ==================== BALANCE RESERVES (IDEMPOTENCY) ====================

    async def reserve_balance_for_generation(
        self,
        user_id: int,
        amount: float,
        model_id: str,
        task_id: str,
        idempotency_key: Optional[str] = None,
    ) -> bool:
        """Резервирует баланс для генерации (idempotent)"""
        reserves_file = self.data_dir / "balance_reserves.json"
        reserves_data = await self._load_json(reserves_file)

        # Проверяем баланс
        balance = await self.get_user_balance(user_id)
        if balance < amount:
            return False  # Недостаточно средств

        # Генерируем idempotency_key если не передан
        if not idempotency_key:
            idempotency_key = f"{task_id}:{user_id}:{model_id}"

        # Проверяем существующий резерв по idempotency_key
        for reserve in reserves_data.values():
            if reserve.get("idempotency_key") == idempotency_key:
                return reserve.get("status") == "reserved"

        # Проверяем существующий резерв по task_id
        for reserve in reserves_data.values():
            if (
                reserve.get("task_id") == task_id
                and reserve.get("user_id") == user_id
                and reserve.get("model_id") == model_id
            ):
                return reserve.get("status") == "reserved"

        # Создаем новый резерв
        reserve_id = str(uuid.uuid4())
        reserve = {
            "id": reserve_id,
            "user_id": user_id,
            "task_id": task_id,
            "model_id": model_id,
            "amount": amount,
            "idempotency_key": idempotency_key,
            "status": "reserved",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        reserves_data[reserve_id] = reserve

        # Резервируем баланс (вычитаем из доступного)
        await self.subtract_user_balance(user_id, amount)

        await self._save_json(reserves_file, reserves_data)
        return True

    async def release_balance_reserve(self, user_id: int, task_id: str, model_id: str) -> bool:
        """Освобождает зарезервированный баланс (при отмене/ошибке)"""
        reserves_file = self.data_dir / "balance_reserves.json"
        reserves_data = await self._load_json(reserves_file)

        # Находим резерв
        for reserve_id, reserve in list(reserves_data.items()):
            if (
                reserve.get("task_id") == task_id
                and reserve.get("user_id") == user_id
                and reserve.get("model_id") == model_id
                and reserve.get("status") == "reserved"
            ):
                # Освобождаем баланс (возвращаем обратно)
                await self.add_user_balance(user_id, reserve["amount"])

                # Обновляем статус резерва
                reserve["status"] = "released"
                reserve["updated_at"] = datetime.now().isoformat()

                await self._save_json(reserves_file, reserves_data)
                return True

        return False  # Резерва не было

    async def commit_balance_reserve(self, user_id: int, task_id: str, model_id: str) -> bool:
        """Подтверждает резерв баланса (списывает при успешной генерации)"""
        reserves_file = self.data_dir / "balance_reserves.json"
        reserves_data = await self._load_json(reserves_file)

        # Находим резерв
        for reserve_id, reserve in list(reserves_data.items()):
            if (
                reserve.get("task_id") == task_id
                and reserve.get("user_id") == user_id
                and reserve.get("model_id") == model_id
                and reserve.get("status") == "reserved"
            ):
                # Обновляем статус резерва (баланс уже списан при резервировании)
                reserve["status"] = "committed"
                reserve["updated_at"] = datetime.now().isoformat()

                await self._save_json(reserves_file, reserves_data)
                return True

        return False  # Резерва не было

    # ==================== REFERRALS ====================

    async def set_referrer(self, user_id: int, referrer_id: int) -> None:
        """Установить реферера"""
        data = await self._load_json(self.referrals_file)
        data[str(user_id)] = referrer_id

        # Добавляем в список рефералов реферера
        if "referrals" not in data:
            data["referrals"] = {}
        if str(referrer_id) not in data["referrals"]:
            data["referrals"][str(referrer_id)] = []

        if user_id not in data["referrals"][str(referrer_id)]:
            data["referrals"][str(referrer_id)].append(user_id)

        await self._save_json(self.referrals_file, data)

    async def get_referrer(self, user_id: int) -> Optional[int]:
        """Получить ID реферера"""
        data = await self._load_json(self.referrals_file)
        referrer_id = data.get(str(user_id))
        return int(referrer_id) if referrer_id else None

    async def get_referrals(self, referrer_id: int) -> List[int]:
        """Получить список рефералов"""
        data = await self._load_json(self.referrals_file)
        if "referrals" not in data:
            return []
        return data["referrals"].get(str(referrer_id), [])

    async def add_referral_bonus(self, referrer_id: int, bonus_generations: int = 5) -> None:
        """Добавить бонусные генерации рефереру"""
        data = await self._load_json(self.free_generations_file)
        user_key = str(referrer_id)

        if user_key not in data:
            data[user_key] = {"date": datetime.now().strftime("%Y-%m-%d"), "count": 0, "bonus": 0}

        data[user_key]["bonus"] = data[user_key].get("bonus", 0) + bonus_generations
        await self._save_json(self.free_generations_file, data)

    # ==================== UTILITY ====================

    async def async_test_connection(self) -> bool:
        """Проверить подключение (async-friendly)"""
        return True  # JSON storage всегда доступен

    def test_connection(self) -> bool:
        """Проверить подключение"""
        try:
            return self.data_dir.exists() and self.data_dir.is_dir()
        except Exception:
            return False

    async def close(self) -> None:
        """Закрыть соединения (для JSON ничего не нужно)"""
        pass

"""
Free Model Manager - управление бесплатными моделями и лимитами.

Концепция:
- Бесплатные модели НЕ списывают баланс
- Используются для onboarding / demo / вовлечения
- Имеют лимиты (daily, hourly)
- Логируется каждое использование
- BATCH 48.42: Базовый лимит 5 генераций в час + 5 за каждого приглашенного друга
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


class FreeModelManager:
    """Manager for free models with usage limits and referral bonuses."""
    
    def __init__(self, db_service, referral_manager=None):
        """
        Initialize free model manager.
        
        Args:
            db_service: Database service (or None for NO DATABASE MODE)
            referral_manager: Optional referral manager for bonus limits
        """
        self.db_service = db_service
        self.referral_manager = referral_manager
    
    async def is_model_free(self, model_id: str) -> bool:
        """Check if model is free."""
        # BATCH 48.42: Support NO DATABASE MODE
        if self.db_service is None:
            # In NO DATABASE MODE, check if model is in known free models list
            # z-image is always free
            if model_id.lower() in ("z-image", "zimage", "z_image"):
                return True
            # Add other free models here if needed
            return False
        
        async with self.db_service.get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT enabled FROM free_models WHERE model_id = $1",
                model_id
            )
            return row is not None and row['enabled'] if row else False
    
    async def get_free_model_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get free model configuration."""
        # BATCH 48.42: Support NO DATABASE MODE
        if self.db_service is None:
            # In NO DATABASE MODE, return default config for known free models
            if model_id.lower() in ("z-image", "zimage", "z_image"):
                return {
                    "model_id": model_id,
                    "enabled": True,
                    "daily_limit": 50,  # High daily limit
                    "hourly_limit": 999,  # Will be overridden by referral_manager
                    "meta": {}
                }
            return None
        
        async with self.db_service.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT model_id, enabled, daily_limit, hourly_limit, meta
                FROM free_models
                WHERE model_id = $1 AND enabled = TRUE
                """,
                model_id
            )
            if not row:
                return None
            
            return {
                "model_id": row['model_id'],
                "enabled": row['enabled'],
                "daily_limit": row['daily_limit'],
                "hourly_limit": row['hourly_limit'],
                "meta": row['meta']
            }
    
    async def check_limits_and_reserve(self, user_id: int, model_id: str, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check limits AND atomically log usage in a single transaction.
        
        CRITICAL: This prevents race conditions where two concurrent requests
        both pass the limit check and then both log usage, exceeding the limit.
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "daily_used": int,
                "daily_limit": int,
                "hourly_used": int,
                "hourly_limit": int
            }
        """
        config = await self.get_free_model_config(model_id)
        
        if not config:
            return {
                "allowed": False,
                "reason": "not_free",
                "daily_used": 0,
                "daily_limit": 0,
                "hourly_used": 0,
                "hourly_limit": 0
            }
        
        # Count daily usage
        now = datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        daily_limit = config['daily_limit']
        # BATCH 48.42: Base hourly limit is 5, plus 5 per referral
        base_hourly_limit = 5
        if self.referral_manager:
            try:
                hourly_limit = await self.referral_manager.get_hourly_limit(user_id)
            except Exception as e:
                logger.warning(f"[FREE] Failed to get referral limit for user {user_id}: {e}, using base limit")
                hourly_limit = base_hourly_limit
        else:
            hourly_limit = base_hourly_limit
        
        # Override with config if explicitly set (for backward compatibility)
        if config.get('hourly_limit') and config['hourly_limit'] < 999:
            hourly_limit = config['hourly_limit']
        
        # BATCH 48.44: Support NO DATABASE MODE with FileStorage
        if self.db_service is None:
            from app.storage import get_storage
            storage = get_storage()
            
            # Get usage counts from FileStorage
            daily_count = await storage.get_daily_free_usage(user_id, model_id)
            hourly_count = await storage.get_hourly_free_usage(user_id, model_id)
            
            # Check limits BEFORE logging
            if daily_count >= daily_limit:
                return {
                    "allowed": False,
                    "reason": "daily_limit_exceeded",
                    "daily_used": daily_count,
                    "daily_limit": daily_limit,
                    "hourly_used": hourly_count,
                    "hourly_limit": hourly_limit
                }
            
            if hourly_count >= hourly_limit:
                return {
                    "allowed": False,
                    "reason": "hourly_limit_exceeded",
                    "daily_used": daily_count,
                    "daily_limit": daily_limit,
                    "hourly_used": hourly_count,
                    "hourly_limit": hourly_limit
                }
            
            # Limits OK - log usage (if job_id provided)
            if job_id:
                await storage.log_free_usage(user_id, model_id, job_id)
            
            return {
                "allowed": True,
                "reason": "ok",
                "daily_used": daily_count + (1 if job_id else 0),
                "daily_limit": daily_limit,
                "hourly_used": hourly_count + (1 if job_id else 0),
                "hourly_limit": hourly_limit
            }
        
        # CRITICAL: Use transaction to atomically check limits AND log usage
        async with self.db_service.transaction() as conn:
            # Daily count
            daily_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, day_start
            )
            
            # Hourly count
            hourly_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, hour_start
            )
            
            # Check limits BEFORE logging
            if daily_count >= daily_limit:
                return {
                    "allowed": False,
                    "reason": "daily_limit_exceeded",
                    "daily_used": daily_count,
                    "daily_limit": daily_limit,
                    "hourly_used": hourly_count,
                    "hourly_limit": hourly_limit
                }
            
            if hourly_count >= hourly_limit:
                return {
                    "allowed": False,
                    "reason": "hourly_limit_exceeded",
                    "daily_used": daily_count,
                    "daily_limit": daily_limit,
                    "hourly_used": hourly_count,
                    "hourly_limit": hourly_limit
                }
            
            # Limits OK - atomically log usage (if job_id provided)
            if job_id:
                await conn.execute(
                    """
                    INSERT INTO free_usage (user_id, model_id, job_id, created_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (user_id, model_id, job_id) DO NOTHING
                    """,
                    user_id, model_id, job_id
                )
        
        return {
            "allowed": True,
            "reason": "ok",
            "daily_used": daily_count + (1 if job_id else 0),  # Include the usage we just logged
            "daily_limit": daily_limit,
            "hourly_used": hourly_count + (1 if job_id else 0),
            "hourly_limit": hourly_limit
        }
    
    async def check_limits(self, user_id: int, model_id: str) -> Dict[str, Any]:
        """
        Check if user can use free model (read-only, no logging).
        
        CRITICAL: Uses transaction to prevent race conditions when checking limits.
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "daily_used": int,
                "daily_limit": int,
                "hourly_used": int,
                "hourly_limit": int
            }
        """
        config = await self.get_free_model_config(model_id)
        
        if not config:
            return {
                "allowed": False,
                "reason": "not_free",
                "daily_used": 0,
                "daily_limit": 0,
                "hourly_used": 0,
                "hourly_limit": 0
            }
        
        # Count daily usage
        now = datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        # BATCH 48.44: Support NO DATABASE MODE with FileStorage
        if self.db_service is None:
            from app.storage import get_storage
            storage = get_storage()
            
            # Get usage counts from FileStorage
            daily_count = await storage.get_daily_free_usage(user_id, model_id)
            hourly_count = await storage.get_hourly_free_usage(user_id, model_id)
            
            # Get limits
            daily_limit = config['daily_limit']
            base_hourly_limit = 5
            if self.referral_manager:
                try:
                    hourly_limit = await self.referral_manager.get_hourly_limit(user_id)
                except Exception as e:
                    logger.warning(f"[FREE] Failed to get referral limit for user {user_id}: {e}, using base limit")
                    hourly_limit = base_hourly_limit
            else:
                hourly_limit = base_hourly_limit
            
            # Override with config if explicitly set
            if config.get('hourly_limit') and config['hourly_limit'] < 999:
                hourly_limit = config['hourly_limit']
            
            # Check limits
            if daily_count >= daily_limit:
                return {
                    "allowed": False,
                    "reason": "daily_limit_exceeded",
                    "daily_used": daily_count,
                    "daily_limit": daily_limit,
                    "hourly_used": hourly_count,
                    "hourly_limit": hourly_limit
                }
            
            if hourly_count >= hourly_limit:
                return {
                    "allowed": False,
                    "reason": "hourly_limit_exceeded",
                    "daily_used": daily_count,
                    "daily_limit": daily_limit,
                    "hourly_used": hourly_count,
                    "hourly_limit": hourly_limit
                }
            
            return {
                "allowed": True,
                "reason": "ok",
                "daily_used": daily_count,
                "daily_limit": daily_limit,
                "hourly_used": hourly_count,
                "hourly_limit": hourly_limit
            }
        
        # Use transaction to prevent race conditions
        async with self.db_service.transaction() as conn:
            # Daily count
            daily_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, day_start
            )
            
            # Hourly count
            hourly_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, hour_start
            )
        
        daily_limit = config['daily_limit']
        # BATCH 48.42: Base hourly limit is 5, plus 5 per referral
        base_hourly_limit = 5
        if self.referral_manager:
            try:
                hourly_limit = await self.referral_manager.get_hourly_limit(user_id)
            except Exception as e:
                logger.warning(f"[FREE] Failed to get referral limit for user {user_id}: {e}, using base limit")
                hourly_limit = base_hourly_limit
        else:
            hourly_limit = base_hourly_limit
        
        # Override with config if explicitly set (for backward compatibility)
        if config.get('hourly_limit') and config['hourly_limit'] < 999:
            hourly_limit = config['hourly_limit']
        
        # Check limits
        if daily_count >= daily_limit:
            return {
                "allowed": False,
                "reason": "daily_limit_exceeded",
                "daily_used": daily_count,
                "daily_limit": daily_limit,
                "hourly_used": hourly_count,
                "hourly_limit": hourly_limit
            }
        
        if hourly_count >= hourly_limit:
            return {
                "allowed": False,
                "reason": "hourly_limit_exceeded",
                "daily_used": daily_count,
                "daily_limit": daily_limit,
                "hourly_used": hourly_count,
                "hourly_limit": hourly_limit
            }
        
        return {
            "allowed": True,
            "reason": "ok",
            "daily_used": daily_count,
            "daily_limit": daily_limit,
            "hourly_used": hourly_count,
            "hourly_limit": hourly_limit
        }
    
    async def log_usage(self, user_id: int, model_id: str, job_id: Optional[str] = None):
        """
        Log free model usage.
        
        CRITICAL: Uses ON CONFLICT to prevent duplicate logging (idempotency).
        BATCH 48.44: Supports NO DATABASE MODE with FileStorage.
        """
        # BATCH 48.44: Support NO DATABASE MODE with FileStorage
        if self.db_service is None:
            from app.storage import get_storage
            storage = get_storage()
            if hasattr(storage, 'log_free_usage'):
                await storage.log_free_usage(user_id, model_id, job_id)
                logger.info(f"Free usage logged (NO DB): user={user_id}, model={model_id}, job={job_id}")
            else:
                logger.warning(f"[FREE] Storage {type(storage).__name__} doesn't support log_free_usage")
            return
        
        async with self.db_service.transaction() as conn:
            # Use ON CONFLICT to prevent duplicates if job_id is provided
            if job_id:
                await conn.execute(
                    """
                    INSERT INTO free_usage (user_id, model_id, job_id, created_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (user_id, model_id, job_id) DO NOTHING
                    """,
                    user_id, model_id, job_id
                )
            else:
                # If no job_id, just insert (no unique constraint to check)
                await conn.execute(
                    """
                    INSERT INTO free_usage (user_id, model_id, job_id, created_at)
                    VALUES ($1, $2, $3, NOW())
                    """,
                    user_id, model_id, job_id
                )
        
        logger.info(f"Free usage logged: user={user_id}, model={model_id}, job={job_id}")
    
    async def delete_usage(self, user_id: int, model_id: str, job_id: str) -> None:
        """
        Delete a specific free usage record. Used when a free generation fails.
        BATCH 48.44: Allow deleting failed free usage.
        """
        # BATCH 48.44: Support NO DATABASE MODE
        if self.db_service is None:
            from app.storage import get_storage
            storage = get_storage()
            if hasattr(storage, 'delete_free_usage'):
                await storage.delete_free_usage(user_id, model_id, job_id)
                logger.info(f"Free usage deleted (NO DB): user={user_id}, model={model_id}, job={job_id}")
            else:
                logger.warning(f"[FREE] Storage {type(storage).__name__} doesn't support delete_free_usage")
            return
        
        async with self.db_service.transaction() as conn:
            await conn.execute(
                """
                DELETE FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND job_id = $3
                """,
                user_id, model_id, job_id
            )
        logger.info(f"Free usage deleted: user={user_id}, model={model_id}, job={job_id}")
    
    async def get_daily_usage(self, user_id: int, model_id: str) -> int:
        """Get daily usage count for a user and model."""
        from datetime import datetime, timezone, timedelta
        
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        async with self.db_service.get_connection() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, day_start
            )
        
        return count or 0
    
    async def get_hourly_usage(self, user_id: int, model_id: str) -> int:
        """Get hourly usage count for a user and model."""
        from datetime import datetime, timezone, timedelta
        
        hour_start = datetime.now(timezone.utc) - timedelta(hours=1)
        
        async with self.db_service.get_connection() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, hour_start
            )
        
        return count or 0
    async def get_all_free_models(self) -> List[Dict[str, Any]]:
        """Get all enabled free models."""
        async with self.db_service.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT model_id, daily_limit, hourly_limit, meta
                FROM free_models
                WHERE enabled = TRUE
                ORDER BY model_id
                """
            )
            
            return [
                {
                    "model_id": row['model_id'],
                    "daily_limit": row['daily_limit'],
                    "hourly_limit": row['hourly_limit'],
                    "meta": row['meta']
                }
                for row in rows
            ]
    
    async def add_free_model(
        self,
        model_id: str,
        daily_limit: int = 5,
        hourly_limit: int = 2,
        meta: Optional[Dict] = None
    ):
        """Add or update free model configuration."""
        async with self.db_service.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO free_models (model_id, enabled, daily_limit, hourly_limit, meta, updated_at)
                VALUES ($1, TRUE, $2, $3, $4, NOW())
                ON CONFLICT (model_id) DO UPDATE SET
                    enabled = TRUE,
                    daily_limit = EXCLUDED.daily_limit,
                    hourly_limit = EXCLUDED.hourly_limit,
                    meta = EXCLUDED.meta,
                    updated_at = NOW()
                """,
                model_id, daily_limit, hourly_limit, json.dumps(meta or {})
            )
        
        logger.info(f"Free model configured: {model_id} (daily={daily_limit}, hourly={hourly_limit})")
    
    async def remove_free_model(self, model_id: str):
        """Disable free model (soft delete)."""
        async with self.db_service.get_connection() as conn:
            await conn.execute(
                """
                UPDATE free_models
                SET enabled = FALSE, updated_at = NOW()
                WHERE model_id = $1
                """,
                model_id
            )
        
        logger.info(f"Free model disabled: {model_id}")
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user's free usage statistics."""
        now = datetime.utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        async with self.db_service.get_connection() as conn:
            # Total free uses today
            total_today = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND created_at >= $2
                """,
                user_id, day_start
            )
            
            # Total free uses all time
            total_all_time = await conn.fetchval(
                "SELECT COUNT(*) FROM free_usage WHERE user_id = $1",
                user_id
            )
            
            # By model
            by_model = await conn.fetch(
                """
                SELECT model_id, COUNT(*) as count
                FROM free_usage
                WHERE user_id = $1
                GROUP BY model_id
                ORDER BY count DESC
                """,
                user_id
            )
        
        return {
            "total_today": total_today,
            "total_all_time": total_all_time,
            "by_model": [
                {"model_id": row['model_id'], "count": row['count']}
                for row in by_model
            ]
        }


__all__ = ["FreeModelManager"]

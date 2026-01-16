"""
Analytics for admin panel.
"""
import logging
from decimal import Decimal
from typing import Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Analytics:
    """Analytics service for admin panel."""
    
    def __init__(self, db_service):
        """
        Initialize analytics service.
        
        Args:
            db_service: DatabaseService instance or None (fail-open)
        """
        self.db_service = db_service
    
    def _check_db_service(self) -> bool:
        """Check if db_service is available and has get_connection method."""
        if self.db_service is None:
            return False
        if not hasattr(self.db_service, 'get_connection'):
            return False
        return True
    
    async def get_top_models(self, limit: int = 10, period_days: int = 30) -> List[Dict[str, Any]]:
        """Get top models by usage."""
        if not self._check_db_service():
            logger.debug("[ANALYTICS] Database service unavailable (NO DATABASE MODE), returning empty list")
            return []
        
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        try:
            async with self.db_service.get_connection() as conn:
                rows = await conn.fetch(
                    """
                    SELECT 
                        model_id,
                        COUNT(*) as total_uses,
                        COUNT(*) FILTER (WHERE status = 'done') as success_count,
                        COUNT(*) FILTER (WHERE status = 'failed') as fail_count,
                        COALESCE(SUM(price_rub) FILTER (WHERE status = 'done'), 0) as revenue
                    FROM jobs
                    WHERE created_at >= $1
                    GROUP BY model_id
                    ORDER BY total_uses DESC
                    LIMIT $2
                    """,
                    cutoff, limit
                )
            
            return [
                {
                    "model_id": row['model_id'],
                    "total_uses": row['total_uses'],
                    "success_count": row['success_count'],
                    "fail_count": row['fail_count'],
                    "revenue": float(row['revenue']),
                    "success_rate": (row['success_count'] / row['total_uses'] * 100) if row['total_uses'] > 0 else 0
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"[ANALYTICS] Failed to get top models: {e}")
            return []
    
    async def get_free_to_paid_conversion(self) -> Dict[str, Any]:
        """
        Get free to paid conversion stats.
        
        Users who:
        1. Used free models
        2. Later used paid models
        """
        if not self._check_db_service():
            logger.debug("[ANALYTICS] Database service unavailable (NO DATABASE MODE), returning empty conversion stats")
            return {
                "total_free_users": 0,
                "converted_users": 0,
                "conversion_rate": 0.0
            }
        
        try:
            async with self.db_service.get_connection() as conn:
                # Total users who used free
                total_free_users = await conn.fetchval(
                    "SELECT COUNT(DISTINCT user_id) FROM free_usage"
                ) or 0
                
                # Users who also used paid
                converted_users = await conn.fetchval(
                    """
                    SELECT COUNT(DISTINCT fu.user_id)
                    FROM free_usage fu
                    WHERE EXISTS (
                        SELECT 1 FROM jobs j
                        WHERE j.user_id = fu.user_id
                        AND j.status = 'done'
                        AND j.price_rub > 0
                    )
                    """
                ) or 0
                
                conversion_rate = (converted_users / total_free_users * 100) if total_free_users > 0 else 0
            
            return {
                "total_free_users": total_free_users,
                "converted_users": converted_users,
                "conversion_rate": conversion_rate
            }
        except Exception as e:
            logger.warning(f"[ANALYTICS] Failed to get conversion stats: {e}")
            return {
                "total_free_users": 0,
                "converted_users": 0,
                "conversion_rate": 0.0
            }
    
    async def get_error_stats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get failed generation stats."""
        if not self._check_db_service():
            logger.debug("[ANALYTICS] Database service unavailable (NO DATABASE MODE), returning empty error stats")
            return []
        
        try:
            async with self.db_service.get_connection() as conn:
                rows = await conn.fetch(
                    """
                    SELECT 
                        model_id,
                        COUNT(*) as fail_count,
                        MAX(updated_at) as last_fail
                    FROM jobs
                    WHERE status = 'failed'
                    GROUP BY model_id
                    ORDER BY fail_count DESC
                    LIMIT $1
                    """,
                    limit
                )
            
            return [
                {
                    "model_id": row['model_id'],
                    "fail_count": row['fail_count'],
                    "last_fail": row['last_fail']
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"[ANALYTICS] Failed to get error stats: {e}")
            return []
    
    async def get_revenue_stats(self, period_days: int = 30) -> Dict[str, Any]:
        """Get revenue statistics."""
        if not self._check_db_service():
            logger.debug("[ANALYTICS] Database service unavailable (NO DATABASE MODE), returning empty revenue stats")
            return {
                "period_days": period_days,
                "total_revenue": 0.0,
                "total_topups": 0.0,
                "total_refunds": 0.0,
                "paying_users": 0,
                "avg_revenue_per_user": 0.0
            }
        
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        try:
            async with self.db_service.get_connection() as conn:
                # Total revenue
                total_revenue = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(price_rub), 0)
                    FROM jobs
                    WHERE status = 'done' AND created_at >= $1
                    """,
                    cutoff
                ) or Decimal("0.00")
                
                # Total topups
                total_topups = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(amount_rub), 0)
                    FROM ledger
                    WHERE kind = 'topup' AND created_at >= $1
                    """,
                    cutoff
                ) or Decimal("0.00")
                
                # Total refunds
                total_refunds = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(amount_rub), 0)
                    FROM ledger
                    WHERE kind = 'refund' AND created_at >= $1
                    """,
                    cutoff
                ) or Decimal("0.00")
                
                # Number of paying users
                paying_users = await conn.fetchval(
                    """
                    SELECT COUNT(DISTINCT user_id)
                    FROM jobs
                    WHERE status = 'done' AND price_rub > 0 AND created_at >= $1
                    """,
                    cutoff
                ) or 0
            
            return {
                "period_days": period_days,
                "total_revenue": float(total_revenue),
                "total_topups": float(total_topups),
                "total_refunds": float(total_refunds),
                "paying_users": paying_users,
                "avg_revenue_per_user": float(total_revenue / paying_users) if paying_users > 0 else 0
            }
        except Exception as e:
            logger.warning(f"[ANALYTICS] Failed to get revenue stats: {e}")
            return {
                "period_days": period_days,
                "total_revenue": 0.0,
                "total_topups": 0.0,
                "total_refunds": 0.0,
                "paying_users": 0,
                "avg_revenue_per_user": 0.0
            }
    
    async def get_user_activity(self, period_days: int = 7) -> Dict[str, Any]:
        """Get user activity stats."""
        if not self._check_db_service():
            logger.debug("[ANALYTICS] Database service unavailable (NO DATABASE MODE), returning empty activity stats")
            return {
                "period_days": period_days,
                "new_users": 0,
                "active_users": 0,
                "total_users": 0
            }
        
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        
        try:
            async with self.db_service.get_connection() as conn:
                # New users
                new_users = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE created_at >= $1",
                    cutoff
                ) or 0
                
                # Active users (made at least one job)
                active_users = await conn.fetchval(
                    """
                    SELECT COUNT(DISTINCT user_id)
                    FROM jobs
                    WHERE created_at >= $1
                    """,
                    cutoff
                ) or 0
                
                # Total users
                total_users = await conn.fetchval(
                    "SELECT COUNT(*) FROM users"
                ) or 0
            
            return {
                "period_days": period_days,
                "new_users": new_users,
                "active_users": active_users,
                "total_users": total_users
            }
        except Exception as e:
            logger.warning(f"[ANALYTICS] Failed to get user activity: {e}")
            return {
                "period_days": period_days,
                "new_users": 0,
                "active_users": 0,
                "total_users": 0
            }


__all__ = ["Analytics"]

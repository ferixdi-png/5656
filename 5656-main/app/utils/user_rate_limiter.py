"""
User Rate Limiter - prevent spam and abuse.

CRITICAL PROTECTION:
- Prevents users from spamming generations (draining balance instantly)
- Prevents abuse (100 gens/second → immediate bankruptcy)
- Protects KIE.ai API from being hammered

LIMITS:
- MAX 5 generations per minute per user
- MAX 20 generations per hour per user
- Cooldown: 10 seconds between paid generations

This is SEPARATE from free tier limits (which are in FreeModelManager).
"""
import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class UserRateLimit:
    """Per-user rate limit tracking."""
    user_id: int
    last_gen_time: float = 0.0
    minute_gens: list = field(default_factory=list)  # timestamps in last minute
    hour_gens: list = field(default_factory=list)    # timestamps in last hour


class UserRateLimiter:
    """Rate limiter for user generations (paid + free)."""
    
    # Limits (BATCH 42: Separate limits for free/paid)
    # Paid models
    MAX_GENS_PER_MINUTE = 5
    MAX_GENS_PER_HOUR = 20
    COOLDOWN_SECONDS = 10  # между платными генерациями
    
    # Free models (stricter to prevent abuse)
    MAX_FREE_GENS_PER_MINUTE = 3
    MAX_FREE_GENS_PER_HOUR = 10
    
    def __init__(self):
        self._user_limits: Dict[int, UserRateLimit] = {}
    
    def _get_user_limit(self, user_id: int) -> UserRateLimit:
        """Get or create user limit tracker."""
        if user_id not in self._user_limits:
            self._user_limits[user_id] = UserRateLimit(user_id=user_id)
        return self._user_limits[user_id]
    
    def _cleanup_old_timestamps(self, timestamps: list, window_seconds: float) -> list:
        """Remove timestamps older than window."""
        now = time.time()
        cutoff = now - window_seconds
        return [ts for ts in timestamps if ts > cutoff]
    
    def check_rate_limit(self, user_id: int, is_paid: bool = True) -> Dict[str, any]:
        """
        Check if user can generate.
        
        Args:
            user_id: Telegram user ID
            is_paid: True for paid models, False for free models
        
        Returns:
            {
                "allowed": bool,
                "reason": str,  # "ok", "cooldown", "minute_limit", "hour_limit"
                "wait_seconds": int,  # seconds to wait before next gen
                "minute_used": int,
                "hour_used": int
            }
        """
        now = time.time()
        user_limit = self._get_user_limit(user_id)
        
        # Cleanup old timestamps
        user_limit.minute_gens = self._cleanup_old_timestamps(user_limit.minute_gens, 60)
        user_limit.hour_gens = self._cleanup_old_timestamps(user_limit.hour_gens, 3600)
        
        minute_count = len(user_limit.minute_gens)
        hour_count = len(user_limit.hour_gens)
        
        # Check cooldown (only for paid)
        if is_paid and user_limit.last_gen_time > 0:
            time_since_last = now - user_limit.last_gen_time
            if time_since_last < self.COOLDOWN_SECONDS:
                wait_seconds = int(self.COOLDOWN_SECONDS - time_since_last) + 1
                logger.warning(f"User {user_id} rate limited: cooldown ({wait_seconds}s)")
                return {
                    "allowed": False,
                    "reason": "cooldown",
                    "wait_seconds": wait_seconds,
                    "minute_used": minute_count,
                    "hour_used": hour_count
                }
        
        # BATCH 42: Separate limits for free/paid models
        max_minute = self.MAX_FREE_GENS_PER_MINUTE if not is_paid else self.MAX_GENS_PER_MINUTE
        max_hour = self.MAX_FREE_GENS_PER_HOUR if not is_paid else self.MAX_GENS_PER_HOUR
        
        # Check minute limit
        if minute_count >= max_minute:
            # Calculate wait time until oldest gen expires
            oldest_ts = min(user_limit.minute_gens)
            wait_seconds = int(60 - (now - oldest_ts)) + 1
            logger.warning(f"User {user_id} rate limited: {minute_count}/min (is_paid={is_paid})")
            return {
                "allowed": False,
                "reason": "minute_limit",
                "wait_seconds": wait_seconds,
                "minute_used": minute_count,
                "hour_used": hour_count
            }
        
        # Check hour limit
        if hour_count >= max_hour:
            # Calculate wait time until oldest gen expires
            oldest_ts = min(user_limit.hour_gens)
            wait_seconds = int(3600 - (now - oldest_ts)) + 1
            logger.warning(f"User {user_id} rate limited: {hour_count}/hour (is_paid={is_paid})")
            return {
                "allowed": False,
                "reason": "hour_limit",
                "wait_seconds": wait_seconds,
                "minute_used": minute_count,
                "hour_used": hour_count
            }
        
        # All checks passed
        return {
            "allowed": True,
            "reason": "ok",
            "wait_seconds": 0,
            "minute_used": minute_count,
            "hour_used": hour_count
        }
    
    def record_generation(self, user_id: int, is_paid: bool = True):
        """Record a generation (call after successful gen)."""
        now = time.time()
        user_limit = self._get_user_limit(user_id)
        
        # Update last gen time (for cooldown)
        if is_paid:
            user_limit.last_gen_time = now
        
        # Add to minute/hour trackers
        user_limit.minute_gens.append(now)
        user_limit.hour_gens.append(now)
        
        logger.info(
            f"Rate limit recorded: user={user_id}, paid={is_paid}, "
            f"minute={len(user_limit.minute_gens)}/{self.MAX_GENS_PER_MINUTE}, "
            f"hour={len(user_limit.hour_gens)}/{self.MAX_GENS_PER_HOUR}"
        )
    
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """Get user rate limit stats."""
        user_limit = self._get_user_limit(user_id)
        
        # Cleanup old timestamps
        user_limit.minute_gens = self._cleanup_old_timestamps(user_limit.minute_gens, 60)
        user_limit.hour_gens = self._cleanup_old_timestamps(user_limit.hour_gens, 3600)
        
        return {
            "minute_used": len(user_limit.minute_gens),
            "minute_limit": self.MAX_GENS_PER_MINUTE,
            "hour_used": len(user_limit.hour_gens),
            "hour_limit": self.MAX_GENS_PER_HOUR,
            "cooldown_seconds": self.COOLDOWN_SECONDS
        }


# Global instance
_rate_limiter: Optional[UserRateLimiter] = None


def get_rate_limiter() -> UserRateLimiter:
    """Get or create global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = UserRateLimiter()
    return _rate_limiter

"""
Referral Manager - управление реферальной системой.

Концепция:
- Пользователь может пригласить друга по реферальной ссылке
- За каждого приглашенного друга получает +5 генераций в час
- Базовый лимит: 5 генераций в час
- Максимальный лимит: 5 + (количество рефералов * 5)
"""
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ReferralManager:
    """Manager for referral system."""
    
    def __init__(self, storage):
        """
        Initialize referral manager.
        
        Args:
            storage: Storage instance (FileStorage or PostgresStorage)
        """
        self.storage = storage
    
    async def get_referrer(self, user_id: int) -> Optional[int]:
        """
        Get referrer ID for user.
        
        Args:
            user_id: User ID
        
        Returns:
            Referrer ID or None
        """
        try:
            return await self.storage.get_referrer(user_id)
        except Exception as e:
            logger.warning(f"[REFERRAL] Failed to get referrer for user {user_id}: {e}")
            return None
    
    async def set_referrer(self, user_id: int, referrer_id: int) -> bool:
        """
        Set referrer for user (only if not already set).
        
        Args:
            user_id: User ID
            referrer_id: Referrer ID
        
        Returns:
            True if referrer was set, False if already set or error
        """
        try:
            # Check if user already has referrer
            existing = await self.get_referrer(user_id)
            if existing:
                logger.info(f"[REFERRAL] User {user_id} already has referrer {existing}")
                return False
            
            # Prevent self-referral
            if user_id == referrer_id:
                logger.warning(f"[REFERRAL] Self-referral attempt: user_id={user_id}")
                return False
            
            # Set referrer
            await self.storage.set_referrer(user_id, referrer_id)
            logger.info(f"[REFERRAL] Set referrer: user={user_id} referrer={referrer_id}")
            return True
        except Exception as e:
            logger.error(f"[REFERRAL] Failed to set referrer: {e}", exc_info=True)
            return False
    
    async def get_referrals_count(self, referrer_id: int) -> int:
        """
        Get count of referrals for referrer.
        
        Args:
            referrer_id: Referrer ID
        
        Returns:
            Number of referrals
        """
        try:
            referrals = await self.storage.get_referrals(referrer_id)
            return len(referrals) if referrals else 0
        except Exception as e:
            logger.warning(f"[REFERRAL] Failed to get referrals count for {referrer_id}: {e}")
            return 0
    
    async def get_hourly_limit(self, user_id: int) -> int:
        """
        Get hourly limit for user (base 5 + 5 per referral).
        
        Args:
            user_id: User ID
        
        Returns:
            Hourly limit (5 base + 5 per referral)
        """
        base_limit = 5
        referrals_count = await self.get_referrals_count(user_id)
        bonus_limit = referrals_count * 5
        total_limit = base_limit + bonus_limit
        
        logger.debug(f"[REFERRAL] User {user_id} limit: base={base_limit} + bonus={bonus_limit} (refs={referrals_count}) = {total_limit}")
        return total_limit
    
    async def get_referral_info(self, user_id: int) -> Dict[str, Any]:
        """
        Get referral information for user.
        
        Args:
            user_id: User ID
        
        Returns:
            Dict with referral info:
            {
                "referrer_id": Optional[int],
                "referrals_count": int,
                "base_limit": 5,
                "bonus_limit": int,
                "total_limit": int
            }
        """
        referrer_id = await self.get_referrer(user_id)
        referrals_count = await self.get_referrals_count(user_id)
        base_limit = 5
        bonus_limit = referrals_count * 5
        total_limit = base_limit + bonus_limit
        
        return {
            "referrer_id": referrer_id,
            "referrals_count": referrals_count,
            "base_limit": base_limit,
            "bonus_limit": bonus_limit,
            "total_limit": total_limit
        }
    
    def generate_referral_link(self, user_id: int, bot_username: str) -> str:
        """
        Generate referral link for user.
        
        Args:
            user_id: User ID
            bot_username: Bot username (without @)
        
        Returns:
            Referral link (t.me/bot_username?start=ref_USER_ID)
        """
        return f"https://t.me/{bot_username}?start=ref_{user_id}"


__all__ = ["ReferralManager"]


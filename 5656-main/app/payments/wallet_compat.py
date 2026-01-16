"""
Wallet Service Compatibility Layer for NO DATABASE MODE (Batch 48).

Provides same interface as PostgreSQL WalletService but uses FileStorage.
"""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

from app.storage.file_storage import get_file_storage

logger = logging.getLogger(__name__)


class WalletServiceCompat:
    """
    Compatibility layer для WalletService без PostgreSQL.
    
    Использует FileStorage вместо PostgreSQL.
    Предоставляет тот же интерфейс что и app.database.services.WalletService.
    """
    
    def __init__(self):
        self.storage = get_file_storage()
        logger.info("[WALLET_COMPAT] Initialized WalletServiceCompat (NO DATABASE MODE)")
    
    async def get_balance(self, user_id: int) -> Dict[str, Any]:
        """
        Get user balance.
        
        Returns:
            dict with 'balance_rub' key
        """
        try:
            balance = await self.storage.get_balance(user_id)
            return {"balance_rub": Decimal(str(balance))}
        except Exception as e:
            logger.error(f"[WALLET_COMPAT] Failed to get balance for user {user_id}: {e}")
            return {"balance_rub": Decimal("0.00")}
    
    async def topup(
        self, 
        user_id: int, 
        amount: Decimal, 
        ref: str, 
        meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Topup user balance.
        
        Args:
            user_id: User ID
            amount: Amount to add
            ref: Reference (for logging)
            meta: Metadata (for logging)
        
        Returns:
            True if successful
        """
        try:
            float_amount = float(amount)
            await self.storage.add_balance(user_id, float_amount)
            logger.info(f"[WALLET_COMPAT] Topup: user={user_id}, amount={float_amount}₽, ref={ref}")
            return True
        except Exception as e:
            logger.error(f"[WALLET_COMPAT] Failed to topup for user {user_id}: {e}")
            return False
    
    async def hold(
        self, 
        user_id: int, 
        amount: Decimal, 
        ref: str, 
        meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Hold (reserve) user balance.
        
        В NO DATABASE MODE - сразу списываем (без hold/commit механики).
        
        Args:
            user_id: User ID
            amount: Amount to hold
            ref: Reference (for logging)
            meta: Metadata (for logging)
        
        Returns:
            True if successful (sufficient balance)
        """
        try:
            float_amount = float(amount)
            
            # Check balance
            current_balance = await self.storage.get_balance(user_id)
            if current_balance < float_amount:
                logger.warning(f"[WALLET_COMPAT] Insufficient balance for hold: user={user_id}, required={float_amount}₽, available={current_balance}₽")
                return False
            
            # Subtract immediately (no hold/commit in FileStorage)
            success = await self.storage.subtract_balance(user_id, float_amount)
            if success:
                logger.info(f"[WALLET_COMPAT] Hold (immediate subtract): user={user_id}, amount={float_amount}₽, ref={ref}")
            return success
        except Exception as e:
            logger.error(f"[WALLET_COMPAT] Failed to hold for user {user_id}: {e}")
            return False
    
    async def charge(
        self, 
        user_id: int, 
        amount: Decimal, 
        ref: str, 
        meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Charge user balance (from held amount).
        
        В NO DATABASE MODE - hold уже вычел баланс, так что charge - no-op.
        
        Args:
            user_id: User ID
            amount: Amount to charge
            ref: Reference (for logging)
            meta: Metadata (for logging)
        
        Returns:
            True (always, since hold already charged)
        """
        logger.info(f"[WALLET_COMPAT] Charge (no-op, already charged in hold): user={user_id}, amount={amount}₽, ref={ref}")
        return True
    
    async def refund(
        self, 
        user_id: int, 
        amount: Decimal, 
        ref: str, 
        meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Refund user balance (return held amount).
        
        Args:
            user_id: User ID
            amount: Amount to refund
            ref: Reference (for logging)
            meta: Metadata (for logging)
        
        Returns:
            True if successful
        """
        try:
            float_amount = float(amount)
            await self.storage.add_balance(user_id, float_amount)
            logger.info(f"[WALLET_COMPAT] Refund: user={user_id}, amount={float_amount}₽, ref={ref}")
            return True
        except Exception as e:
            logger.error(f"[WALLET_COMPAT] Failed to refund for user {user_id}: {e}")
            return False
    
    async def release(
        self, 
        user_id: int, 
        amount: Decimal, 
        ref: str, 
        meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Release held amount (return to available balance).
        
        Alias for refund.
        """
        return await self.refund(user_id, amount, ref, meta)


# Global instance
_wallet_service_compat: Optional[WalletServiceCompat] = None


def get_wallet_service_compat() -> WalletServiceCompat:
    """Get global WalletServiceCompat instance."""
    global _wallet_service_compat
    if _wallet_service_compat is None:
        _wallet_service_compat = WalletServiceCompat()
    return _wallet_service_compat


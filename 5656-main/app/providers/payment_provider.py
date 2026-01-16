"""
Payment Provider - centralized abstraction for payment operations.

Guarantees:
- All payment calls go through this provider
- DRY_RUN mode is enforced here
- No accidental real payments in DRY_RUN mode
"""
import os
import logging
from typing import Dict, Any, Optional

from app.providers.base import BaseProvider, ProviderResult, ProviderStatus

logger = logging.getLogger(__name__)


class PaymentProvider(BaseProvider):
    """Provider for payment operations."""
    
    def __init__(self, dry_run: bool = False):
        super().__init__(dry_run)
        self._real_gateway = None
    
    def _get_real_gateway(self):
        """Get real payment gateway (lazy initialization)."""
        if self._real_gateway is None:
            from app.payments.integration import get_payment_gateway
            self._real_gateway = get_payment_gateway(force_mock=False)
        return self._real_gateway
    
    async def charge(
        self,
        user_id: int,
        amount: float,
        description: str,
        idempotency_key: Optional[str] = None
    ) -> ProviderResult:
        """
        Charge user balance.
        
        In DRY_RUN mode: returns mock success without real charge.
        In real mode: performs actual charge.
        """
        if self.dry_run:
            logger.info(
                f"[PAYMENT_PROVIDER] DRY_RUN: Mock charge | "
                f"User: {user_id} | Amount: {amount} | Description: {description}"
            )
            
            return ProviderResult(
                status=ProviderStatus.SUCCESS,
                data={
                    "charged": True,
                    "amount": amount,
                    "user_id": user_id,
                    "idempotency_key": idempotency_key,
                    "dry_run": True
                }
            )
        
        # Real mode: perform actual charge
        try:
            gateway = self._get_real_gateway()
            result = await gateway.charge(user_id, amount, description, idempotency_key)
            
            if result.get("success"):
                return ProviderResult(
                    status=ProviderStatus.SUCCESS,
                    data=result
                )
            else:
                return ProviderResult(
                    status=ProviderStatus.ERROR,
                    error=result.get("error", "Charge failed"),
                    error_code=result.get("error_code")
                )
        except Exception as e:
            logger.error(f"[PAYMENT_PROVIDER] Error charging: {e}", exc_info=True)
            return ProviderResult(
                status=ProviderStatus.ERROR,
                error=str(e),
                error_code="EXCEPTION"
            )
    
    async def refund(
        self,
        user_id: int,
        amount: float,
        reason: str,
        original_transaction_id: Optional[str] = None
    ) -> ProviderResult:
        """
        Refund user balance.
        
        In DRY_RUN mode: returns mock success without real refund.
        In real mode: performs actual refund.
        """
        if self.dry_run:
            logger.info(
                f"[PAYMENT_PROVIDER] DRY_RUN: Mock refund | "
                f"User: {user_id} | Amount: {amount} | Reason: {reason}"
            )
            
            return ProviderResult(
                status=ProviderStatus.SUCCESS,
                data={
                    "refunded": True,
                    "amount": amount,
                    "user_id": user_id,
                    "reason": reason,
                    "dry_run": True
                }
            )
        
        # Real mode: perform actual refund
        try:
            gateway = self._get_real_gateway()
            result = await gateway.refund(user_id, amount, reason, original_transaction_id)
            
            if result.get("success"):
                return ProviderResult(
                    status=ProviderStatus.SUCCESS,
                    data=result
                )
            else:
                return ProviderResult(
                    status=ProviderStatus.ERROR,
                    error=result.get("error", "Refund failed"),
                    error_code=result.get("error_code")
                )
        except Exception as e:
            logger.error(f"[PAYMENT_PROVIDER] Error refunding: {e}", exc_info=True)
            return ProviderResult(
                status=ProviderStatus.ERROR,
                error=str(e),
                error_code="EXCEPTION"
            )
    
    async def healthcheck(self) -> bool:
        """Check if payment provider is available."""
        if self.dry_run:
            return True  # Mock provider is always available
        
        try:
            gateway = self._get_real_gateway()
            return await gateway.healthcheck() if hasattr(gateway, "healthcheck") else True
        except Exception:
            return False


def get_payment_provider(force_dry_run: Optional[bool] = None) -> PaymentProvider:
    """
    Get payment provider instance (real or mock based on DRY_RUN).
    
    Args:
        force_dry_run: Override DRY_RUN env var (for testing)
    
    Returns:
        PaymentProvider instance
    """
    if force_dry_run is None:
        dry_run = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")
    else:
        dry_run = force_dry_run
    
    return PaymentProvider(dry_run=dry_run)


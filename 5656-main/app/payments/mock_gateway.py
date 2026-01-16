"""
Mock Payment Gateway for DRY_RUN mode.

Returns fake payment responses without making real API calls.
"""
import logging
from typing import Dict, Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MockPaymentGateway:
    """
    Mock payment gateway that returns fake responses.
    
    Used in DRY_RUN mode to prevent real payment API calls.
    """
    
    def __init__(self):
        logger.info("[MOCK_PAYMENT] MockPaymentGateway initialized (DRY_RUN mode)")
    
    async def create_invoice(
        self,
        amount: float,
        user_id: int,
        description: str = "Test payment"
    ) -> Dict[str, Any]:
        """
        Create fake invoice without real API call.
        
        Returns:
            Fake invoice response
        """
        invoice_id = f"mock_invoice_{uuid4().hex[:8]}"
        invoice_url = f"mock://payment/invoice/{invoice_id}"
        
        logger.info(
            f"[MOCK_PAYMENT] EXTERNAL_CALL_MOCKED | InvoiceID: {invoice_id} | "
            f"Amount: {amount} | Reason: DRY_RUN"
        )
        
        return {
            "invoice_id": invoice_id,
            "invoice_url": invoice_url,
            "amount": amount,
            "status": "pending",
            "paid": False
        }
    
    async def check_payment_status(
        self,
        invoice_id: str
    ) -> Dict[str, Any]:
        """
        Check fake payment status.
        
        Returns:
            Fake status response
        """
        logger.info(
            f"[MOCK_PAYMENT] EXTERNAL_CALL_MOCKED | InvoiceID: {invoice_id} | "
            f"Reason: DRY_RUN"
        )
        
        return {
            "invoice_id": invoice_id,
            "status": "pending",
            "paid": False
        }


def get_payment_gateway(force_mock: bool = False):
    """
    Get payment gateway (real or mock based on DRY_RUN).
    
    Args:
        force_mock: Force mock mode even if DRY_RUN is not set
        
    Returns:
        Real PaymentGateway or MockPaymentGateway
    """
    import os
    
    dry_run = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")
    
    if dry_run or force_mock:
        logger.info("[PAYMENT_GATEWAY] Using MockPaymentGateway (DRY_RUN mode)")
        return MockPaymentGateway()
    else:
        # Import real gateway if exists
        try:
            from app.payments.gateway import PaymentGateway
            logger.info("[PAYMENT_GATEWAY] Using real PaymentGateway")
            return PaymentGateway()
        except ImportError:
            logger.warning("[PAYMENT_GATEWAY] Real gateway not found, using mock")
            return MockPaymentGateway()


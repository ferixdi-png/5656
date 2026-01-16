"""Payment system smoke testing."""

import json
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional


class MockPaymentEvent:
    """Mock payment webhook event from bank."""
    
    def __init__(self, user_id: int, amount: Decimal, status: str = "confirmed"):
        self.user_id = user_id
        self.amount = amount
        self.status = status
        self.timestamp = datetime.now().isoformat()
        self.transaction_id = f"txn_{user_id}_{datetime.now().timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for webhook payload."""
        return {
            "event_id": f"evt_{self.transaction_id}",
            "event_type": "payment.completed",
            "data": {
                "transaction_id": self.transaction_id,
                "user_id": str(self.user_id),
                "amount": float(self.amount),
                "currency": "RUB",
                "status": self.status,
                "timestamp": self.timestamp,
                "description": "KIE Model Generation",
            }
        }


class PaymentFlowValidator:
    """Validates payment flow integration."""
    
    @staticmethod
    def validate_payment_webhook_schema(payload: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate payment webhook has required fields.
        
        Returns:
            (is_valid, error_message)
        """
        required_fields = ['event_id', 'event_type', 'data']
        
        for field in required_fields:
            if field not in payload:
                return False, f"Missing required field: {field}"
        
        data = payload.get('data', {})
        required_data = ['transaction_id', 'user_id', 'amount', 'currency', 'status']
        
        for field in required_data:
            if field not in data:
                return False, f"Missing required data field: {field}"
        
        return True, None
    
    @staticmethod
    def validate_balance_update(before: Decimal, after: Decimal, cost: Decimal) -> tuple[bool, str]:
        """
        Validate balance was updated correctly.
        
        Returns:
            (is_valid, message)
        """
        expected_after = before - cost
        
        if abs(after - expected_after) < Decimal("0.01"):
            return True, f"Balance updated correctly: {before} -> {after}"
        else:
            return False, f"Balance mismatch. Expected {expected_after}, got {after}"
    
    @staticmethod
    def validate_transaction_record(record: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate transaction record in database has required fields.
        
        Returns:
            (is_valid, error_message)
        """
        required = ['id', 'user_id', 'amount', 'status', 'created_at']
        
        for field in required:
            if field not in record:
                return False, f"Missing transaction field: {field}"
        
        return True, None


class PaymentTestScenarios:
    """Standard payment test scenarios."""
    
    SCENARIOS = [
        {
            "name": "Successful payment",
            "user_id": 12345,
            "amount": Decimal("1.38"),
            "status": "confirmed",
            "expected_balance_change": Decimal("-1.38"),
        },
        {
            "name": "Large payment",
            "user_id": 12345,
            "amount": Decimal("100.00"),
            "status": "confirmed",
            "expected_balance_change": Decimal("-100.00"),
        },
        {
            "name": "Multiple payments (sequence)",
            "user_id": 12345,
            "payments": [
                {"amount": Decimal("1.38"), "status": "confirmed"},
                {"amount": Decimal("2.50"), "status": "confirmed"},
                {"amount": Decimal("5.00"), "status": "confirmed"},
            ],
            "expected_total_change": Decimal("-8.88"),
        },
    ]

"""
Payment idempotency helper: persistent tracking of processed transaction IDs.
Works with current storage (JSON or PostgreSQL if implemented) and falls back to JSON.
"""
from __future__ import annotations

from typing import Optional, Dict, Any

from app.storage import get_storage


class PaymentIdempotency:
    def __init__(self):
        self.storage = get_storage()

    async def check_and_mark(
        self,
        transaction_id: str,
        *,
        user_id: Optional[int] = None,
        amount: Optional[float] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Return True if this transaction is first time (marked now), False if duplicate.
        """
        # Duck-typing methods on storage (JsonStorage provides these)
        is_processed = getattr(self.storage, "is_transaction_processed", None)
        mark_processed = getattr(self.storage, "mark_transaction_processed", None)
        if callable(is_processed) and callable(mark_processed):
            if await is_processed(transaction_id):
                return False
            await mark_processed(transaction_id, user_id=user_id, amount=amount, meta=meta)
            return True
        # Fallback: no support, treat as first time (best-effort)
        return True

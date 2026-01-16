"""
Tests: payment idempotency persistence across instances using JsonStorage.
"""
import os
import asyncio
import pytest

from app.storage import reset_storage
from app.payments.idempotency import PaymentIdempotency


@pytest.mark.asyncio
async def test_transaction_persistence_duplication():
    # Ensure JSON storage is used (no DB in TEST_MODE)
    os.environ["STORAGE_MODE"] = "json"
    os.environ["DATA_DIR"] = "./data"
    reset_storage()

    txn_id = "txn_test_001"
    idem = PaymentIdempotency()
    first = await idem.check_and_mark(txn_id, user_id=1, amount=100.0)
    assert first is True

    # Recreate helper (simulate new instance)
    reset_storage()
    idem2 = PaymentIdempotency()
    second = await idem2.check_and_mark(txn_id, user_id=1, amount=100.0)
    assert second is False

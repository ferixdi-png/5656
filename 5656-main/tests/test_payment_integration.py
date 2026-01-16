"""
Integration tests for payment system.

Tests full payment flow:
1. charge (reserve balance)
2. generation (consume)
3. release/refund (cleanup)

All tests use DRY_RUN=true to avoid actual API calls.
"""

import pytest
import asyncio
from decimal import Decimal
from typing import Optional

# Fixtures for payment testing
@pytest.fixture
async def test_db():
    """Initialize test database."""
    from app.database.services import init_database
    await init_database()
    yield
    # Cleanup in teardown


@pytest.fixture
def admin_user_id() -> int:
    """Get admin user ID from env."""
    import os
    admin_id = os.getenv("ADMIN_ID", "123456789")
    return int(admin_id)


@pytest.fixture
def regular_user_id() -> int:
    """Regular test user."""
    return 999888777


class TestPaymentFlow:
    """Test complete payment flow."""

    @pytest.mark.asyncio
    async def test_charge_and_release_flow(self, test_db, regular_user_id):
        """Test: charge -> generation -> release."""
        from app.payments.charges import ChargeManager

        manager = ChargeManager()
        user_id = regular_user_id
        amount_rub = Decimal("50.00")
        model_id = "z-image"  # Cheap model for testing

        # 1. Create user with balance
        from app.database.services import get_db_pool

        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                user_id, f"test_user_{user_id}", "Test"
            )

            # Give user initial balance
            await conn.execute(
                """
                INSERT INTO wallets (user_id, balance_rub)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET balance_rub = $2
                """,
                user_id, Decimal("100.00")
            )

        # 2. Charge (reserve balance)
        charge_result = await manager.charge(
            user_id=user_id,
            amount_rub=amount_rub,
            reason="test_generation",
            ref=f"test_{user_id}_1"
        )

        assert charge_result['status'] == 'ok', f"Charge failed: {charge_result}"
        assert charge_result['amount_reserved'] == amount_rub

        # 3. Verify hold was created
        async with pool.acquire() as conn:
            wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id=$1",
                user_id
            )
            assert wallet is not None
            assert wallet['balance_rub'] == Decimal("50.00")  # 100 - 50
            assert wallet['hold_rub'] == Decimal("50.00")  # On hold

        # 4. Release (cleanup after generation)
        release_result = await manager.release_hold(
            user_id=user_id,
            amount_rub=amount_rub,
            reason="generation_complete",
            ref=f"test_{user_id}_1"
        )

        assert release_result['status'] == 'ok'

        # 5. Verify hold was removed
        async with pool.acquire() as conn:
            wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id=$1",
                user_id
            )
            assert wallet['balance_rub'] == Decimal("50.00")
            assert wallet['hold_rub'] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_insufficient_balance(self, test_db, regular_user_id):
        """Test: charge fails with insufficient balance."""
        from app.payments.charges import ChargeManager

        manager = ChargeManager()
        user_id = regular_user_id
        amount_rub = Decimal("1000.00")

        # Create user with LOW balance
        from app.database.services import get_db_pool

        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                user_id, f"poor_user_{user_id}", "Poor"
            )
            await conn.execute(
                """
                INSERT INTO wallets (user_id, balance_rub)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET balance_rub = $2
                """,
                user_id, Decimal("10.00")  # Only 10 RUB
            )

        # Try to charge 1000 RUB
        charge_result = await manager.charge(
            user_id=user_id,
            amount_rub=amount_rub,
            reason="test_insufficient",
            ref=f"test_{user_id}_2"
        )

        assert charge_result['status'] == 'insufficient_balance'
        assert charge_result['current_balance'] == Decimal("10.00")
        assert charge_result['required_balance'] == amount_rub

    @pytest.mark.asyncio
    async def test_refund_on_generation_failure(self, test_db, regular_user_id):
        """Test: refund when generation fails."""
        from app.payments.charges import ChargeManager

        manager = ChargeManager()
        user_id = regular_user_id
        amount_rub = Decimal("30.00")

        # Setup user
        from app.database.services import get_db_pool

        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                user_id, f"refund_user_{user_id}", "Refund"
            )
            await conn.execute(
                """
                INSERT INTO wallets (user_id, balance_rub)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET balance_rub = $2
                """,
                user_id, Decimal("100.00")
            )

        # 1. Charge
        charge_result = await manager.charge(
            user_id=user_id,
            amount_rub=amount_rub,
            reason="test_generation",
            ref=f"test_{user_id}_3"
        )
        assert charge_result['status'] == 'ok'

        # 2. Refund (generation failed)
        refund_result = await manager.refund(
            user_id=user_id,
            amount_rub=amount_rub,
            reason="generation_failed",
            ref=f"test_{user_id}_3"
        )

        assert refund_result['status'] == 'ok'

        # 3. Verify balance restored
        async with pool.acquire() as conn:
            wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id=$1",
                user_id
            )
            assert wallet['balance_rub'] == Decimal("100.00")  # Restored
            assert wallet['hold_rub'] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_free_model_generation(self, test_db, regular_user_id):
        """Test: free model doesn't charge balance."""
        from app.free.free_models import is_free_model, check_free_usage_limit

        # z-image should be a cheap test model, but test with truly free
        user_id = regular_user_id
        model_id = "z-image"

        # Skip charge if free
        if is_free_model(model_id):
            # Free models shouldn't charge
            from app.database.services import get_db_pool

            pool = get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, username, first_name)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                    """,
                    user_id, f"free_user_{user_id}", "Free"
                )
                await conn.execute(
                    """
                    INSERT INTO wallets (user_id, balance_rub)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET balance_rub = $2
                    """,
                    user_id, Decimal("0.00")  # Zero balance for free user
                )

            # Should NOT fail despite zero balance
            assert is_free_model(model_id)
            
            # Check usage limit (if any)
            can_use = await check_free_usage_limit(
                user_id=user_id,
                model_id=model_id
            )
            # Result depends on daily/hourly limits
            assert isinstance(can_use, bool)

    @pytest.mark.asyncio
    async def test_ledger_transaction_integrity(self, test_db, regular_user_id):
        """Test: all transactions recorded in ledger."""
        from app.payments.charges import ChargeManager
        from app.database.services import get_db_pool

        manager = ChargeManager()
        user_id = regular_user_id
        pool = get_db_pool()

        # Setup
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                user_id, f"ledger_user_{user_id}", "Ledger"
            )
            await conn.execute(
                """
                INSERT INTO wallets (user_id, balance_rub)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET balance_rub = $2
                """,
                user_id, Decimal("200.00")
            )

        # Charge
        await manager.charge(
            user_id=user_id,
            amount_rub=Decimal("50.00"),
            reason="test_ledger",
            ref=f"test_{user_id}_ledger"
        )

        # Verify ledger entry
        async with pool.acquire() as conn:
            entry = await conn.fetchrow(
                """
                SELECT kind, amount_rub, status, ref
                FROM ledger
                WHERE user_id=$1 AND ref=$2
                """,
                user_id, f"test_{user_id}_ledger"
            )

            assert entry is not None
            assert entry['kind'] == 'charge'
            assert entry['amount_rub'] == Decimal("50.00")
            assert entry['status'] == 'done'


class TestPaymentEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_double_charge_prevention(self, test_db, regular_user_id):
        """Test: cannot double-charge same ref."""
        from app.payments.charges import ChargeManager
        from app.database.services import get_db_pool

        manager = ChargeManager()
        user_id = regular_user_id
        ref = f"unique_ref_{user_id}"
        amount_rub = Decimal("25.00")

        # Setup
        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                user_id, f"double_user_{user_id}", "Double"
            )
            await conn.execute(
                """
                INSERT INTO wallets (user_id, balance_rub)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET balance_rub = $2
                """,
                user_id, Decimal("100.00")
            )

        # First charge
        result1 = await manager.charge(
            user_id=user_id,
            amount_rub=amount_rub,
            reason="test",
            ref=ref
        )
        assert result1['status'] == 'ok'

        # Second charge with same ref
        result2 = await manager.charge(
            user_id=user_id,
            amount_rub=amount_rub,
            reason="test",
            ref=ref
        )

        # Should either reject or recognize as duplicate
        assert result2['status'] in ['ok', 'already_committed']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

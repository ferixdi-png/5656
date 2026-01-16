"""
Wallet idempotency tests for hold/charge/refund/release flows.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

import pytest


class _FakeConn:
    def __init__(self, wallets, ledger):
        self._wallets = wallets
        self._ledger = ledger

    async def fetchval(self, query, *args):
        if "FROM ledger" in query:
            ref = args[0]
            kind = None
            if "kind = 'topup'" in query:
                kind = "topup"
            elif "kind = 'hold'" in query:
                kind = "hold"
            elif "kind = 'charge'" in query:
                kind = "charge"
            elif "kind = 'refund'" in query:
                kind = "refund"
            elif "kind = 'release'" in query:
                kind = "release"
            for entry in self._ledger:
                if entry["ref"] == ref and entry["status"] == "done":
                    if kind is None or entry["kind"] == kind:
                        return entry["id"]
        return None

    async def fetchrow(self, query, *args):
        user_id = args[0]
        wallet = self._wallets.setdefault(user_id, {"balance_rub": Decimal("0.00"), "hold_rub": Decimal("0.00")})
        if "SELECT balance_rub, hold_rub" in query:
            return dict(wallet)
        if "SELECT balance_rub FROM wallets" in query:
            return {"balance_rub": wallet["balance_rub"]}
        if "SELECT hold_rub FROM wallets" in query:
            return {"hold_rub": wallet["hold_rub"]}
        return None

    async def execute(self, query, *args):
        if query.strip().startswith("INSERT INTO ledger"):
            user_id, amount_rub, ref, meta = args
            if "kind = 'topup'" in query:
                kind = "topup"
            elif "kind = 'hold'" in query:
                kind = "hold"
            elif "kind = 'charge'" in query:
                kind = "charge"
            elif "kind = 'refund'" in query:
                kind = "refund"
            elif "kind = 'release'" in query:
                kind = "release"
            else:
                kind = "unknown"
            self._ledger.append(
                {
                    "id": len(self._ledger) + 1,
                    "user_id": user_id,
                    "kind": kind,
                    "amount_rub": amount_rub,
                    "status": "done",
                    "ref": ref,
                    "meta": meta or {},
                }
            )
            return
        if "SET balance_rub = balance_rub + $2" in query:
            user_id, amount_rub = args
            wallet = self._wallets.setdefault(user_id, {"balance_rub": Decimal("0.00"), "hold_rub": Decimal("0.00")})
            wallet["balance_rub"] += amount_rub
            return
        if "SET balance_rub = balance_rub - $2" in query:
            user_id, amount_rub = args
            wallet = self._wallets.setdefault(user_id, {"balance_rub": Decimal("0.00"), "hold_rub": Decimal("0.00")})
            wallet["balance_rub"] -= amount_rub
            wallet["hold_rub"] += amount_rub
            return
        if "balance_rub = balance_rub + $2" in query and "hold_rub = hold_rub - $2" in query:
            user_id, amount_rub = args
            wallet = self._wallets.setdefault(user_id, {"balance_rub": Decimal("0.00"), "hold_rub": Decimal("0.00")})
            wallet["hold_rub"] -= amount_rub
            wallet["balance_rub"] += amount_rub
            return
        if "hold_rub = hold_rub - $2" in query:
            user_id, amount_rub = args
            wallet = self._wallets.setdefault(user_id, {"balance_rub": Decimal("0.00"), "hold_rub": Decimal("0.00")})
            wallet["hold_rub"] -= amount_rub
            return


class _FakeDB:
    def __init__(self):
        self.wallets = {}
        self.ledger = []

    @asynccontextmanager
    async def transaction(self):
        yield _FakeConn(self.wallets, self.ledger)


@pytest.mark.asyncio
async def test_wallet_hold_charge_release_idempotent():
    from app.database.services import WalletService

    db = _FakeDB()
    service = WalletService(db)
    user_id = 42
    db.wallets[user_id] = {"balance_rub": Decimal("100.00"), "hold_rub": Decimal("0.00")}

    hold_ref = "hold_job_1"
    assert await service.hold(user_id, Decimal("50.00"), ref=hold_ref) is True
    assert await service.hold(user_id, Decimal("50.00"), ref=hold_ref) is True
    balance = await service.get_balance(user_id)
    assert balance["balance_rub"] == Decimal("50.00")
    assert balance["hold_rub"] == Decimal("50.00")

    charge_ref = "charge_job_1"
    assert await service.charge(user_id, Decimal("50.00"), ref=charge_ref) is True
    assert await service.charge(user_id, Decimal("50.00"), ref=charge_ref) is True
    balance = await service.get_balance(user_id)
    assert balance["balance_rub"] == Decimal("50.00")
    assert balance["hold_rub"] == Decimal("0.00")

    hold_ref2 = "hold_job_2"
    assert await service.hold(user_id, Decimal("10.00"), ref=hold_ref2) is True
    release_ref = "release_job_2"
    assert await service.release(user_id, Decimal("10.00"), ref=release_ref) is True
    assert await service.release(user_id, Decimal("10.00"), ref=release_ref) is True
    balance = await service.get_balance(user_id)
    assert balance["balance_rub"] == Decimal("50.00")
    assert balance["hold_rub"] == Decimal("0.00")

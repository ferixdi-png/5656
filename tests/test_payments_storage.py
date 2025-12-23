import pytest

from app.payments.charges import ChargeManager


class DummyStorage:
    def __init__(self, status_map=None):
        self.status_map = status_map or {}

    async def get_charge_status(self, task_id: str):
        return self.status_map.get(task_id)

    async def save_pending_charge(self, charge_info):
        self.status_map[charge_info["task_id"]] = "pending"

    async def save_committed_charge(self, charge_info):
        self.status_map[charge_info["task_id"]] = "committed"

    async def save_released_charge(self, charge_info):
        self.status_map[charge_info["task_id"]] = "released"


@pytest.mark.asyncio
async def test_storage_idempotent_commit():
    storage = DummyStorage({"task_1": "committed"})
    manager = ChargeManager(storage=storage)
    result = await manager.commit_charge("task_1")
    assert result["status"] == "already_committed"

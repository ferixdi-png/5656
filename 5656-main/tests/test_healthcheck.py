"""
Тесты для healthcheck endpoint
"""

import asyncio
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from app.utils.healthcheck import health_handler, set_start_time
import json


class HealthCheckTestCase(AioHTTPTestCase):
    """Тесты для healthcheck endpoint"""

    async def get_application(self):
        """Создает тестовое приложение"""
        app = web.Application()
        app.router.add_get("/health", health_handler)
        app.router.add_get("/", health_handler)
        return app

    @unittest_run_loop
    async def test_health_endpoint_exists(self):
        """Тест: /health endpoint доступен"""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200

    @unittest_run_loop
    async def test_health_endpoint_json(self):
        """Тест: /health возвращает JSON"""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        assert resp.headers["Content-Type"] == "application/json"

        data = await resp.json()
        assert "status" in data
        assert data["status"] == "ok"

    @unittest_run_loop
    async def test_health_endpoint_fields(self):
        """Тест: /health содержит все необходимые поля"""
        set_start_time()
        await asyncio.sleep(0.1)  # Небольшая задержка для uptime

        resp = await self.client.request("GET", "/health")
        data = await resp.json()

        assert "status" in data
        assert "uptime" in data
        assert "storage" in data
        assert "kie_mode" in data

        assert isinstance(data["uptime"], int)
        assert data["uptime"] >= 0

    @unittest_run_loop
    async def test_root_endpoint_compatibility(self):
        """Тест: / endpoint также работает (совместимость)"""
        resp = await self.client.request("GET", "/")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "ok"

    @unittest_run_loop
    async def test_head_root_endpoint(self):
        """Тест: HEAD / возвращает 200 (Render healthcheck)."""
        resp = await self.client.request("HEAD", "/")
        assert resp.status == 200

    @unittest_run_loop
    async def test_head_root_endpoint(self):
        """Тест: HEAD / возвращает 200 (Render healthcheck)."""
        resp = await self.client.request("HEAD", "/")
        assert resp.status == 200


# Простой тест без aiohttp test utils
async def test_health_handler_direct():
    """Прямой тест health_handler"""
    from aiohttp.test_utils import make_mocked_request

    set_start_time()

    request = make_mocked_request("GET", "/health")
    response = await health_handler(request)

    assert response.status == 200
    assert response.content_type == "application/json"

    text = response.text
    data = json.loads(text)

    assert data["status"] == "ok"
    assert "uptime" in data
    assert "storage" in data
    assert "kie_mode" in data
    
    assert data['status'] == 'ok'
    assert 'uptime' in data
    assert 'storage' in data
    assert 'kie_mode' in data

"""
Healthcheck endpoint для Render
Легкий aiohttp endpoint без потоков
"""

import json
import time
from typing import Optional, Dict, List

from aiohttp import web
from telegram import Update

from app.utils.logging_config import get_logger
from app.utils.correlation import ensure_correlation_id, correlation_tag

logger = get_logger(__name__)

_health_server: Optional[web.Application] = None
_health_runner: Optional[web.AppRunner] = None
_start_time: Optional[float] = None

# Webhook resilience state (in-memory; single instance on Render)
_recent_update_ids: set[int] = set()
_rate_map: Dict[str, List[float]] = {}


def _get_client_ip(request: web.Request) -> str:
    # Prefer X-Forwarded-For, fallback to request.remote
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return ip or (request.remote or "unknown")


def _rate_limited(ip: str, now: float, limit: int = 5, window_s: float = 1.0) -> bool:
    hits = _rate_map.get(ip, [])
    # Drop old hits
    hits = [t for t in hits if now - t <= window_s]
    if len(hits) >= limit:
        _rate_map[ip] = hits
        return True
    hits.append(now)
    _rate_map[ip] = hits
    return False


def set_start_time():
    """Устанавливает время старта для расчета uptime"""
    global _start_time
    _start_time = time.time()


async def health_handler(request):
    """Обработчик healthcheck запросов"""
    import os
    from app.locking.single_instance import get_lock_debug_info
    from app.storage.migrations import check_migrations_status

    # Рассчитываем uptime
    uptime = 0
    if _start_time:
        uptime = int(time.time() - _start_time)

    # Определяем storage mode
    storage_mode = "unknown"
    try:
        from app.config import get_settings

        settings = get_settings()
        storage_mode = settings.get_storage_mode()
    except:
        pass

    # Определяем KIE mode
    kie_mode = "stub" if os.getenv("KIE_STUB") else "real"
    if not os.getenv("KIE_API_KEY"):
        kie_mode = "disabled"

    # Проверяем статус миграций
    migrations_ok = False
    migrations_count = 0
    try:
        migrations_ok, migrations_count = await check_migrations_status()
    except Exception as e:
        logger.debug(f"[HEALTH] Migrations check failed: {e}")

    # Формируем JSON ответ
    lock_debug = get_lock_debug_info()
    
    # Check background tasks health (best-effort, non-blocking)
    background_tasks_status = {}
    try:
        from app.utils.runtime_state import runtime_state
        # Track background task last run times (if available)
        background_tasks_status = {
            "fsm_cleanup_last_run": getattr(runtime_state, 'fsm_cleanup_last_run', None),
            "stale_job_cleanup_last_run": getattr(runtime_state, 'stale_job_cleanup_last_run', None),
            "stuck_payment_cleanup_last_run": getattr(runtime_state, 'stuck_payment_cleanup_last_run', None),
        }
    except Exception:
        pass  # Non-critical, don't fail health check
    
    response_data = {
        "status": "ok",
        "uptime": uptime,
        "storage": storage_mode,
        "kie_mode": kie_mode,
        "migrations_applied": migrations_ok,
        "migrations_count": migrations_count,
        "lock_state": lock_debug.get("state"),
        "lock_holder_pid": lock_debug.get("holder_pid"),
        "lock_idle_duration": lock_debug.get("idle_duration"),
        "lock_heartbeat_age": lock_debug.get("heartbeat_age"),
        "lock_takeover_event": lock_debug.get("takeover_event"),
        "background_tasks": background_tasks_status,
    }

    return web.Response(text=json.dumps(response_data), content_type="application/json", status=200)


async def webhook_handler(request, application, secret_path: str, secret_token: str):
    """Обработчик webhook апдейтов от Telegram."""
    if request.match_info.get("secret") != secret_path:
        return web.Response(status=404, text="not found")

    if secret_token:
        header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header_token != secret_token:
            return web.Response(status=403, text="forbidden")

    # Basic rate limiting per IP
    ip = _get_client_ip(request)
    now = time.time()
    if _rate_limited(ip, now):
        logger.warning("[WEBHOOK] %s Rate limit exceeded for ip=%s", correlation_tag(), ip)
        # Return 200 to avoid Telegram retry storms, but skip processing
        return web.Response(status=200, text="ok")

    try:
        payload = await request.json()
    except Exception:
        logger.warning("[WEBHOOK] %s Invalid JSON payload", correlation_tag())
        return web.Response(status=200, text="ok")

    try:
        update_id = (
            int(payload.get("update_id", 0))
            if isinstance(payload.get("update_id", 0), (int, str))
            else 0
        )
        if update_id and update_id in _recent_update_ids:
            logger.info("[WEBHOOK] %s Duplicate update_id=%s ignored", correlation_tag(), update_id)
            return web.Response(status=200, text="ok")

        ensure_correlation_id(str(update_id))
        update = Update.de_json(payload, application.bot)
        await application.process_update(update)
        if update_id:
            _recent_update_ids.add(update_id)
    except Exception as exc:
        logger.exception("[WEBHOOK] %s Failed to process update: %s", correlation_tag(), exc)
        return web.Response(status=200, text="ok")

    return web.Response(status=200, text="ok")


async def start_health_server(
    port: int = 8000,
    application=None,
    webhook_secret_path: str | None = None,
    webhook_secret_token: str | None = None,
):
    """Запустить healthcheck сервер в том же event loop"""
    global _health_server, _health_runner

    if port == 0:
        logger.info("[HEALTH] PORT not set, skipping healthcheck server")
        return False

    try:
        set_start_time()  # Устанавливаем время старта

        app = web.Application()
        app.router.add_get("/health", health_handler, allow_head=False)
        app.router.add_head("/health", health_handler)
        app.router.add_get("/", health_handler, allow_head=False)  # Для совместимости
        app.router.add_head("/", health_handler)
        if application and webhook_secret_path:
            app.router.add_post(
                "/webhook/{secret}",
                lambda request: webhook_handler(
                    request,
                    application=application,
                    secret_path=webhook_secret_path,
                    secret_token=webhook_secret_token or "",
                ),
            )

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        _health_server = app
        _health_runner = runner

        logger.info(f"[HEALTH] Healthcheck server started on port {port}")
        logger.info("[HEALTH] Endpoints: /health, /")
        if application and webhook_secret_path:
            logger.info("[HEALTH] Webhook endpoint enabled")

        return True
    except Exception as e:
        logger.warning(f"[HEALTH] Failed to start healthcheck server: {e}")
        logger.warning(
            "[HEALTH] Continuing without healthcheck (Render may mark service as unhealthy)"
        )
        return False


async def stop_health_server():
    """Остановить healthcheck сервер"""
    global _health_server, _health_runner

    if _health_runner:
        try:
            await _health_runner.cleanup()
            logger.info("[HEALTH] Healthcheck server stopped")
        except Exception as e:
            logger.warning(f"[HEALTH] Failed to stop healthcheck server: {e}")
        finally:
            _health_server = None
            _health_runner = None

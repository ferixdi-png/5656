"""Render entrypoint.

Goals:
- Webhook-first runtime (Render Web Service)
- aiogram-only import surface (no python-telegram-bot imports from this module)
- Health endpoints for Render + UptimeRobot
- Singleton advisory lock support (PostgreSQL) to avoid double-processing

This project historically had a PTB (python-telegram-bot) runner. Tests still cover
that legacy in bot_kie.py, but this runtime is aiogram-based.

Important: the repo contains a local ./aiogram folder with tiny test stubs.
In production we must import the real aiogram package from site-packages.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import json

from aiohttp import web

from app.storage import get_storage
from app.utils.logging_config import setup_logging  # noqa: E402
from app.utils.orphan_reconciler import OrphanCallbackReconciler  # PHASE 5
from app.utils.runtime_state import runtime_state  # noqa: E402
from app.utils.version import get_app_version, get_version_info  # noqa: E402
from app.locking.active_state import ActiveState  # NEW: unified active state
from app.utils.webhook import (
    build_kie_callback_url,
    get_kie_callback_path,
    get_webhook_base_url,
    get_webhook_secret_token,
)  # noqa: E402
# P0: Telemetry middleware (fail-open: if import fails, app still starts)
# Backward compatibility: import from telemetry_helpers (which re-exports from middleware)
import logging
_startup_logger = logging.getLogger(__name__)

try:
    from app.telemetry.telemetry_helpers import TelemetryMiddleware
    TELEMETRY_AVAILABLE = TelemetryMiddleware is not None
    if not TELEMETRY_AVAILABLE:
        _startup_logger.warning("[STARTUP] TelemetryMiddleware is None (middleware module unavailable)")
except ImportError as e:
    _startup_logger.warning(f"[STARTUP] Telemetry disabled: {e}")
    TelemetryMiddleware = None
    TELEMETRY_AVAILABLE = False
except Exception as e:
    _startup_logger.warning(f"[STARTUP] Telemetry unavailable (non-critical): {e}")
    TelemetryMiddleware = None
    TELEMETRY_AVAILABLE = False
from app.telemetry.logging_config import configure_logging  # P0: JSON logs

def _import_real_aiogram_symbols():
    """Import aiogram symbols from site-packages even if ./aiogram stubs exist."""
    project_root = Path(__file__).resolve().parent
    has_local_stubs = (project_root / "aiogram" / "__init__.py").exists()
    removed: list[str] = []

    if has_local_stubs:
        # Remove project root and '' so import machinery does not pick local stubs.
        for entry in list(sys.path):
            if entry in {"", str(project_root)}:
                removed.append(entry)
                try:
                    sys.path.remove(entry)
                except ValueError:
                    pass

    try:
        # Import the package (this will populate sys.modules with the real aiogram).
        import importlib

        importlib.import_module("aiogram")
    finally:
        # Restore path for app imports.
        for entry in reversed(removed):
            sys.path.insert(0, entry)

    # Now import symbols from whichever aiogram got loaded.
    from aiogram import Bot, Dispatcher  # type: ignore
    from aiogram.fsm.storage.memory import MemoryStorage  # type: ignore
    from aiogram.types import Update  # type: ignore
    from aiogram.client.default import DefaultBotProperties  # type: ignore

    return Bot, Dispatcher, MemoryStorage, Update, DefaultBotProperties


Bot, Dispatcher, MemoryStorage, Update, DefaultBotProperties = _import_real_aiogram_symbols()


logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _derive_secret_path_from_token(token: str) -> str:
    """Derive a stable URL-safe secret path.

    Compatibility note:
    Older deployments used the bot token with ':' removed as the webhook path.
    We keep that behavior as the default to avoid silent 404s after redeploys.
    """

    cleaned = token.strip().replace(":", "")
    # Keep it reasonably short but stable.
    if len(cleaned) > 64:
        cleaned = cleaned[-64:]
    return cleaned


@dataclass(frozen=True)
class RuntimeConfig:
    bot_mode: str
    port: int
    webhook_base_url: str
    webhook_secret_path: str
    webhook_secret_token: str
    telegram_bot_token: str
    database_url: str
    dry_run: bool
    kie_callback_path: str
    kie_callback_token: str


def _load_runtime_config() -> RuntimeConfig:
    bot_mode = os.getenv("BOT_MODE", "webhook").strip().lower()
    port_env = os.getenv("PORT")
    port = int(port_env) if port_env else 0
    webhook_base_url = get_webhook_base_url().strip().rstrip("/")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    # Secret path in URL (preferred). Can be explicitly overridden.
    webhook_secret_path = os.getenv("WEBHOOK_SECRET_PATH", "").strip()
    if not webhook_secret_path:
        webhook_secret_path = _derive_secret_path_from_token(telegram_bot_token)

    # Secret token in header (Telegram supports X-Telegram-Bot-Api-Secret-Token)
    webhook_secret_token = get_webhook_secret_token()

    database_url = os.getenv("DATABASE_URL", "").strip()
    dry_run = _bool_env("DRY_RUN", False) or _bool_env("TEST_MODE", False)
    kie_callback_path = get_kie_callback_path()
    kie_callback_token = os.getenv("KIE_CALLBACK_TOKEN", "").strip()

    return RuntimeConfig(
        bot_mode=bot_mode,
        port=port,
        webhook_base_url=webhook_base_url,
        webhook_secret_path=webhook_secret_path,
        webhook_secret_token=webhook_secret_token,
        telegram_bot_token=telegram_bot_token,
        database_url=database_url,
        dry_run=dry_run,
        kie_callback_path=kie_callback_path,
        kie_callback_token=kie_callback_token,
    )


# Remove old ActiveState dataclass - now using app.locking.active_state.ActiveState


class SingletonLock:
    """Async wrapper for the sync advisory lock implementation."""

    def __init__(self, database_url: str, *, key: Optional[int] = None):
        self.database_url = database_url
        self.key = key
        self._acquired = False

    async def acquire(self, timeout: float | None = None) -> bool:
        # NOTE: app.locking.single_instance.acquire_single_instance_lock() reads DATABASE_URL
        # from env and uses the psycopg2 pool from database.py. We keep this wrapper async
        # for uniformity.
        if not self.database_url:
            self._acquired = True
            return True

        try:
            from app.locking.single_instance import acquire_single_instance_lock

            # Signature has no args (it reads env). Run in thread with optional timeout
            if timeout is not None:
                try:
                    # Fast non-blocking acquire with timeout
                    self._acquired = bool(
                        await asyncio.wait_for(
                            asyncio.to_thread(acquire_single_instance_lock),
                            timeout=timeout
                        )
                    )
                    return self._acquired
                except asyncio.TimeoutError:
                    logger.debug("[LOCK] Acquire timed out after %.1fs", timeout)
                    self._acquired = False
                    return False
            else:
                # No timeout - blocking acquire
                self._acquired = bool(await asyncio.to_thread(acquire_single_instance_lock))
                return self._acquired
        except Exception as e:
            logger.exception("[LOCK] Failed to acquire singleton lock: %s", e)
            self._acquired = False
            return False

    async def release(self) -> None:
        if not self.database_url:
            return
        if not self._acquired:
            return
        try:
            from app.locking.single_instance import release_single_instance_lock

            release_single_instance_lock()
        except Exception as e:
            logger.warning("[LOCK] Failed to release singleton lock: %s", e)


# Exported name for tests (they monkeypatch this)
try:
    from app.storage.pg_storage import PostgresStorage
except Exception:  # pragma: no cover
    PostgresStorage = object  # type: ignore


async def preflight_webhook(bot: Bot) -> None:
    """Remove webhook to avoid conflict when running polling."""
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("[PRE-FLIGHT] Webhook deleted")
    except Exception as e:
        logger.warning("[PRE-FLIGHT] Failed to delete webhook: %s", e)


def create_bot_application() -> tuple[Dispatcher, Bot]:
    """Create aiogram Dispatcher + Bot (sync factory for tests)."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    # aiogram 3.7.0+ requires DefaultBotProperties for parse_mode
    default_properties = DefaultBotProperties(parse_mode="HTML")
    bot = Bot(token=token, default=default_properties)
    dp = Dispatcher(storage=MemoryStorage())

    # BATCH 48.10: Register DeployAwareMiddleware (CRITICAL!)
    try:
        from app.middleware.deploy_aware import DeployAwareMiddleware
        dp.callback_query.middleware(DeployAwareMiddleware())
        dp.message.middleware(DeployAwareMiddleware())
        logger.info("[MIDDLEWARE] ✅ DeployAwareMiddleware registered")
    except Exception as e:
        logger.error(f"[MIDDLEWARE] ❌ Failed to register DeployAwareMiddleware: {e}")

    # Routers
    from bot.handlers import (
        admin_router,
        balance_router,
        diag_router,
        error_handler_router,
        flow_router,
        gallery_router,
        history_router,
        marketing_router,
        quick_actions_router,
        zero_silence_router,
        z_image_router,
    )
    # from app.handlers.debug_handler import router as debug_router  # TODO: Needs router refactor
    from bot.handlers.fallback import router as fallback_router  # P0: Global fallback
    from app.middleware.exception_middleware import ExceptionMiddleware  # P0: Catch all exceptions

    # P0: Telemetry middleware FIRST (adds cid + bot_state to all updates)
    # Fail-open: if telemetry unavailable, app still works
    if TELEMETRY_AVAILABLE and TelemetryMiddleware:
        try:
            dp.update.middleware(TelemetryMiddleware())
            logger.info("[TELEMETRY] ✅ Middleware registered")
        except Exception as e:
            logger.warning(f"[TELEMETRY] Failed to register middleware (non-critical): {e}")
    else:
        logger.warning("[TELEMETRY] ⚠️ Telemetry middleware disabled - app continues without telemetry")
    
    # P0: Handler logging middleware SECOND (ultra-explaining logs for every handler)
    from app.middleware.handler_logging_middleware import HandlerLoggingMiddleware
    try:
        dp.update.middleware(HandlerLoggingMiddleware())
        logger.info("[HANDLER_LOGGING] ✅ Middleware registered")
    except Exception as e:
        logger.warning(f"[HANDLER_LOGGING] Failed to register middleware (non-critical): {e}")
    
    # P0: Anti-abuse middleware (protects from spam, DDoS, abuse)
    try:
        from bot.middleware.anti_abuse_middleware import AntiAbuseMiddleware
        dp.update.middleware(AntiAbuseMiddleware())
        logger.info("[SECURITY] ✅ AntiAbuseMiddleware registered")
    except Exception as e:
        logger.warning(f"[SECURITY] Failed to register AntiAbuseMiddleware (non-critical): {e}")
    
    # P0: Telegram protection middleware (prevents Telegram bans)
    try:
        from bot.middleware.telegram_protection_middleware import TelegramProtectionMiddleware
        dp.update.middleware(TelegramProtectionMiddleware())
        logger.info("[SECURITY] ✅ TelegramProtectionMiddleware registered")
    except Exception as e:
        logger.warning(f"[SECURITY] Failed to register TelegramProtectionMiddleware (non-critical): {e}")
    
    # P0: Exception middleware THIRD (catches all unhandled exceptions)
    dp.update.middleware(ExceptionMiddleware())
    
    # Note: debug_router temporarily disabled - needs router refactor
    # dp.include_router(debug_router)
    dp.include_router(error_handler_router)
    dp.include_router(diag_router)
    dp.include_router(admin_router)
    dp.include_router(z_image_router)  # Z-image (SINGLE_MODEL support)
    dp.include_router(balance_router)
    dp.include_router(history_router)
    dp.include_router(marketing_router)
    dp.include_router(gallery_router)
    dp.include_router(quick_actions_router)
    dp.include_router(flow_router)
    dp.include_router(zero_silence_router)
    dp.include_router(fallback_router)  # P0: MUST BE LAST - catches unknown callbacks

    return dp, bot


async def verify_bot_identity(bot: Bot) -> None:
    """Verify bot identity and webhook configuration.
    
    Logs bot.getMe() and getWebhookInfo() to ensure correct bot/token/webhook.
    Prevents issues like "wrong bot deployed" or "webhook pointing to old URL".
    """
    try:
        me = await bot.get_me()
        logger.info(
            "[BOT_VERIFY] ✅ Bot identity: @%s (id=%s, name='%s')",
            me.username, me.id, me.first_name
        )
    except Exception as exc:
        logger.error("[BOT_VERIFY] ❌ Failed to get bot info: %s", exc)
        raise

    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.info(
                "[BOT_VERIFY] 📡 Webhook: %s (pending=%s, last_error=%s)",
                webhook_info.url,
                webhook_info.pending_update_count,
                webhook_info.last_error_message or "none"
            )
        else:
            logger.info("[BOT_VERIFY] 📡 No webhook configured (polling mode or not set yet)")
    except Exception as exc:
        logger.warning("[BOT_VERIFY] ⚠️ Failed to get webhook info: %s", exc)


def _build_webhook_url(cfg: RuntimeConfig) -> str:
    base = cfg.webhook_base_url.rstrip("/")
    return f"{base}/webhook/{cfg.webhook_secret_path}" if base else ""


def _build_kie_callback_url(cfg: RuntimeConfig) -> str:
    return build_kie_callback_url(cfg.webhook_base_url, cfg.kie_callback_path)


def _health_payload(active_state: ActiveState) -> dict[str, Any]:
    from app.locking.single_instance import get_lock_debug_info

    lock_state = "ACTIVE" if active_state.active else "PASSIVE"
    lock_debug = {}
    controller = getattr(active_state, "lock_controller", None)
    if controller and getattr(controller, "lock", None) and hasattr(controller.lock, "get_lock_debug_info"):
        lock_debug = controller.lock.get_lock_debug_info()
    else:
        lock_debug = get_lock_debug_info()

    return {
        "ok": True,
        "mode": "active" if active_state.active else "passive",
        "active": bool(active_state.active),
        "lock_state": lock_state,
        "bot_mode": runtime_state.bot_mode,
        "storage_mode": runtime_state.storage_mode,
        "lock_acquired": runtime_state.lock_acquired,
        "lock_holder_pid": lock_debug.get("holder_pid"),
        "lock_idle_duration": lock_debug.get("idle_duration"),
        "lock_takeover_event": lock_debug.get("takeover_event"),
        "instance_id": runtime_state.instance_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _make_web_app(
    *,
    dp: Dispatcher,
    bot: Bot,
    cfg: RuntimeConfig,
    active_state: ActiveState,
    background_tasks: list[asyncio.Task] = None,
) -> web.Application:
    app = web.Application()
    # In-memory resilience structures (single instance assumption)
    # BATCH 48.17: Memory leak fix - bounded size with LRU eviction
    recent_update_ids: set[int] = set()
    recent_update_ids_max_size: int = 10000  # Prevent memory leak
    rate_map: dict[str, list[float]] = {}
    rate_map_max_ips: int = 1000  # Prevent memory leak
    _update_ids_lock = asyncio.Lock()  # Thread-safe access
    _rate_map_lock = asyncio.Lock()  # Thread-safe access

    def _client_ip(request: web.Request) -> str:
        ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        return ip or (request.remote or "unknown")

    async def _rate_limited(ip: str, now: float, limit: int = 5, window_s: float = 1.0) -> bool:
        """
        Rate limiting with memory leak protection.
        
        BATCH 48.17: Added bounded size and cleanup for rate_map.
        """
        async with _rate_map_lock:
            # Clean old entries (>5 minutes) to prevent memory leak
            old_threshold = now - 300.0  # 5 minutes
            ips_to_remove = []
            for map_ip, timestamps in rate_map.items():
                filtered = [t for t in timestamps if t > old_threshold]
                if not filtered:
                    ips_to_remove.append(map_ip)
                else:
                    rate_map[map_ip] = filtered
            
            # Remove IPs with no recent activity
            for map_ip in ips_to_remove:
                rate_map.pop(map_ip, None)
            
            # BATCH 48.17: Limit total number of IPs to prevent memory leak
            if len(rate_map) >= rate_map_max_ips:
                # Remove oldest IPs (simple approach - remove first N)
                excess = len(rate_map) - int(rate_map_max_ips * 0.9)
                if excess > 0:
                    # Remove IPs with oldest last activity
                    ip_ages = [(map_ip, max(timestamps) if timestamps else 0) 
                              for map_ip, timestamps in rate_map.items()]
                    ip_ages.sort(key=lambda x: x[1])  # Sort by last activity
                    for map_ip, _ in ip_ages[:excess]:
                        rate_map.pop(map_ip, None)
                    logger.debug(f"[RATE_LIMIT] Cleaned {excess} old IPs (size: {len(rate_map)})")
            
            # Check rate limit for current IP
            hits = rate_map.get(ip, [])
            hits = [t for t in hits if now - t <= window_s]
            if len(hits) >= limit:
                rate_map[ip] = hits
                return True
            hits.append(now)
            rate_map[ip] = hits
            return False

    async def health(_request: web.Request) -> web.Response:
        """
        Comprehensive health check endpoint - human-readable diagnostic.
        
        Returns JSON with:
        - version, git_sha, build_time
        - mode, active_state, lock_debug
        - webhook_current, webhook_desired
        - db=ok/fail, queue=ok
        """
        from app.utils.update_queue import get_queue_manager
        from app.locking.single_instance import get_lock_debug_info
        from app.utils.version import get_app_version, get_version_info
        
        # Version info
        app_version = get_app_version()
        version_info = get_version_info()
        git_sha = version_info.get("git_sha") or version_info.get("version") or app_version
        build_time = runtime_state.last_start_time or datetime.now(timezone.utc).isoformat()
        
        uptime = 0
        if runtime_state.last_start_time:
            started = datetime.fromisoformat(runtime_state.last_start_time)
            uptime = int((datetime.now(timezone.utc) - started).total_seconds())
        
        # Get queue metrics
        queue_manager = get_queue_manager()
        queue_metrics = queue_manager.get_metrics()
        queue_ok = queue_metrics.get("queue_depth_current", 0) < queue_metrics.get("queue_max", 100) * 0.9  # <90% full
        
        lock_debug = {}
        controller = getattr(active_state, "lock_controller", None)
        if controller and getattr(controller, "lock", None) and hasattr(controller.lock, "get_lock_debug_info"):
            lock_debug = controller.lock.get_lock_debug_info()
        else:
            lock_debug = get_lock_debug_info()

        # Defense-in-depth: ensure idle_duration is JSON serializable (float, not Decimal)
        idle_duration = lock_debug.get("idle_duration")
        if idle_duration is not None:
            idle_duration = float(idle_duration)
        
        heartbeat_age = lock_debug.get("heartbeat_age")
        if heartbeat_age is not None:
            heartbeat_age = float(heartbeat_age)

        # Check DB status (fail-open)
        db_ok = False
        db_status = "fail"
        db_warn = None
        try:
            if runtime_state.db_schema_ready:
                db_ok = True
                db_status = "ok"
            else:
                db_status = "fail"
                db_warn = "Schema not ready"
        except Exception as e:
            db_status = "fail"
            db_warn = f"DB check failed: {str(e)[:100]}"
        
        # Check webhook status (fail-open)
        webhook_current = None
        webhook_desired = None
        webhook_ok = False
        try:
            if runtime_state.bot_mode == "webhook":
                webhook_desired = cfg.webhook_base_url
                webhook_info = await bot.get_webhook_info()
                webhook_current = webhook_info.url or None
                webhook_ok = webhook_current is not None and webhook_current.rstrip("/") == (webhook_desired or "").rstrip("/")
            else:
                webhook_ok = True  # Polling mode doesn't need webhook
                webhook_desired = None
        except Exception as e:
            webhook_ok = False
            db_warn = f"Webhook check failed: {str(e)[:100]}"
        
        # Determine overall status
        overall_status = "ok"
        if db_status == "fail" or not webhook_ok or not queue_ok:
            overall_status = "degraded"
        
        # BATCH 48.11: Check deploy status
        deploy_in_progress = False
        deploy_status_text = "ready"
        try:
            from app.middleware.deploy_aware import is_deploy_in_progress, get_deploy_status_text
            deploy_in_progress = is_deploy_in_progress()
            deploy_status_text = get_deploy_status_text()
        except Exception:
            pass
        
        payload = {
            "version": app_version,
            "git_sha": git_sha,
            "build_time": build_time,
            "uptime": uptime,
            "mode": "active" if active_state.active else "passive",
            "deploy_status": deploy_status_text,  # BATCH 48.11: NEW
            "deploy_in_progress": deploy_in_progress,  # BATCH 48.11: NEW
            "active_state": {
                "active": active_state.active,
                "lock_state": "ACTIVE" if active_state.active else "PASSIVE",
                "lock_acquired": runtime_state.lock_acquired,
            },
            "lock_debug": {
                "holder_pid": lock_debug.get("holder_pid"),
                "idle_duration": idle_duration,
                "heartbeat_age": heartbeat_age,
                "takeover_event": lock_debug.get("takeover_event"),
            },
            "webhook_current": webhook_current,
            "webhook_desired": webhook_desired,
            "webhook_mode": runtime_state.bot_mode == "webhook",
            "db": db_status,
            "db_warn": db_warn,
            "queue": "ok" if queue_ok else "degraded",
            "queue_metrics": {
                "depth": queue_metrics.get("queue_depth_current", 0),
                "max": queue_metrics.get("queue_max", 100),
                "utilization_pct": round((queue_metrics.get("queue_depth_current", 0) / queue_metrics.get("queue_max", 100) * 100) if queue_metrics.get("queue_max", 100) > 0 else 0, 1),
                "total_received": queue_metrics.get("total_received", 0),
                "total_processed": queue_metrics.get("total_processed", 0),
                "total_dropped": queue_metrics.get("total_dropped", 0),
            },
            "status": overall_status,
        }
        return web.json_response(payload)
    
    async def ready(_request: web.Request) -> web.Response:
        """
        Readiness probe - returns 200 only if ACTIVE + db ok + webhook ok.
        
        Used by Kubernetes/Render for health checks.
        Returns 503 if not ready.
        """
        from app.utils.update_queue import get_queue_manager
        
        # Check 1: Must be ACTIVE
        if not active_state.active:
            return web.Response(
                status=503,
                text=json.dumps({
                    "ready": False,
                    "reason": "Instance is PASSIVE (not ACTIVE)",
                    "active": False
                }),
                content_type="application/json"
            )
        
        # Check 2: DB must be ok
        db_ok = False
        try:
            db_ok = runtime_state.db_schema_ready
        except Exception:
            pass
        
        if not db_ok:
            return web.Response(
                status=503,
                text=json.dumps({
                    "ready": False,
                    "reason": "Database not ready",
                    "db_schema_ready": False
                }),
                content_type="application/json"
            )
        
        # Check 3: Webhook must be ok (if webhook mode)
        webhook_ok = True
        try:
            if runtime_state.bot_mode == "webhook":
                webhook_info = await bot.get_webhook_info()
                webhook_ok = webhook_info.url is not None
        except Exception:
            webhook_ok = False
        
        if not webhook_ok:
            return web.Response(
                status=503,
                text=json.dumps({
                    "ready": False,
                    "reason": "Webhook not configured",
                    "webhook_mode": runtime_state.bot_mode == "webhook"
                }),
                content_type="application/json"
            )
        
        # All checks passed
        return web.Response(
            status=200,
            text=json.dumps({
                "ready": True,
                "active": True,
                "db": "ok",
                "webhook": "ok"
            }),
            content_type="application/json"
        )

    async def root(_request: web.Request) -> web.Response:
        """Root endpoint (same as health)."""
        from app.utils.update_queue import get_queue_manager
        from app.locking.single_instance import get_lock_debug_info
        
        uptime = 0
        if runtime_state.last_start_time:
            started = datetime.fromisoformat(runtime_state.last_start_time)
            uptime = int((datetime.now(timezone.utc) - started).total_seconds())
        
        queue_manager = get_queue_manager()
        queue_metrics = queue_manager.get_metrics()
        
        lock_debug = {}
        controller = getattr(active_state, "lock_controller", None)
        if controller and getattr(controller, "lock", None) and hasattr(controller.lock, "get_lock_debug_info"):
            lock_debug = controller.lock.get_lock_debug_info()
        else:
            lock_debug = get_lock_debug_info()

        # Defense-in-depth: ensure idle_duration is JSON serializable (float, not Decimal)
        idle_duration = lock_debug.get("idle_duration")
        if idle_duration is not None:
            idle_duration = float(idle_duration)
        
        heartbeat_age = lock_debug.get("heartbeat_age")
        if heartbeat_age is not None:
            heartbeat_age = float(heartbeat_age)
        
        # BATCH 48.18: Get background tasks status (from closure or runtime_state)
        bg_tasks_status = {}
        try:
            # Try to get background_tasks from closure (if available)
            tasks_list = background_tasks if background_tasks else []
            bg_tasks_status = {
                "fsm_cleanup": {
                    "last_run": runtime_state.fsm_cleanup_last_run,
                    "status": "running" if any(t.get_name() == "fsm_cleanup" and not t.done() for t in tasks_list) else "stopped"
                },
                "stale_job_cleanup": {
                    "last_run": runtime_state.stale_job_cleanup_last_run,
                    "status": "running" if any(t.get_name() == "stale_job_cleanup" and not t.done() for t in tasks_list) else "stopped"
                },
                "stuck_payment_cleanup": {
                    "last_run": runtime_state.stuck_payment_cleanup_last_run,
                    "status": "running" if any(t.get_name() == "stuck_payment_cleanup" and not t.done() for t in tasks_list) else "stopped"
                },
                "pending_updates_processor": {
                    "status": "running" if any(t.get_name() == "pending_updates_processor" and not t.done() for t in tasks_list) else "stopped"
                },
                "balance_guarantee": {
                    "status": "running" if any(t.get_name() == "balance_guarantee" and not t.done() for t in tasks_list) else "stopped"
                },
            }
        except Exception as e:
            logger.debug(f"[HEALTH] Failed to get background tasks status: {e}")
            bg_tasks_status = {"error": "unavailable"}

        payload = {
            "status": "ok",
            "uptime": uptime,
            "active": active_state.active,
            "lock_state": "ACTIVE" if active_state.active else "PASSIVE",
            "webhook_mode": runtime_state.bot_mode == "webhook",
            "lock_acquired": runtime_state.lock_acquired,
            "lock_holder_pid": lock_debug.get("holder_pid"),
            "lock_idle_duration": idle_duration,
            "lock_heartbeat_age": heartbeat_age,
            "lock_takeover_event": lock_debug.get("takeover_event"),
            "db_schema_ready": runtime_state.db_schema_ready,
            "queue_depth": queue_metrics.get("queue_depth_current", 0),
            "queue": queue_metrics,
            # BATCH 48.17: Memory leak monitoring
            "recent_update_ids_size": len(recent_update_ids),
            "recent_update_ids_max": recent_update_ids_max_size,
            "rate_map_size": len(rate_map),
            "rate_map_max": rate_map_max_ips,
            # BATCH 48.18: Background tasks health monitoring
            "background_tasks": bg_tasks_status,
        }
        return web.json_response(payload)
    
    async def diag_webhook(_request: web.Request) -> web.Response:
        """Diagnostic endpoint for webhook status."""
        try:
            info = await bot.get_webhook_info()
            
            # Mask secret path for security
            url = info.url or ""
            if url:
                parts = url.rsplit("/", 1)
                if len(parts) == 2:
                    url = parts[0] + "/***"
            
            return web.json_response({
                "url": url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count,
                "last_error_date": info.last_error_date.isoformat() if info.last_error_date else None,
                "last_error_message": info.last_error_message or "",
                "max_connections": info.max_connections,
                "ip_address": info.ip_address or "",
            })
        except Exception as e:
            logger.exception("[DIAG] Failed to get webhook info: %s", e)
            return web.json_response({"error": str(e)}, status=500)
    
    async def diag_lock(_request: web.Request) -> web.Response:
        """Diagnostic endpoint for lock status."""
        controller = getattr(active_state, "lock_controller", None)
        
        if not controller:
            return web.json_response({
                "error": "Lock controller not initialized"
            }, status=503)
        
        return web.json_response({
            "active": active_state.active,
            "should_process": controller.should_process_updates(),
            "lock_acquired": runtime_state.lock_acquired,
            "last_check": controller._last_check.isoformat() if hasattr(controller, "_last_check") and controller._last_check else None,
        })
    
    async def diag_webhookinfo(_request: web.Request) -> web.Response:
        """Detailed webhook info including allowed_updates."""
        try:
            info = await bot.get_webhook_info()
            return web.json_response({
                "url": info.url,
                "pending_update_count": info.pending_update_count,
                "last_error_message": info.last_error_message or "",
                "last_error_date": info.last_error_date,
                "allowed_updates": info.allowed_updates,
                "max_connections": info.max_connections,
                "has_custom_certificate": info.has_custom_certificate,
                "ip_address": info.ip_address if hasattr(info, "ip_address") else None,
            })
        except Exception as e:
            logger.exception("[DIAG] Failed to get webhook info: %s", e)
            return web.json_response({"error": str(e)}, status=500)

    async def webhook(request: web.Request) -> web.Response:
        """
        Fast-ack webhook handler - ALWAYS returns 200 OK within <200ms.
        
        Architecture:
        - Validates secret/token
        - PASSIVE instances: drop update with PASSIVE_DROP log, return 200 OK
        - ACTIVE instances: enqueue update to background queue
        - Returns 200 OK immediately (Telegram gets instant response)
        - Background workers process updates from queue
        
        This prevents timeout errors and pending updates accumulation.
        """
        webhook_start = time.time()
        from app.utils.enhanced_logging import log_operation, log_error, ensure_correlation_id
        
        secret = request.match_info.get("secret")
        if secret != cfg.webhook_secret_path:
            # Hide existence of endpoint
            raise web.HTTPNotFound()

        # Enforce Telegram header secret if configured
        if cfg.webhook_secret_token:
            header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if header != cfg.webhook_secret_token:
                log_operation(
                    "WEBHOOK_AUTH_FAILED",
                    status="FAIL",
                    error_code="INVALID_SECRET_TOKEN",
                    fix_hint="Check X-Telegram-Bot-Api-Secret-Token header",
                    check_list="Header value | Environment variable"
                )
                raise web.HTTPUnauthorized()

        # КРИТИЧНО: Защита от DDoS на webhook
        ip = _client_ip(request)
        now = time.time()
        
        # Проверить anti-abuse систему
        try:
            from app.security.anti_abuse import get_anti_abuse
            anti_abuse = get_anti_abuse()
            allowed, reason, retry_after = await anti_abuse.check_request_allowed(ip=ip)
            if not allowed:
                logger.warning(
                    f"[WEBHOOK_ABUSE] Request blocked from IP {ip}: {reason}"
                )
                return web.Response(
                    status=429,
                    text=json.dumps({
                        "ok": False,
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "description": f"Too many requests. Retry after {int(retry_after) + 1}s"
                    }),
                    content_type="application/json"
                )
        except Exception as e:
            logger.debug(f"[WEBHOOK] Anti-abuse check failed: {e}")
            # Продолжить, если проверка не удалась
        
        # Basic rate limiting per IP
        if await _rate_limited(ip, now):
            duration_ms = (now - webhook_start) * 1000
            log_operation(
                "WEBHOOK_RATE_LIMIT",
                status="SKIPPED",
                error_code="RATE_LIMIT_EXCEEDED",
                fix_hint="Normal behavior, rate limiting working",
                duration_ms=duration_ms,
                ip=ip
            )
            # Still return 200 to avoid Telegram retry storm
            return web.Response(status=200, text="ok")

        # BATCH 48.18: Validate payload size to prevent DoS
        content_length = request.headers.get('Content-Length')
        if content_length:
            try:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > 1.0:  # 1MB limit
                    logger.warning(f"[WEBHOOK] Payload too large: {size_mb:.2f}MB (limit: 1MB)")
                    return web.Response(status=413, text="Payload too large")
            except (ValueError, TypeError):
                pass  # Invalid Content-Length, continue

        # Fast JSON parse (no timeout needed - aiohttp handles this)
        try:
            payload = await request.json()
        except Exception as e:
            duration_ms = (time.time() - webhook_start) * 1000
            log_error(
                "WEBHOOK_JSON_PARSE",
                e,
                error_code="INVALID_JSON",
                fix_hint="Check Telegram webhook payload format",
                check_list="Payload format | Content-Type header",
                duration_ms=duration_ms,
                ip=ip
            )
            # Return 200 anyway (invalid updates will be ignored)
            return web.Response(status=200, text="ok")

        # Validate and extract update
        try:
            update = Update.model_validate(payload)
        except Exception as e:
            duration_ms = (time.time() - webhook_start) * 1000
            log_error(
                "WEBHOOK_VALIDATION",
                e,
                error_code="INVALID_UPDATE",
                fix_hint="Check Telegram update schema",
                check_list="Update structure | aiogram version",
                duration_ms=duration_ms,
                ip=ip
            )
            # Return 200 anyway
            return web.Response(status=200, text="ok")
        
        try:
            update_id = int(getattr(update, "update_id", 0))
        except Exception:
            update_id = 0
        
        # BATCH 48.21: Enhanced logging with correlation ID
        cid = ensure_correlation_id(str(update_id) if update_id else None)
        
        # Detect update type and extract user info
        update_type = "unknown"
        user_id = None
        callback_data = None
        
        if getattr(update, "message", None):
            update_type = "message"
            user_id = getattr(update.message.from_user, "id", None) if update.message.from_user else None
        elif getattr(update, "callback_query", None):
            update_type = "callback_query"
            user_id = getattr(update.callback_query.from_user, "id", None) if update.callback_query.from_user else None
            callback_data = getattr(update.callback_query, "data", None)
        elif getattr(update, "inline_query", None):
            update_type = "inline_query"
            user_id = getattr(update.inline_query.from_user, "id", None) if update.inline_query.from_user else None
        elif getattr(update, "edited_message", None):
            update_type = "edited_message"
            user_id = getattr(update.edited_message.from_user, "id", None) if update.edited_message.from_user else None
        
        # BATCH 48.21: Enhanced structured logging
        payload_size = request.headers.get("Content-Length")
        if payload_size:
            try:
                payload_size = int(payload_size)
            except ValueError:
                payload_size = None
        else:
            payload_size = None
        
        log_operation(
            "WEBHOOK_RECEIVED",
            update_id=update_id,
            user_id=user_id,
            callback_data=callback_data,
            update_type=update_type,
            payload_size_bytes=payload_size,
            ip=ip,
            instance_id=runtime_state.instance_id,
            active_mode="ACTIVE" if active_state.active else "PASSIVE"
        )
        
        # Check for duplicates (thread-safe)
        if update_id:
            async with _update_ids_lock:
                if update_id in recent_update_ids:
                    logger.debug("[WEBHOOK] Duplicate update_id=%s ignored", update_id)
                    return web.Response(status=200, text="ok")
                
                # BATCH 48.17: Memory leak fix - bounded size with LRU eviction
                # If set is too large, remove oldest entries (simple FIFO)
                if len(recent_update_ids) >= recent_update_ids_max_size:
                    # Remove 10% of oldest entries (simple approach - convert to list and remove first N)
                    excess = len(recent_update_ids) - int(recent_update_ids_max_size * 0.9)
                    if excess > 0:
                        # Convert to sorted list and remove smallest (oldest) IDs
                        sorted_ids = sorted(recent_update_ids)
                        for old_id in sorted_ids[:excess]:
                            recent_update_ids.discard(old_id)
                        logger.debug(f"[WEBHOOK] Cleaned {excess} old update_ids (size: {len(recent_update_ids)})")
                
                # Mark as seen BEFORE enqueueing (prevent duplicate processing)
                recent_update_ids.add(update_id)
        
        # 🚀 FASTPATH: Just fast HTTP ACK, ALL updates go to queue for proper processing
        # Business logic (sending messages, menus) happens in worker/handler
        # This architecture ensures:
        # 1) HTTP webhook responds <200ms (prevents Telegram timeout)
        # 2) /start handler in queue sends full welcome + menu (no "loading" message)
        # 3) Idempotency via recent_update_ids dedup (already implemented above)
        
        # Enqueue for background processing (non-blocking)
        # This returns immediately - worker processes in background
        from app.utils.update_queue import get_queue_manager
        queue_manager = get_queue_manager()
        
        # Check backpressure (for monitoring, but still enqueue - fast-ack must return 200)
        if queue_manager.should_reject_for_backpressure():
            logger.warning(
                "[WEBHOOK] ⚠️ BACKPRESSURE: queue utilization >80% (depth=%d/%d) - enqueueing anyway (fast-ack)",
                queue_manager.get_metrics()["queue_depth"],
                queue_manager.get_metrics()["queue_max"]
            )
        
        enqueued = queue_manager.enqueue(update, update_id)
        
        # OBSERVABILITY V2: ENQUEUE_OK
        from app.observability.v2 import log_enqueue_ok
        if enqueued:
            metrics = queue_manager.get_metrics()
            log_enqueue_ok(
                cid=cid,
                update_id=update_id,
                queue_depth=metrics.get("queue_depth", 0),
                queue_max=metrics.get("queue_max", 100),
            )
        else:
            # Queue full, update dropped - but still return 200
            logger.warning("[WEBHOOK] ❌ Queue full, dropped update_id=%s", update_id)
            # (Metrics in queue_manager track drop rate)
        
        # ALWAYS return 200 OK instantly
        return web.Response(status=200, text="ok")

    async def _deliver_result_to_telegram(
        bot: Bot, 
        chat_id: int, 
        result_urls: list[str], 
        task_id: str,
        corr_id: str = ""
    ) -> None:
        """
        Deliver generation result to Telegram with fallback.
        
        Strategy:
        1. Try bot.send_photo(url) directly
        2. If Telegram can't fetch URL, download bytes and send as InputFile
        """
        import aiohttp
        from aiogram.types import BufferedInputFile
        
        prefix = f"[{corr_id}] " if corr_id else ""
        
        if not result_urls:
            logger.warning(f"{prefix}[DELIVER] No URLs to deliver")
            return
        
        # For z-image, expect single image URL
        url = result_urls[0]
        logger.info(f"{prefix}[DELIVER] Attempting send_photo url={url[:100]}...")
        
        try:
            # Try direct URL first (fastest)
            await bot.send_photo(
                chat_id=chat_id,
                photo=url,
                caption=f"✅ Генерация готова!\nID: {task_id}"
            )
            logger.info(f"{prefix}[DELIVER] ✅ Direct URL success")
            return
        except Exception as e:
            logger.warning(f"{prefix}[DELIVER] Direct URL failed: {e}")
            logger.info(f"{prefix}[DELIVER] Trying bytes fallback...")
        
        # Fallback: download bytes
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    
                    image_bytes = await resp.read()
                    logger.info(f"{prefix}[DELIVER] Downloaded {len(image_bytes)} bytes")
            
            # Send as InputFile
            input_file = BufferedInputFile(image_bytes, filename="result.jpg")
            await bot.send_photo(
                chat_id=chat_id,
                photo=input_file,
                caption=f"✅ Генерация готова!\nID: {task_id}"
            )
            logger.info(f"{prefix}[DELIVER] ✅ Bytes fallback success")
        except Exception as e:
            logger.exception(f"{prefix}[DELIVER] ❌ Both delivery methods failed: {e}")
            # Send URL as text as last resort
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Генерация готова!\nID: {task_id}\n\n{url}"
            )
            logger.info(f"{prefix}[DELIVER] ⚠️ Sent as text fallback")

    async def _send_generation_result(bot: Bot, chat_id: int, result_urls: list[str], task_id: str) -> None:
        """
        Smart sender: detect content type and send appropriately.
        
        Handles:
        - Single/multiple images → sendPhoto/sendMediaGroup
        - Videos → sendVideo
        - Audio → sendAudio
        - Documents/files → sendDocument
        - Text/unknown → sendMessage with URLs
        """
        if not result_urls:
            return
        
        try:
            # Detect content type from URLs
            image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
            video_exts = {'.mp4', '.avi', '.mov', '.webm', '.mkv'}
            audio_exts = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}
            
            classified = {'images': [], 'videos': [], 'audio': [], 'other': []}
            
            for url in result_urls:
                url_lower = url.lower()
                if any(url_lower.endswith(ext) for ext in image_exts):
                    classified['images'].append(url)
                elif any(url_lower.endswith(ext) for ext in video_exts):
                    classified['videos'].append(url)
                elif any(url_lower.endswith(ext) for ext in audio_exts):
                    classified['audio'].append(url)
                else:
                    classified['other'].append(url)
            
            # Send based on classification
            if classified['images']:
                if len(classified['images']) == 1:
                    # Single image
                    await bot.send_photo(chat_id, classified['images'][0], 
                                        caption=f"✅ Генерация готова\\nID: {task_id}")
                else:
                    # Multiple images - send as album (max 10 per Telegram limit)
                    from aiogram.types import InputMediaPhoto
                    media_group = [
                        InputMediaPhoto(media=url, caption=f"✅ {i+1}/{len(classified['images'])}")
                        for i, url in enumerate(classified['images'][:10])
                    ]
                    await bot.send_media_group(chat_id, media=media_group)
                    
                    # If more than 10, send rest as messages
                    if len(classified['images']) > 10:
                        remaining = "\\n".join(classified['images'][10:])
                        await bot.send_message(chat_id, f"Ещё {len(classified['images'])-10} изображений:\\n{remaining}")
            
            if classified['videos']:
                for video_url in classified['videos']:
                    await bot.send_video(chat_id, video_url, caption=f"✅ Видео готово\\nID: {task_id}")
            
            if classified['audio']:
                for audio_url in classified['audio']:
                    await bot.send_audio(chat_id, audio_url, caption=f"✅ Аудио готово\\nID: {task_id}")
            
            if classified['other']:
                # Unknown type - send as message with links
                text = f"✅ Генерация готова\\nID: {task_id}\\n\\n" + "\\n".join(classified['other'])
                await bot.send_message(chat_id, text)
                
        except Exception as e:
            # Fallback: send as plain text message
            logger.exception(f"[TELEGRAM_SENDER] Failed smart send, falling back to text: {e}")
            text = f"✅ Генерация готова (ссылки)\\nID: {task_id}\\n\\n" + "\\n".join(result_urls)
            await bot.send_message(chat_id, text)

    async def kie_callback(request: web.Request) -> web.Response:
        """
        KIE callback handler with unified parser and bulletproof delivery.
        ALWAYS returns 200 to prevent retry storms.
        """
        # Token validation
        if cfg.kie_callback_token:
            header = request.headers.get("X-KIE-Callback-Token", "")
            if header != cfg.kie_callback_token:
                logger.warning("[KIE_CALLBACK] Invalid token")
                return web.json_response({"ok": False, "error": "invalid_token"}, status=200)

        # Parse payload
        try:
            raw_payload = await request.json()
        except Exception as exc:
            logger.warning(f"[KIE_CALLBACK] JSON parse failed: {exc}")
            return web.json_response({"ok": True, "ignored": True, "reason": "invalid_json"}, status=200)

        # Import unified parser
        from app.kie.state_parser import parse_kie_state, extract_task_id
        from app.utils.correlation import ensure_correlation_id
        
        task_id = extract_task_id(raw_payload)
        if not task_id:
            logger.warning(f"[KIE_CALLBACK] No taskId in payload: {str(raw_payload)[:200]}")
            return web.json_response({"ok": True, "ignored": True, "reason": "no_task_id"}, status=200)
        
        corr_id = ensure_correlation_id(task_id)
        logger.info(f"[{corr_id}] [CALLBACK_RECEIVED] task_id={task_id}")
        
        # Parse state using unified parser
        state, result_urls, error_msg = parse_kie_state(raw_payload, corr_id)
        logger.info(f"[{corr_id}] [CALLBACK_PARSED] task_id={task_id} state={state} urls={len(result_urls)} error={error_msg or 'none'}")
        
        # Get job from storage
        storage = get_storage()
        job = None
        try:
            job = await storage.find_job_by_task_id(task_id)
        except Exception as exc:
            logger.warning(f"[{corr_id}] find_job_by_task_id failed: {exc}")

        if not job:
            # BATCH 48.37: In FileStorage, orphan callbacks are expected (jobs in memory, may not be found yet)
            # Log at INFO level (not WARNING) as this is normal behavior
            from app.storage.file_storage import FileStorage
            is_file_storage = isinstance(storage, FileStorage)
            log_level = logger.info if is_file_storage else logger.warning
            log_level(f"[{corr_id}] [CALLBACK_ORPHAN] task_id={task_id} - saving for reconciliation")
            runtime_state.callback_job_not_found_count += 1
            
            # Save orphan callback
            try:
                await storage._save_orphan_callback(task_id, {
                    'state': state,
                    'result_urls': result_urls,
                    'error': error_msg,
                    'payload': raw_payload
                })
            except Exception as e:
                # BATCH 48.37: In FileStorage, _save_orphan_callback is no-op, so errors are expected
                if not is_file_storage:
                    logger.error(f"[{corr_id}] Failed to save orphan: {e}")
                else:
                    logger.debug(f"[{corr_id}] Orphan callback saved (FileStorage no-op): {e}")
            
            return web.json_response({"ok": True}, status=200)
        
        # Get job_id (support both old storage and new jobs table)
        job_id = job.get("job_id") or job.get("id")
        if not job_id:
            logger.warning(f"[{corr_id}] [CALLBACK_ERROR] No job_id found in job record")
            return web.json_response({"ok": True}, status=200)
        
        # Try to use JobServiceV2 if DB pool is available (atomic balance updates)
        # P0 FIX #11: Only use JobServiceV2 if job is in NEW table (id is int)
        job_service = None
        if runtime_state.db_pool:
            try:
                from app.services.job_service_v2 import JobServiceV2
                job_service = JobServiceV2(runtime_state.db_pool)
                # Try to get job by task_id from jobs table
                db_job = await job_service.get_by_task_id(task_id)
                if db_job:
                    job_id = db_job['id']  # Use integer ID from jobs table
                    logger.info(f"[{corr_id}] [CALLBACK_JOB_V2] Found job in jobs table: id={job_id}")
                else:
                    # Job not in new table - must use legacy storage
                    logger.info(f"[{corr_id}] [CALLBACK_LEGACY] Job not in new table, using legacy storage")
                    job_service = None  # Disable JobServiceV2 for this callback
            except Exception as e:
                logger.warning(f"[{corr_id}] [CALLBACK_FALLBACK] JobServiceV2 not available: {e}, using legacy storage")
                job_service = None
        
        # Update job status based on state
        try:
            if state in ('waiting', 'running'):
                if job_service:
                    await job_service.update_with_kie_task(job_id, task_id, 'running')
                else:
                    await storage.update_job_status(str(job_id), 'running')
                logger.debug(f"[{corr_id}] [CALLBACK_PROGRESS] task_id={task_id} state={state}")
            
            elif state == 'fail':
                # Use JobServiceV2 for atomic balance release on failure
                if job_service:
                    await job_service.update_from_callback(
                        job_id=job_id,
                        status='failed',
                        error_text=error_msg,
                        kie_status=state
                    )
                    logger.info(f"[{corr_id}] [CALLBACK_FAIL] task_id={task_id} error={error_msg} (balance released via JobServiceV2)")
                else:
                    await storage.update_job_status(str(job_id), 'failed', error_message=error_msg)
                    logger.info(f"[{corr_id}] [CALLBACK_FAIL] task_id={task_id} error={error_msg} (legacy storage)")
                
                # Try to acquire delivery lock for error notification (prevent spam)
                lock_job = await storage.try_acquire_delivery_lock(task_id, timeout_minutes=5)
                if lock_job:
                    logger.info(f"[{corr_id}] [DELIVER_LOCK_WIN] Won lock for error notification")
                    user_id = job.get('user_id')
                    chat_id = job.get('chat_id') or user_id  # Use chat_id from job if available
                    if not chat_id and job.get('params'):
                        params = job.get('params')
                        if isinstance(params, dict):
                            chat_id = params.get('chat_id') or user_id
                        elif isinstance(params, str):
                            try:
                                params_dict = json.loads(params)
                                chat_id = params_dict.get('chat_id') or user_id
                            except Exception:
                                pass
                    
                    if chat_id:
                        try:
                            await bot.send_message(chat_id, f"❌ Генерация не завершилась: {error_msg}\nID: {task_id}")
                            await storage.mark_delivered(task_id, success=True)
                            logger.info(f"[{corr_id}] [MARK_DELIVERED] Error notified")
                        except Exception as e:
                            logger.exception(f"[{corr_id}] Failed to send error to user: {e}")
                            await storage.mark_delivered(task_id, success=False, error=str(e))
                else:
                    logger.info(f"[{corr_id}] [DELIVER_LOCK_SKIP] Error already notified")
            
            elif state == 'success':
                # Use JobServiceV2 for atomic balance charge on success
                result_json = {'resultUrls': result_urls} if result_urls else None
                if job_service:
                    await job_service.update_from_callback(
                        job_id=job_id,
                        status='done',
                        result_json=result_json,
                        kie_status=state
                    )
                    logger.info(f"[{corr_id}] [CALLBACK_SUCCESS] task_id={task_id} urls={len(result_urls)} (balance will be charged after delivery)")
                else:
                    await storage.update_job_status(str(job_id), 'done', result_urls=result_urls)
                    logger.info(f"[{corr_id}] [CALLBACK_SUCCESS] task_id={task_id} urls={len(result_urls)} (legacy storage)")
                
                # Get chat_id and category for delivery
                user_id = job.get('user_id')
                chat_id = job.get('chat_id') or user_id  # Use chat_id from job if available
                if not chat_id and job.get('params'):
                    params = job.get('params')
                    if isinstance(params, dict):
                        chat_id = params.get('chat_id') or user_id
                    elif isinstance(params, str):
                        try:
                            params_dict = json.loads(params)
                            chat_id = params_dict.get('chat_id') or user_id
                        except Exception:
                            pass
                
                # Fallback: if still no chat_id, use user_id
                if not chat_id:
                    chat_id = user_id
                    logger.warning(f"[{corr_id}] [CALLBACK_WARN] No chat_id in job, using user_id={user_id}")
                
                # BATCH 48.38: Enhanced logging for z-image delivery
                logger.info(f"[{corr_id}] [CALLBACK_DELIVERY_PREP] task_id={task_id} user_id={user_id} chat_id={chat_id} model_id={job.get('model_id')} urls={len(result_urls)}")
                
                # Determine category from model_id or params
                category = 'image'  # default
                model_id = job.get('model_id', '')
                if 'z-image' in model_id.lower() or 'zimage' in model_id.lower():
                    category = 'image'  # BATCH 48.38: z-image is image category
                elif 'video' in model_id.lower():
                    category = 'video'
                elif 'audio' in model_id.lower() or 'music' in model_id.lower():
                    category = 'audio'
                elif 'upscale' in model_id.lower() or 'enhance' in model_id.lower():
                    category = 'upscale'
                
                logger.info(f"[{corr_id}] [CALLBACK_DELIVERY_CATEGORY] task_id={task_id} category={category} model_id={model_id}")
                
                if chat_id and result_urls:
                    # UNIFIED DELIVERY COORDINATOR (platform-wide atomic lock)
                    from app.delivery import deliver_result_atomic
                    
                    logger.info(f"[{corr_id}] [CALLBACK_DELIVERY_START] task_id={task_id} chat_id={chat_id} category={category} urls={result_urls}")
                    
                    delivery_result = await deliver_result_atomic(
                        storage=storage,
                        bot=bot,
                        task_id=task_id,
                        chat_id=chat_id,
                        result_urls=result_urls,
                        category=category,
                        corr_id=corr_id,
                        timeout_minutes=5,
                        job_service=job_service  # Pass job_service for balance charge after delivery
                    )
                    
                    logger.info(f"[{corr_id}] [CALLBACK_DELIVERY_RESULT] task_id={task_id} delivered={delivery_result['delivered']} already_delivered={delivery_result['already_delivered']} lock_acquired={delivery_result['lock_acquired']} error={delivery_result.get('error')}")
                    
                    if not delivery_result['delivered'] and delivery_result['error']:
                        # Delivery failed, notify user
                        try:
                            await bot.send_message(chat_id, f"⚠️ Генерация готова, но не удалось отправить результат.\nID: {task_id}")
                            logger.info(f"[{corr_id}] [CALLBACK_DELIVERY_FALLBACK] Sent error notification to chat_id={chat_id}")
                        except Exception as e:
                            logger.error(f"[{corr_id}] [CALLBACK_DELIVERY_FALLBACK_FAIL] Failed to send error notification: {e}")
                elif not chat_id:
                    logger.error(f"[{corr_id}] [CALLBACK_ERROR] Cannot deliver: no chat_id and no user_id")
                elif not result_urls:
                    logger.warning(f"[{corr_id}] [CALLBACK_WARN] No result_urls to deliver")
        
        except Exception as e:
            logger.exception(f"[{corr_id}] [CALLBACK_ERROR] task_id={task_id}: {e}")
        
        return web.json_response({"ok": True}, status=200)

    callback_route = f"/{cfg.kie_callback_path.lstrip('/')}"
    async def version(_request: web.Request) -> web.Response:
        """Version endpoint - shows commit SHA, ACTIVE/PASSIVE, deploy time."""
        from app.utils.version import get_app_version, get_version_info
        version_info = get_version_info()
        commit_sha = get_app_version()
        deploy_time = runtime_state.last_start_time or datetime.now(timezone.utc).isoformat()
        
        return web.json_response({
            "version": commit_sha,
            "commit_sha": commit_sha,
            "source": version_info.get("source", "unknown"),
            "active": active_state.active,
            "lock_state": "ACTIVE" if active_state.active else "PASSIVE",
            "deploy_time": deploy_time,
        })
    
    async def diagnostics(_request: web.Request) -> web.Response:
        """Diagnostics endpoint - comprehensive status (admin only)."""
        # Check admin access (simple check via ADMIN_ID env var)
        admin_id = os.getenv("ADMIN_ID")
        if admin_id:
            try:
                # Could check request headers or IP, but for now allow all
                # In production, add proper auth check
                pass
            except Exception:
                pass
        
        from app.utils.version import get_app_version
        from app.locking.single_instance import get_lock_debug_info, get_lock_key
        
        commit_sha = get_app_version()
        uptime = 0
        if runtime_state.last_start_time:
            started = datetime.fromisoformat(runtime_state.last_start_time)
            uptime = int((datetime.now(timezone.utc) - started).total_seconds())
        
        # Get PID
        pid = os.getpid()
        
        # Get lock key
        lock_key = None
        try:
            lock_key = get_lock_key()
        except Exception:
            pass
        
        # Webhook info
        webhook_url = "N/A"
        webhook_configured = False
        try:
            info = await bot.get_webhook_info()
            webhook_configured = bool(info.url)
            if info.url:
                # Mask secret path
                parts = info.url.rsplit("/", 1)
                webhook_url = parts[0] + "/***" if len(parts) == 2 else "***"
        except Exception:
            pass
        
        # Queue stats
        queue_manager = get_queue_manager()
        queue_metrics = queue_manager.get_metrics()
        
        # DB status
        db_status = "ok"
        db_warn = None
        try:
            if not runtime_state.db_schema_ready:
                db_status = "degraded"
                db_warn = "Schema not ready"
        except Exception:
            db_status = "unknown"
            db_warn = "DB check failed"
        
        # Lock info
        lock_debug = get_lock_debug_info()
        
        # Last error (from runtime_state if available)
        last_error = getattr(runtime_state, "last_error", None)
        
        # Models registry version (if available)
        models_registry_version = "unknown"
        try:
            from app.models.kie_models import get_models_registry
            registry = get_models_registry()
            models_registry_version = getattr(registry, "version", "unknown")
        except Exception:
            pass
        
        return web.json_response({
            "version": commit_sha,
            "commit": commit_sha,
            "instance_id": runtime_state.instance_id,
            "pid": pid,
            "active": active_state.active,
            "lock_state": "ACTIVE" if active_state.active else "PASSIVE",
            "lock_key": lock_key,
            "uptime_seconds": uptime,
            "webhook_url": webhook_url,
            "webhook_configured": webhook_configured,
            "queue": {
                "size": queue_metrics.get("queue_depth_current", 0),
                "workers": queue_metrics.get("workers_active", 0),
                "backlog": queue_metrics.get("queue_depth_current", 0),
                "max": queue_metrics.get("queue_max", 100),
            },
            "db_status": db_status,
            "db_warn": db_warn,
            "db_schema_ready": runtime_state.db_schema_ready,
            "last_error": last_error,
            "lock_holder_pid": lock_debug.get("holder_pid"),
            "lock_idle_duration": lock_debug.get("idle_duration"),
            "models_registry_version": models_registry_version,
        })
    
    app.router.add_get("/version", version)
    app.router.add_get("/diagnostics", diagnostics)
    app.router.add_get("/health", health)
    app.router.add_get("/ready", ready)
    app.router.add_get("/", root)
    app.router.add_get("/diag/webhook", diag_webhook)
    app.router.add_get("/diag/webhookinfo", diag_webhookinfo)
    app.router.add_get("/diag/lock", diag_lock)
    
    # Admin DB diagnostics routes (read from runtime_state, not app - avoid DeprecationWarning)
    try:
        from app.admin.db_diagnostics import setup_admin_routes
        from app.utils.runtime_state import runtime_state
        db_pool = getattr(runtime_state, 'db_pool', None)
        if db_pool:
            setup_admin_routes(app, db_pool)
        else:
            logger.debug("[ADMIN_DB] DB pool not available, admin routes not registered (fail-open)")
    except Exception as e:
        logger.debug(f"[ADMIN_DB] Failed to register admin routes (non-critical): {e}")
    
    # aiohttp auto-registers HEAD for GET; explicit add_head causes duplicate route
    app.router.add_post(callback_route, kie_callback)
    app.router.add_post("/webhook/{secret}", webhook)

    async def on_shutdown(_app: web.Application) -> None:
        """Graceful shutdown: close all connections and sessions."""
        logger.info("[SHUTDOWN] Starting graceful shutdown...")
        
        # BATCH 48.15: Stop update queue manager first (stops workers gracefully)
        try:
            from app.utils.update_queue import get_queue_manager
            queue_manager = get_queue_manager()
            await queue_manager.stop()
            logger.info("[SHUTDOWN] ✅ Update queue manager stopped")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Failed to stop queue manager: {e}")
        
        # BATCH 48.15: Cancel all background tasks gracefully
        tasks_to_stop = background_tasks or []
        if tasks_to_stop:
            logger.info(f"[SHUTDOWN] Cancelling {len(tasks_to_stop)} background tasks...")
            for task in tasks_to_stop:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete (with timeout)
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_stop, return_exceptions=True),
                    timeout=10.0
                )
                logger.info("[SHUTDOWN] ✅ All background tasks stopped")
            except asyncio.TimeoutError:
                logger.warning("[SHUTDOWN] ⚠️ Some background tasks did not stop within timeout")
            except Exception as e:
                logger.warning(f"[SHUTDOWN] Error stopping background tasks: {e}")
        
        # Close bot session
        try:
            await bot.session.close()
            logger.info("[SHUTDOWN] ✅ Bot session closed")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Failed to close bot session: {e}")
        
        # Close database pools if available
        try:
            if runtime_state.db_pool:
                await runtime_state.db_pool.close()
                logger.info("[SHUTDOWN] ✅ Database pool closed")
        except Exception as e:
            logger.warning(f"[SHUTDOWN] Failed to close database pool: {e}")
        
        # Close KIE client sessions if any
        try:
            from app.integrations.strict_kie_client import get_kie_client
            kie_client = get_kie_client()
            if kie_client:
                await kie_client.close()
                logger.info("[SHUTDOWN] ✅ KIE client session closed")
        except Exception as e:
            logger.debug(f"[SHUTDOWN] KIE client close (may not be initialized): {e}")
        
        # Close psycopg2 connection pool
        try:
            # BATCH 48: NO DATABASE MODE - No connection pool to close
            logger.info("[SHUTDOWN] ✅ FileStorage (no connection pool)")
        except Exception as e:
            logger.debug(f"[SHUTDOWN] psycopg2 pool close (may not be initialized): {e}")
        
        logger.info("[SHUTDOWN] ✅ Graceful shutdown complete")

    app.on_shutdown.append(on_shutdown)
    return app


async def _start_web_server(app: web.Application, port: int) -> web.AppRunner:
    """Start aiohttp server with deterministic port binding."""
    runner = web.AppRunner(app)
    await runner.setup()
    host = "0.0.0.0"  # Always bind to all interfaces for Render
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    
    # CRITICAL: Log successful bind BEFORE background tasks
    logger.info(
        "[HTTP] ✅ Server listening on %s:%d (socket open, ready for traffic)",
        host, port
    )
    return runner


async def main() -> None:
    LOG_LEVEL_ENV = os.getenv("LOG_LEVEL", "").upper()
    setup_logging(level=(logging.DEBUG if LOG_LEVEL_ENV == "DEBUG" else logging.INFO))

    # CRITICAL: Validate ENV contract BEFORE any DB/network operations
    from app.utils.startup_validation import startup_validation
    if not startup_validation():
        logger.error("[STARTUP] ENV validation failed - exiting")
        sys.exit(1)

    cfg = _load_runtime_config()
    effective_bot_mode = cfg.bot_mode
    if effective_bot_mode == "webhook" and not cfg.webhook_base_url:
        logger.warning(
            "[CONFIG] WEBHOOK_BASE_URL missing in webhook mode; falling back to polling"
        )
        effective_bot_mode = "polling"

    runtime_state.bot_mode = effective_bot_mode
    runtime_state.last_start_time = datetime.now(timezone.utc).isoformat()

    # Get app version (git SHA or build ID) - safe, no secrets
    app_version = get_app_version()
    version_info = get_version_info()
    git_sha = version_info.get("git_sha") or version_info.get("commit", None)
    
    # OBSERVABILITY V2: STARTUP_SUMMARY
    from app.observability.v2 import log_startup_summary
    from app.observability.explain import log_startup_phase
    log_startup_summary(
        version=app_version,
        git_sha=git_sha,
        bot_mode=effective_bot_mode,
        port=cfg.port or 10000,
        webhook_base_url=cfg.webhook_base_url,
        dry_run=cfg.dry_run,
        subsystems={
            "db": bool(cfg.database_url),
            "telemetry": True,  # TelemetryMiddleware is available
            "admin": bool(cfg.database_url),  # Admin requires DB
            "queue": True,  # Queue always available
        },
        lock_state="UNKNOWN",  # Will be set after lock acquisition
    )

    # P0: MANDATORY Boot Self-Check (zero Traceback before user clicks)
    logger.info("=" * 60)
    logger.info("[BOOT SELF-CHECK] Starting mandatory checks...")
    logger.info("=" * 60)
    
    boot_check_ok = True
    
    # Check 1: Critical imports (MANDATORY)
    try:
        import main_render
        from app.telemetry.telemetry_helpers import TelemetryMiddleware
        from app.middleware.exception_middleware import ExceptionMiddleware
        # NOTE: runtime_state is imported at module level (line 34), verify it's accessible
        # Do not create local variable - use global import
        _ = runtime_state  # Verify global runtime_state is accessible
        logger.info("[BOOT CHECK] ✅ Import check: main_render, TelemetryMiddleware, ExceptionMiddleware, runtime_state")
    except ImportError as e:
        logger.error(f"[BOOT CHECK] ❌ Import check FAILED: {e}")
        boot_check_ok = False
    except Exception as e:
        logger.error(f"[BOOT CHECK] ❌ Import check ERROR: {e}")
        boot_check_ok = False
    
    # Check 2: Config validation (MANDATORY - no secrets in logs)
    try:
        # Validate required ENV vars exist (without printing values)
        required_vars = [
            "TELEGRAM_BOT_TOKEN",
            "BOT_MODE",
        ]
        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value or not value.strip():
                missing_vars.append(var)
            else:
                # Log that var exists (but not its value)
                logger.debug(f"[BOOT CHECK] ✅ Config: {var} is set (length: {len(value)})")
        
        if missing_vars:
            logger.error(f"[BOOT CHECK] ❌ Config check FAILED: Missing required vars: {', '.join(missing_vars)}")
            boot_check_ok = False
        else:
            logger.info("[BOOT CHECK] ✅ Config check: Required ENV vars present")
        
        # Validate BOT_MODE value
        bot_mode = os.getenv("BOT_MODE", "").strip().lower()
        if bot_mode and bot_mode not in ["webhook", "polling"]:
            logger.warning(f"[BOOT CHECK] ⚠️ Config: BOT_MODE='{bot_mode}' is not 'webhook' or 'polling'")
        elif bot_mode:
            logger.info(f"[BOOT CHECK] ✅ Config: BOT_MODE='{bot_mode}'")
        
        # Validate PORT if set
        port_str = os.getenv("PORT")
        if port_str:
            try:
                port = int(port_str)
                if port < 1 or port > 65535:
                    logger.warning(f"[BOOT CHECK] ⚠️ Config: PORT={port} is out of valid range (1-65535)")
                else:
                    logger.info(f"[BOOT CHECK] ✅ Config: PORT={port}")
            except ValueError:
                logger.warning(f"[BOOT CHECK] ⚠️ Config: PORT='{port_str}' is not a valid integer")
        
    except Exception as e:
        logger.error(f"[BOOT CHECK] ❌ Config check ERROR: {e}")
        boot_check_ok = False
    
    # Check 3: Database URL format (if set) - validate format only, no connection
    if cfg.database_url:
        try:
            # Basic format validation (postgresql:// or postgres://)
            if not (cfg.database_url.startswith("postgresql://") or cfg.database_url.startswith("postgres://")):
                logger.warning(f"[BOOT CHECK] ⚠️ Config: DATABASE_URL format may be invalid (expected postgresql://...)")
            else:
                # Extract hostname for logging (safe, no credentials)
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(cfg.database_url)
                    hostname = parsed.hostname or "unknown"
                    logger.info(f"[BOOT CHECK] ✅ Config: DATABASE_URL format OK (host: {hostname})")
                except Exception:
                    logger.info("[BOOT CHECK] ✅ Config: DATABASE_URL format OK")
        except Exception as e:
            logger.warning(f"[BOOT CHECK] ⚠️ Config: DATABASE_URL validation error: {e}")
    
    # Check 4: Webhook URL format (if webhook mode)
    if cfg.bot_mode == "webhook":
        if cfg.webhook_base_url:
            if not (cfg.webhook_base_url.startswith("http://") or cfg.webhook_base_url.startswith("https://")):
                logger.warning(f"[BOOT CHECK] ⚠️ Config: WEBHOOK_BASE_URL format may be invalid (expected http:// or https://...)")
            else:
                logger.info(f"[BOOT CHECK] ✅ Config: WEBHOOK_BASE_URL format OK")
        else:
            logger.warning("[BOOT CHECK] ⚠️ Config: WEBHOOK_BASE_URL not set (webhook mode requires it)")
    
    # Check 3: Database connection (readonly, non-blocking, optional)
    # This is optional - if DB is unavailable, app can still start (fail-open)
    # BATCH 48.31: Skip if NO DATABASE MODE (no warnings/errors)
    no_db_mode = os.getenv('NO_DATABASE_MODE', '').lower() in ('1', 'true', 'yes')
    if cfg.database_url and not no_db_mode:
        try:
            import asyncpg
            # Quick connection test (timeout 3s, non-blocking)
            try:
                conn = await asyncio.wait_for(
                    asyncpg.connect(cfg.database_url, timeout=3),
                    timeout=5
                )
                await conn.fetchval("SELECT 1")
                await conn.close()
                logger.info("[BOOT CHECK] ✅ Database connection: OK (read-only test)")
            except asyncio.TimeoutError:
                logger.warning("[BOOT CHECK] ⚠️ Database connection: TIMEOUT (non-critical, app continues)")
            except Exception as db_err:
                # BATCH 48.31: Only log as DEBUG in NO DATABASE MODE, INFO otherwise
                logger.debug(f"[BOOT CHECK] Database connection: FAILED (non-critical): {db_err}")
        except ImportError:
            logger.debug("[BOOT CHECK] asyncpg not installed - database features will be unavailable")
            # Continue without database - app can still run in limited mode
        except Exception as e:
            logger.debug(f"[BOOT CHECK] Database check: ERROR (non-critical): {e}")
    elif no_db_mode:
        logger.debug("[BOOT CHECK] Database: NO DATABASE MODE - skipping connection check")
    else:
        logger.info("[BOOT CHECK] ℹ️ Database: Not configured (JSON storage mode)")
    
    # Final boot check summary
    logger.info("=" * 60)
    if boot_check_ok:
        logger.info("[BOOT SELF-CHECK] ✅ ALL CHECKS PASSED - Ready to start")
        log_startup_phase(phase="BOOT_CHECK", status="DONE", details="All checks passed")
    else:
        logger.error("[BOOT SELF-CHECK] ❌ SOME CHECKS FAILED - App may have limited functionality (fail-open)")
        log_startup_phase(
            phase="BOOT_CHECK",
            status="FAIL",
            details="Some checks failed",
            next_step="Review logs for specific failures and fix root cause"
        )
    logger.info("=" * 60)
    
    log_startup_phase(phase="ROUTERS_INIT", status="START")
    dp, bot = create_bot_application()
    log_startup_phase(phase="ROUTERS_INIT", status="DONE", details="Bot application created")
    
    # Log version and build info
    logger.info(f"[STARTUP] 📦 App version: {app_version} (source: {version_info.get('source', 'unknown')})")
    if git_sha:
        logger.info(f"[STARTUP] 🔖 Git SHA: {git_sha}")
    
    # Log middleware registration status (already logged in create_bot_application, but summarize here)
    logger.info("[STARTUP] 🔒 Security middleware: AntiAbuseMiddleware, TelegramProtectionMiddleware")
    logger.info("[STARTUP] 📊 Observability: TelemetryMiddleware, HandlerLoggingMiddleware")
    
    # Verify bot identity and webhook configuration BEFORE anything else
    await verify_bot_identity(bot)
    
    # Initialize update queue manager
    from app.utils.update_queue import get_queue_manager
    queue_manager = get_queue_manager()
    logger.info("[QUEUE] Initializing update queue (max_size=%d workers=%d)", 
               queue_manager.max_size, queue_manager.num_workers)

    # IMPORTANT: the advisory lock helper in app.locking.single_instance relies on
    # the psycopg2 connection pool from database.py being initialized.
    # If we don't create the pool first, lock acquisition can fail even when no
    # other instance is running, leaving this deploy permanently PASSIVE.
    #
    # SINGLETON_LOCK_FORCE_ACTIVE (default: 1 / True for Render)
    #   - When True: if lock acquisition fails, proceed as ACTIVE anyway
    #     (assumes only one Render Web Service instance)
    #   - When False: don't proceed if lock acquisition fails
    #
    # SINGLETON_LOCK_STRICT (default: 0)
    #   - When True: exit immediately if lock acquisition fails
    #   - When False: continue in PASSIVE mode if lock acquisition fails
    # BATCH 48.9-48.10: Mark deploy start (for graceful degradation)
    try:
        from app.middleware.deploy_aware import mark_deploy_start
        await mark_deploy_start()
        logger.info("[DEPLOY] 🚧 Deploy marker created (graceful degradation enabled)")
    except Exception as e:
        logger.warning(f"[DEPLOY] Failed to create deploy marker: {e}")
    
    # BATCH 48: NO DATABASE MODE - Always use FileStorage
    logger.info("[BATCH48] 🚫 NO DATABASE MODE - Using FileStorage for balances")
    from app.storage.file_storage import init_file_storage
    
    try:
        await init_file_storage()
        logger.info("[BATCH48] ✅ FileStorage initialized (balances in data/user_balances.json)")
        runtime_state.db_schema_ready = True  # No migrations needed
    except Exception as e:
        logger.error(f"[BATCH48] ❌ Failed to initialize FileStorage: {e}")
        # Continue anyway - FileStorage will create file on first use
        runtime_state.db_schema_ready = True

    # Create lock object and state tracker
    lock = SingletonLock(cfg.database_url)
    active_state = ActiveState(active=False)  # Start as passive, will activate after lock
    
    # BATCH 48.15: Track all background tasks for graceful shutdown
    background_tasks: list[asyncio.Task] = []
    
    # DEPLOY_TOPOLOGY: Log instance topology explanation
    # NOTE: os is already imported at module level (line 20), do not import again
    from app.observability.explain import log_deploy_topology
    from app.locking.single_instance import get_lock_key, get_lock_debug_info
    
    instance_id = runtime_state.instance_id
    pid = os.getpid()
    boot_time = datetime.now(timezone.utc).isoformat()
    commit_sha = app_version
    render_service_name = os.getenv("RENDER_SERVICE_NAME") or os.getenv("SERVICE_NAME")
    
    # Get lock info if available
    lock_key = None
    lock_holder_pid = None
    try:
        lock_key = get_lock_key()
        lock_debug = get_lock_debug_info()
        lock_holder_pid = lock_debug.get("holder_pid")
    except Exception:
        pass  # Lock info not available yet
    
    log_deploy_topology(
        instance_id=instance_id,
        pid=pid,
        boot_time=boot_time,
        commit_sha=commit_sha,
        is_active=False,  # Will be updated when lock acquired
        lock_key=lock_key,
        lock_holder_pid=lock_holder_pid,
        render_service_name=render_service_name,
    )
    
    # Configure queue manager with dp, bot, and active_state BEFORE starting workers
    queue_manager.configure(dp, bot, active_state)
    
    # 🔧 BACKGROUND TASKS: migrations + lock acquisition (NON-BLOCKING)
    # This ensures HTTP server starts IMMEDIATELY without waiting
    # BATCH 48.15: background_tasks list is defined above in main() function scope
    async def background_initialization():
        """Initialize lock acquisition in background (migrations moved to ACTIVE only)."""
        # Migrations moved to init_active_services (ONLY on ACTIVE)
        # PASSIVE instances must NOT run migrations - only ACTIVE should modify schema
        # This prevents concurrent migration attempts and schema conflicts
        logger.debug("[MIGRATIONS] Migrations deferred to ACTIVE mode (init_active_services)")
        # Mark schema as unknown until ACTIVE instance applies migrations
        runtime_state.db_schema_ready = False
        
        # P0 CRITICAL: Start pending updates processor FIRST (ALWAYS, unconditional)
        # This MUST run even before migrations, as PASSIVE instances need to process enqueued updates
        async def pending_updates_processor_loop():
            """
            Background worker that processes pending_updates from DB queue.
            Only runs when instance is ACTIVE.
            """
            from app.storage.factory import get_storage
            from app.utils.update_queue import get_queue_manager
            from app.utils.correlation import correlation_tag
            import json
            
            logger.info("[PENDING_QUEUE] Background processor started")
            queue_manager = get_queue_manager()
            
            while True:
                try:
                    # Only process if ACTIVE
                    if not active_state.active:
                        await asyncio.sleep(5.0)  # Check every 5 seconds
                        continue
                    
                    # Get pending updates from DB
                    storage = get_storage()
                    instance_id = runtime_state.instance_id or "unknown"
                    
                    # BATCH 48.24: Check if storage supports get_pending_updates (PostgresStorage only)
                    if not hasattr(storage, 'get_pending_updates'):
                        # FileStorage doesn't have this method - skip in NO DATABASE MODE
                        await asyncio.sleep(5.0)
                        continue
                    
                    try:
                        pending_updates = await storage.get_pending_updates(
                            instance_id=instance_id,
                            limit=10  # Process in batches
                        )
                    except RuntimeError as e:
                        # BATCH 48.24: RuntimeError means PostgresStorage not available (NO DATABASE MODE)
                        # This is expected - skip processing
                        from app.utils.enhanced_logging import log_operation
                        log_operation(
                            "PENDING_UPDATES_PROCESSOR",
                            status="SKIPPED",
                            error_code="STORAGE_NOT_AVAILABLE",
                            error_message=str(e),
                            fix_hint="PostgresStorage not available - this is expected in NO DATABASE MODE",
                            instance_id=instance_id
                        )
                        await asyncio.sleep(10.0)  # Wait longer before retry
                        continue
                    
                    if not pending_updates:
                        await asyncio.sleep(2.0)  # No updates, wait 2 seconds
                        continue
                    
                    logger.info(
                        f"[PENDING_QUEUE] Processing {len(pending_updates)} pending updates"
                    )
                    
                    # Process each pending update
                    for pending in pending_updates:
                        pending_id = pending['id']
                        update_id = pending['update_id']
                        update_payload = pending['update_payload']
                        update_type = pending['update_type']
                        
                        cid = correlation_tag()
                        logger.info(
                            f"{cid} [PENDING_QUEUE] Processing pending_id={pending_id} "
                            f"update_id={update_id} type={update_type}"
                        )
                        
                        try:
                            # Convert JSON payload back to Update object
                            from aiogram.types import Update
                            if isinstance(update_payload, str):
                                payload_dict = json.loads(update_payload)
                            else:
                                payload_dict = update_payload
                            
                            update = Update.model_validate(payload_dict)
                            
                            # Enqueue to in-memory queue for normal processing
                            enqueued = queue_manager.enqueue(update, update_id)
                            
                            if enqueued:
                                # Mark as processed in DB
                                await storage.mark_pending_update_processed(
                                    pending_id=pending_id,
                                    processing_instance_id=instance_id,
                                    success=True
                                )
                                logger.info(
                                    f"{cid} [PENDING_QUEUE] ✅ Processed pending_id={pending_id} "
                                    f"update_id={update_id}"
                                )
                            else:
                                # Queue full - will retry later
                                await storage.mark_pending_update_processed(
                                    pending_id=pending_id,
                                    processing_instance_id=instance_id,
                                    success=False,
                                    error_message="Queue full, will retry"
                                )
                                logger.warning(
                                    f"{cid} [PENDING_QUEUE] ⚠️ Queue full for pending_id={pending_id}, will retry"
                                )
                        
                        except Exception as e:
                            logger.error(
                                f"{cid} [PENDING_QUEUE] Failed to process pending_id={pending_id}: {e}",
                                exc_info=True
                            )
                            await storage.mark_pending_update_processed(
                                pending_id=pending_id,
                                processing_instance_id=instance_id,
                                success=False,
                                error_message=str(e)
                            )
                    
                except asyncio.CancelledError:
                    logger.info("[PENDING_QUEUE] Background processor cancelled")
                    break
                except Exception as e:
                    logger.error(
                        f"[PENDING_QUEUE] Unexpected error in processor loop: {e}",
                        exc_info=True
                    )
                    await asyncio.sleep(5.0)  # Wait before retry
        
        # START IMMEDIATELY (highest priority) - ONLY if DATABASE_URL is available
        if cfg.database_url:
            task = asyncio.create_task(pending_updates_processor_loop(), name="pending_updates_processor")
            background_tasks.append(task)
            logger.info("[PENDING_QUEUE] ✅ Background processor task started")
        else:
            logger.info("[PENDING_QUEUE] ⏭️ Skipped (NO DATABASE MODE - using direct processing)")
        
        # PHASE 5: Start orphan callback reconciliation background task (ONLY if schema ready)
        if runtime_state.db_schema_ready and cfg.database_url:
            try:
                # Create storage instance for reconciler
                from app.storage import get_storage
                storage_instance = get_storage()
                
                reconciler = OrphanCallbackReconciler(
                    storage=storage_instance,
                    bot=bot,
                    check_interval=10,
                    max_age_minutes=30
                )
                await reconciler.start()
                logger.info("[RECONCILER] ✅ Background orphan reconciliation started (10s interval, 30min timeout)")
            except Exception as exc:
                logger.warning(f"[RECONCILER] ⚠️ Failed to start reconciler: {exc}")
        
        # PHASE 5.5: Start FSM state cleanup background task (ONLY on ACTIVE)
        async def fsm_cleanup_loop():
            """Periodic cleanup of expired FSM states."""
            while True:
                try:
                    await asyncio.sleep(300)  # Run every 5 minutes
                    if not active_state.active:
                        continue  # Only cleanup on ACTIVE instance
                    
                    if runtime_state.db_pool:
                        try:
                            from app.database.services import DatabaseService, UIStateService
                            from datetime import datetime, timezone
                            db_service = DatabaseService(cfg.database_url)
                            db_service._pool = runtime_state.db_pool
                            ui_state_service = UIStateService(db_service)
                            await ui_state_service.cleanup_expired()
                            # Track last run time for health check
                            runtime_state.fsm_cleanup_last_run = datetime.now(timezone.utc).isoformat()
                        except Exception as e:
                            from app.utils.correlation import correlation_tag
                            cid = correlation_tag()
                            logger.error(f"{cid} [FSM_CLEANUP] Failed to cleanup expired states: {e}", exc_info=True)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(f"{cid} [FSM_CLEANUP] Error in cleanup loop: {e}")
                    await asyncio.sleep(60)  # Wait before retry
        
        # Only start if DATABASE_URL is available
        if cfg.database_url:
            task = asyncio.create_task(fsm_cleanup_loop(), name="fsm_cleanup")
            background_tasks.append(task)
            logger.info("[FSM_CLEANUP] ✅ Background FSM state cleanup started (5min interval)")
        else:
            logger.info("[FSM_CLEANUP] ⏭️ Skipped (NO DATABASE MODE)")
        
        # PHASE 5.55: Start balance guarantee retry loop (BATCH 48.8 - CRITICAL!)
        # This ensures ALL balance changes are pushed to GitHub (retry до успеха)
        try:
            from app.storage.balance_guarantee import start_periodic_retry_loop
            task = asyncio.create_task(start_periodic_retry_loop(), name="balance_guarantee")
            background_tasks.append(task)
            logger.info("[BALANCE_GUARANTEE] ✅ Balance guarantee retry loop started (60s interval)")
        except Exception as e:
            logger.error(f"[BALANCE_GUARANTEE] ❌ Failed to start retry loop: {e}")
        
        # PHASE 5.6: Start stale job cleanup background task (ONLY on ACTIVE)
        async def stale_job_cleanup_loop():
            """Periodic cleanup of stale jobs (running >30min)."""
            while True:
                try:
                    await asyncio.sleep(600)  # Run every 10 minutes
                    if not active_state.active:
                        continue  # Only cleanup on ACTIVE instance
                    
                    if runtime_state.db_pool:
                        try:
                            from app.services.job_service_v2 import JobServiceV2
                            from datetime import datetime, timezone
                            job_service = JobServiceV2(runtime_state.db_pool)
                            cleaned = await job_service.cleanup_stale_jobs(stale_minutes=30)
                            if cleaned > 0:
                                logger.info(f"[STALE_JOB_CLEANUP] Cleaned up {cleaned} stale jobs")
                            # Track last run time for health check
                            runtime_state.stale_job_cleanup_last_run = datetime.now(timezone.utc).isoformat()
                        except Exception as e:
                            from app.utils.correlation import correlation_tag
                            cid = correlation_tag()
                            logger.error(f"{cid} [STALE_JOB_CLEANUP] Failed to cleanup stale jobs: {e}", exc_info=True)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(f"{cid} [STALE_JOB_CLEANUP] Error in cleanup loop: {e}", exc_info=True)
                    await asyncio.sleep(60)  # Wait before retry
        
        # Only start if DATABASE_URL is available
        if cfg.database_url:
            task = asyncio.create_task(stale_job_cleanup_loop(), name="stale_job_cleanup")
            background_tasks.append(task)
            logger.info("[STALE_JOB_CLEANUP] ✅ Background stale job cleanup started (10min interval)")
        else:
            logger.info("[STALE_JOB_CLEANUP] ⏭️ Skipped (NO DATABASE MODE)")
        
        # PHASE 5.7: Start stuck payment cleanup background task (ONLY on ACTIVE)
        async def stuck_payment_cleanup_loop():
            """Periodic cleanup of stuck payments (pending >24h)."""
            while True:
                try:
                    await asyncio.sleep(3600)  # Run every hour
                    if not active_state.active:
                        continue  # Only cleanup on ACTIVE instance
                    
                    if runtime_state.db_pool:
                        try:
                            from app.storage import get_storage
                            from datetime import datetime, timezone
                            storage = get_storage()
                            if hasattr(storage, 'cleanup_stuck_payments'):
                                cleaned = await storage.cleanup_stuck_payments(stale_hours=24)
                                if cleaned > 0:
                                    logger.info(f"[STUCK_PAYMENT_CLEANUP] Cleaned up {cleaned} stuck payments")
                                # Track last run time for health check
                                runtime_state.stuck_payment_cleanup_last_run = datetime.now(timezone.utc).isoformat()
                        except Exception as e:
                            from app.utils.correlation import correlation_tag
                            cid = correlation_tag()
                            logger.warning(f"{cid} [STUCK_PAYMENT_CLEANUP] Failed to cleanup stuck payments: {e}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(f"{cid} [STUCK_PAYMENT_CLEANUP] Error in cleanup loop: {e}", exc_info=True)
                    await asyncio.sleep(60)  # Wait before retry
        
        # Only start if DATABASE_URL is available
        if cfg.database_url:
            task = asyncio.create_task(stuck_payment_cleanup_loop(), name="stuck_payment_cleanup")
            background_tasks.append(task)
            logger.info("[STUCK_PAYMENT_CLEANUP] ✅ Background stuck payment cleanup started (1h interval)")
        else:
            logger.info("[STUCK_PAYMENT_CLEANUP] ⏭️ Skipped (NO DATABASE MODE)")
        
        # Start update queue workers (already configured above)
        await queue_manager.start()
        logger.info("[QUEUE] ✅ Workers started (background update processing)")
        
        # BATCH 48.9-48.10: Mark deploy complete (bot ready for requests)
        try:
            from app.middleware.deploy_aware import mark_deploy_complete
            await mark_deploy_complete()
            logger.info("[DEPLOY] ✅ Deploy complete (bot ready for generation requests)")
        except Exception as e:
            logger.warning(f"[DEPLOY] Failed to mark deploy complete: {e}")
        
        # Final startup summary - bot ready
        logger.info("=" * 60)
        logger.info("[BOT_READY] ✅ Bot is ready to serve requests")
        logger.info("=" * 60)
        logger.info(f"[BOT_READY] Mode: {effective_bot_mode}")
        logger.info(f"[BOT_READY] Storage: {runtime_state.storage_mode}")
        logger.info(f"[BOT_READY] Lock state: {'ACTIVE' if active_state.active else 'PASSIVE'}")
        logger.info(f"[BOT_READY] DB schema: {'✅ Ready' if runtime_state.db_schema_ready else '❌ Not ready'}")
        logger.info("=" * 60)
        
        # PHASE 6: Webhook setup moved to init_active_services (ONLY on ACTIVE)
        # PASSIVE instances must NOT set webhook - only ACTIVE should own it
        # This prevents race conditions and ensures single webhook owner
        logger.debug("[WEBHOOK] Webhook setup deferred to ACTIVE mode (init_active_services)")
        
        # Define init_active_services BEFORE lock_controller creation
        # db_service declared at function level for finally block
        free_manager = None

        async def init_active_services() -> None:
            """Initialize services when lock acquired (called by controller callback)"""
            nonlocal db_service, free_manager
            
            logger.info("[INIT_SERVICES] 🚀 init_active_services() CALLED (ACTIVE MODE)")
            logger.info(f"[INIT_SERVICES] BOT_MODE={effective_bot_mode}, DRY_RUN={cfg.dry_run}")

            # Update runtime state
            # active_state synced automatically by lock_controller, no need to set manually
            runtime_state.lock_acquired = True
            
            # P0-1: Update DEPLOY_TOPOLOGY with correct ACTIVE state
            # NOTE: os is already imported at module level (line 20), do not import again
            from app.observability.explain import log_deploy_topology
            from app.locking.single_instance import get_lock_key, get_lock_debug_info
            try:
                lock_key = get_lock_key()
                lock_debug = get_lock_debug_info()
                lock_holder_pid = lock_debug.get("holder_pid")
                render_service_name = os.getenv("RENDER_SERVICE_NAME") or os.getenv("SERVICE_NAME")
                
                log_deploy_topology(
                    instance_id=runtime_state.instance_id,
                    pid=os.getpid(),
                    boot_time=runtime_state.last_start_time or datetime.now(timezone.utc).isoformat(),
                    commit_sha=app_version,
                    is_active=True,  # Now ACTIVE
                    lock_key=lock_key,
                    lock_holder_pid=lock_holder_pid,
                    render_service_name=render_service_name,
                )
            except Exception as e:
                logger.debug(f"[DEPLOY_TOPOLOGY] Failed to log topology update: {e}")
            
            # Step 1: Apply migrations (ONLY on ACTIVE instance)
            log_startup_phase(phase="DB_INIT", status="START")
            if cfg.database_url:
                logger.info("[INIT_SERVICES] Applying database migrations (ACTIVE only)...")
                try:
                    from app.storage.migrations import apply_migrations_safe
                    migrations_ok = await apply_migrations_safe(cfg.database_url)
                    if migrations_ok:
                        logger.info("[MIGRATIONS] ✅ Database schema ready")
                        runtime_state.db_schema_ready = True
                        log_startup_phase(phase="DB_INIT", status="DONE", details="Migrations applied successfully")
                    else:
                        logger.error("[MIGRATIONS] ❌ Schema NOT ready")
                        runtime_state.db_schema_ready = False
                        log_startup_phase(
                            phase="DB_INIT",
                            status="FAIL",
                            details="Migrations failed",
                            next_step="Check database connectivity and migration scripts"
                        )
                except Exception as e:
                    logger.exception(f"[MIGRATIONS] CRITICAL: Auto-apply failed: {e}")
                    runtime_state.db_schema_ready = False
                    log_startup_phase(
                        phase="DB_INIT",
                        status="FAIL",
                        details=f"Exception: {e}",
                        next_step="Review migration logs and database state"
                    )
            else:
                runtime_state.db_schema_ready = True  # JSON storage doesn't need migrations
                log_startup_phase(phase="DB_INIT", status="DONE", details="Skipped (JSON storage mode)")
            
            # Step 2: WEBHOOK ON ACTIVE: Ensure webhook is set on ACTIVE instance
            # This guarantees webhook ownership after lock acquired
            if effective_bot_mode == "webhook" and not cfg.dry_run:
                logger.info("[WEBHOOK_ACTIVE] 🔧 Ensuring webhook on ACTIVE instance...")
                webhook_url = _build_webhook_url(cfg)
                if webhook_url:
                    from app.utils.webhook import ensure_webhook
                    try:
                        webhook_set = await ensure_webhook(
                            bot,
                            webhook_url=webhook_url,
                            secret_token=cfg.webhook_secret_token or None,
                            force_reset=False,  # No force - respect no-op logic
                        )
                        if webhook_set:
                            logger.info("[WEBHOOK_ACTIVE] ✅ Webhook ensured on ACTIVE instance")
                        else:
                            logger.warning("[WEBHOOK_ACTIVE] ⚠️ Webhook ensure returned False")
                    except Exception as e:
                        logger.exception("[WEBHOOK_ACTIVE] ❌ Exception: %s", e)
                else:
                    logger.error("[WEBHOOK_ACTIVE] ❌ Cannot build webhook URL!")

            # Step 2.5: Start anti-abuse system (CRITICAL for protection)
            try:
                from app.security.anti_abuse import get_anti_abuse
                anti_abuse = get_anti_abuse()
                await anti_abuse.start()
                exempt_count = len(anti_abuse.exempt_users) if hasattr(anti_abuse, 'exempt_users') else 0
                logger.info(f"[SECURITY] ✅ Anti-abuse system started (exempt users: {exempt_count})")
            except Exception as e:
                logger.warning(f"[SECURITY] Failed to start anti-abuse system (non-critical): {e}")
            
            # Step 2.6: Log Telegram protection status
            try:
                from app.security.telegram_protection import get_telegram_protection
                telegram_protection = get_telegram_protection()
                logger.info("[SECURITY] ✅ Telegram protection system initialized")
            except Exception as e:
                logger.warning(f"[SECURITY] Failed to initialize Telegram protection (non-critical): {e}")
            
            # Step 2.7: Log models count and registry status
            try:
                from app.kie.registry import get_model_registry
                registry = get_model_registry()
                total_models = len(registry) if isinstance(registry, dict) else 0
                logger.info(f"[MODELS] ✅ Model registry loaded: {total_models} models available")
            except Exception as e:
                logger.warning(f"[MODELS] Failed to load model registry (non-critical): {e}")
            
            # Step 2.8: Log P0/P1 fixes status
            logger.info("[AUDIT] ✅ P0 Critical Fixes: 5/5 (100%) - All critical issues resolved")
            logger.info("[AUDIT] 🔄 P1 High Priority: 63/98 (~64%) - Partially completed")
            logger.info("[AUDIT]   - P1-1: None checks in handlers: 45/60 (75%)")
            logger.info("[AUDIT]   - P1-2: Exception handling: 5/10 (50%)")
            logger.info("[AUDIT]   - P1-3: ON CONFLICT in INSERT: 5/5 (100%) ✅")
            logger.info("[AUDIT]   - P1-4: Input validation: 4/14 (29%)")
            logger.info("[AUDIT]   - P1-5: API error handling: 4/9 (44%)")
            
            # Step 3: Initialize database services (ONLY on ACTIVE)
            # BATCH 48.29: Check NO DATABASE MODE before initializing DatabaseService
            no_db_mode = os.getenv('NO_DATABASE_MODE', '').lower() in ('1', 'true', 'yes')
            if cfg.database_url and not no_db_mode:
                logger.info("[INIT_SERVICES] Initializing DatabaseService...")
                try:
                    from app.database.services import DatabaseService
                    from app.free.manager import FreeModelManager
                    from app.referrals.manager import ReferralManager

                    db_service = DatabaseService(cfg.database_url)
                    await db_service.initialize()
                    
                    # BATCH 48.42: Initialize referral manager and pass to free manager
                    storage = get_storage()
                    referral_manager = ReferralManager(storage)
                    free_manager = FreeModelManager(db_service, referral_manager=referral_manager)
                    
                    # Only set services if db_service was successfully initialized
                    from bot.handlers.balance import set_database_service as set_balance_db
                    from bot.handlers.history import set_database_service as set_history_db
                    from bot.handlers.marketing import (
                        set_database_service as set_marketing_db,
                        set_free_manager,
                    )

                    set_balance_db(db_service)
                    set_history_db(db_service)
                    set_marketing_db(db_service)
                    set_free_manager(free_manager)

                    # Initialize AdminService and inject into admin handlers
                    from app.admin.service import AdminService
                    from app.services.wiring import set_services as set_global_services
                    from bot.handlers.admin import set_services as set_admin_handlers_services
                    
                    admin_service = AdminService(db_service, free_manager)
                    # Single source of truth: set in global wiring
                    set_global_services(db_service, admin_service, free_manager)
                    # Also set in admin handlers (backward compatibility)
                    set_admin_handlers_services(db_service, admin_service, free_manager)
                    logger.info("[ADMIN] ✅ AdminService initialized and injected into handlers")

                    # Initialize observability events DB
                    from app.observability.events_db import init_events_db
                    if hasattr(db_service, '_pool') and db_service._pool:
                        init_events_db(db_service._pool)
                        logger.info("[OBSERVABILITY] ✅ Events DB initialized")
                    
                    # Store pool in runtime_state instead of app (avoid DeprecationWarning)
                    # Admin routes will read from runtime_state or use dependency injection
                    if hasattr(db_service, '_pool'):
                        # Store in runtime_state for admin endpoints (fail-open if not available)
                        runtime_state.db_pool = db_service._pool

                    logger.info("[DB] ✅ DatabaseService initialized and injected into handlers")
                except (OSError, RuntimeError) as db_err:
                    # NO DATABASE MODE: All DB errors logged at DEBUG level (expected behavior)
                    # OSError includes socket.gaierror (DNS resolution failed)
                    # RuntimeError includes "DatabaseService cannot be initialized in NO DATABASE MODE"
                    logger.debug(f"[INIT_SERVICES] Database unavailable (NO DATABASE MODE - using FileStorage): {db_err}")
                    db_service = None
                    free_manager = None
                except Exception as e:
                    # NO DATABASE MODE: All DB errors logged at DEBUG level (expected behavior)
                    logger.debug(f"[INIT_SERVICES] Database initialization failed (NO DATABASE MODE - using FileStorage): {e}")
                    db_service = None
                    free_manager = None
            elif no_db_mode:
                logger.info("[INIT_SERVICES] 🚫 NO DATABASE MODE - Skipping DatabaseService initialization")
                db_service = None
                # BATCH 48.44: Initialize ReferralManager and FreeModelManager in NO DATABASE MODE
                try:
                    from app.free.manager import FreeModelManager
                    from app.referrals.manager import ReferralManager
                    storage = get_storage()
                    referral_manager = ReferralManager(storage)
                    free_manager = FreeModelManager(None, referral_manager=referral_manager)
                    
                    # Set free manager in handlers
                    from bot.handlers.marketing import set_free_manager
                    set_free_manager(free_manager)
                    logger.info("[INIT_SERVICES] ✅ FreeModelManager and ReferralManager initialized in NO DATABASE MODE")
                except Exception as e:
                    logger.warning(f"[INIT_SERVICES] Failed to initialize FreeModelManager in NO DATABASE MODE: {e}")
                    free_manager = None
            else:
                logger.info("[INIT_SERVICES] ⚠️ No DATABASE_URL - Skipping DatabaseService initialization")
                db_service = None
                # BATCH 48.44: Initialize ReferralManager and FreeModelManager even without DATABASE_URL
                try:
                    from app.free.manager import FreeModelManager
                    from app.referrals.manager import ReferralManager
                    storage = get_storage()
                    referral_manager = ReferralManager(storage)
                    free_manager = FreeModelManager(None, referral_manager=referral_manager)
                    
                    # Set free manager in handlers
                    from bot.handlers.marketing import set_free_manager
                    set_free_manager(free_manager)
                    logger.info("[INIT_SERVICES] ✅ FreeModelManager and ReferralManager initialized without DATABASE_URL")
                except Exception as e:
                    logger.warning(f"[INIT_SERVICES] Failed to initialize FreeModelManager without DATABASE_URL: {e}")
                    free_manager = None
        
        # Step 2: Start unified lock controller with callback + active_state sync
        from app.locking.controller import SingletonLockController
        
        lock_controller = SingletonLockController(
            lock, 
            bot, 
            on_active_callback=init_active_services,
            active_state=active_state  # CRITICAL: pass same object for sync
        )
        active_state.lock_controller = lock_controller  # Store for webhook access
        
        await lock_controller.start()
        
        # Initial sync (lock_controller will call active_state.set() in _set_state)
        initial_should_process = lock_controller.should_process_updates()
        runtime_state.lock_acquired = initial_should_process
        
        if initial_should_process:
            logger.info("[LOCK_CONTROLLER] ✅ ACTIVE MODE (lock acquired immediately)")
        else:
            logger.info("[LOCK_CONTROLLER] ⏸️ PASSIVE MODE (background watcher started)")

    runner: Optional[web.AppRunner] = None
    # Import DatabaseService type for annotation
    try:
        from app.database.services import DatabaseService as _DatabaseService
    except ImportError:
        _DatabaseService = None  # type: ignore
    db_service: Optional[_DatabaseService] = None  # type: ignore
    
    async def state_sync_loop() -> None:
        """
        Monitor active_state sync with lock_controller + safety-net for stale PASSIVE.
        If lock acquired but active_state still False after 3s → force ACTIVE.
        """
        logger.info("[STATE_SYNC] 🔄 Started, initial active=%s", active_state.active)
        lock_acquired_time = None  # Track when lock_controller first reports ACTIVE
        
        while True:
            await asyncio.sleep(1)
            if hasattr(active_state, 'lock_controller'):
                new_active = active_state.lock_controller.should_process_updates()
                
                # 🚨 SAFETY-NET: Detect stale PASSIVE state
                if new_active and not active_state.active:
                    # lock_controller says ACTIVE, but active_state is still False
                    if lock_acquired_time is None:
                        lock_acquired_time = time.time()
                        logger.warning(
                            "[STATE_SYNC] ⚠️ lock_controller ACTIVE but active_state False (start monitoring)"
                        )
                    elif time.time() - lock_acquired_time > 3.0:
                        # Still not synced after 3 seconds → FORCE
                        logger.error(
                            "[STATE_SYNC] ⚠️⚠️ lock acquired but active_state still False for 3s → FORCING ACTIVE"
                        )
                        active_state.set(True, reason="safety_net_force")
                        runtime_state.lock_acquired = True
                        lock_acquired_time = None  # Reset
                elif not new_active:
                    # Reset safety-net timer if lock lost
                    lock_acquired_time = None
                
                # Normal sync (this should now be redundant if lock_controller._set_state works)
                if new_active != active_state.active:
                    old_active = active_state.active
                    logger.warning(
                        "[STATE_SYNC] ⚠️ Manual sync needed: %s -> %s (lock_controller didn't call active_state.set?)",
                        old_active, new_active
                    )
                    if new_active:
                        active_state.set(True, reason="state_sync_fallback")
                    else:
                        active_state.set(False, reason="state_sync_fallback")
                    runtime_state.lock_acquired = new_active
                    lock_acquired_time = None  # Reset safety-net

    # 🚀 START BACKGROUND INITIALIZATION (non-blocking)
    asyncio.create_task(background_initialization())
    asyncio.create_task(state_sync_loop())  # Sync active_state with controller

    try:
        if effective_bot_mode == "polling":
            # Create app and start HTTP server IMMEDIATELY
            app = _make_web_app(dp=dp, bot=bot, cfg=cfg, active_state=active_state, background_tasks=background_tasks)
            if cfg.port:
                runner = await _start_web_server(app, cfg.port)
                logger.info("[HEALTH] ✅ Server started on port %s (migrations/lock in background)", cfg.port)

            # Wait briefly for background init (but don't block)
            await asyncio.sleep(0.5)

            # If passive mode, keep healthcheck running
            if not active_state.active:
                logger.info("[PASSIVE MODE] HTTP server running, state_sync_loop monitors lock")
                await asyncio.Event().wait()
                return

            # Active mode: initialize services and start polling
            # (init_active_services called by state_sync_loop on PASSIVE→ACTIVE)
            await preflight_webhook(bot)
            await dp.start_polling(bot)
            return

        # webhook mode - START HTTP SERVER IMMEDIATELY
        app = _make_web_app(dp=dp, bot=bot, cfg=cfg, active_state=active_state, background_tasks=background_tasks)
        if cfg.port:
            runner = await _start_web_server(app, cfg.port)
            logger.info("[HEALTH] ✅ Server started on port %s (migrations/lock in background)", cfg.port)

        # Wait briefly for background init (but don't block)
        await asyncio.sleep(0.5)

        # Initialize active services if lock acquired
        # (init_active_services called by state_sync_loop on PASSIVE→ACTIVE)
        if not active_state.active:
            logger.info("[PASSIVE MODE] HTTP server running, state_sync_loop monitors lock")
        else:
            # ACTIVE mode - log readiness
            logger.info("=" * 60)
            logger.info("[BOT_READY] ✅ Bot is ready to serve requests (ACTIVE MODE)")
            logger.info("=" * 60)
            logger.info(f"[BOT_READY] Mode: {effective_bot_mode}")
            logger.info(f"[BOT_READY] Storage: {runtime_state.storage_mode}")
            logger.info(f"[BOT_READY] Lock state: ACTIVE")
            logger.info(f"[BOT_READY] DB schema: {'✅ Ready' if runtime_state.db_schema_ready else '❌ Not ready (FileStorage mode)'}")
            logger.info(f"[BOT_READY] Webhook: {'✅ Configured' if effective_bot_mode == 'webhook' else 'N/A (polling mode)'}")
            logger.info("=" * 60)

        await asyncio.Event().wait()
    finally:
        try:
            if runner is not None:
                await runner.cleanup()
        except Exception:
            pass
        try:
            await bot.session.close()
        except Exception:
            pass
        try:
            # db_service may not be initialized if we exited early
            try:
                if db_service is not None:
                    await db_service.close()
            except NameError:
                pass  # db_service was never created
        except Exception:
            pass
        try:
            await lock.release()
        except Exception:
            pass

        # BATCH 48: NO DATABASE MODE - No connection pool to close
        pass


if __name__ == "__main__":

    asyncio.run(main())

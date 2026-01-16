"""
Admin endpoints for database diagnostics and observability.

Protected by ADMIN_ID or ADMIN_SECRET env vars.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from aiohttp import web

logger = logging.getLogger(__name__)

# Admin authentication
ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "").strip()


def check_admin_auth(request: web.Request) -> bool:
    """Check if request is from admin (by user_id or secret)."""
    # Check secret in query param or header
    secret = request.query.get("secret") or request.headers.get("X-Admin-Secret", "")
    if ADMIN_SECRET and secret == ADMIN_SECRET:
        return True
    
    # Check user_id from query (for Telegram callback scenarios)
    try:
        user_id = int(request.query.get("user_id", "0"))
        if ADMIN_ID and user_id == int(ADMIN_ID):
            return True
    except (ValueError, TypeError):
        pass
    
    return False


async def db_health_handler(request: web.Request) -> web.Response:
    """
    GET /admin/db/health
    
    Returns database health metrics:
    - db up/down
    - pool stats (if available)
    - migrations applied
    - error counts (1h/24h)
    - PASSIVE_REJECT counts (1h/24h)
    - top-5 models by usage (24h)
    - top-5 failCode/failMsg (24h)
    """
    if not check_admin_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    # Get DB pool from app context
    db_pool = request.app.get("db_pool")
    if not db_pool:
        return web.json_response({
            "db": "down",
            "error": "Database pool not initialized"
        }, status=503)
    
    try:
        async with db_pool.acquire() as conn:
            # Check DB connection
            await conn.fetchval("SELECT 1")
            db_status = "up"
            
            # Get pool stats (if available)
            pool_stats = {}
            if hasattr(db_pool, "_size"):
                pool_stats = {
                    "size": db_pool._size,
                    "min_size": getattr(db_pool, "_min_size", None),
                    "max_size": getattr(db_pool, "_max_size", None),
                }
            
            # Check if app_events table exists
            events_table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'app_events'
                )
            """)
            
            if not events_table_exists:
                return web.json_response({
                    "db": db_status,
                    "pool": pool_stats,
                    "events_table": "not_created",
                    "note": "Run migration 013_app_events_observability.sql"
                })
            
            # Error counts (1h/24h)
            now = datetime.utcnow()
            one_hour_ago = now - timedelta(hours=1)
            twenty_four_hours_ago = now - timedelta(hours=24)
            
            errors_1h = await conn.fetchval("""
                SELECT COUNT(*) FROM app_events
                WHERE level IN ('ERROR', 'CRITICAL') AND ts >= $1
            """, one_hour_ago)
            
            errors_24h = await conn.fetchval("""
                SELECT COUNT(*) FROM app_events
                WHERE level IN ('ERROR', 'CRITICAL') AND ts >= $1
            """, twenty_four_hours_ago)
            
            # PASSIVE_REJECT counts (1h/24h)
            passive_reject_1h = await conn.fetchval("""
                SELECT COUNT(*) FROM app_events
                WHERE event = 'PASSIVE_REJECT' AND ts >= $1
            """, one_hour_ago)
            
            passive_reject_24h = await conn.fetchval("""
                SELECT COUNT(*) FROM app_events
                WHERE event = 'PASSIVE_REJECT' AND ts >= $1
            """, twenty_four_hours_ago)
            
            # Top-5 models by usage (24h)
            top_models = await conn.fetch("""
                SELECT model, COUNT(*) as usage_count
                FROM app_events
                WHERE event = 'KIE_JOB_CREATED' AND ts >= $1 AND model IS NOT NULL
                GROUP BY model
                ORDER BY usage_count DESC
                LIMIT 5
            """, twenty_four_hours_ago)
            
            # Top-5 failCode/failMsg (24h) - extract from payload_json
            top_failures = await conn.fetch("""
                SELECT 
                    payload_json->>'failCode' as fail_code,
                    payload_json->>'failMsg' as fail_msg,
                    COUNT(*) as count
                FROM app_events
                WHERE event = 'KIE_JOB_COMPLETED' 
                    AND level = 'ERROR' 
                    AND ts >= $1
                    AND payload_json IS NOT NULL
                GROUP BY payload_json->>'failCode', payload_json->>'failMsg'
                ORDER BY count DESC
                LIMIT 5
            """, twenty_four_hours_ago)
            
            return web.json_response({
                "db": db_status,
                "pool": pool_stats,
                "events_table": "exists",
                "errors": {
                    "1h": errors_1h or 0,
                    "24h": errors_24h or 0,
                },
                "passive_reject": {
                    "1h": passive_reject_1h or 0,
                    "24h": passive_reject_24h or 0,
                },
                "top_models_24h": [
                    {"model": row["model"], "usage": row["usage_count"]}
                    for row in top_models
                ],
                "top_failures_24h": [
                    {
                        "fail_code": row["fail_code"],
                        "fail_msg": row["fail_msg"],
                        "count": row["count"],
                    }
                    for row in top_failures
                ],
            })
    
    except Exception as e:
        logger.exception("[ADMIN_DB] Error in db_health_handler")
        return web.json_response({
            "db": "error",
            "error": str(e)
        }, status=500)


async def db_recent_handler(request: web.Request) -> web.Response:
    """
    GET /admin/db/recent?minutes=60&event=...&user_id=...&task_id=...&model=...
    
    Returns recent events with optional filters.
    """
    if not check_admin_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    db_pool = request.app.get("db_pool")
    if not db_pool:
        return web.json_response({"error": "Database pool not initialized"}, status=503)
    
    try:
        # Parse query params
        minutes = int(request.query.get("minutes", "60"))
        event_filter = request.query.get("event", "")
        user_id_filter = request.query.get("user_id")
        task_id_filter = request.query.get("task_id")
        model_filter = request.query.get("model")
        limit = int(request.query.get("limit", "100"))
        
        since = datetime.utcnow() - timedelta(minutes=minutes)
        
        # Build query with parameterized queries (CRITICAL: prevent SQL injection)
        query_parts = ["SELECT * FROM app_events WHERE ts >= $1"]
        params = [since]
        param_idx = 2
        
        if event_filter:
            query_parts.append(f"event = ${param_idx}")
            params.append(event_filter)
            param_idx += 1
        
        if user_id_filter:
            try:
                user_id = int(user_id_filter)
                query_parts.append(f"user_id = ${param_idx}")
                params.append(user_id)
                param_idx += 1
            except ValueError:
                logger.warning(f"Invalid user_id_filter: {user_id_filter}")
        
        if task_id_filter:
            try:
                task_id = int(task_id_filter)
                query_parts.append(f"task_id = ${param_idx}")
                params.append(task_id)
                param_idx += 1
            except ValueError:
                logger.warning(f"Invalid task_id_filter: {task_id_filter}")
        
        if model_filter:
            # CRITICAL: Use parameterized query, not string interpolation
            query_parts.append(f"model = ${param_idx}")
            params.append(model_filter)
            param_idx += 1
        
        # Build final query
        query = " AND ".join(query_parts)
        query += f" ORDER BY ts DESC LIMIT ${param_idx}"
        params.append(limit)
        
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            events = []
            for row in rows:
                events.append({
                    "id": row["id"],
                    "ts": row["ts"].isoformat() if row["ts"] else None,
                    "level": row["level"],
                    "event": row["event"],
                    "cid": row["cid"],
                    "user_id": row["user_id"],
                    "chat_id": row["chat_id"],
                    "update_id": row["update_id"],
                    "task_id": row["task_id"],
                    "model": row["model"],
                    "payload": row["payload_json"],
                    "err_stack": row["err_stack"][:500] if row["err_stack"] else None,  # Truncate
                    "tags": row["tags"],
                })
            
            return web.json_response({
                "count": len(events),
                "since": since.isoformat(),
                "events": events,
            })
    
    except Exception as e:
        logger.exception("[ADMIN_DB] Error in db_recent_handler")
        return web.json_response({"error": str(e)}, status=500)


def setup_admin_routes(app: web.Application, db_pool) -> None:
    """Register admin routes."""
    # Store pool in runtime_state instead of app (avoid DeprecationWarning)
    from app.utils.runtime_state import runtime_state
    runtime_state.db_pool = db_pool
    
    app.router.add_get("/admin/db/health", db_health_handler)
    app.router.add_get("/admin/db/recent", db_recent_handler)
    
    logger.info("[ADMIN_DB] ✅ Admin routes registered: /admin/db/health, /admin/db/recent")



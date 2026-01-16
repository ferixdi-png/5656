"""
Database read-only diagnostics.

Connects to DATABASE_URL_READONLY and collects safe metrics.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    print("WARNING: asyncpg not available, using psycopg2 fallback", file=sys.stderr)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

from app.ops.observer_config import load_config, validate_config


async def fetch_metrics_async(conn: asyncpg.Connection) -> Dict[str, Any]:
    """Fetch metrics using asyncpg."""
    metrics = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "connection_ok": True,
    }
    
    try:
        # Test connection
        await conn.fetchval("SELECT 1")
        
        # pg_stat_activity counts
        try:
            activity = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_connections,
                    COUNT(*) FILTER (WHERE state = 'active') as active_connections,
                    COUNT(*) FILTER (WHERE state = 'idle') as idle_connections,
                    COUNT(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            if activity:
                metrics["pg_stat_activity"] = dict(activity)
        except Exception as e:
            metrics["pg_stat_activity"] = {"error": str(e)}
        
        # Current database connection limit
        try:
            max_conn = await conn.fetchval("SHOW max_connections")
            metrics["max_connections"] = int(max_conn) if max_conn else None
        except Exception:
            pass
        
        # Table sizes (main tables)
        try:
            table_sizes = await conn.fetch("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                    AND tablename IN ('users', 'wallets', 'ledger', 'jobs', 'app_events', 'ui_state')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)
            metrics["table_sizes"] = [dict(row) for row in table_sizes]
        except Exception as e:
            metrics["table_sizes"] = {"error": str(e)}
        
        # Slow queries (if pg_stat_statements exists)
        try:
            slow_queries = await conn.fetch("""
                SELECT 
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    max_exec_time
                FROM pg_stat_statements
                WHERE mean_exec_time > 100  -- > 100ms
                ORDER BY mean_exec_time DESC
                LIMIT 10
            """)
            metrics["slow_queries"] = [dict(row) for row in slow_queries]
        except Exception:
            # pg_stat_statements not available or no permission
            metrics["slow_queries"] = None
        
        # Recent errors from app_events (if table exists)
        try:
            error_count = await conn.fetchval("""
                SELECT COUNT(*) FROM app_events
                WHERE level IN ('ERROR', 'CRITICAL')
                    AND ts >= NOW() - INTERVAL '1 hour'
            """)
            metrics["recent_errors_1h"] = error_count
        except Exception:
            metrics["recent_errors_1h"] = None
        
    except Exception as e:
        metrics["connection_ok"] = False
        metrics["error"] = str(e)
    
    return metrics


def fetch_metrics_sync(conn) -> Dict[str, Any]:
    """Fetch metrics using psycopg2 (sync fallback)."""
    metrics = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "connection_ok": True,
    }
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Test connection
            cur.execute("SELECT 1")
            
            # pg_stat_activity counts
            try:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_connections,
                        COUNT(*) FILTER (WHERE state = 'active') as active_connections,
                        COUNT(*) FILTER (WHERE state = 'idle') as idle_connections,
                        COUNT(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """)
                row = cur.fetchone()
                if row:
                    metrics["pg_stat_activity"] = dict(row)
            except Exception as e:
                metrics["pg_stat_activity"] = {"error": str(e)}
            
            # Table sizes
            try:
                cur.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                    FROM pg_tables
                    WHERE schemaname = 'public'
                        AND tablename IN ('users', 'wallets', 'ledger', 'jobs', 'app_events', 'ui_state')
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                """)
                metrics["table_sizes"] = [dict(row) for row in cur.fetchall()]
            except Exception as e:
                metrics["table_sizes"] = {"error": str(e)}
            
            # Recent errors
            try:
                cur.execute("""
                    SELECT COUNT(*) FROM app_events
                    WHERE level IN ('ERROR', 'CRITICAL')
                        AND ts >= NOW() - INTERVAL '1 hour'
                """)
                metrics["recent_errors_1h"] = cur.fetchone()[0]
            except Exception:
                metrics["recent_errors_1h"] = None
    
    except Exception as e:
        metrics["connection_ok"] = False
        metrics["error"] = str(e)
    
    return metrics


async def main_async():
    """Async main."""
    import asyncio
    
    config = load_config()
    
    if not validate_config(config, require_db=True):
        print("ERROR: DATABASE_URL_READONLY required", file=sys.stderr)
        sys.exit(1)
    
    try:
        conn = await asyncpg.connect(config.database_url_readonly, timeout=10)
        try:
            metrics = await fetch_metrics_async(conn)
            return metrics
        finally:
            await conn.close()
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}", file=sys.stderr)
        sys.exit(1)


def main_sync():
    """Sync main (fallback)."""
    config = load_config()
    
    if not validate_config(config, require_db=True):
        print("ERROR: DATABASE_URL_READONLY required", file=sys.stderr)
        sys.exit(1)
    
    try:
        conn = psycopg2.connect(config.database_url_readonly, connect_timeout=10)
        try:
            metrics = fetch_metrics_sync(conn)
            return metrics
        finally:
            conn.close()
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Database read-only diagnostics")
    parser.add_argument(
        "--out",
        type=str,
        default="artifacts/db_diag_latest.json",
        help="Output file path (default: artifacts/db_diag_latest.json)"
    )
    
    args = parser.parse_args()
    
    # Try async first, fallback to sync
    if HAS_ASYNCPG:
        import asyncio
        metrics = asyncio.run(main_async())
    elif HAS_PSYCOPG2:
        metrics = main_sync()
    else:
        print("ERROR: Neither asyncpg nor psycopg2 available", file=sys.stderr)
        sys.exit(1)
    
    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    
    print(f"✅ Saved to {out_path}", file=sys.stderr)
    sys.exit(0 if metrics.get("connection_ok") else 1)


if __name__ == "__main__":
    main()


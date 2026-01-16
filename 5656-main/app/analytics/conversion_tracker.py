"""
Conversion tracking for lead magnet → paid user funnel.

Tracks key events:
- free_generation_start
- free_generation_success
- upsell_shown
- upsell_click_topup
- upsell_click_premium
- upsell_click_repeat_free
- first_paid_generation

Storage: PostgreSQL (analytics_events table)
"""
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


async def track_conversion_event(
    event_type: str,
    user_id: int,
    model_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> None:
    """
    Track a conversion funnel event.
    
    Args:
        event_type: Type of event (free_generation_start, upsell_shown, etc.)
        user_id: User ID
        model_id: Model ID (optional)
        metadata: Additional metadata (optional)
    """
    try:
        from app.storage.factory import get_storage
        storage = get_storage()
        
        # Log to database (best-effort, non-blocking)
        async with storage._get_pool() as pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO analytics_events (
                        event_type,
                        user_id,
                        model_id,
                        metadata,
                        created_at
                    ) VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    event_type,
                    user_id,
                    model_id,
                    metadata or {}
                )
        
        logger.info(
            f"[CONVERSION] event={event_type} user={user_id} model={model_id}"
        )
    
    except Exception as e:
        # FAIL-OPEN: Don't block user flow on analytics failure
        logger.debug(f"Failed to track conversion event: {e}")


async def get_conversion_stats(user_id: Optional[int] = None) -> dict:
    """
    Get conversion funnel stats.
    
    Args:
        user_id: Filter by user ID (optional, default: all users)
        
    Returns:
        Dict with funnel metrics
    """
    try:
        from app.storage.factory import get_storage
        storage = get_storage()
        
        async with storage._get_pool() as pool:
            async with pool.acquire() as conn:
                # Count events by type
                where_clause = "WHERE user_id = $1" if user_id else ""
                params = [user_id] if user_id else []
                
                rows = await conn.fetch(
                    f"""
                    SELECT
                        event_type,
                        COUNT(*) as count,
                        COUNT(DISTINCT user_id) as unique_users
                    FROM analytics_events
                    {where_clause}
                    GROUP BY event_type
                    ORDER BY count DESC
                    """,
                    *params
                )
                
                stats = {row['event_type']: {
                    'count': row['count'],
                    'unique_users': row['unique_users']
                } for row in rows}
                
                # Calculate conversion rates
                free_gens = stats.get('free_generation_success', {}).get('count', 0)
                upsell_shown = stats.get('upsell_shown', {}).get('count', 0)
                topup_clicks = stats.get('upsell_click_topup', {}).get('count', 0)
                
                conversion_rate = (topup_clicks / upsell_shown * 100) if upsell_shown > 0 else 0
                
                return {
                    'events': stats,
                    'funnel': {
                        'free_generations': free_gens,
                        'upsell_impressions': upsell_shown,
                        'topup_clicks': topup_clicks,
                        'conversion_rate': round(conversion_rate, 2)
                    }
                }
    
    except Exception as e:
        logger.error(f"Failed to get conversion stats: {e}")
        return {'events': {}, 'funnel': {}}


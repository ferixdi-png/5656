"""
Integration layer for providers - bridges existing code with new provider system.

This allows gradual migration while ensuring DRY_RUN is enforced.
"""
import os
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def is_dry_run() -> bool:
    """Check if DRY_RUN mode is enabled."""
    return os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")


def get_kie_provider_wrapper():
    """
    Get KIE provider wrapper - returns provider if DRY_RUN, None otherwise.
    
    This allows existing code to check if provider should be used.
    """
    if is_dry_run():
        from app.providers.kie_provider import get_kie_provider
        return get_kie_provider()
    return None


def get_payment_provider_wrapper():
    """
    Get payment provider wrapper - returns provider if DRY_RUN, None otherwise.
    
    This allows existing code to check if provider should be used.
    """
    if is_dry_run():
        from app.providers.payment_provider import get_payment_provider
        return get_payment_provider()
    return None


async def create_kie_task_via_provider(
    model_id: str,
    input_data: Dict[str, Any],
    callback_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Create KIE task via provider if DRY_RUN, otherwise return None (use existing code).
    
    Returns:
        Result dict if DRY_RUN, None if real mode (existing code should handle)
    """
    if not is_dry_run():
        return None
    
    provider = get_kie_provider_wrapper()
    if provider:
        result = await provider.create_task(model_id, input_data, callback_url)
        if result.is_success:
            return result.data
        else:
            return {
                "ok": False,
                "error": result.error,
                "error_code": result.error_code
            }
    return None


async def get_kie_task_status_via_provider(
    task_id: str,
    model_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get KIE task status via provider if DRY_RUN, otherwise return None (use existing code).
    
    Returns:
        Status dict if DRY_RUN, None if real mode (existing code should handle)
    """
    if not is_dry_run():
        return None
    
    provider = get_kie_provider_wrapper()
    if provider:
        result = await provider.get_task_status(task_id, model_id)
        if result.is_success:
            return result.data
        else:
            return {
                "ok": False,
                "error": result.error,
                "error_code": result.error_code,
                "state": "fail"
            }
    return None


def get_preview_result_for_user(
    task_id: str,
    model_id: str,
    prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get beautiful preview result for user in DRY_RUN mode.
    
    Returns:
        Dict with preview_urls and preview_text for user display
    """
    if not is_dry_run():
        return {}
    
    provider = get_kie_provider_wrapper()
    if provider and hasattr(provider, '_get_mock_result_urls'):
        preview_urls = provider._get_mock_result_urls(model_id, prompt)
        preview_text = provider._get_mock_preview_text(model_id, prompt)
        return {
            "preview_urls": preview_urls,
            "preview_text": preview_text
        }
    return {}


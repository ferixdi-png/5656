"""
Unified Kie.ai state parser for callback and polling.

Handles API contract:
- payload.code (200 = success API call)
- payload.msg
- payload.data.state (waiting/running/success/fail)
- payload.data.resultJson (JSON string containing resultUrls)
- payload.data.failMsg

Usage:
    state, result_urls, error = parse_kie_state(payload)
"""
import json
import logging
from typing import Dict, Any, Tuple, List, Optional

logger = logging.getLogger(__name__)


def parse_kie_state(payload: Dict[str, Any], corr_id: str = "") -> Tuple[str, List[str], Optional[str]]:
    """
    Parse Kie.ai API response (works for both callback and recordInfo).
    
    Args:
        payload: API response dict
        corr_id: Correlation ID for logging
    
    Returns:
        (state, result_urls, error_msg)
        - state: 'waiting'|'running'|'success'|'fail'|'unknown'
        - result_urls: List of URLs (empty if not success)
        - error_msg: Error message if fail, None otherwise
    """
    prefix = f"[{corr_id}] " if corr_id else ""
    
    # Check API-level success
    api_code = payload.get('code')
    if api_code and api_code != 200:
        api_msg = payload.get('msg', 'Unknown API error')
        logger.warning(f"{prefix}API error code={api_code}: {api_msg}")
        return 'fail', [], f"API error [{api_code}]: {api_msg}"
    
    # Extract data object
    data = payload.get('data', {})
    if not isinstance(data, dict):
        logger.warning(f"{prefix}Invalid payload.data (not dict)")
        return 'unknown', [], "Invalid API response"
    
    # Extract state
    state = data.get('state', '').lower()
    if state not in ('waiting', 'running', 'success', 'fail'):
        logger.warning(f"{prefix}Unknown state={state}")
        state = 'unknown'
    
    logger.debug(f"{prefix}Parsed state={state}")
    
    # Handle fail
    if state == 'fail':
        fail_msg = data.get('failMsg') or data.get('error') or 'Unknown error'
        logger.info(f"{prefix}FAIL: {fail_msg}")
        return 'fail', [], fail_msg
    
    # Handle success
    if state == 'success':
        result_urls = []
        
        # Parse resultJson (JSON string!)
        result_json_str = data.get('resultJson')
        if result_json_str:
            try:
                if isinstance(result_json_str, str):
                    # CRITICAL: Handle malformed JSON gracefully
                    try:
                        result_data = json.loads(result_json_str)
                    except json.JSONDecodeError as json_err:
                        logger.error(f"{prefix}Failed to parse resultJson as JSON: {json_err}. Raw: {result_json_str[:200]}...")
                        # Try to extract URLs from malformed JSON as fallback
                        import re
                        url_pattern = r'https?://[^\s"\'<>]+'
                        extracted_urls = re.findall(url_pattern, result_json_str)
                        if extracted_urls:
                            result_urls = extracted_urls[:10]  # Limit to 10 URLs
                            logger.warning(f"{prefix}Extracted {len(result_urls)} URLs from malformed JSON using regex")
                        else:
                            result_data = {}  # Fallback to empty dict
                    else:
                        result_data = result_data  # Use parsed data
                else:
                    result_data = result_json_str
                
                # Extract resultUrls
                if isinstance(result_data, dict):
                    urls = result_data.get('resultUrls') or result_data.get('urls') or []
                    # CRITICAL: Validate that urls is not None and filter out empty/null values
                    if urls is None:
                        urls = []
                    if isinstance(urls, list):
                        result_urls = [str(url) for url in urls if url and url.strip()]  # Filter out None, empty, and whitespace-only URLs
                    elif isinstance(urls, str) and urls.strip():
                        result_urls = [urls]
                    else:
                        result_urls = []
                
                if result_urls:
                    logger.info(f"{prefix}SUCCESS: {len(result_urls)} URL(s) parsed from resultJson")
            except Exception as e:
                # CRITICAL: Catch all exceptions to prevent crashes on malformed responses
                logger.error(f"{prefix}Unexpected error parsing resultJson: {e}", exc_info=True)
                logger.debug(f"{prefix}resultJson value: {str(result_json_str)[:200]}...")
        
        # Fallback: direct resultUrls field
        if not result_urls:
            direct_urls = data.get('resultUrls')
            # CRITICAL: Validate that direct_urls is not None and filter out empty/null values
            if direct_urls is not None:
                if isinstance(direct_urls, list):
                    result_urls = [str(url) for url in direct_urls if url and url.strip()]  # Filter out None, empty, and whitespace-only URLs
                elif isinstance(direct_urls, str) and direct_urls.strip():
                    result_urls = [direct_urls]
        
        if not result_urls:
            logger.warning(f"{prefix}SUCCESS but no resultUrls found")
            return 'success', [], None  # Success but empty result
        
        return 'success', result_urls, None
    
    # waiting/running - no action needed
    return state, [], None


def extract_task_id(payload: Dict[str, Any]) -> Optional[str]:
    """Extract taskId from callback/response."""
    # Try different locations
    task_id = (
        payload.get('taskId') or
        payload.get('task_id') or
        payload.get('recordId') or
        (payload.get('data', {}).get('taskId') if isinstance(payload.get('data'), dict) else None) or
        (payload.get('data', {}).get('recordId') if isinstance(payload.get('data'), dict) else None)
    )
    return str(task_id) if task_id else None

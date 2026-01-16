"""
Universal parser for Kie.ai recordInfo responses.
Handles state=waiting/success/fail with proper error messages.
"""
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def parse_record_info(record_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse recordInfo response from Kie.ai API.
    
    Args:
        record_info: Raw recordInfo dictionary from API
        
    Returns:
        Parsed result with:
        - state: 'waiting', 'success', 'fail', 'unknown'
        - message: Human-readable message
        - result_urls: List of result URLs (if success)
        - result_object: Parsed result object (if success)
        - error_code: Error code (if fail)
        - error_message: Error message (if fail)
    """
    result = {
        'state': 'unknown',
        'message': '',
        'result_urls': [],
        'result_object': None,
        'error_code': None,
        'error_message': None,
        'raw': record_info
    }
    
    # BATCH 48.41: Aligned with official KIE.ai API documentation
    # Official format: {"code": 200, "data": {"state": "waiting|success|fail", ...}}
    # Always check 'data' field first (official API structure)
    main_obj = record_info
    if 'data' in record_info and isinstance(record_info['data'], dict):
        main_obj = record_info['data']
    
    # Extract state from main_obj (data field) according to official docs
    # Official API uses 'state' field (not 'status')
    state_raw = (
        main_obj.get('state') or  # Official API field
        main_obj.get('status') or  # Fallback for backward compatibility
        record_info.get('state') or  # Fallback if no 'data' field
        record_info.get('status') or  # Fallback for old format
        ''
    ).lower()
    
    # Extract state for initial result
    state = state_raw if state_raw else 'pending'
    
    # Normalize state to canonical: done, fail, pending
    if state_raw in ('success', 'succeed', 'done', 'completed', 'finished'):
        state = 'done'
    elif state_raw in ('fail', 'failed', 'error'):
        state = 'fail'
    elif state_raw in ('waiting', 'pending', 'processing', 'running', 'in_progress'):
        state = 'pending'
    else:
        state = state_raw if state_raw else 'pending'  # default to pending if unsure
    
    result['state'] = state
    result['is_done'] = state == 'done'
    result['is_failed'] = state == 'fail'
    
    if state == 'pending':
        # Extract progress info if available
        progress_percent = main_obj.get('progress', 0)
        eta_seconds = main_obj.get('eta')
        
        if progress_percent and progress_percent > 0:
            result['message'] = f"⏳ Генерация: {progress_percent}% готово"
        elif eta_seconds:
            result['message'] = f"⏳ Генерация... (осталось ~{eta_seconds}с)"
        else:
            result['message'] = "⏳ Генерация в процессе..."
        
        result['progress'] = progress_percent
        result['eta'] = eta_seconds
        return result
    
    elif state == 'done':
        # Parse resultJson
        result_json = main_obj.get('resultJson') or main_obj.get('result_json')
        if result_json:
            try:
                # Handle string JSON
                if isinstance(result_json, str):
                    result_json = json.loads(result_json)
                
                # Extract resultUrls
                if isinstance(result_json, dict):
                    result['result_object'] = result_json
                    
                    # Try different keys for URLs
                    url_keys = ['resultUrls', 'result_urls', 'urls', 'results', 'output', 'files']
                    for key in url_keys:
                        if key in result_json:
                            urls = result_json[key]
                            if isinstance(urls, list):
                                result['result_urls'] = [str(url) for url in urls if url]
                            elif isinstance(urls, str):
                                result['result_urls'] = [urls]
                            break
                    
                    # If no URLs found, check if result_json itself is a URL
                    if not result['result_urls']:
                        # Check if the whole object is a URL string
                        if isinstance(result_json, str) and (
                            result_json.startswith('http://') or 
                            result_json.startswith('https://')
                        ):
                            result['result_urls'] = [result_json]
                # After parsing JSON, if result_json is now a string (was JSON string with URL)
                elif isinstance(result_json, str):
                    if result_json.startswith(('http://', 'https://')):
                        result['result_urls'] = [result_json]
                elif isinstance(result_json, list):
                    # List of URLs or objects
                    for item in result_json:
                        if isinstance(item, str) and (
                            item.startswith('http://') or 
                            item.startswith('https://')
                        ):
                            result['result_urls'].append(item)
                        elif isinstance(item, dict):
                            # Try to extract URL from object
                            for url_key in ['url', 'link', 'file', 'result']:
                                if url_key in item and isinstance(item[url_key], str):
                                    if item[url_key].startswith(('http://', 'https://')):
                                        result['result_urls'].append(item[url_key])
                                        break
                    result['result_object'] = result_json
                
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to parse resultJson: {e}")
                # Try to extract URL from raw string
                if isinstance(result_json, str):
                    if result_json.startswith(('http://', 'https://')):
                        result['result_urls'] = [result_json]
        
        # Also check direct resultUrls field
        if not result['result_urls']:
            direct_urls = main_obj.get('resultUrls') or main_obj.get('result_urls')
            if direct_urls:
                if isinstance(direct_urls, list):
                    result['result_urls'] = [str(url) for url in direct_urls if url]
                elif isinstance(direct_urls, str):
                    result['result_urls'] = [direct_urls]
        
        if result['result_urls']:
            result['message'] = f"✅ Готово! Результатов: {len(result['result_urls'])}"
        else:
            result['message'] = "✅ Задача выполнена успешно"
        
        return result
    
    elif state == 'fail':
        # Extract error information
        fail_msg = (
            main_obj.get('failMsg') or 
            main_obj.get('fail_message') or 
            main_obj.get('error') or
            main_obj.get('errorMessage') or
            record_info.get('failMsg') or 
            record_info.get('fail_message')
        )
        fail_code = (
            main_obj.get('failCode') or 
            main_obj.get('fail_code') or 
            main_obj.get('error_code') or
            main_obj.get('code') or
            record_info.get('failCode')
        )
        
        result['error_code'] = fail_code
        result['error_message'] = fail_msg
        
        # Generate human-readable message
        if fail_code and fail_msg:
            result['message'] = f"❌ Ошибка [{fail_code}]: {fail_msg}"
        elif fail_msg:
            result['message'] = f"❌ Ошибка: {fail_msg}"
        elif fail_code:
            result['message'] = f"❌ Ошибка: код {fail_code}"
        else:
            result['message'] = "❌ Задача завершилась с ошибкой"
        
        return result
    
    else:
        result['message'] = f"⚠️ Неизвестное состояние: {state_raw}"
        return result


def get_human_readable_error(fail_code: Optional[str], fail_msg: Optional[str]) -> str:
    """Get human-readable error message from fail code and message."""
    # Common error codes mapping
    error_messages = {
        'INVALID_INPUT': 'Некорректные входные данные',
        'MODEL_NOT_FOUND': 'Модель не найдена',
        'RATE_LIMIT': 'Превышен лимит запросов, попробуйте позже',
        'TIMEOUT': 'Превышено время ожидания',
        'SERVER_ERROR': 'Ошибка сервера, попробуйте позже',
        'INSUFFICIENT_CREDITS': 'Недостаточно кредитов',
        'INVALID_FILE': 'Некорректный файл',
        'FILE_TOO_LARGE': 'Файл слишком большой',
    }
    
    if fail_code and fail_code in error_messages:
        base_message = error_messages[fail_code]
        if fail_msg:
            return f"{base_message}: {fail_msg}"
        return base_message
    
    if fail_msg:
        return fail_msg
    
    if fail_code:
        return f"Ошибка: {fail_code}"
    
    return "Произошла неизвестная ошибка"


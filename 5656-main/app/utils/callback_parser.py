"""
Robust callback payload parser for KIE callbacks.
Handles multiple payload formats without throwing exceptions.
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_task_id(
    payload: Any,
    query_params: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Extract taskId/recordId from KIE callback payload.
    
    Handles:
    - String JSON
    - Bytes (utf-8)
    - Dict with various nesting patterns
    - Query parameters
    - Array wrappers
    - Multiple field name variations (taskId, task_id, recordId, record_id, id)
    
    Args:
        payload: Raw payload (str, bytes, dict, list, etc.)
        query_params: URL query parameters (optional)
        headers: HTTP headers (optional)
    
    Returns:
        (task_id, record_id, debug_info):
            - task_id: str or None
            - record_id: str or None (secondary ID if available)
            - debug_info: dict with extraction details
    
    NEVER raises exceptions - always returns safe tuple.
    """
    debug_info = {
        "payload_type": type(payload).__name__,
        "extraction_path": [],
        "errors": []
    }
    
    # Step 1: Normalize payload to dict
    normalized_payload = None
    
    try:
        # Handle bytes
        if isinstance(payload, bytes):
            try:
                payload = payload.decode('utf-8')
                debug_info["extraction_path"].append("decoded_bytes")
            except Exception as e:
                debug_info["errors"].append(f"bytes_decode_failed: {e}")
                return None, None, debug_info
        
        # Handle string
        if isinstance(payload, str):
            try:
                normalized_payload = json.loads(payload)
                debug_info["extraction_path"].append("parsed_json_string")
            except json.JSONDecodeError as e:
                debug_info["errors"].append(f"json_parse_failed: {e}")
                # Try query params as fallback
                if query_params:
                    return _extract_from_query(query_params, debug_info)
                return None, None, debug_info
        
        # Handle dict directly
        elif isinstance(payload, dict):
            normalized_payload = payload
            debug_info["extraction_path"].append("dict_payload")
        
        # Handle list/array wrapper
        elif isinstance(payload, list):
            if len(payload) > 0:
                normalized_payload = payload[0] if isinstance(payload[0], dict) else {"items": payload}
                debug_info["extraction_path"].append("unwrapped_array")
            else:
                debug_info["errors"].append("empty_array")
                return None, None, debug_info
        
        else:
            debug_info["errors"].append(f"unsupported_type: {type(payload)}")
            return None, None, debug_info
        
    except Exception as e:
        debug_info["errors"].append(f"normalization_failed: {e}")
        return None, None, debug_info
    
    # Step 2: Extract IDs from normalized dict
    if normalized_payload and isinstance(normalized_payload, dict):
        task_id, record_id = _extract_from_dict(normalized_payload, debug_info)
        
        # If nothing found in payload, try query params
        if not task_id and not record_id and query_params:
            return _extract_from_query(query_params, debug_info)
        
        return task_id, record_id, debug_info
    
    # Fallback: try query params
    if query_params:
        return _extract_from_query(query_params, debug_info)
    
    debug_info["errors"].append("no_extraction_possible")
    return None, None, debug_info


def _extract_from_dict(data: Dict[str, Any], debug_info: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract IDs from dict using DFS search.
    
    Checks:
    - Root level: taskId, task_id, recordId, record_id, id
    - Nested fields: data.*, result.*, payload.*
    - Deep search: recursive DFS through all nested dicts
    """
    task_id = None
    record_id = None
    
    # Define field names to search (in priority order)
    task_id_fields = ["taskId", "task_id", "task", "job_id", "jobId"]
    record_id_fields = ["recordId", "record_id", "record"]
    generic_id_fields = ["id", "ID", "_id"]
    
    # Level 1: Check root level
    for field in task_id_fields:
        if field in data and data[field]:
            task_id = str(data[field])
            debug_info["extraction_path"].append(f"root.{field}")
            break
    
    for field in record_id_fields:
        if field in data and data[field]:
            record_id = str(data[field])
            debug_info["extraction_path"].append(f"root.{field}")
            break
    
    # If found both, return
    if task_id and record_id:
        return task_id, record_id
    
    # Level 2: Check common nested paths
    nested_containers = ["data", "result", "payload", "response", "body"]
    for container in nested_containers:
        if container in data and isinstance(data[container], dict):
            nested = data[container]
            
            if not task_id:
                for field in task_id_fields:
                    if field in nested and nested[field]:
                        task_id = str(nested[field])
                        debug_info["extraction_path"].append(f"{container}.{field}")
                        break
            
            if not record_id:
                for field in record_id_fields:
                    if field in nested and nested[field]:
                        record_id = str(nested[field])
                        debug_info["extraction_path"].append(f"{container}.{field}")
                        break
            
            if task_id and record_id:
                return task_id, record_id
    
    # Level 3: DFS through entire structure
    if not task_id or not record_id:
        task_id_dfs, record_id_dfs = _dfs_search(data, task_id_fields, record_id_fields, debug_info)
        task_id = task_id or task_id_dfs
        record_id = record_id or record_id_dfs
    
    # Level 4: Fallback to generic "id" field
    if not task_id and not record_id:
        for field in generic_id_fields:
            if field in data and data[field]:
                task_id = str(data[field])
                debug_info["extraction_path"].append(f"fallback.{field}")
                break
    
    return task_id, record_id


def _dfs_search(
    obj: Any,
    task_fields: list,
    record_fields: list,
    debug_info: Dict[str, Any],
    path: str = "",
    max_depth: int = 10,
    current_depth: int = 0
) -> Tuple[Optional[str], Optional[str]]:
    """
    Deep recursive search for task/record IDs.
    """
    if current_depth >= max_depth:
        return None, None
    
    task_id = None
    record_id = None
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            
            # Check if this key matches
            if key in task_fields and value:
                task_id = str(value)
                debug_info["extraction_path"].append(f"dfs.{current_path}")
            
            if key in record_fields and value:
                record_id = str(value)
                debug_info["extraction_path"].append(f"dfs.{current_path}")
            
            # Early exit if found both
            if task_id and record_id:
                return task_id, record_id
            
            # Recurse into nested structures
            if isinstance(value, (dict, list)):
                nested_task, nested_record = _dfs_search(
                    value, task_fields, record_fields, debug_info,
                    current_path, max_depth, current_depth + 1
                )
                task_id = task_id or nested_task
                record_id = record_id or nested_record
                
                if task_id and record_id:
                    return task_id, record_id
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            current_path = f"{path}[{i}]" if path else f"[{i}]"
            if isinstance(item, (dict, list)):
                nested_task, nested_record = _dfs_search(
                    item, task_fields, record_fields, debug_info,
                    current_path, max_depth, current_depth + 1
                )
                task_id = task_id or nested_task
                record_id = record_id or nested_record
                
                if task_id and record_id:
                    return task_id, record_id
    
    return task_id, record_id


def _extract_from_query(query_params: Dict[str, str], debug_info: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """Extract from URL query parameters."""
    task_id = None
    record_id = None
    
    # Check query params
    task_fields = ["taskId", "task_id", "task", "id"]
    record_fields = ["recordId", "record_id", "record"]
    
    for field in task_fields:
        if field in query_params:
            task_id = query_params[field]
            debug_info["extraction_path"].append(f"query.{field}")
            break
    
    for field in record_fields:
        if field in query_params:
            record_id = query_params[field]
            debug_info["extraction_path"].append(f"query.{field}")
            break
    
    if not task_id and not record_id:
        debug_info["errors"].append("no_ids_in_query_params")
    
    return task_id, record_id, debug_info


def safe_truncate_payload(payload: Any, max_length: int = 500) -> str:
    """
    Safely truncate payload for logging without throwing exceptions.
    """
    try:
        if isinstance(payload, (dict, list)):
            payload_str = json.dumps(payload, ensure_ascii=False)
        else:
            payload_str = str(payload)
        
        if len(payload_str) > max_length:
            return payload_str[:max_length] + "... (truncated)"
        return payload_str
    except Exception:
        return f"<{type(payload).__name__} object - cannot serialize>"

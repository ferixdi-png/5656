"""Kie.ai contract utilities for payloads and responses."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Tuple

from app.kie.builder import build_payload
from app.kie.parser import get_human_readable_error


def normalize_base_url(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if base.endswith("/api/v1"):
        base = base[: -len("/api/v1")]
    return base


def build_create_task_payload(model_spec: Dict[str, Any], user_inputs: Dict[str, Any]) -> Dict[str, Any]:
    model_id = model_spec.get("model_id")
    if not model_id:
        raise ValueError("model_id is required")
    return build_payload(model_id, user_inputs, {"models": [model_spec]})


def build_create_task_url(base_url: str) -> str:
    base = normalize_base_url(base_url)
    return f"{base}/api/v1/jobs/createTask"


def build_record_info_url(base_url: str) -> str:
    base = normalize_base_url(base_url)
    return f"{base}/api/v1/jobs/recordInfo"


def parse_result(record_info: Dict[str, Any]) -> Dict[str, Any]:
    result_urls = []
    result_object = None
    payload = record_info.get("resultJson")
    if payload:
        try:
            result_object = payload if isinstance(payload, dict) else json.loads(payload)
        except json.JSONDecodeError:
            result_object = {"raw": payload}
    if isinstance(result_object, dict):
        urls = result_object.get("resultUrls") or result_object.get("result_urls") or []
        if isinstance(urls, str):
            urls = [urls]
        result_urls.extend(urls)
        single_url = result_object.get("resultUrl") or result_object.get("result_url")
        if single_url:
            result_urls.append(single_url)
    if not result_urls and isinstance(payload, str):
        result_urls.extend(re.findall(r"https?://[^\\s\"']+", payload))
    direct_urls = record_info.get("resultUrls") or []
    if isinstance(direct_urls, str):
        direct_urls = [direct_urls]
    result_urls.extend(direct_urls)
    if record_info.get("resultUrl"):
        result_urls.append(record_info.get("resultUrl"))
    return {
        "result_urls": [url for url in result_urls if url],
        "result_object": result_object,
    }


def parse_failure(record_info: Dict[str, Any]) -> Tuple[str, str]:
    error_code = record_info.get("failCode") or record_info.get("errorCode") or "UNKNOWN"
    error_message = record_info.get("failMsg") or record_info.get("error") or ""
    human_message = get_human_readable_error(error_code, error_message)
    if not error_message and (not human_message or human_message.startswith("Ошибка:")):
        human_message = f"Ошибка генерации (код {error_code}). Попробуйте поменять параметры или модель."
    return error_code, human_message

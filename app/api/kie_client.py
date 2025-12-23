"""
Kie.ai API client.
Strictly uses:
- POST /api/v1/jobs/createTask
- GET /api/v1/jobs/recordInfo
"""
import asyncio
import logging
import os
from typing import Dict, Any

import requests

from app.kie.contract import build_create_task_url, build_record_info_url, normalize_base_url

logger = logging.getLogger(__name__)


class KieApiClient:
    """Minimal, strict Kie.ai API client."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or os.getenv("KIE_API_KEY")
        if not self.api_key:
            raise ValueError("KIE_API_KEY environment variable is required")
        raw_base = base_url or os.getenv("KIE_BASE_URL") or ""
        self.base_url = normalize_base_url(raw_base)
        if not self.base_url:
            raise ValueError("KIE_BASE_URL environment variable is required")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _request_with_retries(self, method: str, url: str, payload: Dict[str, Any], retries: int = 2) -> Dict[str, Any]:
        for attempt in range(retries + 1):
            try:
                if method == "post":
                    return self._post(url, payload)
                return self._get(url, payload)
            except requests.RequestException as exc:
                logger.warning("Kie request failed (%s/%s): %s", attempt + 1, retries + 1, exc)
                if attempt >= retries:
                    raise
        raise requests.RequestException("Kie request retries exhausted")

    async def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create Kie.ai task."""
        url = build_create_task_url(self.base_url)
        try:
            return await asyncio.to_thread(self._request_with_retries, "post", url, payload)
        except requests.RequestException as exc:
            logger.error("Kie createTask failed: %s", exc, exc_info=True)
            return {"error": str(exc), "state": "fail"}

    async def get_record_info(self, task_id: str) -> Dict[str, Any]:
        """Get Kie.ai task record info."""
        url = build_record_info_url(self.base_url)
        payload = {"taskId": task_id}
        try:
            return await asyncio.to_thread(self._request_with_retries, "get", url, payload)
        except requests.RequestException as exc:
            logger.error("Kie recordInfo failed: %s", exc, exc_info=True)
            return {"error": str(exc), "state": "fail"}

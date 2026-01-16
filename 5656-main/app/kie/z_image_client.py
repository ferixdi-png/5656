"""
Lightweight Kie.ai client for z-image model.

Official API:
- POST https://api.kie.ai/api/v1/jobs/createTask
  Body: {"model": "z-image", "input": {"prompt": "...", "aspect_ratio": "1:1"}}
  Response: {"code": 200, "data": {"taskId": "..."}}

- GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId=...
  Response: {"code": 200, "data": {"status": "SUCCESS", "output": {"image_url": "..."}}}

Aspect ratios: 1:1, 16:9, 9:16, 4:3, 3:4

This client DOES NOT log API keys or secrets.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Kie.ai task statuses."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ZImageResult:
    """Result from z-image generation."""
    task_id: str
    status: TaskStatus
    image_url: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[dict] = None


class ZImageClient:
    """
    Client for Kie.ai z-image model.
    
    Features:
    - Automatic retries with exponential backoff
    - Timeout protection
    - No secret logging
    - Async/await interface
    """
    
    BASE_URL = "https://api.kie.ai/api/v1/jobs"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("KIE_API_KEY", "")
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.api_key:
            logger.warning("[KIE] API key not set, operations will fail")
    
    async def create_task(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        callback_url: Optional[str] = None,
    ) -> ZImageResult:
        """
        Create z-image generation task.
        
        Args:
            prompt: Text prompt for image generation
            aspect_ratio: One of: 1:1, 16:9, 9:16, 4:3, 3:4
            callback_url: Optional webhook for completion notification
        
        Returns:
            ZImageResult with task_id and PENDING status
        
        Raises:
            Exception if API call fails after retries
        """
        if not self.api_key:
            raise ValueError("KIE_API_KEY not configured")
        
        # Validate aspect ratio
        valid_ratios = {"1:1", "16:9", "9:16", "4:3", "3:4"}
        if aspect_ratio not in valid_ratios:
            logger.warning(
                "[KIE] Invalid aspect_ratio=%s, using 1:1", 
                aspect_ratio
            )
            aspect_ratio = "1:1"
        
        # Build request
        payload = {
            "model": "z-image",
            "input": {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
            }
        }
        
        if callback_url:
            payload["callBackUrl"] = callback_url
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        url = f"{self.BASE_URL}/createTask"
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await asyncio.wait_for(
                        client.post(url, json=payload, headers=headers),
                        timeout=self.timeout
                    )
                    
                    # Check HTTP status
                    if resp.status_code != 200:
                        raise Exception(
                            f"HTTP {resp.status_code}: {resp.text[:200]}"
                        )
                    
                    # Parse response
                    data = resp.json()
                    
                    # Check API code
                    code = data.get("code")
                    if code != 200:
                        msg = data.get("msg", "Unknown error")
                        raise Exception(f"API error code={code}: {msg}")
                    
                    # Extract task_id
                    task_data = data.get("data", {})
                    task_id = task_data.get("taskId")
                    
                    if not task_id:
                        raise Exception(f"No taskId in response: {data}")
                    
                    logger.info(
                        "[KIE] Created task_id=%s prompt=%s ratio=%s",
                        task_id, prompt[:50], aspect_ratio
                    )
                    
                    return ZImageResult(
                        task_id=task_id,
                        status=TaskStatus.PENDING,
                        raw_response=data,
                    )
            
            except asyncio.TimeoutError:
                last_error = Exception(f"Timeout after {self.timeout}s")
                logger.warning(
                    "[KIE] createTask timeout (attempt %d/%d)",
                    attempt + 1, self.max_retries
                )
            
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[KIE] createTask failed (attempt %d/%d): %s",
                    attempt + 1, self.max_retries, exc
                )
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = 2 ** attempt
                await asyncio.sleep(delay)
        
        # All retries exhausted
        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")
    
    async def get_task_status(self, task_id: str) -> ZImageResult:
        """
        Get task status and result.
        
        Args:
            task_id: Task ID from create_task()
        
        Returns:
            ZImageResult with current status and image_url if SUCCESS
        
        Raises:
            Exception if API call fails after retries
        """
        if not self.api_key:
            raise ValueError("KIE_API_KEY not configured")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        
        url = f"{self.BASE_URL}/recordInfo?taskId={task_id}"
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await asyncio.wait_for(
                        client.get(url, headers=headers),
                        timeout=self.timeout
                    )
                    
                    # Check HTTP status
                    if resp.status_code != 200:
                        raise Exception(
                            f"HTTP {resp.status_code}: {resp.text[:200]}"
                        )
                    
                    # Parse response
                    data = resp.json()
                    
                    # Check API code
                    code = data.get("code")
                    if code != 200:
                        msg = data.get("msg", "Unknown error")
                        raise Exception(f"API error code={code}: {msg}")
                    
                    # Extract status and output
                    task_data = data.get("data", {})
                    # BATCH 48.39: Use 'state' field (waiting/success/fail) instead of 'status'
                    state_str = task_data.get("state", task_data.get("status", "UNKNOWN")).lower()
                    
                    # Map to enum (convert state to status)
                    if state_str in ("success", "done", "completed"):
                        status = TaskStatus.SUCCESS
                    elif state_str in ("failed", "error", "fail"):
                        status = TaskStatus.FAILED
                    elif state_str in ("waiting", "running", "pending", "processing"):
                        status = TaskStatus.PROCESSING
                    else:
                        status = TaskStatus.UNKNOWN
                    
                    # Extract image URL if SUCCESS
                    # BATCH 48.39: Parse resultJson according to official API docs
                    # resultJson is a JSON string: {"resultUrls": ["url1", "url2", ...]}
                    image_url = None
                    error = None
                    
                    if status == TaskStatus.SUCCESS:
                        # Try resultJson first (official API format)
                        result_json_str = task_data.get("resultJson")
                        if result_json_str:
                            try:
                                import json
                                result_json = json.loads(result_json_str)
                                result_urls = result_json.get("resultUrls", [])
                                if result_urls:
                                    image_url = result_urls[0]  # Use first URL
                                    logger.debug(f"[KIE] Extracted image_url from resultJson: {image_url[:80]}")
                            except Exception as e:
                                logger.warning(f"[KIE] Failed to parse resultJson: {e}, trying fallback")
                        
                        # Fallback to old format (output.image_url or output.url)
                        if not image_url:
                            output = task_data.get("output", {})
                            image_url = output.get("image_url") or output.get("url")
                    
                    elif status == TaskStatus.FAILED:
                        error = task_data.get("failMsg") or task_data.get("error") or task_data.get("msg")
                    
                    logger.debug(
                        "[KIE] Status task_id=%s: %s",
                        task_id, status.value
                    )
                    
                    return ZImageResult(
                        task_id=task_id,
                        status=status,
                        image_url=image_url,
                        error=error,
                        raw_response=data,
                    )
            
            except asyncio.TimeoutError:
                last_error = Exception(f"Timeout after {self.timeout}s")
                logger.warning(
                    "[KIE] recordInfo timeout (attempt %d/%d)",
                    attempt + 1, self.max_retries
                )
            
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "[KIE] recordInfo failed (attempt %d/%d): %s",
                    attempt + 1, self.max_retries, exc
                )
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = 2 ** attempt
                await asyncio.sleep(delay)
        
        # All retries exhausted
        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")
    
    async def poll_until_complete(
        self,
        task_id: str,
        max_wait: float = 90.0,  # BATCH 39: Image default is 90s (not 300s like video)
        poll_interval: float = 3.0,
    ) -> ZImageResult:
        """
        Poll task status until SUCCESS or FAILED.
        
        Args:
            task_id: Task ID from create_task()
            max_wait: Maximum wait time in seconds (default 5 minutes)
            poll_interval: Seconds between polls (default 3s)
        
        Returns:
            ZImageResult with final status
        
        Raises:
            Exception if timeout or API errors
        """
        start_time = time.monotonic()
        poll_count = 0
        
        # BATCH 38: Exponential backoff for polling (reduce API load)
        # Start fast (2s), then gradually increase to max (10s)
        min_interval = 2.0  # Fast initial polls
        max_interval = 10.0  # Slow down after a while
        current_interval = min_interval
        
        logger.info(
            f"[KIE] Starting polling for task_id={task_id}, max_wait={max_wait}s, "
            f"initial_interval={min_interval}s (exponential backoff to {max_interval}s)"
        )
        
        while True:
            elapsed = time.monotonic() - start_time
            
            if elapsed > max_wait:
                logger.error(f"[KIE] Polling timeout for task_id={task_id} after {elapsed:.1f}s ({poll_count} polls)")
                raise Exception(
                    f"Timeout waiting for task_id={task_id} after {max_wait}s"
                )
            
            poll_count += 1
            try:
                result = await self.get_task_status(task_id)
                
                # Log progress every 5 polls (less noise)
                if poll_count % 5 == 0:
                    logger.info(
                        f"[KIE] Polling progress: task_id={task_id}, status={result.status.value}, "
                        f"elapsed={elapsed:.1f}s, poll_count={poll_count}, interval={current_interval:.1f}s"
                    )
                
                if result.status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                    logger.info(
                        f"[KIE] Polling complete: task_id={task_id}, status={result.status.value}, "
                        f"elapsed={elapsed:.1f}s, poll_count={poll_count}"
                    )
                    return result
                
                # Still processing, wait and retry with exponential backoff
                await asyncio.sleep(current_interval)
                
                # Increase interval for next poll (exponential backoff)
                # Multiplier 1.5x per poll, capped at max_interval
                current_interval = min(current_interval * 1.5, max_interval)
            
            except Exception as poll_error:
                logger.warning(
                    f"[KIE] Poll attempt {poll_count} failed for task_id={task_id}: {poll_error}"
                )
                # Continue polling unless it's a critical error
                if "timeout" in str(poll_error).lower() or "connection" in str(poll_error).lower():
                    # Network error - wait longer and reset backoff
                    logger.info(f"[KIE] Network error detected, resetting backoff to {min_interval}s")
                    current_interval = min_interval  # Reset backoff on network errors
                    await asyncio.sleep(current_interval * 2)  # Wait 2x for network recovery
                else:
                    # Other error - wait current interval
                    await asyncio.sleep(current_interval)


# Global singleton
_client: Optional[ZImageClient] = None


def get_z_image_client() -> ZImageClient:
    """Get or create global z-image client."""
    global _client
    if _client is None:
        _client = ZImageClient()
    return _client

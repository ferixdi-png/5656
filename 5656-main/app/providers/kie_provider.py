"""
KIE API Provider - centralized abstraction for all KIE API calls.

Guarantees:
- All KIE calls go through this provider
- DRY_RUN mode is enforced here
- Beautiful preview results for users
"""
import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from uuid import uuid4

from app.providers.base import BaseProvider, ProviderResult, ProviderStatus

logger = logging.getLogger(__name__)


class KieProvider(BaseProvider):
    """Provider for KIE API calls."""
    
    def __init__(self, dry_run: bool = False):
        super().__init__(dry_run)
        self._real_client = None
        self._mock_results = {}  # Cache for mock results
    
    def _get_real_client(self):
        """Get real KIE client (lazy initialization)."""
        if self._real_client is None:
            from app.kie.client_v4 import KieApiClientV4
            self._real_client = KieApiClientV4()
        return self._real_client
    
    def _get_mock_result_urls(self, model_id: str, prompt: Optional[str] = None) -> List[str]:
        """
        Generate beautiful preview result URLs for DRY_RUN mode.
        
        Returns:
            List of preview URLs (can be placeholder images or text descriptions)
        """
        # Determine result type from model_id
        model_lower = model_id.lower()
        
        if "image" in model_lower or "flux" in model_lower or "dalle" in model_lower:
            # Image generation - return placeholder image URL
            # In production, could use a real placeholder service or local test image
            return [f"https://via.placeholder.com/1024x1024/4A90E2/FFFFFF?text=Preview+Image"]
        elif "video" in model_lower or "kling" in model_lower or "veo" in model_lower:
            # Video generation - return placeholder video URL
            return [f"https://via.placeholder.com/1920x1080/4A90E2/FFFFFF?text=Preview+Video"]
        elif "audio" in model_lower or "music" in model_lower or "speech" in model_lower:
            # Audio generation - return placeholder audio URL
            return [f"https://via.placeholder.com/300x100/4A90E2/FFFFFF?text=Preview+Audio"]
        elif "text" in model_lower:
            # Text generation - return text preview
            return [f"mock://text/preview"]
        else:
            # Default: image placeholder
            return [f"https://via.placeholder.com/1024x1024/4A90E2/FFFFFF?text=Preview+Result"]
    
    def _get_mock_preview_text(self, model_id: str, prompt: Optional[str] = None) -> str:
        """
        Generate beautiful preview text description for DRY_RUN mode.
        
        Returns:
            Human-readable preview text
        """
        model_lower = model_id.lower()
        
        if prompt:
            prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        else:
            prompt_preview = "ваш запрос"
        
        if "image" in model_lower:
            return (
                f"🎨 <b>Превью результата (DRY_RUN)</b>\n\n"
                f"<b>Запрос:</b> {prompt_preview}\n\n"
                f"<b>Результат:</b> Изображение будет сгенерировано в реальном режиме.\n"
                f"В демо-режиме показываем превью-заглушку.\n\n"
                f"💡 <i>Это демо-режим. В реальном режиме здесь будет ваше изображение.</i>"
            )
        elif "video" in model_lower:
            return (
                f"🎬 <b>Превью результата (DRY_RUN)</b>\n\n"
                f"<b>Запрос:</b> {prompt_preview}\n\n"
                f"<b>Результат:</b> Видео будет сгенерировано в реальном режиме.\n"
                f"В демо-режиме показываем превью-заглушку.\n\n"
                f"💡 <i>Это демо-режим. В реальном режиме здесь будет ваше видео.</i>"
            )
        elif "audio" in model_lower:
            return (
                f"🎵 <b>Превью результата (DRY_RUN)</b>\n\n"
                f"<b>Запрос:</b> {prompt_preview}\n\n"
                f"<b>Результат:</b> Аудио будет сгенерировано в реальном режиме.\n"
                f"В демо-режиме показываем превью-заглушку.\n\n"
                f"💡 <i>Это демо-режим. В реальном режиме здесь будет ваше аудио.</i>"
            )
        else:
            return (
                f"✨ <b>Превью результата (DRY_RUN)</b>\n\n"
                f"<b>Запрос:</b> {prompt_preview}\n\n"
                f"<b>Результат:</b> Контент будет сгенерирован в реальном режиме.\n"
                f"В демо-режиме показываем превью-заглушку.\n\n"
                f"💡 <i>Это демо-режим. В реальном режиме здесь будет ваш результат.</i>"
            )
    
    async def create_task(
        self,
        model_id: str,
        input_data: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> ProviderResult:
        """
        Create KIE task.
        
        In DRY_RUN mode: returns mock task_id without real API call.
        In real mode: calls real KIE API.
        """
        if self.dry_run:
            # Generate mock task_id
            task_id = f"mock_task_{uuid4().hex[:8]}"
            
            # Extract prompt for preview
            prompt = input_data.get("prompt") or input_data.get("text") or input_data.get("description")
            
            # Store mock result for later retrieval
            self._mock_results[task_id] = {
                "model_id": model_id,
                "prompt": prompt,
                "input_data": input_data,
                "status": "done",  # Simulate immediate completion in DRY_RUN
                "preview_urls": self._get_mock_result_urls(model_id, prompt),
                "preview_text": self._get_mock_preview_text(model_id, prompt)
            }
            
            logger.info(
                f"[KIE_PROVIDER] DRY_RUN: Mock task created | "
                f"Model: {model_id} | TaskID: {task_id}"
            )
            
            # Simulate async delay
            await asyncio.sleep(0.1)
            
            return ProviderResult(
                status=ProviderStatus.SUCCESS,
                data={
                    "taskId": task_id,
                    "state": "pending"
                },
                preview_urls=self._get_mock_result_urls(model_id, prompt),
                preview_text=self._get_mock_preview_text(model_id, prompt)
            )
        
        # Real mode: call actual KIE API
        try:
            client = self._get_real_client()
            payload = {
                "model": model_id,
                "input": input_data
            }
            if callback_url:
                payload["callBackUrl"] = callback_url
            
            result = await client.create_task(model_id, payload)
            
            if result.get("code") == 0 or result.get("ok"):
                task_id = result.get("data", {}).get("taskId") or result.get("taskId")
                return ProviderResult(
                    status=ProviderStatus.SUCCESS,
                    data={
                        "taskId": task_id,
                        "state": result.get("data", {}).get("state", "pending")
                    }
                )
            else:
                error_msg = result.get("msg") or result.get("error", "Unknown error")
                return ProviderResult(
                    status=ProviderStatus.ERROR,
                    error=error_msg,
                    error_code=result.get("code")
                )
        except Exception as e:
            logger.error(f"[KIE_PROVIDER] Error creating task: {e}", exc_info=True)
            return ProviderResult(
                status=ProviderStatus.ERROR,
                error=str(e),
                error_code="EXCEPTION"
            )
    
    async def get_task_status(
        self,
        task_id: str,
        model_id: Optional[str] = None
    ) -> ProviderResult:
        """
        Get KIE task status.
        
        In DRY_RUN mode: returns mock "done" status with preview results.
        In real mode: calls real KIE API.
        """
        if self.dry_run:
            # Check if we have mock result cached
            if task_id in self._mock_results:
                mock_result = self._mock_results[task_id]
                
                logger.info(
                    f"[KIE_PROVIDER] DRY_RUN: Mock status retrieved | "
                    f"TaskID: {task_id} | Status: done"
                )
                
                await asyncio.sleep(0.05)
                
                return ProviderResult(
                    status=ProviderStatus.SUCCESS,
                    data={
                        "taskId": task_id,
                        "state": "done",
                        "result": {
                            "urls": mock_result["preview_urls"],
                            "type": "preview"
                        }
                    },
                    preview_urls=mock_result["preview_urls"],
                    preview_text=mock_result["preview_text"]
                )
            else:
                # Task not found in cache - return error
                return ProviderResult(
                    status=ProviderStatus.ERROR,
                    error="Mock task not found",
                    error_code="TASK_NOT_FOUND"
                )
        
        # Real mode: call actual KIE API
        try:
            client = self._get_real_client()
            result = await client.get_task_status(task_id, model_id)
            
            if result.get("code") == 0:
                state = result.get("data", {}).get("state", "unknown")
                
                # Parse result URLs if done
                result_urls = []
                if state == "done":
                    result_data = result.get("data", {}).get("result", {})
                    if isinstance(result_data, dict):
                        if "urls" in result_data:
                            result_urls = result_data["urls"]
                        elif "url" in result_data:
                            result_urls = [result_data["url"]]
                    elif isinstance(result_data, list):
                        result_urls = result_data
                
                return ProviderResult(
                    status=ProviderStatus.SUCCESS if state == "done" else ProviderStatus.PENDING,
                    data={
                        "taskId": task_id,
                        "state": state,
                        "result": {
                            "urls": result_urls
                        } if result_urls else None
                    }
                )
            else:
                error_msg = result.get("msg") or result.get("error", "Unknown error")
                return ProviderResult(
                    status=ProviderStatus.ERROR,
                    error=error_msg,
                    error_code=result.get("code")
                )
        except Exception as e:
            logger.error(f"[KIE_PROVIDER] Error getting task status: {e}", exc_info=True)
            return ProviderResult(
                status=ProviderStatus.ERROR,
                error=str(e),
                error_code="EXCEPTION"
            )
    
    async def healthcheck(self) -> bool:
        """Check if KIE provider is available."""
        if self.dry_run:
            return True  # Mock provider is always available
        
        try:
            client = self._get_real_client()
            # Simple healthcheck - could be improved
            return True
        except Exception:
            return False


def get_kie_provider(force_dry_run: Optional[bool] = None) -> KieProvider:
    """
    Get KIE provider instance (real or mock based on DRY_RUN).
    
    Args:
        force_dry_run: Override DRY_RUN env var (for testing)
    
    Returns:
        KieProvider instance
    """
    if force_dry_run is None:
        dry_run = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")
    else:
        dry_run = force_dry_run
    
    return KieProvider(dry_run=dry_run)


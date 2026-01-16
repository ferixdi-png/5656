"""
Mock KIE Client for DRY_RUN mode.

Returns fake responses without making real HTTP requests.
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MockKieApiClientV4:
    """
    Mock KIE API client that returns fake responses.
    
    Used in DRY_RUN mode to prevent real API calls.
    """
    
    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or "mock_key"
        self.timeout = timeout
        logger.info("[MOCK_KIE] MockKieApiClientV4 initialized (DRY_RUN mode)")
    
    async def create_task(
        self,
        model_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create fake task without real API call.
        
        Returns:
            Fake task response with mock taskId
        """
        task_id = f"mock_task_{uuid4().hex[:8]}"
        
        logger.info(
            f"[MOCK_KIE] EXTERNAL_CALL_MOCKED | Model: {model_id} | "
            f"TaskID: {task_id} | Reason: DRY_RUN"
        )
        
        # Simulate async delay
        await asyncio.sleep(0.1)
        
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "taskId": task_id,
                "state": "pending"
            }
        }
    
    async def get_task_status(
        self,
        task_id: str,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get fake task status.
        
        Returns:
            Fake status response
        """
        logger.info(
            f"[MOCK_KIE] EXTERNAL_CALL_MOCKED | TaskID: {task_id} | "
            f"Reason: DRY_RUN"
        )
        
        await asyncio.sleep(0.05)
        
        return {
            "code": 0,
            "msg": "success",
            "data": {
                "taskId": task_id,
                "state": "done",
                "result": {
                    "url": "mock://result/image.jpg",
                    "type": "image"
                }
            }
        }


def get_kie_client(force_mock: bool = False):
    """
    Get KIE client (real or mock based on DRY_RUN).
    
    Args:
        force_mock: Force mock mode even if DRY_RUN is not set
        
    Returns:
        KieApiClientV4 or MockKieApiClientV4
    """
    import os
    from app.kie.client_v4 import KieApiClientV4
    
    dry_run = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")
    
    if dry_run or force_mock:
        logger.info("[KIE_CLIENT] Using MockKieApiClientV4 (DRY_RUN mode)")
        return MockKieApiClientV4()
    else:
        logger.info("[KIE_CLIENT] Using real KieApiClientV4")
        return KieApiClientV4()


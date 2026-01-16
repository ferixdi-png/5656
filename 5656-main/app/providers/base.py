"""
Base provider interface for all external service providers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class ProviderStatus(Enum):
    """Status of provider operation."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    CANCELLED = "cancelled"


@dataclass
class ProviderResult:
    """Result from provider operation."""
    status: ProviderStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    preview_urls: Optional[List[str]] = None  # For DRY_RUN preview results
    preview_text: Optional[str] = None  # For DRY_RUN text preview
    
    @property
    def is_success(self) -> bool:
        return self.status == ProviderStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        return self.status == ProviderStatus.ERROR


class BaseProvider(ABC):
    """Base class for all external service providers."""
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize provider.
        
        Args:
            dry_run: If True, provider should return mock results without real API calls
        """
        self.dry_run = dry_run
    
    @abstractmethod
    async def healthcheck(self) -> bool:
        """Check if provider is available."""
        pass


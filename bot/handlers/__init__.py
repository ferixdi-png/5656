"""Bot handlers package."""
from .flow import router as flow_router
from .zero_silence import router as zero_silence_router
from .diag import router as diag_router
from .error_handler import router as error_handler_router

__all__ = ["flow_router", "zero_silence_router", "diag_router", "error_handler_router"]

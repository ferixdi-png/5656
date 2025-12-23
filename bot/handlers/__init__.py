"""Bot handlers package."""
from .core import router as core_router
from .flow import router as flow_router
from .smoke import router as smoke_router
from .zero_silence import router as zero_silence_router
from .diag import router as diag_router
from .error_handler import router as error_handler_router

__all__ = [
    "core_router",
    "flow_router",
    "smoke_router",
    "zero_silence_router",
    "diag_router",
    "error_handler_router",
]

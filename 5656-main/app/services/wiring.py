"""
Single Source of Truth for Service Injection.

This module provides unified service wiring to prevent NoneType.get_connection errors.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global service registry
_db_service: Optional[object] = None
_admin_service: Optional[object] = None
_free_manager: Optional[object] = None


def set_services(
    db_service: Optional[object] = None,
    admin_service: Optional[object] = None,
    free_manager: Optional[object] = None,
) -> None:
    """
    Set global services (single source of truth).
    
    Args:
        db_service: DatabaseService instance
        admin_service: AdminService instance
        free_manager: FreeModelManager instance
    """
    global _db_service, _admin_service, _free_manager
    
    _db_service = db_service
    _admin_service = admin_service
    _free_manager = free_manager
    
    # Guard: verify db_service has get_connection if provided
    if db_service is not None:
        if not hasattr(db_service, 'get_connection'):
            logger.error(
                "[WIRING] CRITICAL: db_service provided but missing get_connection method. "
                "This will cause AttributeError at runtime."
            )
            raise ValueError("db_service must have get_connection method")
    
    logger.info(
        "[WIRING] Services set: db_service=%s admin_service=%s free_manager=%s",
        "OK" if db_service else "None",
        "OK" if admin_service else "None",
        "OK" if free_manager else "None",
    )


def get_db_service() -> Optional[object]:
    """Get database service (fail-open if None)."""
    return _db_service


def get_admin_service() -> Optional[object]:
    """Get admin service (fail-open if None)."""
    return _admin_service


def get_free_manager() -> Optional[object]:
    """Get free manager (fail-open if None)."""
    return _free_manager


def require_db_service(operation: str = "operation") -> object:
    """
    Require database service (raises if None).
    
    Args:
        operation: Operation name for error message
        
    Returns:
        Database service (never None)
        
    Raises:
        RuntimeError: If db_service is None
    """
    if _db_service is None:
        error_msg = (
            f"[WIRING] CRITICAL: db_service is None but required for {operation}. "
            "This indicates services were not properly initialized. "
            "Check init_active_services() in main_render.py"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    return _db_service


def require_admin_service(operation: str = "operation") -> object:
    """
    Require admin service (raises if None).
    
    Args:
        operation: Operation name for error message
        
    Returns:
        Admin service (never None)
        
    Raises:
        RuntimeError: If admin_service is None
    """
    if _admin_service is None:
        error_msg = (
            f"[WIRING] CRITICAL: admin_service is None but required for {operation}. "
            "This indicates services were not properly initialized. "
            "Check init_active_services() in main_render.py"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    return _admin_service


__all__ = [
    "set_services",
    "get_db_service",
    "get_admin_service",
    "get_free_manager",
    "require_db_service",
    "require_admin_service",
]


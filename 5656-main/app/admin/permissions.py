"""
Admin permissions and authorization checks.
"""
import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


def get_admin_id() -> Optional[int]:
    """
    Get primary admin ID from environment.
    
    Returns:
        Admin user ID or None if not set
    """
    admin_id_str = os.getenv('ADMIN_ID')
    if not admin_id_str:
        return None
    
    try:
        return int(admin_id_str)
    except ValueError:
        logger.error(f"Invalid ADMIN_ID in environment: {admin_id_str}")
        return None


def get_admin_ids() -> List[int]:
    """
    Get list of all admin IDs (primary + secondary).
    
    Returns:
        List of admin user IDs
    """
    admin_ids = []
    
    # Primary admin
    primary_admin = get_admin_id()
    if primary_admin:
        admin_ids.append(primary_admin)
    
    # Secondary admins (if any) from ADMIN_IDS env var (comma-separated)
    secondary_str = os.getenv('ADMIN_IDS', '')
    if secondary_str:
        for admin_str in secondary_str.split(','):
            try:
                admin_id = int(admin_str.strip())
                if admin_id not in admin_ids:
                    admin_ids.append(admin_id)
            except ValueError:
                logger.warning(f"Invalid admin ID in ADMIN_IDS: {admin_str}")
    
    return admin_ids


def is_admin(user_id: int) -> bool:
    """
    Check if user is an admin.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        True if user is admin, False otherwise
    """
    admin_ids = get_admin_ids()
    return user_id in admin_ids


def is_primary_admin(user_id: int) -> bool:
    """
    Check if user is the primary admin.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        True if user is primary admin, False otherwise
    """
    primary_admin = get_admin_id()
    return primary_admin is not None and user_id == primary_admin

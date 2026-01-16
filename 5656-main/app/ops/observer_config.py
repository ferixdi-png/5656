"""
Observer configuration loader.

Reads TRT_RENDER.env from Desktop (or env vars) for observability operations.
Never commits secrets; redacts in logs.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class ObserverConfig:
    """Observer configuration (Render + DB read-only)."""
    render_api_key: Optional[str] = None
    render_service_id: Optional[str] = None
    database_url_readonly: Optional[str] = None
    
    def redact_secret(self, secret: Optional[str]) -> str:
        """Redact secret: show only last 4 chars."""
        if not secret:
            return "***"
        if len(secret) <= 4:
            return "***"
        return f"***{secret[-4:]}"
    
    def __repr__(self) -> str:
        """Safe repr: redact secrets."""
        return (
            f"ObserverConfig("
            f"render_api_key={self.redact_secret(self.render_api_key)}, "
            f"render_service_id={self.render_service_id}, "
            f"database_url_readonly={'***' if self.database_url_readonly else None}"
            f")"
        )


def get_desktop_path() -> Path:
    """Get Desktop path for current OS."""
    if sys.platform == "win32":
        desktop = Path(os.getenv("USERPROFILE", "")) / "Desktop"
    else:
        desktop = Path.home() / "Desktop"
    
    # Fallback if Desktop doesn't exist
    if not desktop.exists():
        desktop = Path.home() / "_desktop"
        desktop.mkdir(exist_ok=True)
    
    return desktop


def load_config() -> ObserverConfig:
    """
    Load observer configuration from Desktop TRT_RENDER.env or env vars.
    
    Priority:
    1. Environment variables (for CI/Render runtime)
    2. Desktop TRT_RENDER.env file
    
    Returns:
        ObserverConfig with loaded values (None if not found)
    """
    config = ObserverConfig()
    
    # First, try environment variables (highest priority)
    config.render_api_key = os.getenv("RENDER_API_KEY", "").strip() or None
    config.render_service_id = os.getenv("RENDER_SERVICE_ID", "").strip() or None
    config.database_url_readonly = os.getenv("DATABASE_URL_READONLY", "").strip() or None
    
    # If env vars not set, try Desktop file
    if not config.render_api_key or not config.render_service_id:
        desktop = get_desktop_path()
        env_file = desktop / "TRT_RENDER.env"
        
        if env_file.exists():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and blank lines
                        if not line or line.startswith("#"):
                            continue
                        
                        # Parse KEY=VALUE
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            
                            # Remove quotes if present
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            
                            # Set config (only if not already set from env)
                            if key == "RENDER_API_KEY" and not config.render_api_key:
                                config.render_api_key = value
                            elif key == "RENDER_SERVICE_ID" and not config.render_service_id:
                                config.render_service_id = value
                            elif key == "DATABASE_URL_READONLY" and not config.database_url_readonly:
                                config.database_url_readonly = value
            except Exception as e:
                print(f"WARNING: Failed to read {env_file}: {e}", file=sys.stderr)
    
    return config


def validate_config(config: ObserverConfig, require_render: bool = False, require_db: bool = False) -> bool:
    """
    Validate configuration.
    
    Args:
        config: ObserverConfig to validate
        require_render: If True, render_api_key and render_service_id must be set
        require_db: If True, database_url_readonly must be set
    
    Returns:
        True if valid, False otherwise
    """
    if require_render:
        if not config.render_api_key:
            print("ERROR: RENDER_API_KEY is required", file=sys.stderr)
            return False
        if not config.render_service_id:
            print("ERROR: RENDER_SERVICE_ID is required", file=sys.stderr)
            return False
    
    if require_db:
        if not config.database_url_readonly:
            print("ERROR: DATABASE_URL_READONLY is required", file=sys.stderr)
            return False
    
    return True


if __name__ == "__main__":
    """CLI: Print config (redacted)."""
    config = load_config()
    print(config)
    sys.exit(0 if (config.render_api_key or config.database_url_readonly) else 1)


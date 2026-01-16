"""
Smoke tests for ops observability modules.

Validates that CLIs work correctly with and without config.
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from app.ops.observer_config import load_config, validate_config


class TestOpsSmoke(unittest.TestCase):
    """Smoke tests for ops modules."""
    
    def test_config_loader_with_desktop_file(self):
        """Test config loader reads Desktop file correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            desktop = Path(tmpdir) / "Desktop"
            desktop.mkdir()
            env_file = desktop / "TRT_RENDER.env"
            
            with open(env_file, "w") as f:
                f.write("RENDER_API_KEY=test-key-123\n")
                f.write("RENDER_SERVICE_ID=srv-test\n")
                f.write("DATABASE_URL_READONLY=postgresql://test\n")
            
            with patch("app.ops.observer_config.get_desktop_path", return_value=desktop):
                with patch.dict(os.environ, {}, clear=True):
                    config = load_config()
                    self.assertEqual(config.render_api_key, "test-key-123")
                    self.assertEqual(config.render_service_id, "srv-test")
                    self.assertEqual(config.database_url_readonly, "postgresql://test")
    
    def test_config_loader_env_override(self):
        """Test env vars override Desktop file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            desktop = Path(tmpdir) / "Desktop"
            desktop.mkdir()
            env_file = desktop / "TRT_RENDER.env"
            
            with open(env_file, "w") as f:
                f.write("RENDER_API_KEY=file-key\n")
            
            with patch("app.ops.observer_config.get_desktop_path", return_value=desktop):
                with patch.dict(os.environ, {"RENDER_API_KEY": "env-key"}):
                    config = load_config()
                    # Env should override file
                    self.assertEqual(config.render_api_key, "env-key")
    
    def test_render_logs_cli_missing_config(self):
        """Test render_logs CLI soft-fails when config missing."""
        # This should exit 0 with helpful message, not crash
        result = subprocess.run(
            [sys.executable, "-m", "app.ops.render_logs", "--minutes", "1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should exit 1 (error) but not crash
        self.assertIn(result.returncode, [0, 1])
        # Should have helpful error message
        if result.returncode != 0:
            self.assertIn("RENDER_API_KEY", result.stderr or result.stdout)
    
    def test_db_diag_cli_missing_config(self):
        """Test db_diag CLI soft-fails when config missing."""
        result = subprocess.run(
            [sys.executable, "-m", "app.ops.db_diag"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should exit 1 (error) but not crash
        self.assertIn(result.returncode, [0, 1])
        # Should have helpful error message
        if result.returncode != 0:
            self.assertIn("DATABASE_URL_READONLY", result.stderr or result.stdout)
    
    def test_critical5_cli_missing_files(self):
        """Test critical5 CLI handles missing files gracefully."""
        result = subprocess.run(
            [sys.executable, "-m", "app.ops.critical5", "--render-logs", "/nonexistent", "--db-diag", "/nonexistent"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should exit 0 (no issues found) or 1 (issues found), but not crash
        self.assertIn(result.returncode, [0, 1])


if __name__ == "__main__":
    unittest.main()


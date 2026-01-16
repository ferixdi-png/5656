"""
Unit tests for ops observer config loader.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from app.ops.observer_config import load_config, validate_config, ObserverConfig


class TestObserverConfig(unittest.TestCase):
    """Test observer configuration loader."""
    
    def test_redact_secret(self):
        """Test secret redaction."""
        config = ObserverConfig()
        self.assertEqual(config.redact_secret("rnd_abc123def456"), "***def456")
        self.assertEqual(config.redact_secret("short"), "***")
        self.assertEqual(config.redact_secret(None), "***")
    
    def test_load_from_env(self):
        """Test loading from environment variables."""
        with patch.dict(os.environ, {
            "RENDER_API_KEY": "test-key",
            "RENDER_SERVICE_ID": "srv-test",
            "DATABASE_URL_READONLY": "postgresql://test",
        }):
            config = load_config()
            self.assertEqual(config.render_api_key, "test-key")
            self.assertEqual(config.render_service_id, "srv-test")
            self.assertEqual(config.database_url_readonly, "postgresql://test")
    
    def test_load_from_file(self):
        """Test loading from Desktop file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock Desktop
            desktop = Path(tmpdir) / "Desktop"
            desktop.mkdir()
            env_file = desktop / "TRT_RENDER.env"
            
            with open(env_file, "w") as f:
                f.write("RENDER_API_KEY=file-key\n")
                f.write("RENDER_SERVICE_ID=srv-file\n")
                f.write("DATABASE_URL_READONLY=postgresql://file-db\n")
            
            with patch("app.ops.observer_config.get_desktop_path", return_value=desktop):
                with patch.dict(os.environ, {}, clear=True):
                    config = load_config()
                    self.assertEqual(config.render_api_key, "file-key")
                    self.assertEqual(config.render_service_id, "srv-file")
                    self.assertEqual(config.database_url_readonly, "postgresql://file-db")
    
    def test_validate_config(self):
        """Test config validation."""
        config = ObserverConfig()
        
        # Should pass with no requirements
        self.assertTrue(validate_config(config))
        
        # Should fail if render required but missing
        self.assertFalse(validate_config(config, require_render=True))
        
        # Should fail if db required but missing
        self.assertFalse(validate_config(config, require_db=True))
        
        # Should pass if all required are present
        config.render_api_key = "test"
        config.render_service_id = "test"
        config.database_url_readonly = "test"
        self.assertTrue(validate_config(config, require_render=True, require_db=True))


if __name__ == "__main__":
    unittest.main()


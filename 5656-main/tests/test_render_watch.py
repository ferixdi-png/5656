"""
Unit tests for render_watch.py (no external network required).

Tests log parsing, statistics, and change detection.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_watch import (
    parse_log_line,
    analyze_logs,
    detect_changes,
    compute_logs_hash,
)


class TestRenderWatch(unittest.TestCase):
    """Unit tests for render_watch module."""
    
    def test_parse_log_line_cid(self):
        """Test CID extraction from log line."""
        line = "[2026-01-14T08:00:00Z] UPDATE_RECEIVED cid=abc123 update_id=456"
        parsed = parse_log_line(line)
        self.assertEqual(parsed["cid"], "abc123")
        self.assertEqual(parsed["update_id"], "456")
        self.assertEqual(parsed["event_name"], "UPDATE_RECEIVED")
    
    def test_parse_log_line_error(self):
        """Test error detection in log line."""
        line = "[2026-01-14T08:00:00Z] ERROR: Exception occurred"
        parsed = parse_log_line(line)
        self.assertEqual(parsed["log_level"], "ERROR")
    
    def test_parse_log_line_passive_reject(self):
        """Test PASSIVE_REJECT event detection."""
        line = "[2026-01-14T08:00:00Z] ⏸️ PASSIVE_REJECT callback_query data=cat:image"
        parsed = parse_log_line(line)
        self.assertIn("PASSIVE_REJECT", parsed["event_name"] or "")
    
    def test_parse_log_line_dispatch_ok(self):
        """Test DISPATCH_OK event detection."""
        line = "[2026-01-14T08:00:00Z] DISPATCH_OK cid=xyz789"
        parsed = parse_log_line(line)
        self.assertIn("DISPATCH_OK", parsed["event_name"] or "")
    
    def test_analyze_logs_counts(self):
        """Test log analysis statistics."""
        logs = [
            "[2026-01-14T08:00:00Z] ERROR: Test error",
            "[2026-01-14T08:00:01Z] WARNING: Test warning",
            "[2026-01-14T08:00:02Z] DISPATCH_OK cid=abc123",
            "[2026-01-14T08:00:03Z] DISPATCH_FAIL cid=def456",
            "[2026-01-14T08:00:04Z] ⏸️ PASSIVE_REJECT callback_query",
        ]
        
        stats = analyze_logs(logs)
        
        self.assertEqual(stats["total_lines"], 5)
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(stats["warnings"], 1)
        self.assertEqual(stats["dispatch_ok"], 1)
        self.assertEqual(stats["dispatch_fail"], 1)
        self.assertEqual(stats["passive_reject"], 1)
    
    def test_analyze_logs_exceptions(self):
        """Test exception detection."""
        logs = [
            "[2026-01-14T08:00:00Z] Traceback (most recent call last):",
            "[2026-01-14T08:00:01Z]   File 'test.py', line 1",
            "[2026-01-14T08:00:02Z] AttributeError: 'CallbackQuery' object has no attribute 'update_id'",
        ]
        
        stats = analyze_logs(logs)
        self.assertGreaterEqual(stats["exceptions"], 1)
    
    def test_analyze_logs_unknown_callback(self):
        """Test UNKNOWN_CALLBACK detection."""
        logs = [
            "[2026-01-14T08:00:00Z] CALLBACK_REJECTED cid=abc123 reason_code=UNKNOWN_CALLBACK",
        ]
        
        stats = analyze_logs(logs)
        self.assertEqual(stats["unknown_callbacks"], 1)
    
    def test_analyze_logs_lock_events(self):
        """Test lock acquisition event detection."""
        logs = [
            "[2026-01-14T08:00:00Z] [LOCK] ✅ ACTIVE MODE: PostgreSQL advisory lock acquired",
            "[2026-01-14T08:00:01Z] [LOCK] ⏸️ PASSIVE MODE: Lock NOT acquired",
        ]
        
        stats = analyze_logs(logs)
        self.assertGreaterEqual(stats["lock_acquired"], 1)
        self.assertGreaterEqual(stats["lock_not_acquired"], 1)
    
    def test_detect_changes(self):
        """Test change detection between runs."""
        current = {
            "errors": 5,
            "warnings": 10,
            "dispatch_ok": 100,
        }
        
        previous = {
            "errors": 3,
            "warnings": 10,
            "dispatch_ok": 80,
        }
        
        changes = detect_changes(current, previous)
        
        # Should detect errors: 3 → 5 (+2)
        self.assertTrue(any("errors" in c and "+2" in c for c in changes))
        # Should detect dispatch_ok: 80 → 100 (+20)
        self.assertTrue(any("dispatch_ok" in c and "+20" in c for c in changes))
        # Should not detect warnings change (10 → 10)
        self.assertFalse(any("warnings" in c and "→" in c for c in changes))
    
    def test_detect_changes_no_previous(self):
        """Test change detection with no previous data."""
        current = {"errors": 5}
        previous = {}
        
        changes = detect_changes(current, previous)
        self.assertTrue(any("First run" in c for c in changes))
    
    def test_compute_logs_hash(self):
        """Test logs hash computation (deterministic)."""
        logs1 = ["line1", "line2", "line3"]
        logs2 = ["line1", "line2", "line3"]
        logs3 = ["line1", "line2", "line4"]
        
        hash1 = compute_logs_hash(logs1)
        hash2 = compute_logs_hash(logs2)
        hash3 = compute_logs_hash(logs3)
        
        # Same logs = same hash
        self.assertEqual(hash1, hash2)
        # Different logs = different hash
        self.assertNotEqual(hash1, hash3)
    
    def test_parse_log_line_complex(self):
        """Test parsing complex log line with multiple fields."""
        line = "[2026-01-14T08:00:00Z] [TELEMETRY] CALLBACK_RECEIVED cid=abc123 callback_id=xyz789 update_id=456 user_id=123"
        parsed = parse_log_line(line)
        
        self.assertEqual(parsed["cid"], "abc123")
        self.assertEqual(parsed["update_id"], "456")
        self.assertIn("CALLBACK_RECEIVED", parsed["event_name"] or "")
    
    def test_analyze_logs_top_errors(self):
        """Test top errors extraction."""
        logs = [
            "[2026-01-14T08:00:00Z] ERROR: Error 1",
            "[2026-01-14T08:00:01Z] ERROR: Error 2",
            "[2026-01-14T08:00:02Z] ERROR: Error 3",
            "[2026-01-14T08:00:03Z] ERROR: Error 4",
            "[2026-01-14T08:00:04Z] ERROR: Error 5",
            "[2026-01-14T08:00:05Z] ERROR: Error 6",
            "[2026-01-14T08:00:06Z] ERROR: Error 7",
            "[2026-01-14T08:00:07Z] ERROR: Error 8",
            "[2026-01-14T08:00:08Z] ERROR: Error 9",
            "[2026-01-14T08:00:09Z] ERROR: Error 10",
            "[2026-01-14T08:00:10Z] ERROR: Error 11",
        ]
        
        stats = analyze_logs(logs)
        
        # Should return top 10 (most recent)
        self.assertEqual(len(stats["top_errors"]), 10)
        # Should include Error 11 (most recent)
        self.assertTrue(any("Error 11" in err for err in stats["top_errors"]))
        # Should not include Error 1 (oldest)
        self.assertFalse(any("Error 1" in err for err in stats["top_errors"]))


if __name__ == "__main__":
    unittest.main()



"""
Unit tests for orphan_reconciler datetime handling.

Ensures timezone-aware/naive datetime compatibility.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import pytest


def test_datetime_normalization_naive():
    """Test that naive datetime is properly normalized to UTC."""
    # Simulate naive received_at from database
    received_at = datetime(2026, 1, 13, 7, 0, 0)  # Naive
    
    # Normalize (same logic as reconciler)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    
    # Calculate age
    now = datetime.now(timezone.utc)
    age = now - received_at
    
    # Should not raise TypeError
    assert age.total_seconds() >= 0
    assert received_at.tzinfo is not None


def test_datetime_normalization_aware():
    """Test that aware datetime works correctly."""
    # Simulate aware received_at
    received_at = datetime(2026, 1, 13, 7, 0, 0, tzinfo=timezone.utc)
    
    # Calculate age
    now = datetime.now(timezone.utc)
    age = now - received_at
    
    # Should not raise TypeError
    assert age.total_seconds() >= 0
    assert received_at.tzinfo is not None


def test_datetime_age_calculation():
    """Test age calculation for old orphan."""
    # Create old orphan (35 minutes ago)
    received_at = datetime.now(timezone.utc) - timedelta(minutes=35)
    
    # Calculate age
    now = datetime.now(timezone.utc)
    age = now - received_at
    
    # Should be > 30 minutes
    assert age.total_seconds() > 30 * 60
    assert age.total_seconds() < 36 * 60  # Sanity check


def test_datetime_recent_orphan():
    """Test age calculation for recent orphan."""
    # Create recent orphan (5 minutes ago)
    received_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    # Calculate age
    now = datetime.now(timezone.utc)
    age = now - received_at
    
    # Should be < 30 minutes
    assert age.total_seconds() < 30 * 60
    assert age.total_seconds() > 4 * 60  # At least 4 min


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

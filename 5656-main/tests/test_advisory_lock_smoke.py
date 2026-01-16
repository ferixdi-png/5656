"""
Smoke test для advisory lock: гарантия что lock_key всегда в signed int64 диапазоне
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from render_singleton_lock import make_lock_key


def test_lock_key_in_range():
    """Test that lock_key is always in signed int64 range"""
    MAX_BIGINT = 0x7FFFFFFFFFFFFFFF  # 2^63 - 1
    
    # Test with various tokens
    test_tokens = [
        "1234567890:ABCdefGHI-jklMNOpqrSTUvwxYZ",
        "a" * 100,
        "short",
        "8524869517:AAHemOL6zZkl0kN4wVHqQCJ8i65Bc-OGZkM",  # Real bot token pattern
        "x" * 1000,  # Very long
    ]
    
    for token in test_tokens:
        key = make_lock_key(token)
        
        # CRITICAL: key must be in [0, 2^63-1]
        assert key >= 0, f"Lock key is negative: {key}"
        assert key <= MAX_BIGINT, f"Lock key exceeds MAX_BIGINT: {key} > {MAX_BIGINT}"
        
        # Verify it's an integer
        assert isinstance(key, int), f"Lock key is not int: {type(key)}"
        
        print(f"✅ Token '{token[:10]}...' -> key={key} (OK)")
    
    print(f"\n✅ All {len(test_tokens)} tokens generated valid lock keys!")


def test_lock_key_stable():
    """Test that same token always produces same key"""
    token = "test_token_123"
    
    key1 = make_lock_key(token)
    key2 = make_lock_key(token)
    key3 = make_lock_key(token)
    
    assert key1 == key2 == key3, f"Lock keys not stable: {key1}, {key2}, {key3}"
    print(f"✅ Lock key is stable for same token: {key1}")


def test_different_tokens_different_keys():
    """Test that different tokens produce different keys"""
    key1 = make_lock_key("token1")
    key2 = make_lock_key("token2")
    
    assert key1 != key2, f"Different tokens produced same key: {key1}"
    print(f"✅ Different tokens produce different keys: {key1} != {key2}")


if __name__ == "__main__":
    print("=" * 60)
    print("SMOKE TEST: Advisory Lock Key Generation")
    print("=" * 60)
    
    test_lock_key_in_range()
    print()
    test_lock_key_stable()
    print()
    test_different_tokens_different_keys()
    
    print("\n" + "=" * 60)
    print("✅ ALL SMOKE TESTS PASSED!")
    print("=" * 60)

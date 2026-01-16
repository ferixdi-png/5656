"""
Unit tests for render_singleton_lock module.

Tests:
- split_bigint_to_pg_advisory_oids: correct splitting of 64-bit lock_key
- make_lock_key: correct generation of lock key
"""
import pytest
from render_singleton_lock import split_bigint_to_pg_advisory_oids, make_lock_key


class TestSplitBigintToPgAdvisoryOids:
    """Test split_bigint_to_pg_advisory_oids function."""
    
    def test_split_example_lock_key(self):
        """Test with example lock key from docs."""
        lock_key = 2797505866569588743
        hi, lo = split_bigint_to_pg_advisory_oids(lock_key)
        
        # Проверяем что оба значения в диапазоне signed int32
        assert -0x80000000 <= hi <= 0x7FFFFFFF, f"hi={hi} out of signed int32 range"
        assert -0x80000000 <= lo <= 0x7FFFFFFF, f"lo={lo} out of signed int32 range"
        
        # Проверяем обратное восстановление (через unsigned)
        hi_unsigned = hi if hi >= 0 else hi + 0x100000000
        lo_unsigned = lo if lo >= 0 else lo + 0x100000000
        reconstructed = (hi_unsigned << 32) | lo_unsigned
        assert reconstructed == lock_key, f"Reconstructed {reconstructed} != original {lock_key}"
    
    def test_split_max_signed_int64(self):
        """Test with maximum signed int64."""
        lock_key = 0x7FFFFFFFFFFFFFFF  # 2^63 - 1
        hi, lo = split_bigint_to_pg_advisory_oids(lock_key)
        
        assert -0x80000000 <= hi <= 0x7FFFFFFF
        assert -0x80000000 <= lo <= 0x7FFFFFFF
        
        hi_unsigned = hi if hi >= 0 else hi + 0x100000000
        lo_unsigned = lo if lo >= 0 else lo + 0x100000000
        reconstructed = (hi_unsigned << 32) | lo_unsigned
        assert reconstructed == lock_key
    
    def test_split_zero(self):
        """Test with zero."""
        lock_key = 0
        hi, lo = split_bigint_to_pg_advisory_oids(lock_key)
        
        assert hi == 0
        assert lo == 0
    
    def test_split_small_value(self):
        """Test with small value (fits in 32 bits)."""
        lock_key = 12345
        hi, lo = split_bigint_to_pg_advisory_oids(lock_key)
        
        assert hi == 0, "hi should be 0 for small values"
        assert lo == 12345
        
        reconstructed = (hi << 32) | lo
        assert reconstructed == lock_key
    
    def test_split_all_ones_lower_32(self):
        """Test with all ones in lower 32 bits."""
        lock_key = 0xFFFFFFFF
        hi, lo = split_bigint_to_pg_advisory_oids(lock_key)
        
        assert hi == 0
        assert lo == -1  # 0xFFFFFFFF как signed int32 = -1
    
    def test_split_all_ones_upper_32(self):
        """Test with all ones in upper 32 bits (within int64 range)."""
        lock_key = 0x7FFFFFFF00000000
        hi, lo = split_bigint_to_pg_advisory_oids(lock_key)
        
        assert hi == 0x7FFFFFFF
        assert lo == 0


class TestMakeLockKey:
    """Test make_lock_key function."""
    
    def test_make_lock_key_deterministic(self):
        """Test that same token produces same key."""
        token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        
        key1 = make_lock_key(token)
        key2 = make_lock_key(token)
        
        assert key1 == key2, "Same token should produce same key"
    
    def test_make_lock_key_different_tokens(self):
        """Test that different tokens produce different keys."""
        token1 = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        token2 = "654321:XYZ-GHI5678abCdE-fgh12M3n4o567pq89"
        
        key1 = make_lock_key(token1)
        key2 = make_lock_key(token2)
        
        assert key1 != key2, "Different tokens should produce different keys"
    
    def test_make_lock_key_in_valid_range(self):
        """Test that generated key is in valid signed int64 range."""
        token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        key = make_lock_key(token)
        
        # Должен быть в диапазоне [0, 2^63-1]
        assert 0 <= key <= 0x7FFFFFFFFFFFFFFF, f"key={key} out of valid range"
    
    def test_make_lock_key_different_namespace(self):
        """Test that different namespaces produce different keys."""
        token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        
        key1 = make_lock_key(token, namespace="telegram_polling")
        key2 = make_lock_key(token, namespace="telegram_webhook")
        
        assert key1 != key2, "Different namespaces should produce different keys"
    
    def test_make_lock_key_splittable(self):
        """Test that generated key can be split into valid signed int32."""
        token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        key = make_lock_key(token)
        
        hi, lo = split_bigint_to_pg_advisory_oids(key)
        
        # Проверяем что части в допустимом диапазоне signed int32
        assert -0x80000000 <= hi <= 0x7FFFFFFF
        assert -0x80000000 <= lo <= 0x7FFFFFFF
        
        # Проверяем обратное восстановление
        hi_unsigned = hi if hi >= 0 else hi + 0x100000000
        lo_unsigned = lo if lo >= 0 else lo + 0x100000000
        reconstructed = (hi_unsigned << 32) | lo_unsigned
        assert reconstructed == key

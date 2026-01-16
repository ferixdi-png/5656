#!/usr/bin/env python3
"""
Deterministic test for KIE sync - ensures two consecutive CHECK runs produce identical fingerprints.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.kie_sync import KIERegistrySync, ModelFingerprint


def test_deterministic_fingerprints():
    """Test that fingerprints are deterministic."""
    sync = KIERegistrySync()
    sync.load_local_registry()
    
    models = sync.local_sot.get("models", {})
    if not models:
        print("⚠️  No models found in registry")
        return True
    
    # Test first 5 models
    test_models = list(models.items())[:5]
    
    fingerprints_1 = {}
    fingerprints_2 = {}
    
    for model_id, model_data in test_models:
        fp1 = sync.compute_fingerprint(model_id, model_data, "local")
        fp2 = sync.compute_fingerprint(model_id, model_data, "local")
        
        fingerprints_1[model_id] = fp1.fingerprint_hash
        fingerprints_2[model_id] = fp2.fingerprint_hash
        
        assert fp1.fingerprint_hash == fp2.fingerprint_hash, \
            f"Fingerprint not deterministic for {model_id}: {fp1.fingerprint_hash} != {fp2.fingerprint_hash}"
    
    print(f"✅ Deterministic test passed for {len(test_models)} models")
    return True


if __name__ == "__main__":
    try:
        test_deterministic_fingerprints()
        print("✅ All deterministic tests passed")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


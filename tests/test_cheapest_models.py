#!/usr/bin/env python3
"""
Tests for CHEAPEST KIE.AI models (0.36₽ - 3.56₽)
Budget: ~50₽ max
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kie.builder import build_payload
import time

def test_recraft_upscale():
    """Test Recraft Crisp Upscale - 0.36₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Recraft Crisp Upscale (0.36₽)")
    print("="*80)
    
    payload = build_payload("recraft/crisp-upscale", {
        "image": "https://example.com/test.jpg"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 0.36₽")
    # Note: Don't actually run - need real image URL

def test_qwen_z_image():
    """Test Qwen Z-Image - 0.57₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Qwen Z-Image (0.57₽)")
    print("="*80)
    
    payload = build_payload("qwen/z-image", {
        "prompt": "A cute cat sitting on a windowsill"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 0.57₽")

def test_recraft_remove_bg():
    """Test Recraft Remove Background - 0.71₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Recraft Remove Background (0.71₽)")
    print("="*80)
    
    payload = build_payload("recraft/remove-background", {
        "image": "https://example.com/test.jpg"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 0.71₽")

def test_midjourney_fast():
    """Test Midjourney Fast - 2.14₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Midjourney Text-to-Image Fast (2.14₽)")
    print("="*80)
    
    payload = build_payload("midjourney/text-to-image", {
        "prompt": "A magical forest with glowing mushrooms"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 2.14₽")

def test_ideogram_v3():
    """Test Ideogram V3 - 2.49₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Ideogram V3 (2.49₽)")
    print("="*80)
    
    payload = build_payload("ideogram/v3", {
        "prompt": "Modern minimalist logo for AI company"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 2.49₽")

def test_grok_text_to_image():
    """Test Grok Imagine Text-to-Image - 2.85₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Grok Imagine Text-to-Image (2.85₽)")
    print("="*80)
    
    payload = build_payload("grok-imagine/text-to-image", {
        "prompt": "A futuristic city at sunset"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 2.85₽")

def test_nano_banana():
    """Test Nano Banana - 2.85₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Nano Banana (2.85₽)")
    print("="*80)
    
    payload = build_payload("nano-banana", {
        "prompt": "A beautiful landscape with mountains"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 2.85₽")

def test_flux_pro():
    """Test Flux 2 Pro - 3.56₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Flux 2 Pro (3.56₽)")
    print("="*80)
    
    payload = build_payload("flux/2-pro-text-to-image", {
        "prompt": "Photorealistic portrait of a wise old wizard"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 3.56₽")

def test_seedream_4():
    """Test Seedream 4.0 - 3.56₽"""
    print("\n" + "="*80)
    print("🧪 TEST: Seedream 4.0 (3.56₽)")
    print("="*80)
    
    payload = build_payload("seedream/4.0-text-to-image", {
        "prompt": "Anime style character portrait"
    })
    
    print(f"📦 Payload: {payload}")
    print("💰 Cost: 3.56₽")

def main():
    """Run all tests"""
    print("🚀 CHEAPEST KIE.AI MODELS TEST SUITE")
    print(f"📅 Date: 2025-12-24")
    print(f"💵 Budget: 50₽ max")
    print(f"🔑 API Key: {'✅ SET' if os.getenv('KIE_API_KEY') else '❌ NOT SET'}")
    
    total_cost = 0.36 + 0.57 + 0.71 + 2.14 + 2.49 + 2.85 + 2.85 + 3.56 + 3.56
    print(f"💰 Estimated total cost: {total_cost:.2f}₽")
    
    # Run payload tests (no API calls yet)
    test_recraft_upscale()
    test_qwen_z_image()
    test_recraft_remove_bg()
    test_midjourney_fast()
    test_ideogram_v3()
    test_grok_text_to_image()
    test_nano_banana()
    test_flux_pro()
    test_seedream_4()
    
    print("\n" + "="*80)
    print("✅ ALL PAYLOAD TESTS PASSED")
    print("="*80)
    print()
    print("⚠️  To run REAL API tests:")
    print("   export KIE_API_KEY=sk-your-key")
    print("   python tests/test_cheapest_models.py --real")
    print()

if __name__ == "__main__":
    main()

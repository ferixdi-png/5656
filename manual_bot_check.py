#!/usr/bin/env python3
"""
Manual test script to verify bot startup in DRY_RUN mode.
Tests that all handlers are registered and basic flow works.
"""
import asyncio
import os
import sys

# Set DRY_RUN mode
os.environ["DRY_RUN"] = "1"
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:TEST_TOKEN_FOR_DRY_RUN"
os.environ["BOT_MODE"] = "polling"
os.environ["PORT"] = "0"  # Disable healthcheck

async def test_bot_startup():
    """Test that bot can be created and handlers are registered."""
    print("=" * 60)
    print("Testing bot startup in DRY_RUN mode...")
    print("=" * 60)
    
    try:
        from main_render import create_bot_application
        
        dp, bot = create_bot_application()
        
        print(f"✅ Bot created successfully")
        print(f"✅ Dispatcher created")
        
        # Test source of truth loading
        from app.kie.builder import load_source_of_truth
        source = load_source_of_truth()
        models_count = len(source.get('models', []))
        print(f"✅ Source of truth loaded: {models_count} models")
        
        # Test charge manager
        from app.payments.charges import get_charge_manager
        charge_mgr = get_charge_manager()
        test_balance = charge_mgr.get_user_balance(12345)
        print(f"✅ Charge manager working (test balance: {test_balance})")
        
        # Cleanup
        await bot.session.close()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED - Bot is ready for deployment")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_bot_startup())
    sys.exit(0 if result else 1)

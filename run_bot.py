"""
Run script for KIE Telegram Bot
This is a simplified version that only starts the bot if a token is available
"""

import os
import sys
import shutil
import importlib
from dotenv import load_dotenv

# Clear Python cache to force module reload
cache_dirs = ['__pycache__']
for cache_dir in cache_dirs:
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print(f"Cleared cache: {cache_dir}")
        except Exception as e:
            print(f"Warning: Could not clear cache {cache_dir}: {e}")

# Load environment variables
load_dotenv()

# Check if bot token is available
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
    print("ERROR: No valid bot token found!")
    print("\nTo run the bot:")
    print("1. Get a bot token from @BotFather on Telegram")
    print("2. Update the .env file with your bot token")
    print("3. Run this script again")
    sys.exit(1)

print("=" * 60)
print("Starting KIE Telegram Bot...")
print("=" * 60)
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"Platform: {os.name}")
print("=" * 60)
sys.stdout.flush()

# Import and run the bot only if token is available
try:
    # Force reload modules to ensure latest changes are loaded
    print("Step 1: Removing modules from cache...", flush=True)
    modules_to_remove = ['bot_kie', 'kie_models', 'kie_client', 'knowledge_storage']
    for mod_name in modules_to_remove:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
            print(f"  ✓ Removed {mod_name} from cache", flush=True)
    
    print("Step 2: Loading kie_models fresh...", flush=True)
    import kie_models
    importlib.reload(kie_models)
    print("  ✓ kie_models reloaded", flush=True)
    
    print("Step 3: Verifying models...", flush=True)
    from kie_models import KIE_MODELS, get_categories
    categories = get_categories()
    sora_models = [m for m in KIE_MODELS if m['id'] == 'sora-watermark-remover']
    
    print(f"\n{'='*60}", flush=True)
    print(f"MODEL VERIFICATION:", flush=True)
    print(f"Total models: {len(KIE_MODELS)}", flush=True)
    print(f"Categories: {categories}", flush=True)
    if sora_models:
        print(f"✅ Sora model found: {sora_models[0]['name']} ({sora_models[0]['category']})", flush=True)
    else:
        print("❌ WARNING: Sora model NOT found in KIE_MODELS!", flush=True)
        print("Available models:", flush=True)
        for m in KIE_MODELS:
            print(f"  - {m['id']} ({m['category']})", flush=True)
    print(f"{'='*60}\n", flush=True)
    sys.stdout.flush()
    
    print("Step 4: Loading bot_kie...", flush=True)
    if 'bot_kie' in sys.modules:
        del sys.modules['bot_kie']
    dependent_modules = ['kie_client', 'knowledge_storage']
    for mod_name in dependent_modules:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    
    import bot_kie
    importlib.reload(bot_kie)
    print("  ✓ bot_kie reloaded", flush=True)
    
    from bot_kie import main
    print("Using enhanced bot with KIE AI support", flush=True)
    print("✅ All modules reloaded - latest changes will be applied\n", flush=True)
    sys.stdout.flush()
    main()
except ImportError as e:
    print(f"Error importing bot: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error running bot: {e}")
    sys.exit(1)
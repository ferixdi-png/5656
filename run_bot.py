#!/usr/bin/env python3
"""
Entry point for KIE Telegram Bot
This script starts the bot and handles graceful shutdown
"""

import sys
import os
import logging

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    try:
        # Import and run bot
        from bot_kie import main as bot_main
        logger.info("🚀 Starting KIE Telegram Bot...")
        bot_main()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

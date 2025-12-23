#!/usr/bin/env python3
"""
Auto-configure 5 cheapest models as free tier.
Run this during initialization to setup free models automatically.
"""
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_free_tier():
    """Setup 5 cheapest models as free tier."""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        logger.error("DATABASE_URL not set")
        return False
    
    # Load registry
    registry_path = "models/kie_models_source_of_truth.json"
    if not os.path.exists(registry_path):
        logger.error(f"Registry not found: {registry_path}")
        return False
    
    with open(registry_path, 'r') as f:
        sot = json.load(f)
    
    # Find 5 cheapest models
    models = [m for m in sot['models'] if m.get('is_pricing_known')]
    models.sort(key=lambda m: m.get('price', 999999))
    cheapest_5 = models[:5]
    
    logger.info(f"Found {len(cheapest_5)} cheapest models:")
    for m in cheapest_5:
        logger.info(f"  - {m['model_id']:40} {m.get('price', 0):6.2f} RUB")
    
    # Initialize services
    from app.database.services import DatabaseService
    from app.free.manager import FreeModelManager
    
    db_service = DatabaseService(database_url)
    await db_service.initialize()
    
    free_manager = FreeModelManager(db_service)
    
    # Configure each as free
    for model in cheapest_5:
        model_id = model['model_id']
        
        # Check if already free
        is_free = await free_manager.is_model_free(model_id)
        
        if is_free:
            logger.info(f"✓ {model_id} already free")
            continue
        
        # Add as free with generous limits
        await free_manager.add_free_model(
            model_id=model_id,
            daily_limit=10,   # 10 per day
            hourly_limit=3    # 3 per hour
        )
        logger.info(f"✅ {model_id} configured as free (10/day, 3/hour)")
    
    await db_service.close()
    logger.info("✅ Free tier setup complete!")
    return True


if __name__ == "__main__":
    success = asyncio.run(setup_free_tier())
    sys.exit(0 if success else 1)

"""
Smart File Discovery для multi-bot балансов (Batch 48.9)

Автоматически определяет и создаёт файлы балансов для каждого бота.
"""
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def discover_balance_file(bot_token: Optional[str] = None) -> Path:
    """
    Умное определение файла балансов для бота.
    
    Логика:
    1. Извлечь bot_id из BOT_TOKEN
    2. Проверить существует ли data/user_balances_bot_<ID>.json
    3. Если нет → создать с пустыми балансами
    4. Если есть → использовать существующий
    5. Логировать процесс для диагностики
    
    Returns:
        Path к файлу балансов для этого бота
    """
    if not bot_token:
        bot_token = os.getenv("BOT_TOKEN", "")
    
    if not bot_token:
        logger.debug("BOT_TOKEN not found, using default file (expected in single-bot setups)")
        return Path("data/user_balances.json")
    
    # Extract bot_id from token
    try:
        bot_id = bot_token.split(":")[0]
        logger.info(f"🔍 Detected bot_id: {bot_id}")
    except Exception as e:
        logger.error(f"❌ Failed to extract bot_id: {e}")
        return Path("data/user_balances.json")
    
    # Construct file path
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    balance_file = data_dir / f"user_balances_bot_{bot_id}.json"
    
    # Check if file exists
    if balance_file.exists():
        logger.info(f"✅ Balance file EXISTS: {balance_file.name}")
        logger.info(f"📊 Using existing balances for bot {bot_id}")
        return balance_file
    else:
        logger.info(f"🆕 Balance file NOT FOUND: {balance_file.name}")
        logger.info(f"📝 Will create new balance file for bot {bot_id}")
        # File will be created by FileStorage._init_file()
        return balance_file


def check_multi_bot_conflicts(bot_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Проверка на конфликты между ботами (одинаковые bot_id).
    
    Returns:
        dict с информацией о других ботах в data/
    """
    if not bot_token:
        bot_token = os.getenv("BOT_TOKEN", "")
    
    if not bot_token:
        return {"error": "BOT_TOKEN not set"}
    
    try:
        bot_id = bot_token.split(":")[0]
    except Exception:
        return {"error": "Invalid BOT_TOKEN"}
    
    # Find all balance files
    data_dir = Path("data")
    if not data_dir.exists():
        return {"bot_id": bot_id, "other_bots": [], "conflicts": False}
    
    other_bots = []
    for file in data_dir.glob("user_balances_bot_*.json"):
        # Extract bot_id from filename
        filename = file.stem  # user_balances_bot_123456789
        file_bot_id = filename.split("_")[-1]  # 123456789
        
        if file_bot_id != bot_id:
            other_bots.append({
                "bot_id": file_bot_id,
                "file": file.name,
                "size_kb": file.stat().st_size / 1024
            })
    
    return {
        "bot_id": bot_id,
        "my_file": f"user_balances_bot_{bot_id}.json",
        "other_bots": other_bots,
        "conflicts": False  # No conflicts with file-based approach
    }


def log_balance_file_status(balance_file: Path):
    """
    Логирует подробный статус файла балансов.
    
    Для диагностики и monitoring.
    """
    try:
        if balance_file.exists():
            import json
            
            # Read file (handle UTF-8 BOM)
            # BATCH 48.31: Handle UTF-8 BOM (some editors add BOM)
            try:
                with open(balance_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                # Try with utf-8-sig if regular utf-8 fails (BOM handling)
                with open(balance_file, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            
            users_count = len(data.get("users", {}))
            total_balance = sum(
                user.get("balance", 0.0)
                for user in data.get("users", {}).values()
            )
            
            metadata = data.get("metadata", {})
            created_at = metadata.get("created_at", "unknown")
            updated_at = metadata.get("updated_at", "unknown")
            bot_id = metadata.get("bot_id", "unknown")
            
            logger.info("=" * 60)
            logger.info(f"📊 BALANCE FILE STATUS: {balance_file.name}")
            logger.info("=" * 60)
            logger.info(f"  Bot ID: {bot_id}")
            logger.info(f"  Users: {users_count}")
            logger.info(f"  Total Balance: {total_balance:.2f}₽")
            logger.info(f"  Created: {created_at}")
            logger.info(f"  Updated: {updated_at}")
            logger.info(f"  File Size: {balance_file.stat().st_size / 1024:.2f} KB")
            logger.info("=" * 60)
        else:
            logger.info(f"📝 Balance file will be created: {balance_file.name}")
    
    except Exception as e:
        logger.error(f"❌ Failed to read balance file status: {e}")


def ensure_balance_file_in_git(balance_file: Path):
    """
    Убедиться что файл балансов tracked в git.
    
    Добавляет в .gitignore правило чтобы НЕ игнорировать balance files.
    """
    try:
        gitignore_path = Path(".gitignore")
        
        # Read current .gitignore
        if gitignore_path.exists():
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = ""
        
        # Check if data/ is ignored
        if "data/" in content or "data/*" in content:
            # Ensure balance files are NOT ignored
            rule = f"!{balance_file.name}"
            
            if rule not in content:
                logger.info(f"📝 Adding git rule: {rule}")
                with open(gitignore_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n# BATCH 48.9: Track balance files\n")
                    f.write(f"{rule}\n")
                logger.info("✅ Balance file will be tracked in git")
        
        # Also ensure pending_git_pushes is ignored
        pending_rule = "data/pending_git_pushes/"
        if pending_rule not in content:
            with open(gitignore_path, 'a', encoding='utf-8') as f:
                f.write(f"\n# BATCH 48.9: Ignore pending git pushes (temporary)\n")
                f.write(f"{pending_rule}\n")
    
    except Exception as e:
        logger.error(f"❌ Failed to update .gitignore: {e}")


def verify_balance_file_integrity(balance_file: Path) -> bool:
    """
    Проверка целостности файла балансов.
    
    Returns:
        True if file is valid, False otherwise
    """
    if not balance_file.exists():
        logger.warning(f"⚠️ Balance file does not exist: {balance_file.name}")
        return False
    
    try:
        import json
        
        # BATCH 48.31: Handle UTF-8 BOM (some editors add BOM)
        with open(balance_file, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        
        # Check required fields
        if "users" not in data:
            logger.error("❌ Missing 'users' field in balance file")
            return False
        
        if "metadata" not in data:
            logger.error("❌ Missing 'metadata' field in balance file")
            return False
        
        # Check metadata
        metadata = data["metadata"]
        required_metadata = ["bot_id", "created_at", "version"]
        for field in required_metadata:
            if field not in metadata:
                logger.warning(f"⚠️ Missing metadata field: {field}")
        
        # Check users structure
        for user_id, user_data in data["users"].items():
            if "balance" not in user_data:
                logger.error(f"❌ User {user_id} missing 'balance' field")
                return False
            
            balance = user_data["balance"]
            if not isinstance(balance, (int, float)):
                logger.error(f"❌ User {user_id} has invalid balance type: {type(balance)}")
                return False
            
            if balance < 0:
                logger.warning(f"⚠️ User {user_id} has negative balance: {balance}")
        
        logger.info(f"✅ Balance file integrity check PASSED: {balance_file.name}")
        return True
    
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in balance file: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Balance file integrity check failed: {e}")
        return False


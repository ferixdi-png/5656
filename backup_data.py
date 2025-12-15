#!/usr/bin/env python3
"""
Скрипт для резервного копирования данных бота
Использование: python backup_data.py [--output backup_dir]
"""

import os
import json
import shutil
import argparse
from datetime import datetime
from pathlib import Path

# Data files to backup
DATA_FILES = [
    "user_balances.json",
    "payments.json",
    "generations_history.json",
    "user_languages.json",
    "daily_free_generations.json",
    "promocodes.json",
    "referrals.json",
    "broadcasts.json",
    "blocked_users.json",
    "admin_limits.json",
    "currency_rate.json",
    "gift_claimed.json"
]

def backup_data(data_dir="./data", output_dir=None):
    """Create backup of all data files."""
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"backup_{timestamp}"
    
    # Create backup directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📁 Data directory: {data_dir}")
    print(f"💾 Backup directory: {output_dir}")
    print()
    
    backed_up = 0
    skipped = 0
    errors = 0
    
    for filename in DATA_FILES:
        source_path = os.path.join(data_dir, filename) if data_dir != '.' else filename
        
        if not os.path.exists(source_path):
            print(f"⚠️  Skipping (not found): {filename}")
            skipped += 1
            continue
        
        try:
            dest_path = os.path.join(output_dir, filename)
            shutil.copy2(source_path, dest_path)
            file_size = os.path.getsize(dest_path)
            print(f"✅ Backed up: {filename} ({file_size} bytes)")
            backed_up += 1
        except Exception as e:
            print(f"❌ Error backing up {filename}: {e}")
            errors += 1
    
    # Create backup info file
    backup_info = {
        "timestamp": datetime.now().isoformat(),
        "data_dir": data_dir,
        "files_backed_up": backed_up,
        "files_skipped": skipped,
        "errors": errors,
        "files": {}
    }
    
    for filename in DATA_FILES:
        source_path = os.path.join(data_dir, filename) if data_dir != '.' else filename
        if os.path.exists(source_path):
            backup_info["files"][filename] = {
                "size": os.path.getsize(source_path),
                "modified": datetime.fromtimestamp(os.path.getmtime(source_path)).isoformat()
            }
    
    info_path = os.path.join(output_dir, "backup_info.json")
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(backup_info, f, ensure_ascii=False, indent=2)
    
    print()
    print("=" * 60)
    print(f"✅ Backup complete!")
    print(f"   Files backed up: {backed_up}")
    print(f"   Files skipped: {skipped}")
    print(f"   Errors: {errors}")
    print(f"   Backup location: {os.path.abspath(output_dir)}")
    print("=" * 60)
    
    return output_dir

def restore_backup(backup_dir, data_dir="./data"):
    """Restore data from backup."""
    print(f"📁 Backup directory: {backup_dir}")
    print(f"💾 Data directory: {data_dir}")
    print()
    
    if not os.path.exists(backup_dir):
        print(f"❌ Backup directory not found: {backup_dir}")
        return False
    
    # Create data directory if it doesn't exist
    if data_dir != '.' and not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        print(f"✅ Created data directory: {data_dir}")
    
    restored = 0
    errors = 0
    
    for filename in DATA_FILES:
        backup_path = os.path.join(backup_dir, filename)
        
        if not os.path.exists(backup_path):
            print(f"⚠️  Skipping (not in backup): {filename}")
            continue
        
        try:
            dest_path = os.path.join(data_dir, filename) if data_dir != '.' else filename
            
            # Backup existing file if it exists
            if os.path.exists(dest_path):
                backup_existing = dest_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(dest_path, backup_existing)
                print(f"💾 Backed up existing: {filename} -> {os.path.basename(backup_existing)}")
            
            shutil.copy2(backup_path, dest_path)
            file_size = os.path.getsize(dest_path)
            print(f"✅ Restored: {filename} ({file_size} bytes)")
            restored += 1
        except Exception as e:
            print(f"❌ Error restoring {filename}: {e}")
            errors += 1
    
    print()
    print("=" * 60)
    print(f"✅ Restore complete!")
    print(f"   Files restored: {restored}")
    print(f"   Errors: {errors}")
    print("=" * 60)
    
    return errors == 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup or restore bot data")
    parser.add_argument("--data-dir", default="./data", help="Data directory (default: ./data)")
    parser.add_argument("--output", help="Output directory for backup")
    parser.add_argument("--restore", help="Restore from backup directory")
    
    args = parser.parse_args()
    
    # Use DATA_DIR environment variable if set
    data_dir = os.getenv("DATA_DIR", args.data_dir)
    
    if args.restore:
        restore_backup(args.restore, data_dir)
    else:
        backup_data(data_dir, args.output)


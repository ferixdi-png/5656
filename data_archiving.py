"""
Модуль для архивации старых данных в базе данных.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import json
import gzip

logger = logging.getLogger(__name__)

# Директория для архивов
ARCHIVE_DIR = Path("data/archives")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def archive_old_generations(days_to_keep: int = 90, batch_size: int = 1000) -> Dict[str, Any]:
    """
    Архивирует старые генерации в файлы.
    
    Args:
        days_to_keep: Количество дней для хранения в БД
        batch_size: Размер батча для архивации
    
    Returns:
        Словарь со статистикой архивации
    """
    try:
        from database import get_db_connection
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Получаем количество записей для архивации
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM generations 
                    WHERE created_at < %s
                """, (cutoff_date,))
                total_count = cur.fetchone()[0]
                
                if total_count == 0:
                    return {
                        'archived': 0,
                        'deleted': 0,
                        'files_created': 0
                    }
                
                # Создаем архивный файл
                archive_file = ARCHIVE_DIR / f"generations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
                
                archived_count = 0
                deleted_count = 0
                
                # Архивируем батчами
                offset = 0
                while True:
                    cur.execute("""
                        SELECT id, user_id, model_id, model_name, params, result_urls, 
                               task_id, price, is_free, created_at
                        FROM generations 
                        WHERE created_at < %s
                        ORDER BY created_at
                        LIMIT %s OFFSET %s
                    """, (cutoff_date, batch_size, offset))
                    
                    batch = cur.fetchall()
                    if not batch:
                        break
                    
                    # Записываем в архив
                    archive_data = []
                    for row in batch:
                        archive_data.append({
                            'id': row[0],
                            'user_id': row[1],
                            'model_id': row[2],
                            'model_name': row[3],
                            'params': row[4] if isinstance(row[4], dict) else json.loads(row[4]) if row[4] else {},
                            'result_urls': row[5] if isinstance(row[5], list) else json.loads(row[5]) if row[5] else [],
                            'task_id': row[6],
                            'price': float(row[7]) if row[7] else 0,
                            'is_free': row[8],
                            'created_at': row[9].isoformat() if row[9] else None
                        })
                    
                    # Добавляем в архивный файл
                    with gzip.open(archive_file, 'at', encoding='utf-8') as f:
                        for item in archive_data:
                            f.write(json.dumps(item, ensure_ascii=False) + '\n')
                    
                    # Удаляем из БД
                    ids_to_delete = [row[0] for row in batch]
                    cur.execute("""
                        DELETE FROM generations 
                        WHERE id = ANY(%s)
                    """, (ids_to_delete,))
                    
                    archived_count += len(batch)
                    deleted_count += len(ids_to_delete)
                    offset += batch_size
                    
                    logger.info(f"📦 Архивировано {archived_count}/{total_count} записей...")
                
                conn.commit()
                
                logger.info(f"✅ Архивировано {archived_count} генераций в {archive_file}")
                
                return {
                    'archived': archived_count,
                    'deleted': deleted_count,
                    'files_created': 1,
                    'archive_file': str(archive_file)
                }
                
    except Exception as e:
        logger.error(f"❌ Ошибка при архивации генераций: {e}", exc_info=True)
        return {
            'archived': 0,
            'deleted': 0,
            'files_created': 0,
            'error': str(e)
        }


def archive_old_sessions(days_to_keep: int = 7) -> Dict[str, Any]:
    """
    Архивирует старые сессии.
    
    Args:
        days_to_keep: Количество дней для хранения в БД
    
    Returns:
        Словарь со статистикой архивации
    """
    try:
        from database import get_db_connection
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Получаем количество записей для архивации
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM operations 
                    WHERE type = 'session' AND created_at < %s
                """, (cutoff_date,))
                total_count = cur.fetchone()[0]
                
                if total_count == 0:
                    return {
                        'archived': 0,
                        'deleted': 0
                    }
                
                # Удаляем старые сессии (они обычно не требуют архивации)
                cur.execute("""
                    DELETE FROM operations 
                    WHERE type = 'session' AND created_at < %s
                """, (cutoff_date,))
                
                deleted_count = cur.rowcount
                conn.commit()
                
                logger.info(f"✅ Удалено {deleted_count} старых сессий")
                
                return {
                    'archived': 0,
                    'deleted': deleted_count
                }
                
    except Exception as e:
        logger.error(f"❌ Ошибка при архивации сессий: {e}", exc_info=True)
        return {
            'archived': 0,
            'deleted': 0,
            'error': str(e)
        }


def cleanup_old_archives(days_to_keep: int = 365) -> int:
    """
    Удаляет старые архивные файлы.
    
    Args:
        days_to_keep: Количество дней для хранения архивов
    
    Returns:
        Количество удаленных файлов
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        for archive_file in ARCHIVE_DIR.glob("*.json.gz"):
            file_time = datetime.fromtimestamp(archive_file.stat().st_mtime)
            if file_time < cutoff_date:
                archive_file.unlink()
                deleted_count += 1
                logger.info(f"🗑️ Удален старый архив: {archive_file.name}")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке архивов: {e}", exc_info=True)
        return 0


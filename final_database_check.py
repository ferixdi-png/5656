#!/usr/bin/env python3
"""
Скрипт для проверки базы данных и её производительности.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_database_size():
    """Проверяет размер базы данных."""
    logger.info("🔍 Проверка размера базы данных...")
    
    try:
        from database import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Получаем размер базы данных
                cur.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size
                """)
                result = cur.fetchone()
                db_size = result[0] if result else "Unknown"
                
                logger.info(f"📊 Размер базы данных: {db_size}")
                
                # Проверяем размер таблиц
                cur.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 10
                """)
                
                tables = cur.fetchall()
                logger.info("\n📋 Размеры таблиц:")
                for table in tables:
                    logger.info(f"  {table[1]}: {table[2]}")
                
                # Проверяем, не превышает ли база 1 ГБ
                cur.execute("""
                    SELECT pg_database_size(current_database()) / 1024 / 1024 / 1024.0 as size_gb
                """)
                result = cur.fetchone()
                size_gb = result[0] if result else 0
                
                if size_gb > 1.0:
                    logger.warning(f"⚠️ База данных превышает 1 ГБ: {size_gb:.2f} ГБ")
                    return False
                else:
                    logger.info(f"✅ Размер базы данных в пределах нормы: {size_gb:.2f} ГБ")
                    return True
                
    except ImportError:
        logger.warning("⚠️ Модуль database не доступен, пропускаем проверку")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке размера БД: {e}", exc_info=True)
        return False


def check_old_data():
    """Проверяет наличие старых данных."""
    logger.info("🔍 Проверка старых данных...")
    
    try:
        from database import get_db_connection
        from datetime import datetime, timedelta
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем старые генерации (старше 90 дней)
                cutoff_date = datetime.now() - timedelta(days=90)
                cur.execute("""
                    SELECT COUNT(*) FROM generations
                    WHERE created_at < %s
                """, (cutoff_date,))
                
                old_generations = cur.fetchone()[0]
                logger.info(f"📊 Старых генераций (старше 90 дней): {old_generations}")
                
                # Проверяем старые операции (старше 30 дней)
                cutoff_date = datetime.now() - timedelta(days=30)
                cur.execute("""
                    SELECT COUNT(*) FROM operations
                    WHERE created_at < %s
                """, (cutoff_date,))
                
                old_operations = cur.fetchone()[0]
                logger.info(f"📊 Старых операций (старше 30 дней): {old_operations}")
                
                if old_generations > 1000 or old_operations > 10000:
                    logger.warning("⚠️ Обнаружено много старых данных, рекомендуется очистка")
                    return False
                else:
                    logger.info("✅ Количество старых данных в пределах нормы")
                    return True
                
    except ImportError:
        logger.warning("⚠️ Модуль database не доступен, пропускаем проверку")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке старых данных: {e}", exc_info=True)
        return False


def test_database_performance():
    """Тестирует производительность базы данных."""
    logger.info("🔍 Тестирование производительности БД...")
    
    try:
        from database import get_db_connection
        import time
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Тест 1: Получение баланса пользователя
                start_time = time.time()
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0) as balance
                    FROM operations
                    WHERE user_id = %s
                """, (1,))
                result = cur.fetchone()
                elapsed = time.time() - start_time
                
                logger.info(f"⏱️ Получение баланса: {elapsed*1000:.2f} мс")
                
                if elapsed > 0.1:
                    logger.warning("⚠️ Медленный запрос баланса (>100 мс)")
                    return False
                
                # Тест 2: Получение генераций пользователя
                start_time = time.time()
                cur.execute("""
                    SELECT id, model_id, created_at
                    FROM generations
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (1,))
                results = cur.fetchall()
                elapsed = time.time() - start_time
                
                logger.info(f"⏱️ Получение генераций: {elapsed*1000:.2f} мс")
                
                if elapsed > 0.2:
                    logger.warning("⚠️ Медленный запрос генераций (>200 мс)")
                    return False
                
                logger.info("✅ Производительность БД в пределах нормы")
                return True
                
    except ImportError:
        logger.warning("⚠️ Модуль database не доступен, пропускаем проверку")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании производительности: {e}", exc_info=True)
        return False


def main():
    """Основная функция проверки."""
    logger.info("🚀 Начало проверки базы данных...")
    
    results = {
        'size': False,
        'old_data': False,
        'performance': False
    }
    
    # Проверка размера БД
    results['size'] = check_database_size()
    
    # Проверка старых данных
    results['old_data'] = check_old_data()
    
    # Тестирование производительности
    results['performance'] = test_database_performance()
    
    # Итоговый отчет
    logger.info("\n" + "="*60)
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ:")
    logger.info("="*60)
    
    for check_name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info(f"  {check_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✅ Все проверки пройдены успешно!")
        return 0
    else:
        logger.warning("\n⚠️ Некоторые проверки не пройдены")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)


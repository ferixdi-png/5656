#!/usr/bin/env python3
"""
Скрипт для создания индексов в базе данных для оптимизации производительности.
Индексы ускоряют поиск по часто используемым полям.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

load_dotenv()

# Настройка логирования
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_indexes():
    """Создает индексы для оптимизации производительности БД."""
    try:
        from database import get_db_connection
        
        indexes = [
            # Индекс для быстрого поиска пользователей
            ("CREATE INDEX IF NOT EXISTS idx_users_id ON users(id)", "users.id"),
            
            # Индексы для операций
            ("CREATE INDEX IF NOT EXISTS idx_operations_user_id ON operations(user_id)", "operations.user_id"),
            ("CREATE INDEX IF NOT EXISTS idx_operations_type ON operations(type)", "operations.type"),
            ("CREATE INDEX IF NOT EXISTS idx_operations_created_at ON operations(created_at)", "operations.created_at"),
            ("CREATE INDEX IF NOT EXISTS idx_operations_user_type ON operations(user_id, type)", "operations(user_id, type)"),
            
            # Индексы для генераций
            ("CREATE INDEX IF NOT EXISTS idx_generations_user_id ON generations(user_id)", "generations.user_id"),
            ("CREATE INDEX IF NOT EXISTS idx_generations_model_id ON generations(model_id)", "generations.model_id"),
            ("CREATE INDEX IF NOT EXISTS idx_generations_created_at ON generations(created_at)", "generations.created_at"),
            ("CREATE INDEX IF NOT EXISTS idx_generations_user_created ON generations(user_id, created_at)", "generations(user_id, created_at)"),
            
            # Индексы для KIE логов
            ("CREATE INDEX IF NOT EXISTS idx_kie_logs_user_id ON kie_logs(user_id)", "kie_logs.user_id"),
            ("CREATE INDEX IF NOT EXISTS idx_kie_logs_model ON kie_logs(model)", "kie_logs.model"),
            ("CREATE INDEX IF NOT EXISTS idx_kie_logs_created_at ON kie_logs(created_at)", "kie_logs.created_at"),
        ]
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                created_count = 0
                for index_sql, index_name in indexes:
                    try:
                        cur.execute(index_sql)
                        logger.info(f"✅ Индекс создан: {index_name}")
                        created_count += 1
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось создать индекс {index_name}: {e}")
                
                logger.info(f"\n📊 Итоговая статистика:")
                logger.info(f"  • Создано индексов: {created_count}")
                logger.info(f"  • Всего попыток: {len(indexes)}")
                
                return created_count
                
    except Exception as e:
        logger.error(f"❌ Ошибка при создании индексов: {e}", exc_info=True)
        return 0


def check_indexes():
    """Проверяет существующие индексы в БД."""
    try:
        from database import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    ORDER BY tablename, indexname
                """)
                
                indexes = cur.fetchall()
                
                logger.info(f"\n📊 Существующие индексы в БД:")
                for idx in indexes:
                    logger.info(f"  • {idx[1]}.{idx[2]}")
                
                return len(indexes)
                
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке индексов: {e}", exc_info=True)
        return 0


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Создание индексов в БД для оптимизации')
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Только проверить существующие индексы, не создавать новые'
    )
    
    args = parser.parse_args()
    
    if args.check_only:
        # Только проверяем индексы
        count = check_indexes()
        logger.info(f"\n✅ Найдено {count} индексов")
        return 0
    
    # Создаем индексы
    try:
        logger.info("🔧 Начало создания индексов...")
        created = create_indexes()
        
        if created > 0:
            logger.info(f"\n✅ Создано {created} индексов успешно!")
        else:
            logger.warning("\n⚠️ Индексы не были созданы")
        
        # Проверяем результат
        check_indexes()
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании индексов: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)


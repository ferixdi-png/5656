"""
Модуль для работы с PostgreSQL базой данных
Оптимизирован для эффективного использования пространства (1 ГБ)
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Константы для ограничения размера данных
MAX_PROMPT_LENGTH = 1000
MAX_ERROR_MESSAGE_LENGTH = 500
MAX_CONTEXT_LENGTH = 1000

# Глобальный пул соединений
_connection_pool: Optional[SimpleConnectionPool] = None


def get_connection_pool():
    """Создает и возвращает пул соединений с БД."""
    global _connection_pool
    
    if _connection_pool is None:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL не установлен в переменных окружения")
        
        try:
            # Парсим DATABASE_URL для создания пула
            # Формат: postgresql://user:password@host:port/database
            _connection_pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=database_url
            )
            logger.info("✅ Пул соединений с БД создан успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка создания пула соединений: {e}")
            raise
    
    return _connection_pool


@contextmanager
def get_db_connection():
    """Контекстный менеджер для получения соединения с БД."""
    pool = get_connection_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка БД: {e}")
        raise
    finally:
        pool.putconn(conn)


def init_database():
    """Инициализирует БД, создавая таблицы если их нет."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Читаем и выполняем schema.sql
                schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
                if os.path.exists(schema_path):
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        schema_sql = f.read()
                    cur.execute(schema_sql)
                    logger.info("✅ Схема БД инициализирована")
                else:
                    logger.warning("⚠️ Файл schema.sql не найден, таблицы могут не существовать")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise


def truncate_text(text: Optional[str], max_length: int) -> Optional[str]:
    """Обрезает текст до указанной длины."""
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length]


# ==================== USERS ====================

def get_or_create_user(user_id: int) -> Dict[str, Any]:
    """Получает пользователя или создает нового с балансом 0."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Пытаемся получить пользователя
            cur.execute(
                "SELECT * FROM users WHERE id = %s",
                (user_id,)
            )
            user = cur.fetchone()
            
            if user:
                return dict(user)
            
            # Создаем нового пользователя
            cur.execute(
                "INSERT INTO users (id, balance) VALUES (%s, 0.00) RETURNING *",
                (user_id,)
            )
            new_user = cur.fetchone()
            return dict(new_user)


def get_user_balance(user_id: int) -> Decimal:
    """Получает баланс пользователя."""
    user = get_or_create_user(user_id)
    return Decimal(str(user['balance']))


def update_user_balance(user_id: int, new_balance: Decimal) -> bool:
    """Обновляет баланс пользователя."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET balance = %s WHERE id = %s",
                    (new_balance, user_id)
                )
                return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка обновления баланса: {e}")
        return False


def add_to_balance(user_id: int, amount: Decimal) -> bool:
    """Добавляет сумму к балансу пользователя."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET balance = balance + %s WHERE id = %s",
                    (amount, user_id)
                )
                return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка добавления к балансу: {e}")
        return False


# ==================== OPERATIONS ====================

def create_operation(
    user_id: int,
    operation_type: str,
    amount: Decimal,
    model: Optional[str] = None,
    result_url: Optional[str] = None,
    prompt: Optional[str] = None
) -> Optional[int]:
    """Создает запись об операции."""
    try:
        # Обрезаем промпт до максимальной длины
        prompt_truncated = truncate_text(prompt, MAX_PROMPT_LENGTH)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO operations 
                       (user_id, type, amount, model, result_url, prompt)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (user_id, operation_type, amount, model, result_url, prompt_truncated)
                )
                operation_id = cur.fetchone()[0]
                return operation_id
    except Exception as e:
        logger.error(f"Ошибка создания операции: {e}")
        return None


def get_user_operations(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    operation_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Получает операции пользователя."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if operation_type:
                cur.execute(
                    """SELECT * FROM operations 
                       WHERE user_id = %s AND type = %s
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s""",
                    (user_id, operation_type, limit, offset)
                )
            else:
                cur.execute(
                    """SELECT * FROM operations 
                       WHERE user_id = %s
                       ORDER BY created_at DESC
                       LIMIT %s OFFSET %s""",
                    (user_id, limit, offset)
                )
            return [dict(row) for row in cur.fetchall()]


# ==================== KIE LOGS ====================

def log_kie_operation(
    user_id: Optional[int],
    model: Optional[str],
    prompt: Optional[str],
    result_url: Optional[str],
    error_message: Optional[str] = None
) -> Optional[int]:
    """Логирует операцию KIE."""
    try:
        prompt_truncated = truncate_text(prompt, MAX_PROMPT_LENGTH)
        error_truncated = truncate_text(error_message, MAX_ERROR_MESSAGE_LENGTH)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO kie_logs 
                       (user_id, model, prompt, result_url, error_message)
                       VALUES (%s, %s, %s, %s, %s)
                       RETURNING id""",
                    (user_id, model, prompt_truncated, result_url, error_truncated)
                )
                log_id = cur.fetchone()[0]
                return log_id
    except Exception as e:
        logger.error(f"Ошибка логирования KIE: {e}")
        return None


# ==================== DEBUG LOGS ====================

def log_debug(
    level: str,
    message: str,
    context: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """Логирует debug сообщение."""
    try:
        message_truncated = truncate_text(message, MAX_CONTEXT_LENGTH)
        
        # Ограничиваем размер JSON контекста
        if context:
            # Преобразуем в JSON и обрезаем если нужно
            context_json = json.dumps(context)
            if len(context_json) > MAX_CONTEXT_LENGTH:
                context_json = context_json[:MAX_CONTEXT_LENGTH]
            context_dict = json.loads(context_json) if context_json else None
        else:
            context_dict = None
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO debug_logs (level, message, context)
                       VALUES (%s, %s, %s::jsonb)
                       RETURNING id""",
                    (level, message_truncated, json.dumps(context_dict) if context_dict else None)
                )
                log_id = cur.fetchone()[0]
                return log_id
    except Exception as e:
        logger.error(f"Ошибка логирования debug: {e}")
        return None


# ==================== CLEANUP ====================

def cleanup_old_logs(days_to_keep: int = 30) -> Dict[str, int]:
    """Очищает старые логи (KIE и debug)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM cleanup_old_logs(%s)",
                    (days_to_keep,)
                )
                result = cur.fetchone()
                deleted_kie = result[0] if result else 0
                deleted_debug = result[1] if result else 0
                
                logger.info(f"Очищено: {deleted_kie} KIE логов, {deleted_debug} debug логов")
                return {
                    'deleted_kie_logs': deleted_kie,
                    'deleted_debug_logs': deleted_debug
                }
    except Exception as e:
        logger.error(f"Ошибка очистки логов: {e}")
        return {'deleted_kie_logs': 0, 'deleted_debug_logs': 0}


def get_database_size() -> Dict[str, Any]:
    """Получает информацию о размере БД."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Получаем размер БД
                cur.execute("""
                    SELECT 
                        pg_size_pretty(pg_database_size(current_database())) as db_size,
                        pg_database_size(current_database()) as db_size_bytes
                """)
                db_info = cur.fetchone()
                
                # Получаем размер таблиц
                cur.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                        pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY size_bytes DESC
                """)
                tables = [dict(row) for row in cur.fetchall()]
                
                return {
                    'database_size': dict(db_info),
                    'tables': tables
                }
    except Exception as e:
        logger.error(f"Ошибка получения размера БД: {e}")
        return {'database_size': {}, 'tables': []}


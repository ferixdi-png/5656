"""
Модуль для расширенной безопасности: шифрование, 2FA и проверки.
"""

import logging
import hashlib
import hmac
import secrets
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import base64

logger = logging.getLogger(__name__)

# Простое шифрование для чувствительных данных (для продакшена лучше использовать cryptography)
try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("⚠️ cryptography не установлен. Шифрование будет ограничено.")


def generate_encryption_key() -> bytes:
    """Генерирует ключ шифрования."""
    if CRYPTOGRAPHY_AVAILABLE:
        return Fernet.generate_key()
    else:
        # Простой ключ для базового шифрования (не рекомендуется для продакшена)
        return secrets.token_bytes(32)


def encrypt_sensitive_data(data: str, key: Optional[bytes] = None) -> str:
    """
    Шифрует чувствительные данные.
    
    Args:
        data: Данные для шифрования
        key: Ключ шифрования (если None, используется ключ из env)
    
    Returns:
        Зашифрованные данные в base64
    """
    try:
        import os
        
        if CRYPTOGRAPHY_AVAILABLE:
            if key is None:
                key_str = os.getenv('ENCRYPTION_KEY')
                if key_str:
                    key = base64.b64decode(key_str)
                else:
                    key = generate_encryption_key()
                    logger.warning("⚠️ Используется новый ключ шифрования. Сохраните ENCRYPTION_KEY в .env")
            
            f = Fernet(key)
            encrypted = f.encrypt(data.encode())
            return base64.b64encode(encrypted).decode()
        else:
            # Простое кодирование (не безопасно, только для тестов)
            logger.warning("⚠️ Используется простое кодирование вместо шифрования")
            return base64.b64encode(data.encode()).decode()
            
    except Exception as e:
        logger.error(f"❌ Ошибка при шифровании данных: {e}", exc_info=True)
        return data


def decrypt_sensitive_data(encrypted_data: str, key: Optional[bytes] = None) -> str:
    """
    Расшифровывает чувствительные данные.
    
    Args:
        encrypted_data: Зашифрованные данные
        key: Ключ шифрования
    
    Returns:
        Расшифрованные данные
    """
    try:
        import os
        
        if CRYPTOGRAPHY_AVAILABLE:
            if key is None:
                key_str = os.getenv('ENCRYPTION_KEY')
                if key_str:
                    key = base64.b64decode(key_str)
                else:
                    logger.error("❌ Ключ шифрования не найден")
                    return encrypted_data
            
            f = Fernet(key)
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted = f.decrypt(encrypted_bytes)
            return decrypted.decode()
        else:
            # Простое декодирование
            return base64.b64decode(encrypted_data.encode()).decode()
            
    except Exception as e:
        logger.error(f"❌ Ошибка при расшифровке данных: {e}", exc_info=True)
        return encrypted_data


# Хранилище 2FA кодов
_2fa_codes: Dict[int, Dict[str, Any]] = {}


def generate_2fa_code(user_id: int, operation: str = 'generation') -> str:
    """
    Генерирует код для двухфакторной аутентификации.
    
    Args:
        user_id: ID пользователя
        operation: Тип операции
    
    Returns:
        6-значный код
    """
    code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    _2fa_codes[user_id] = {
        'code': code,
        'operation': operation,
        'expires_at': datetime.now() + timedelta(minutes=10),
        'created_at': datetime.now()
    }
    
    logger.info(f"🔐 Сгенерирован 2FA код для пользователя {user_id}, операция: {operation}")
    return code


def verify_2fa_code(user_id: int, code: str, operation: Optional[str] = None) -> bool:
    """
    Проверяет код двухфакторной аутентификации.
    
    Args:
        user_id: ID пользователя
        code: Код для проверки
        operation: Тип операции (опционально)
    
    Returns:
        True, если код верен
    """
    if user_id not in _2fa_codes:
        return False
    
    code_data = _2fa_codes[user_id]
    
    # Проверяем срок действия
    if datetime.now() > code_data['expires_at']:
        del _2fa_codes[user_id]
        return False
    
    # Проверяем операцию
    if operation and code_data['operation'] != operation:
        return False
    
    # Проверяем код
    if code_data['code'] != code:
        return False
    
    # Код верен, удаляем его
    del _2fa_codes[user_id]
    logger.info(f"✅ 2FA код подтвержден для пользователя {user_id}")
    return True


def requires_2fa(operation: str, price: float = 0.0) -> bool:
    """
    Определяет, требуется ли 2FA для операции.
    
    Args:
        operation: Тип операции
        price: Стоимость операции
    
    Returns:
        True, если требуется 2FA
    """
    # 2FA требуется для:
    # - Генераций с высокой стоимостью (>1000 ₽)
    # - Изменения настроек бота
    # - Важных операций
    
    high_price_threshold = 1000.0
    important_operations = ['settings_change', 'admin_action', 'balance_transfer']
    
    if operation in important_operations:
        return True
    
    if price > high_price_threshold:
        return True
    
    return False


def hash_sensitive_data(data: str) -> str:
    """
    Хеширует чувствительные данные (одностороннее).
    
    Args:
        data: Данные для хеширования
    
    Returns:
        Хеш в hex формате
    """
    return hashlib.sha256(data.encode()).hexdigest()


def verify_data_integrity(data: str, expected_hash: str) -> bool:
    """
    Проверяет целостность данных.
    
    Args:
        data: Данные для проверки
        expected_hash: Ожидаемый хеш
    
    Returns:
        True, если данные не изменены
    """
    actual_hash = hash_sensitive_data(data)
    return hmac.compare_digest(actual_hash, expected_hash)


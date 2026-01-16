"""
Единый контракт логирования для инструментируемого продукта.

Цель: любой отказ кнопки/параметра должен быть диагностирован по логам за 60с
без участия разработчика.

Структура: correlation_id объединяет цепочку событий:
  CALLBACK_RECEIVED → CALLBACK_ROUTED → CALLBACK_ACCEPTED/REJECTED
  + UI_RENDER, PARAM_INPUT, ENQUEUE, DISPATCH, и т.д.

Все события логируются одной функцией log_event(**fields).
"""

import logging
import time
import json
import hashlib
from enum import Enum
from typing import Optional, Any, Dict
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


# ============================================================================
# REASON CODES - Почему кнопка/параметр не сработал
# ============================================================================

class ReasonCode(str, Enum):
    """Причины отказа callback/параметра/действия."""
    
    # LOCK/Mode
    PASSIVE_REJECT = "PASSIVE_REJECT"  # Инстанс не ACTIVE
    
    # Callback parsing
    UNKNOWN_ACTION = "UNKNOWN_ACTION"  # callback_data не распарсился
    CALLBACK_PARSE_ERROR = "CALLBACK_PARSE_ERROR"  # JSON parsing error
    
    # FSM/State
    STATE_MISMATCH = "STATE_MISMATCH"  # FSM state не тот
    EXPIRED_MESSAGE = "EXPIRED_MESSAGE"  # Кнопка на старом сообщении
    
    # Permission
    PERMISSION_DENIED = "PERMISSION_DENIED"  # Нет прав (не admin для /debug)
    
    # Validation
    VALIDATION_FAILED = "VALIDATION_FAILED"  # Параметр неверный
    INVALID_INPUT = "INVALID_INPUT"  # Input не соответствует schema
    
    # Rate limiting
    RATE_LIMIT = "RATE_LIMIT"
    
    # External services
    DOWNSTREAM_TIMEOUT = "DOWNSTREAM_TIMEOUT"  # KIE.ai, webhook timeout
    DOWNSTREAM_ERROR = "DOWNSTREAM_ERROR"  # KIE.ai, webhook error
    
    # Storage
    STORAGE_ERROR = "STORAGE_ERROR"  # File/JSON storage error
    DB_ERROR = "DB_ERROR"  # PostgreSQL error
    
    # System
    INTERNAL_ERROR = "INTERNAL_ERROR"  # Unexpected exception
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"  # Feature not yet implemented
    
    # Success/no-op
    NOOP = "NOOP"  # Действие игнорировано (обычно OK)
    SUCCESS = "SUCCESS"


class EventType(str, Enum):
    """Типы событий в логах."""
    MESSAGE = "message"
    CALLBACK_QUERY = "callback_query"
    PRE_CHECKOUT = "pre_checkout_query"
    KIE_CALLBACK = "kie_callback"
    COMMAND = "command"
    TEXT_INPUT = "text_input"


class Domain(str, Enum):
    """Предметная область события."""
    UX = "UX"
    BILLING = "BILLING"
    MODEL = "MODEL"
    STORAGE = "STORAGE"
    LOCK = "LOCK"
    WEBHOOK = "WEBHOOK"
    QUEUE = "QUEUE"


class BotState(str, Enum):
    """Режим бота при обработке события."""
    ACTIVE = "ACTIVE"
    PASSIVE = "PASSIVE"


# ============================================================================
# ТЕЛЕМЕТРИЯ
# ============================================================================

def hash_user_id(user_id: int) -> str:
    """Безопасно хэшировать user_id (без PII)."""
    return hashlib.sha256(str(user_id).encode()).hexdigest()[:8]


def hash_chat_id(chat_id: int) -> str:
    """Безопасно хэшировать chat_id (без PII)."""
    return hashlib.sha256(str(chat_id).encode()).hexdigest()[:8]


def new_correlation_id() -> str:
    """Генерировать уникальный correlation_id для tracking цепочки событий."""
    return str(uuid.uuid4())[:8]


def log_event(
    name: str,
    *,
    correlation_id: str,
    event_type: Optional[str] = None,
    update_id: Optional[int] = None,
    user_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    bot_state: Optional[str] = None,
    screen_id: Optional[str] = None,
    button_id: Optional[str] = None,
    action_id: Optional[str] = None,
    payload_sanitized: Optional[str] = None,
    handler: Optional[str] = None,
    result: Optional[str] = None,
    reason_code: Optional[str] = None,
    reason_text: Optional[str] = None,
    latency_ms: Optional[float] = None,
    domain: Optional[str] = None,
    flow_id: Optional[str] = None,
    step_id: Optional[str] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Логировать структурированное событие с correlation_id.
    
    Все поля опциональные (используй только необходимые).
    Все user_id/chat_id автоматически хэшируются для безопасности.
    
    Логируется как JSON line для удобного парсинга.
    
    Пример:
        log_event(
            "CALLBACK_RECEIVED",
            correlation_id=cid,
            event_type="callback_query",
            update_id=update.update_id,
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            button_id="CAT_IMAGE",
            payload_sanitized="action=category&id=1",
            reason_code="SUCCESS"
        )
    """
    
    # Безопасное хэширование
    user_hash = hash_user_id(user_id) if user_id else None
    chat_hash = hash_chat_id(chat_id) if chat_id else None
    
    # Timestamp
    ts = datetime.utcnow().isoformat() + "Z"
    
    # Построить event dict
    event = {
        "ts": ts,
        "name": name,
        "cid": correlation_id,
        "event_type": event_type,
        "update_id": update_id,
        "user_hash": user_hash,
        "chat_hash": chat_hash,
        "bot_state": bot_state,
        "domain": domain,
        "screen_id": screen_id,
        "button_id": button_id,
        "action_id": action_id,
        "handler": handler,
        "result": result,
        "reason_code": reason_code,
        "reason_text": reason_text,
        "latency_ms": latency_ms,
        "flow_id": flow_id,
        "step_id": step_id,
        "error_type": error_type,
        "error_message": error_message,
    }
    
    # Убрать None значения
    event = {k: v for k, v in event.items() if v is not None}
    
    # Добавить extra поля
    if extra:
        event.update(extra)
    
    # Логировать как JSON line
    log_line = json.dumps(event, ensure_ascii=False)
    logger.info(log_line)


# ============================================================================
# TIMING HELPER
# ============================================================================

class LatencyTracker:
    """Трекировать latency операции."""
    
    def __init__(self):
        self.start_time = time.time()
    
    def elapsed_ms(self) -> float:
        """Получить elapsed time в миллисекундах."""
        return (time.time() - self.start_time) * 1000

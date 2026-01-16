"""
Настройка логирования в JSON/KV формате для Render.

Render ищет структурированные логи, поэтому используем:
- JSON: {"name": "...", "cid": "...", ...}
- KV: name=CALLBACK_ACCEPTED cid=a1b2c3d4 user=...

Оба формата парсятся Render dashboard.
"""

import logging
import json
import os

# ============================================================================
# JSON FORMATTER
# ============================================================================

class JSONFormatter(logging.Formatter):
    """Логировать события как JSON line (одна JSON per line)."""
    
    def format(self, record):
        """
        Если record.msg уже JSON (из log_event), используй его как есть.
        Иначе обёрнуть в JSON.
        """
        
        # Если сообщение уже JSON (от log_event)
        if isinstance(record.msg, str) and record.msg.startswith("{"):
            # Попробовать распарсить и переформатировать
            try:
                event = json.loads(record.msg)
                # Добавить уровень логирования
                event["level"] = record.levelname
                return json.dumps(event, ensure_ascii=False)
            except (json.JSONDecodeError, Exception):
                # Если не распарсилось, использовать как есть
                return record.msg
        else:
            # Обычное сообщение - обёрнуть в JSON
            event = {
                "level": record.levelname,
                "name": record.name,
                "msg": record.getMessage(),
                "module": record.module,
            }
            return json.dumps(event, ensure_ascii=False)


# ============================================================================
# KV FORMATTER
# ============================================================================

class KeyValueFormatter(logging.Formatter):
    """Логировать события как key=value pairs."""
    
    def format(self, record):
        """Преобразовать JSON (если есть) в key=value формат."""
        
        if isinstance(record.msg, str) and record.msg.startswith("{"):
            try:
                event = json.loads(record.msg)
                # Преобразовать в key=value
                pairs = [f'{k}={v}' for k, v in event.items()]
                return " ".join(pairs)
            except (json.JSONDecodeError, Exception):
                return record.msg
        else:
            return record.getMessage()


# ============================================================================
# CONFIGURATOR
# ============================================================================

def configure_logging():
    """
    Настроить логирование согласно ENV:
    - LOG_FORMAT: json (default) или kv
    - LOG_LEVEL: INFO (default), DEBUG (if debug enabled)
    - SILENCE_GUARD: true (default) - warn if handler didn't log result
    """
    
    log_format = os.getenv("LOG_FORMAT", "json").lower()  # json или kv
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    silence_guard = os.getenv("SILENCE_GUARD", "true").lower() == "true"
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Stream handler (stdout для Render) - StreamHandler из logging, не logging.handlers
    handler = logging.StreamHandler()
    
    # Выбрать formatter
    if log_format == "kv":
        formatter = KeyValueFormatter()
    else:  # json по умолчанию
        formatter = JSONFormatter()
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Log initial configuration
    root_logger.info(json.dumps({
        "event": "LOGGING_CONFIGURED",
        "log_format": log_format,
        "log_level": log_level,
        "silence_guard": silence_guard,
    }))


# ============================================================================
# SILENCE GUARD (предупреждение если handler не залогировал result)
# ============================================================================

class SilenceGuardMiddleware:
    """
    Middleware для проверки что handler залогировал результат.
    
    Если после обработки callback не было log_event с result=accepted/rejected/noop,
    → WARNING.
    """
    
    def __init__(self, cid_timeout_seconds=30):
        self.pending_cids = {}  # cid → timestamp
        self.cid_timeout = cid_timeout_seconds
    
    def mark_callback_received(self, cid: str) -> None:
        """Отметить что callback поступил."""
        import time
        self.pending_cids[cid] = time.time()
    
    def mark_result_logged(self, cid: str) -> None:
        """Отметить что результат залогирован."""
        self.pending_cids.pop(cid, None)
    
    def check_silence(self) -> None:
        """Проверить если есть cid без результата дольше timeout."""
        import time
        now = time.time()
        
        silent_cids = [
            cid for cid, ts in self.pending_cids.items()
            if (now - ts) > self.cid_timeout
        ]
        
        if silent_cids:
            logger = logging.getLogger(__name__)
            for cid in silent_cids:
                logger.warning(json.dumps({
                    "event": "SILENCE_GUARD_WARNING",
                    "cid": cid,
                    "msg": "Callback processed but no result logged",
                }))
                self.pending_cids.pop(cid, None)


# ============================================================================
# USAGE IN APP
# ============================================================================

"""
В main.py или app initialization:

    from app.telemetry.logging_config import configure_logging
    
    configure_logging()
    
    # Опционально: silence guard
    # silence_guard = SilenceGuardMiddleware(timeout_seconds=30)
    # Periodically call: silence_guard.check_silence()

В callback handler:

    from app.telemetry.logging_contract import log_event
    from app.telemetry.logging_config import SilenceGuardMiddleware
    
    async def handle_callback(callback, **kwargs):
        cid = kwargs.get("cid")
        
        # silence_guard.mark_callback_received(cid)
        
        # ... processing ...
        
        if success:
            log_event("CALLBACK_ACCEPTED", correlation_id=cid, ...)
            # silence_guard.mark_result_logged(cid)
        else:
            log_event("CALLBACK_REJECTED", correlation_id=cid, ...)
            # silence_guard.mark_result_logged(cid)
"""

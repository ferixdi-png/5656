"""
Analytics и мониторинг для KIE AI интеграции.
Логирование latencies, errors, success/fail ratio per model/mode.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Хранилище аналитики
_analytics_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
    "total_requests": 0,
    "success": 0,
    "fail": 0,
    "latencies": [],
    "errors": []
})


def log_request(
    model_id: str,
    mode: str,
    operation: str,
    start_time: float,
    success: bool,
    error: Optional[str] = None
):
    """
    Логирует запрос для аналитики.
    
    Args:
        model_id: ID модели
        mode: ID mode
        operation: Операция (create_task, get_status)
        start_time: Время начала запроса
        success: Успешность операции
        error: Сообщение об ошибке (если есть)
    """
    latency = time.time() - start_time
    key = f"{model_id}:{mode}"
    
    _analytics_data[key]["total_requests"] += 1
    
    if success:
        _analytics_data[key]["success"] += 1
    else:
        _analytics_data[key]["fail"] += 1
        if error:
            _analytics_data[key]["errors"].append({
                "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
                "error": error,
                "operation": operation
            })
    
    _analytics_data[key]["latencies"].append(latency)
    
    # Ограничиваем размер истории
    if len(_analytics_data[key]["latencies"]) > 1000:
        _analytics_data[key]["latencies"] = _analytics_data[key]["latencies"][-1000:]
    if len(_analytics_data[key]["errors"]) > 100:
        _analytics_data[key]["errors"] = _analytics_data[key]["errors"][-100:]


def get_analytics_report() -> Dict[str, Any]:
    """
    Формирует отчёт аналитики.
    
    Returns:
        Отчёт с статистикой по каждой модели/mode
    """
    report = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "models": {}
    }
    
    for key, data in _analytics_data.items():
        model_id, mode = key.split(":", 1) if ":" in key else (key, "unknown")
        
        latencies = data.get("latencies", [])
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        report["models"][key] = {
            "model_id": model_id,
            "mode": mode,
            "total_requests": data.get("total_requests", 0),
            "success": data.get("success", 0),
            "fail": data.get("fail", 0),
            "success_rate": data.get("success", 0) / data.get("total_requests", 1) if data.get("total_requests", 0) > 0 else 0.0,
            "avg_latency": avg_latency,
            "min_latency": min(latencies) if latencies else 0.0,
            "max_latency": max(latencies) if latencies else 0.0,
            "recent_errors": data.get("errors", [])[-10:]  # Последние 10 ошибок
        }
    
    return report


def print_analytics_report():
    """Выводит отчёт аналитики в консоль."""
    report = get_analytics_report()
    
    print("\n" + "="*80)
    print("📊 ОТЧЁТ АНАЛИТИКИ KIE AI")
    print("="*80)
    print(f"Время: {report['timestamp']}")
    
    for key, stats in report["models"].items():
        print(f"\n📋 {key}:")
        print(f"  Всего запросов: {stats['total_requests']}")
        print(f"  Успешно: {stats['success']}")
        print(f"  Ошибок: {stats['fail']}")
        print(f"  Успешность: {stats['success_rate']*100:.1f}%")
        print(f"  Средняя задержка: {stats['avg_latency']*1000:.2f} мс")
        print(f"  Мин/Макс задержка: {stats['min_latency']*1000:.2f} / {stats['max_latency']*1000:.2f} мс")
        
        if stats['recent_errors']:
            print(f"  Последние ошибки:")
            for error in stats['recent_errors'][:3]:
                print(f"    - {error['error']}")
    
    print("\n" + "="*80)


def reset_analytics():
    """Сбрасывает аналитику."""
    global _analytics_data
    _analytics_data.clear()
    logger.info("🧹 Аналитика сброшена")


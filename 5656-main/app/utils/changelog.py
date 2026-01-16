"""
Changelog system - tracks version history and what's new.

Each version entry contains:
- version: Version string (e.g., "1.2.3" or git SHA)
- date: Release date (YYYY-MM-DD)
- changes: List of 3 most important changes (max 3 items)
"""
from typing import List, Dict, Any
from datetime import datetime

# Changelog entries (most recent first)
CHANGELOG: List[Dict[str, Any]] = [
    {
        "version": "1.0.0",
        "date": "2026-01-15",
        "changes": [
            "✨ Улучшен UX: все тексты на русском, понятные примеры и ошибки",
            "🆓 Бесплатные модели для старта — попробуй прямо сейчас!",
            "💰 Низкие цены на премиум-модели — дешевле чем у конкурентов"
        ]
    },
    {
        "version": "0.9.0",
        "date": "2026-01-14",
        "changes": [
            "🛡️ Предотвращена потеря апдейтов в PASSIVE режиме",
            "📈 Единый Runtime State и понятный /health для диагностики",
            "📝 Ультра объясняющие логи для каждой кнопки"
        ]
    },
    {
        "version": "0.8.0",
        "date": "2026-01-13",
        "changes": [
            "🔒 Улучшена безопасность платежей и идемпотентность",
            "⚡ Оптимизирована работа с базой данных",
            "🎨 Улучшен UX и обработка ошибок"
        ]
    }
]


def get_latest_version() -> Dict[str, Any]:
    """
    Get latest version info.
    
    Returns:
        Dict with version, date, and changes
    """
    if not CHANGELOG:
        return {
            "version": "unknown",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "changes": ["Информация о версии недоступна"]
        }
    
    return CHANGELOG[0]


def get_version_changelog(version: str = None) -> Dict[str, Any]:
    """
    Get changelog for specific version or latest.
    
    Args:
        version: Version string (optional, defaults to latest)
    
    Returns:
        Dict with version, date, and changes
    """
    if version is None:
        return get_latest_version()
    
    for entry in CHANGELOG:
        if entry["version"] == version:
            return entry
    
    # Version not found, return latest
    return get_latest_version()


def format_changelog_for_user(version_info: Dict[str, Any] = None) -> str:
    """
    Format changelog for user display.
    
    Args:
        version_info: Version info dict (optional, defaults to latest)
    
    Returns:
        Formatted string for Telegram message
    """
    if version_info is None:
        version_info = get_latest_version()
    
    version = version_info.get("version", "unknown")
    date = version_info.get("date", "unknown")
    changes = version_info.get("changes", [])
    
    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Версия:</b> {version}\n"
        f"📅 <b>Дата:</b> {date}\n\n"
        f"<b>Что нового:</b>\n"
    )
    
    for i, change in enumerate(changes[:3], 1):  # Max 3 changes
        text += f"{i}. {change}\n"
    
    return text


def get_all_versions() -> List[Dict[str, Any]]:
    """
    Get all version entries.
    
    Returns:
        List of version dicts (most recent first)
    """
    return CHANGELOG.copy()


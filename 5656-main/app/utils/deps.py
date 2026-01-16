"""
Helper для получения зависимостей из context
"""

from typing import TYPE_CHECKING
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from telegram.ext import Application
    from app.bootstrap import DependencyContainer


def get_deps_from_context(context: ContextTypes.DEFAULT_TYPE) -> "DependencyContainer":
    """
    Получить dependency container из context
    
    Args:
        context: Telegram context
        
    Returns:
        DependencyContainer
    """
    from app.bootstrap import get_deps
    return get_deps(context.application)


def get_storage_from_context(context: ContextTypes.DEFAULT_TYPE):
    """Получить storage из context"""
    deps = get_deps_from_context(context)
    return deps.get_storage()


def get_kie_client_from_context(context: ContextTypes.DEFAULT_TYPE):
    """Получить KIE client из context"""
    deps = get_deps_from_context(context)
    return deps.get_kie_client()



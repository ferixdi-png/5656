"""
Модуль для расширенной поддержки нескольких языков.
Включает динамическую локализацию и выбор языка пользователем.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Поддерживаемые языки
SUPPORTED_LANGUAGES = {
    'ru': 'Русский',
    'en': 'English',
    'uk': 'Українська',
    'de': 'Deutsch',
    'fr': 'Français',
    'es': 'Español',
    'it': 'Italiano',
    'pt': 'Português',
    'zh': '中文',
    'ja': '日本語',
    'ko': '한국어'
}

# Расширенные переводы для интерфейса
EXTENDED_TRANSLATIONS = {
    'ru': {
        'language_selection': 'Выберите язык',
        'language_changed': 'Язык изменен на: {language}',
        'model_selection': 'Выберите модель',
        'parameter_input': 'Введите параметр: {param}',
        'generation_started': 'Генерация запущена',
        'generation_completed': 'Генерация завершена',
        'balance_info': 'Ваш баланс: {balance} ₽',
        'insufficient_balance': 'Недостаточно средств',
        'error_occurred': 'Произошла ошибка',
        'help_text': 'Помощь',
        'settings': 'Настройки',
        'feedback': 'Обратная связь'
    },
    'en': {
        'language_selection': 'Select language',
        'language_changed': 'Language changed to: {language}',
        'model_selection': 'Select model',
        'parameter_input': 'Enter parameter: {param}',
        'generation_started': 'Generation started',
        'generation_completed': 'Generation completed',
        'balance_info': 'Your balance: {balance} ₽',
        'insufficient_balance': 'Insufficient funds',
        'error_occurred': 'An error occurred',
        'help_text': 'Help',
        'settings': 'Settings',
        'feedback': 'Feedback'
    }
}


def get_supported_languages() -> Dict[str, str]:
    """Возвращает словарь поддерживаемых языков."""
    return SUPPORTED_LANGUAGES.copy()


def get_language_name(lang_code: str) -> str:
    """Возвращает название языка по коду."""
    return SUPPORTED_LANGUAGES.get(lang_code, lang_code)


def translate_extended(key: str, lang: str = 'ru', **kwargs) -> str:
    """
    Расширенная функция перевода с поддержкой форматирования.
    
    Args:
        key: Ключ перевода
        lang: Код языка
        **kwargs: Параметры для форматирования
    
    Returns:
        Переведенный текст
    """
    translations = EXTENDED_TRANSLATIONS.get(lang, EXTENDED_TRANSLATIONS['ru'])
    text = translations.get(key, key)
    
    # Форматируем текст с параметрами
    try:
        return text.format(**kwargs)
    except KeyError:
        logger.warning(f"Missing parameter for translation key '{key}' in language '{lang}'")
        return text


def get_language_keyboard(current_lang: str = 'ru') -> List[List[Any]]:
    """
    Создает клавиатуру для выбора языка.
    
    Args:
        current_lang: Текущий язык пользователя
    
    Returns:
        Список строк с кнопками для клавиатуры
    """
    from telegram import InlineKeyboardButton
    
    keyboard = []
    row = []
    
    for lang_code, lang_name in SUPPORTED_LANGUAGES.items():
        # Добавляем галочку для текущего языка
        prefix = "✅ " if lang_code == current_lang else ""
        button = InlineKeyboardButton(
            f"{prefix}{lang_name}",
            callback_data=f"set_language:{lang_code}"
        )
        row.append(button)
        
        # Размещаем по 2 кнопки в ряд
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # Добавляем оставшиеся кнопки
    if row:
        keyboard.append(row)
    
    return keyboard


def set_user_language(user_id: int, lang: str) -> bool:
    """
    Устанавливает язык для пользователя.
    
    Args:
        user_id: ID пользователя
        lang: Код языка
    
    Returns:
        True, если язык установлен успешно
    """
    if lang not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language code: {lang}")
        return False
    
    try:
        from bot_kie import USER_LANGUAGES_FILE, save_json_file, load_json_file
        
        # Загружаем текущие языки
        user_languages = load_json_file(USER_LANGUAGES_FILE, {})
        user_languages[str(user_id)] = lang
        
        # Сохраняем
        save_json_file(USER_LANGUAGES_FILE, user_languages)
        
        # Очищаем кеш языка пользователя
        try:
            from bot_kie import _user_language_cache, _user_language_cache_time
            user_key = str(user_id)
            if user_key in _user_language_cache:
                del _user_language_cache[user_key]
            if user_key in _user_language_cache_time:
                del _user_language_cache_time[user_key]
        except:
            pass
        
        logger.info(f"✅ Язык пользователя {user_id} установлен на {lang}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при установке языка для пользователя {user_id}: {e}", exc_info=True)
        return False


def get_localized_model_name(model_info: Dict[str, Any], lang: str = 'ru') -> str:
    """
    Возвращает локализованное название модели.
    
    Args:
        model_info: Информация о модели
        lang: Код языка
    
    Returns:
        Локализованное название
    """
    # Если есть локализованные названия в модели
    if 'localized_names' in model_info:
        return model_info['localized_names'].get(lang, model_info.get('name', 'Unknown'))
    
    # Иначе используем стандартное название
    return model_info.get('name', 'Unknown')


def get_localized_parameter_hint(param_name: str, lang: str = 'ru') -> str:
    """
    Возвращает локализованную подсказку для параметра.
    
    Args:
        param_name: Название параметра
        lang: Код языка
    
    Returns:
        Локализованная подсказка
    """
    try:
        from optimization_ux import get_parameter_hint
        return get_parameter_hint(param_name, lang)
    except ImportError:
        # Если модуль не доступен, возвращаем базовую подсказку
        hints = {
            'ru': {
                'aspect_ratio': 'Соотношение сторон',
                'resolution': 'Разрешение',
                'duration': 'Длительность',
                'guidance_scale': 'Сила следования промпту'
            },
            'en': {
                'aspect_ratio': 'Aspect ratio',
                'resolution': 'Resolution',
                'duration': 'Duration',
                'guidance_scale': 'Prompt following strength'
            }
        }
        return hints.get(lang, hints['ru']).get(param_name, param_name)


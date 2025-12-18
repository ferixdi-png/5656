"""
Модуль для построения меню с поддержкой modes.
Структура: Категория → Модель → Mode → Параметры → Подтверждение → Генерация
"""

import logging
from typing import Dict, List, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def build_category_menu(user_lang: str = 'ru') -> InlineKeyboardMarkup:
    """
    Строит меню выбора категории.
    
    Returns:
        InlineKeyboardMarkup с кнопками категорий
    """
    try:
        from kie_models_new import get_all_models
        
        models = get_all_models()
        
        # Собираем уникальные категории
        categories = set()
        for model_data in models.values():
            modes = model_data.get("modes", {})
            for mode_data in modes.values():
                category = mode_data.get("category", "Other")
                categories.add(category)
        
        categories = sorted(categories)
        
        buttons = []
        row = []
        
        for category in categories:
            # Эмодзи для категорий
            emoji_map = {
                'Image': '🖼️',
                'Video': '🎬',
                'Audio': '🎵',
                'Tools': '🔧',
                'Other': '📦'
            }
            emoji = emoji_map.get(category, '📦')
            
            button_text = f"{emoji} {category}"
            row.append(InlineKeyboardButton(
                button_text,
                callback_data=f"category:{category}"
            ))
            
            if len(row) == 2:  # 2 кнопки в ряд
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        return InlineKeyboardMarkup(buttons)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при построении меню категорий: {e}", exc_info=True)
        # Fallback меню
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🖼️ Image", callback_data="category:Image"),
            InlineKeyboardButton("🎬 Video", callback_data="category:Video")
        ]])


def build_model_menu(category: str, user_lang: str = 'ru') -> InlineKeyboardMarkup:
    """
    Строит меню выбора модели для категории.
    
    Args:
        category: Категория (Image, Video, Audio, Tools)
        user_lang: Язык пользователя
    
    Returns:
        InlineKeyboardMarkup с кнопками моделей
    """
    try:
        from kie_models_new import get_all_models, get_models_by_category
        
        models = get_models_by_category(category)
        
        buttons = []
        row = []
        
        for model_key, model_data in models.items():
            title = model_data.get("title", model_key)
            provider = model_data.get("provider", "unknown")
            
            # Эмодзи для провайдеров
            emoji_map = {
                'openai': '🤖',
                'google': '🔵',
                'kling': '⚡',
                'wan': '🌊',
                'bytedance': '🎨',
                'blackforest': '🌲',
                'qwen': '🐉',
                'elevenlabs': '🎤',
                'hailuo': '🌊',
                'topaz': '💎',
                'recraft': '🎭',
                'ideogram': '🖼️',
                'infinitalk': '👄',
                'suno': '🎵',
                'midjourney': '🎨',
                'runway': '🎬',
                'xai': '🤖',
                'tongyi': '🖼️'
            }
            emoji = emoji_map.get(provider, '📦')
            
            button_text = f"{emoji} {title}"
            row.append(InlineKeyboardButton(
                button_text,
                callback_data=f"model:{model_key}"
            ))
            
            if len(row) == 1:  # 1 кнопка в ряд (модели могут быть длинными)
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        # Кнопка "Назад"
        buttons.append([InlineKeyboardButton(
            "◀️ Назад" if user_lang == 'ru' else "◀️ Back",
            callback_data="back_to_categories"
        )])
        
        return InlineKeyboardMarkup(buttons)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при построении меню моделей: {e}", exc_info=True)
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_categories")
        ]])


def build_mode_menu(model_key: str, user_lang: str = 'ru') -> InlineKeyboardMarkup:
    """
    Строит меню выбора mode для модели.
    
    Args:
        model_key: Ключ модели (provider/model_name)
        user_lang: Язык пользователя
    
    Returns:
        InlineKeyboardMarkup с кнопками modes
    """
    try:
        from kie_models_new import get_model_by_key
        
        model = get_model_by_key(model_key)
        if not model:
            logger.warning(f"⚠️ Модель {model_key} не найдена")
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_to_models")
            ]])
        
        modes = model.get("modes", {})
        
        buttons = []
        
        # Названия modes для отображения
        mode_names = {
            'text_to_image': '📝 Текст → Изображение',
            'image_to_image': '🖼️ Изображение → Изображение',
            'text_to_video': '📝 Текст → Видео',
            'image_to_video': '🖼️ Изображение → Видео',
            'video_to_video': '🎬 Видео → Видео',
            'image_edit': '✏️ Редактирование',
            'image_upscale': '⬆️ Увеличение',
            'video_edit': '✂️ Редактирование видео',
            'watermark_remove': '🚫 Удаление водяного знака',
            'speech_to_video': '🎤 Речь → Видео',
            'text_to_speech': '🗣️ Текст → Речь',
            'speech_to_text': '📝 Речь → Текст',
            'text_to_music': '🎵 Текст → Музыка',
            'storyboard': '📽️ Раскадровка'
        }
        
        for mode_id, mode_data in modes.items():
            mode_name = mode_names.get(mode_id, mode_id.replace('_', ' ').title())
            help_text = mode_data.get("help", "")
            
            # Обрезаем help_text для кнопки
            if len(help_text) > 30:
                help_text = help_text[:30] + "..."
            
            button_text = f"{mode_name}"
            if help_text:
                button_text += f"\n💡 {help_text}"
            
            buttons.append([InlineKeyboardButton(
                button_text,
                callback_data=f"mode:{model_key}:{mode_id}"
            )])
        
        # Кнопка "Назад"
        buttons.append([InlineKeyboardButton(
            "◀️ Назад" if user_lang == 'ru' else "◀️ Back",
            callback_data=f"back_to_model:{model_key}"
        )])
        
        return InlineKeyboardMarkup(buttons)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при построении меню modes: {e}", exc_info=True)
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_models")
        ]])


def build_parameter_keyboard(
    input_schema: Dict[str, Any],
    current_params: Dict[str, Any],
    user_lang: str = 'ru'
) -> InlineKeyboardMarkup:
    """
    Строит динамическую клавиатуру для ввода параметров на основе input_schema.
    
    Args:
        input_schema: Схема параметров
        current_params: Текущие параметры
        user_lang: Язык пользователя
    
    Returns:
        InlineKeyboardMarkup с кнопками параметров
    """
    try:
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        buttons = []
        
        # Группируем параметры по типам
        enum_params = []
        boolean_params = []
        other_params = []
        
        for param_name, param_schema in properties.items():
            param_type = param_schema.get("type", "string")
            enum_values = param_schema.get("enum")
            
            if enum_values:
                enum_params.append((param_name, param_schema))
            elif param_type == "boolean":
                boolean_params.append((param_name, param_schema))
            else:
                other_params.append((param_name, param_schema))
        
        # Enum параметры - кнопки со значениями
        for param_name, param_schema in enum_params:
            enum_values = param_schema.get("enum", [])
            current_value = current_params.get(param_name)
            
            # Показываем текущее значение
            status = "✅" if current_value else "⚪"
            param_display = param_schema.get("description", param_name)
            if len(param_display) > 20:
                param_display = param_display[:20] + "..."
            
            buttons.append([InlineKeyboardButton(
                f"{status} {param_display}: {current_value or 'не выбрано'}",
                callback_data=f"param_menu:{param_name}"
            )])
        
        # Boolean параметры - кнопки Да/Нет
        for param_name, param_schema in boolean_params:
            current_value = current_params.get(param_name)
            param_display = param_schema.get("description", param_name)
            
            status = "✅" if current_value is not None else "⚪"
            value_text = "Да" if current_value else "Нет" if current_value is False else "не выбрано"
            
            buttons.append([InlineKeyboardButton(
                f"{status} {param_display}: {value_text}",
                callback_data=f"param_menu:{param_name}"
            )])
        
        # Другие параметры - кнопки для ввода
        for param_name, param_schema in other_params:
            current_value = current_params.get(param_name)
            param_display = param_schema.get("description", param_name)
            
            status = "✅" if current_value else "⚪"
            if len(param_display) > 25:
                param_display = param_display[:25] + "..."
            
            buttons.append([InlineKeyboardButton(
                f"{status} {param_display}",
                callback_data=f"param_input:{param_name}"
            )])
        
        # Кнопки действий
        action_buttons = []
        
        # Проверяем, все ли обязательные параметры заполнены
        all_required_filled = all(
            param_name in current_params and current_params[param_name] is not None
            for param_name in required
        )
        
        if all_required_filled:
            action_buttons.append(InlineKeyboardButton(
                "✅ Подтвердить и показать цену" if user_lang == 'ru' else "✅ Confirm and show price",
                callback_data="show_price_confirmation"
            ))
        
        action_buttons.append(InlineKeyboardButton(
            "◀️ Назад" if user_lang == 'ru' else "◀️ Back",
            callback_data="back_to_mode"
        ))
        
        buttons.append(action_buttons)
        
        return InlineKeyboardMarkup(buttons)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при построении клавиатуры параметров: {e}", exc_info=True)
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_mode")
        ]])


def build_enum_value_keyboard(
    param_name: str,
    enum_values: List[Any],
    current_value: Any = None,
    user_lang: str = 'ru'
) -> InlineKeyboardMarkup:
    """Строит клавиатуру для выбора значения enum параметра."""
    buttons = []
    row = []
    
    for value in enum_values:
        status = "✅" if value == current_value else "⚪"
        button_text = f"{status} {value}"
        
        row.append(InlineKeyboardButton(
            button_text,
            callback_data=f"set_param:{param_name}:{value}"
        ))
        
        if len(row) == 2:  # 2 кнопки в ряд
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    # Кнопка "Назад"
    buttons.append([InlineKeyboardButton(
        "◀️ Назад" if user_lang == 'ru' else "◀️ Back",
        callback_data=f"back_to_params"
    )])
    
    return InlineKeyboardMarkup(buttons)


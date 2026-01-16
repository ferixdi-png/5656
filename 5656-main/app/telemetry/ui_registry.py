"""
UI Registry - единый источник истины для экранов, кнопок и потоков.

Позволяет логировать полный путь пользователя:
  MAIN_MENU (screen) → нажата кнопка CAT_IMAGE → CATEGORY_PICK (screen) → ...

Все button_id, screen_id, flow_id должны быть отсюда.
"""

from enum import Enum
from typing import List, Dict, Optional


class ScreenId(str, Enum):
    """Уникальные идентификаторы экранов."""
    MAIN_MENU = "MAIN_MENU"
    CATEGORY_PICK = "CATEGORY_PICK"
    MODEL_PICK = "MODEL_PICK"
    PARAMS_FORM = "PARAMS_FORM"
    CONFIRM = "CONFIRM"
    PROCESSING = "PROCESSING"
    RESULT = "RESULT"
    RESULT_ERROR = "RESULT_ERROR"
    HELP = "HELP"
    BALANCE = "BALANCE"
    SETTINGS = "SETTINGS"


class ButtonId(str, Enum):
    """Уникальные идентификаторы кнопок."""
    # Категории
    CAT_IMAGE = "CAT_IMAGE"
    CAT_VIDEO = "CAT_VIDEO"
    CAT_AUDIO = "CAT_AUDIO"
    CAT_UPSCALE = "CAT_UPSCALE"
    
    # Модели (примеры)
    MODEL_ZIMAGE = "MODEL_ZIMAGE"
    MODEL_DEEPDREAM = "MODEL_DEEPDREAM"
    MODEL_UPSCALE_2X = "MODEL_UPSCALE_2X"
    
    # Параметры
    PARAM_ASPECT_169 = "PARAM_ASPECT_169"
    PARAM_ASPECT_11 = "PARAM_ASPECT_11"
    PARAM_ASPECT_43 = "PARAM_ASPECT_43"
    PARAM_STYLE_PHOTO = "PARAM_STYLE_PHOTO"
    PARAM_STYLE_ART = "PARAM_STYLE_ART"
    PARAM_QUALITY_FAST = "PARAM_QUALITY_FAST"
    PARAM_QUALITY_BEST = "PARAM_QUALITY_BEST"
    
    # Действия
    CONFIRM_RUN = "CONFIRM_RUN"
    CANCEL = "CANCEL"
    BACK = "BACK"
    RETRY = "RETRY"
    
    # Admin
    DEBUG_PANEL = "DEBUG_PANEL"
    SHOW_LAST_CID = "SHOW_LAST_CID"
    
    # Unknown/Unmapped buttons
    UNKNOWN = "UNKNOWN"


class FlowId(str, Enum):
    """Типы потоков (цепочки экранов)."""
    GENERATION_FLOW = "GENERATION_FLOW"  # Новая генерация
    BALANCE_TOPUP_FLOW = "BALANCE_TOPUP_FLOW"  # Пополнение баланса
    HELP_FLOW = "HELP_FLOW"  # Справка


class FlowStep(str, Enum):
    """Шаги внутри потока."""
    # Generation flow
    GEN_CATEGORY_SELECT = "GEN_CATEGORY_SELECT"
    GEN_MODEL_SELECT = "GEN_MODEL_SELECT"
    GEN_PARAMS_INPUT = "GEN_PARAMS_INPUT"
    GEN_PROMPT_INPUT = "GEN_PROMPT_INPUT"
    GEN_CONFIRM = "GEN_CONFIRM"
    GEN_PROCESSING = "GEN_PROCESSING"
    GEN_DELIVER = "GEN_DELIVER"


# ============================================================================
# UI MAP - описание переходов между экранами
# ============================================================================

class UIMap:
    """
    Хранит описание экранов, кнопок и переходов.
    Используется для валидации и логирования.
    """
    
    # Экран -> список button_ids что на нём есть
    SCREEN_BUTTONS: Dict[str, List[str]] = {
        ScreenId.MAIN_MENU: [
            ButtonId.CAT_IMAGE,
            ButtonId.CAT_VIDEO,
            ButtonId.CAT_AUDIO,
            ButtonId.CAT_UPSCALE,
        ],
        ScreenId.CATEGORY_PICK: [
            ButtonId.MODEL_ZIMAGE,
            ButtonId.MODEL_DEEPDREAM,
            ButtonId.BACK,
        ],
        ScreenId.MODEL_PICK: [
            ButtonId.PARAM_ASPECT_169,
            ButtonId.PARAM_ASPECT_11,
            ButtonId.PARAM_ASPECT_43,
            ButtonId.BACK,
        ],
        ScreenId.PARAMS_FORM: [
            ButtonId.PARAM_STYLE_PHOTO,
            ButtonId.PARAM_STYLE_ART,
            ButtonId.PARAM_QUALITY_FAST,
            ButtonId.PARAM_QUALITY_BEST,
            ButtonId.CONFIRM_RUN,
            ButtonId.BACK,
        ],
        ScreenId.CONFIRM: [
            ButtonId.CONFIRM_RUN,
            ButtonId.CANCEL,
        ],
        ScreenId.PROCESSING: [],
        ScreenId.RESULT: [
            ButtonId.BACK,
            ButtonId.CAT_IMAGE,  # Быстрый повтор
        ],
        ScreenId.RESULT_ERROR: [
            ButtonId.RETRY,
            ButtonId.BACK,
        ],
    }
    
    # Button -> ожидаемый следующий экран (примерно)
    BUTTON_NEXT_SCREEN: Dict[str, str] = {
        ButtonId.CAT_IMAGE: ScreenId.CATEGORY_PICK,
        ButtonId.CAT_VIDEO: ScreenId.CATEGORY_PICK,
        ButtonId.CAT_AUDIO: ScreenId.CATEGORY_PICK,
        ButtonId.MODEL_ZIMAGE: ScreenId.MODEL_PICK,
        ButtonId.PARAM_ASPECT_169: ScreenId.PARAMS_FORM,
        ButtonId.PARAM_ASPECT_11: ScreenId.PARAMS_FORM,
        ButtonId.CONFIRM_RUN: ScreenId.PROCESSING,
        ButtonId.RETRY: ScreenId.PROCESSING,
        ButtonId.BACK: ScreenId.MAIN_MENU,  # Зависит от контекста
    }
    
    @staticmethod
    def is_valid_button_on_screen(screen_id: str, button_id: str) -> bool:
        """Проверить, возможна ли такая кнопка на экране."""
        return button_id in UIMap.SCREEN_BUTTONS.get(screen_id, [])
    
    @staticmethod
    def get_expected_next_screen(button_id: str) -> Optional[str]:
        """Получить ожидаемый следующий экран после нажатия кнопки."""
        return UIMap.BUTTON_NEXT_SCREEN.get(button_id)

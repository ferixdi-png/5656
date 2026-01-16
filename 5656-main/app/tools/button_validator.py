"""Button handler validation module."""

import re
from pathlib import Path
from typing import Set, Tuple, List, Dict


def extract_button_callbacks(app_dir: Path = None) -> Dict[str, List[str]]:
    """Extract callback patterns from buttons/menus.

    Возвращает словарь: имя файла -> список callback_data. Теперь сканируем
    как `app/helpers`, так и `bot/handlers`, потому что часть кнопок (например
    help-меню) объявлена прямо в хэндлерах.
    """
    if app_dir is None:
        app_dir = Path(__file__).parent.parent

    callbacks: Dict[str, List[str]] = {}

    # Директории, где могут объявляться InlineKeyboardButton
    search_roots = [app_dir / "helpers", app_dir.parent / "bot" / "handlers"]

    for root in search_roots:
        if not root.exists():
            continue

        for py_file in root.glob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            pattern = r'InlineKeyboardButton\([^,]+,\s*callback_data=["\']([^"\']+)["\']'
            matches = re.findall(pattern, content)

            if matches:
                callbacks.setdefault(py_file.stem, []).extend(matches)

    return callbacks


def extract_handler_names(app_dir: Path = None) -> Set[str]:
    """
    Extract handler names from routers/dispatchers.
    
    Returns:
        Set of handler function names
    """
    if app_dir is None:
        app_dir = Path(__file__).parent.parent.parent
    
    handlers = set()
    
    # Check main_render.py for handler registration
    main_file = app_dir / "main_render.py"
    if main_file.exists():
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find register_handlers calls or router.* definitions
        pattern = r'(?:async\s+)?def\s+(\w+_handler|handle_\w+|\w+_callback)'
        matches = re.findall(pattern, content)
        handlers.update(matches)
    
    # Check app/helpers for handler definitions
    if (app_dir / "app" / "helpers").exists():
        for py_file in (app_dir / "app" / "helpers").glob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find handler definitions
            pattern = r'async\s+def\s+(\w+)\s*\('
            matches = re.findall(pattern, content)
            handlers.update(matches)
    
    return handlers


def validate_callback_handlers(app_dir: Path = None) -> Tuple[List[str], List[str]]:
    """
    Validate that all button callbacks have handlers.
    
    Returns:
        Tuple of (valid_callbacks, missing_handlers)
    """
    if app_dir is None:
        app_dir = Path(__file__).parent.parent.parent
    
    callbacks = extract_button_callbacks(app_dir / "app")
    handlers = extract_handler_names(app_dir)
    
    valid = []
    missing = []
    
    for button_name, callback_list in callbacks.items():
        for callback in callback_list:
            # Extract base callback (before colon or underscore)
            base = callback.split(':')[0].split('_')[0]
            
            # Check if there's a matching handler
            found = any(
                base in h or h.endswith(base)
                for h in handlers
            )
            
            if found:
                valid.append(callback)
            else:
                missing.append(f"{callback} (no handler in {button_name})")
    
    return valid, missing


def check_essential_buttons() -> Dict[str, bool]:
    """
    Check that essential buttons are implemented.
    
    Returns:
        Dict of button_name -> is_present
    """
    essential = {
        'back_to_menu': False,
        'show_models': False,
        'help': False,
    }
    
    app_dir = Path(__file__).parent.parent
    callbacks = extract_button_callbacks(app_dir)
    
    all_callbacks = []
    for cb_list in callbacks.values():
        all_callbacks.extend(cb_list)
    
    for button in essential:
        # Check if button or any variant exists
        essential[button] = any(
            button in cb or 
            cb.startswith(button) or
            button in cb.replace('_', '-').replace('-', '_')
            for cb in all_callbacks
        )
    
    return essential

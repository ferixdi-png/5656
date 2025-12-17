#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ всех callback_data и их обработчиков
"""

import re
import sys
import io

# Установить UTF-8 для вывода
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def extract_callback_data(content):
    """Извлечь все callback_data из InlineKeyboardButton"""
    # Найти все callback_data="..." или callback_data='...'
    pattern = r'callback_data=["\']([^"\']+)["\']'
    matches = re.findall(pattern, content)
    
    # Также найти f-strings с переменными (например, f"select_model:{model_id}")
    f_pattern = r'callback_data=f["\']([^"\']*?)\{.*?\}([^"\']*?)["\']'
    f_matches = re.findall(f_pattern, content)
    
    callback_data_set = set()
    
    # Добавить статические callback_data
    for match in matches:
        if '{' not in match:  # Пропустить f-strings без переменных (они уже в matches)
            callback_data_set.add(match)
    
    # Добавить динамические паттерны (префиксы)
    dynamic_prefixes = set()
    for match in matches:
        if ':' in match:
            prefix = match.split(':')[0] + ':'
            dynamic_prefixes.add(prefix)
    
    # Найти все f-strings с переменными
    f_string_pattern = r'callback_data=f["\']([^"\']*?)\{'
    f_string_matches = re.findall(f_string_pattern, content)
    for prefix in f_string_matches:
        if prefix:
            dynamic_prefixes.add(prefix)
    
    return callback_data_set, dynamic_prefixes

def extract_handlers(content):
    """Извлечь все обработчики callback_data"""
    exact_handlers = set()
    startswith_handlers = set()
    
    # Точные совпадения: if data == "..." или if data == "..."
    exact_pattern = r'if\s+data\s*==\s*["\']([^"\']+)["\']'
    for match in re.finditer(exact_pattern, content):
        exact_handlers.add(match.group(1))
    
    # Также проверить elif
    elif_exact_pattern = r'elif\s+data\s*==\s*["\']([^"\']+)["\']'
    for match in re.finditer(elif_exact_pattern, content):
        exact_handlers.add(match.group(1))
    
    # Проверить or в условиях
    or_pattern = r'data\s*==\s*["\']([^"\']+)["\']\s+or\s+data\s*==\s*["\']([^"\']+)["\']'
    for match in re.finditer(or_pattern, content):
        exact_handlers.add(match.group(1))
        exact_handlers.add(match.group(2))
    
    # startswith: if data.startswith("...")
    startswith_pattern = r'data\.startswith\(["\']([^"\']+)["\']'
    for match in re.finditer(startswith_pattern, content):
        startswith_handlers.add(match.group(1))
    
    return exact_handlers, startswith_handlers

def main():
    try:
        with open('bot_kie.py', 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        return
    
    # Извлечь callback_data
    callback_data_set, dynamic_prefixes = extract_callback_data(content)
    
    # Извлечь обработчики
    exact_handlers, startswith_handlers = extract_handlers(content)
    
    print("=" * 80)
    print("АНАЛИЗ CALLBACK_DATA И ОБРАБОТЧИКОВ")
    print("=" * 80)
    print(f"\nНайдено статических callback_data: {len(callback_data_set)}")
    print(f"Найдено динамических префиксов: {len(dynamic_prefixes)}")
    print(f"Найдено точных обработчиков (if data ==): {len(exact_handlers)}")
    print(f"Найдено обработчиков (startswith): {len(startswith_handlers)}")
    
    # Проверить необработанные callback_data
    unhandled = []
    handled = []
    
    for cb_data in sorted(callback_data_set):
        # Проверить точное совпадение
        if cb_data in exact_handlers:
            handled.append((cb_data, "exact"))
            continue
        
        # Проверить startswith
        is_handled = False
        for prefix in startswith_handlers:
            if cb_data.startswith(prefix):
                handled.append((cb_data, f"startswith({prefix})"))
                is_handled = True
                break
        
        if not is_handled:
            unhandled.append(cb_data)
    
    print("\n" + "=" * 80)
    print("ОБРАБОТАННЫЕ CALLBACK_DATA:")
    print("=" * 80)
    for cb, handler_type in sorted(handled):
        print(f"  [OK] {cb:40s} -> {handler_type}")
    
    print("\n" + "=" * 80)
    print("НЕОБРАБОТАННЫЕ CALLBACK_DATA:")
    print("=" * 80)
    if unhandled:
        for cb in sorted(unhandled):
            print(f"  [MISSING] {cb}")
    else:
        print("  [OK] Все callback_data обработаны!")
    
    # Проверить динамические префиксы
    print("\n" + "=" * 80)
    print("ДИНАМИЧЕСКИЕ ПРЕФИКСЫ:")
    print("=" * 80)
    for prefix in sorted(dynamic_prefixes):
        is_handled = prefix in startswith_handlers or any(prefix.startswith(h) for h in startswith_handlers)
        status = "[OK]" if is_handled else "[MISSING]"
        print(f"  {status} {prefix}")
    
    # Проверить обработчики без соответствующих кнопок
    print("\n" + "=" * 80)
    print("ОБРАБОТЧИКИ БЕЗ СООТВЕТСТВУЮЩИХ КНОПОК:")
    print("=" * 80)
    handlers_without_buttons = []
    for handler in sorted(exact_handlers):
        if handler not in callback_data_set:
            handlers_without_buttons.append(handler)
    
    if handlers_without_buttons:
        for handler in handlers_without_buttons:
            print(f"  [WARNING] {handler}")
    else:
        print("  [OK] Все обработчики имеют соответствующие кнопки")

if __name__ == '__main__':
    main()


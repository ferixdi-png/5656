#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка всех callback_data из InlineKeyboardButton
и сравнение с обработчиками
"""

import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def extract_callback_data(file_path):
    """Извлечь все callback_data из InlineKeyboardButton"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Паттерн для поиска callback_data
    # InlineKeyboardButton(..., callback_data="...")
    # InlineKeyboardButton(..., callback_data='...')
    # InlineKeyboardButton(..., callback_data=f"...")
    patterns = [
        r'callback_data=["\']([^"\']+)["\']',
        r'callback_data=f["\']([^"\']+)["\']',
        r'callback_data=f["\']([^"\']+)\{.*?\}["\']',  # f-strings с переменными
    ]
    
    callback_data_list = []
    for pattern in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            callback_data = match.group(1)
            # Пропустить f-strings с переменными (они обрабатываются динамически)
            if '{' in callback_data and '}' in callback_data:
                continue
            callback_data_list.append(callback_data)
    
    # Также найти callback_data с переменными (set_param:, retry_generate:, etc.)
    dynamic_patterns = [
        r'callback_data=f["\']set_param:([^:]+):',
        r'callback_data=f["\']retry_generate:([^"\']+)["\']',
        r'callback_data=f["\']select_model:([^"\']+)["\']',
        r'callback_data=f["\']gen_type:([^"\']+)["\']',
        r'callback_data=f["\']language_select:([^"\']+)["\']',
    ]
    
    for pattern in dynamic_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            prefix = pattern.split(':')[0].split('"')[1] if ':' in pattern else match.group(0)
            callback_data_list.append(prefix + ":*")  # * означает любой параметр
    
    return sorted(set(callback_data_list))

def extract_handlers(file_path):
    """Извлечь все обработчики callback_data"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    handlers = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # if data == "..."
        if re.match(r'if\s+data\s*==\s*["\']([^"\']+)["\']', line):
            match = re.search(r'==\s*["\']([^"\']+)["\']', line)
            if match:
                handlers.append(('==', match.group(1)))
        # elif data == "..."
        elif re.match(r'elif\s+data\s*==\s*["\']([^"\']+)["\']', line):
            match = re.search(r'==\s*["\']([^"\']+)["\']', line)
            if match:
                handlers.append(('==', match.group(1)))
        # if data.startswith("...")
        elif 'data.startswith(' in line:
            match = re.search(r'startswith\(["\']([^"\']+)["\']', line)
            if match:
                handlers.append(('startswith', match.group(1)))
        # elif data.startswith("...")
        elif 'elif' in line and 'data.startswith(' in line:
            match = re.search(r'startswith\(["\']([^"\']+)["\']', line)
            if match:
                handlers.append(('startswith', match.group(1)))
        i += 1
    
    return handlers

def main():
    file_path = 'bot_kie.py'
    
    print("=" * 80)
    print("ПРОВЕРКА CALLBACK_DATA")
    print("=" * 80)
    print()
    
    # Извлечь все callback_data
    callback_data_list = extract_callback_data(file_path)
    print(f"📋 Найдено callback_data: {len(callback_data_list)}")
    print()
    
    # Извлечь все обработчики
    handlers = extract_handlers(file_path)
    print(f"🔧 Найдено обработчиков: {len(handlers)}")
    print()
    
    # Создать множество обрабатываемых callback_data
    handled_data = set()
    for handler_type, handler_value in handlers:
        if handler_type == '==':
            handled_data.add(handler_value)
        elif handler_type == 'startswith':
            # Для startswith добавить все callback_data, которые начинаются с этого префикса
            for cb in callback_data_list:
                if cb.startswith(handler_value):
                    handled_data.add(cb)
    
    # Найти необработанные callback_data
    unhandled = []
    for cb in callback_data_list:
        if cb not in handled_data and not cb.endswith(':*'):  # Пропустить динамические
            # Проверить, обрабатывается ли через startswith
            is_handled = False
            for handler_type, handler_value in handlers:
                if handler_type == 'startswith' and cb.startswith(handler_value):
                    is_handled = True
                    break
            if not is_handled:
                unhandled.append(cb)
    
    # Найти обработчики без соответствующих callback_data
    unused_handlers = []
    for handler_type, handler_value in handlers:
        found = False
        for cb in callback_data_list:
            if handler_type == '==' and cb == handler_value:
                found = True
                break
            elif handler_type == 'startswith' and cb.startswith(handler_value):
                found = True
                break
        if not found:
            unused_handlers.append((handler_type, handler_value))
    
    # Вывести результаты
    print("=" * 80)
    print("НЕОБРАБОТАННЫЕ CALLBACK_DATA:")
    print("=" * 80)
    if unhandled:
        for cb in sorted(unhandled):
            print(f"  ❌ {cb}")
    else:
        print("  ✅ Все callback_data обработаны")
    print()
    
    print("=" * 80)
    print("НЕИСПОЛЬЗУЕМЫЕ ОБРАБОТЧИКИ:")
    print("=" * 80)
    if unused_handlers:
        for handler_type, handler_value in unused_handlers:
            print(f"  ⚠️ {handler_type}: {handler_value}")
    else:
        print("  ✅ Все обработчики используются")
    print()
    
    # Показать все callback_data
    print("=" * 80)
    print("ВСЕ CALLBACK_DATA:")
    print("=" * 80)
    for cb in sorted(callback_data_list):
        status = "✅" if cb in handled_data or any(cb.startswith(h[1]) for h in handlers if h[0] == 'startswith') else "❌"
        print(f"  {status} {cb}")
    print()
    
    # Показать все обработчики
    print("=" * 80)
    print("ВСЕ ОБРАБОТЧИКИ:")
    print("=" * 80)
    for handler_type, handler_value in handlers:
        print(f"  {handler_type}: {handler_value}")
    print()
    
    return len(unhandled) == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)



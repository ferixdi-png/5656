#!/usr/bin/env python3
"""
Полная проверка всех кнопок в боте
Проверяет, что все callback_data обрабатываются в button_callback
"""

import re
import sys

def extract_callback_data(file_path):
    """Извлекает все callback_data из файла"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Находим все callback_data
    patterns = [
        r'callback_data=["\']([^"\']+)["\']',
        r'callback_data=f["\']([^"\']+)["\']',
    ]
    
    callbacks = set()
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            # Обрабатываем f-строки
            if '{' in match:
                # Извлекаем базовый паттерн (до :)
                base = match.split(':')[0] if ':' in match else match
                callbacks.add(base)
            else:
                callbacks.add(match)
    
    return callbacks

def extract_handlers(file_path):
    """Извлекает все обработчики из button_callback"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    handlers = set()
    startswith_handlers = set()
    
    # Находим все обработчики
    exact_pattern = r'if data == ["\']([^"\']+)["\']'
    startswith_pattern = r'if data\.startswith\(["\']([^"\']+)["\']'
    
    for match in re.finditer(exact_pattern, content):
        handlers.add(match.group(1))
    
    for match in re.finditer(startswith_pattern, content):
        startswith_handlers.add(match.group(1))
    
    # Также проверяем обработчики с or
    or_pattern = r'if data == ["\']([^"\']+)["\'] or data == ["\']([^"\']+)["\']'
    for match in re.finditer(or_pattern, content):
        handlers.add(match.group(1))
        handlers.add(match.group(2))
    
    return handlers, startswith_handlers

def check_handler_coverage(callbacks, handlers, startswith_handlers):
    """Проверяет покрытие всех callback_data обработчиками"""
    unhandled = []
    handled = []
    
    for cb in callbacks:
        is_handled = False
        
        # Проверяем точное совпадение
        if cb in handlers:
            is_handled = True
            handled.append(cb)
            continue
        
        # Проверяем startswith
        for sh in startswith_handlers:
            if cb.startswith(sh):
                is_handled = True
                handled.append(f"{cb} (startswith: {sh})")
                break
        
        if not is_handled:
            unhandled.append(cb)
    
    return handled, unhandled

def main():
    file_path = 'bot_kie.py'
    
    print("=" * 70)
    print("ПРОВЕРКА ВСЕХ КНОПОК В БОТЕ")
    print("=" * 70)
    print()
    
    # Извлекаем все callback_data
    print("1. Извлечение всех callback_data из кнопок...")
    callbacks = extract_callback_data(file_path)
    print(f"   Найдено {len(callbacks)} уникальных callback_data")
    print()
    
    # Извлекаем все обработчики
    print("2. Извлечение всех обработчиков из button_callback...")
    handlers, startswith_handlers = extract_handlers(file_path)
    print(f"   Найдено {len(handlers)} точных обработчиков")
    print(f"   Найдено {len(startswith_handlers)} startswith обработчиков")
    print()
    
    # Проверяем покрытие
    print("3. Проверка покрытия обработчиками...")
    handled, unhandled = check_handler_coverage(callbacks, handlers, startswith_handlers)
    
    print(f"   Обработано: {len(handled)}")
    print(f"   Не обработано: {len(unhandled)}")
    print()
    
    if unhandled:
        print("=" * 70)
        print("❌ НАЙДЕНЫ НЕОБРАБОТАННЫЕ CALLBACK_DATA:")
        print("=" * 70)
        for cb in sorted(unhandled):
            print(f"  - {cb}")
        print()
        return 1
    else:
        print("=" * 70)
        print("✅ ВСЕ CALLBACK_DATA ОБРАБАТЫВАЮТСЯ!")
        print("=" * 70)
        print()
        return 0

if __name__ == '__main__':
    sys.exit(main())





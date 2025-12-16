#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенная проверка всех кнопок в боте
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
            # Обрабатываем f-строки - извлекаем базовый паттерн
            if '{' in match:
                # Для паттернов типа "select_model:{model_id}" берем "select_model:"
                if ':' in match:
                    base = match.split(':')[0] + ':'
                    callbacks.add(base)
                else:
                    # Для других паттернов с {} берем все до {
                    base = match.split('{')[0]
                    if base:
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
    print("PROVERKA VSEH KNOPOK V BOTE")
    print("=" * 70)
    print()
    
    # Извлекаем все callback_data
    print("1. Izvlechenie vseh callback_data iz knopok...")
    callbacks = extract_callback_data(file_path)
    print(f"   Naydeno {len(callbacks)} unikalnyh callback_data")
    print()
    
    # Извлекаем все обработчики
    print("2. Izvlechenie vseh obrabotchikov iz button_callback...")
    handlers, startswith_handlers = extract_handlers(file_path)
    print(f"   Naydeno {len(handlers)} tochnyh obrabotchikov")
    print(f"   Naydeno {len(startswith_handlers)} startswith obrabotchikov")
    print()
    
    # Показываем все найденные callback_data
    print("3. Vse naydennye callback_data:")
    for cb in sorted(callbacks):
        print(f"   - {cb}")
    print()
    
    # Показываем все обработчики
    print("4. Vse obrabotchiki:")
    for h in sorted(handlers):
        print(f"   - {h}")
    for sh in sorted(startswith_handlers):
        print(f"   - {sh} (startswith)")
    print()
    
    # Проверяем покрытие
    print("5. Proverka pokrytiya obrabotchikami...")
    handled, unhandled = check_handler_coverage(callbacks, handlers, startswith_handlers)
    
    print(f"   Obrabotano: {len(handled)}")
    print(f"   Ne obrabotano: {len(unhandled)}")
    print()
    
    if unhandled:
        print("=" * 70)
        print("NAYDENY NEOBRABOTANNYE CALLBACK_DATA:")
        print("=" * 70)
        for cb in sorted(unhandled):
            print(f"  - {cb}")
        print()
        return 1
    else:
        print("=" * 70)
        print("VSE CALLBACK_DATA OBRABATYVAYUTSYA!")
        print("=" * 70)
        print()
        return 0

if __name__ == '__main__':
    sys.exit(main())


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Финальная проверка всех callback_data и обработчиков
"""

import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def extract_all_callback_data(file_path):
    """Извлечь все callback_data из InlineKeyboardButton"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    callback_data_set = set()
    
    # Простой паттерн для callback_data="..." или callback_data='...'
    pattern1 = r'callback_data=["\']([^"\']+)["\']'
    for match in re.finditer(pattern1, content):
        cb = match.group(1)
        # Пропустить f-strings с переменными (они обрабатываются динамически)
        if '{' not in cb:
            callback_data_set.add(cb)
    
    # Найти динамические callback_data (с переменными)
    # set_param:*, select_model:*, gen_type:*, etc.
    dynamic_patterns = [
        r'callback_data=f["\']set_param:',
        r'callback_data=f["\']select_model:',
        r'callback_data=f["\']gen_type:',
        r'callback_data=f["\']retry_generate:',
        r'callback_data=f["\']gen_view:',
        r'callback_data=f["\']gen_repeat:',
        r'callback_data=f["\']gen_history:',
        r'callback_data=f["\']category:',
        r'callback_data=f["\']topup_amount:',
        r'callback_data=f["\']pay_stars:',
        r'callback_data=f["\']pay_sbp:',
        r'callback_data=f["\']admin_gen_nav:',
        r'callback_data=f["\']admin_gen_view:',
        r'callback_data=f["\']payment_screenshot_nav:',
        r'callback_data=f["\']language_select:',
    ]
    
    for pattern in dynamic_patterns:
        if re.search(pattern, content):
            prefix = pattern.split(':')[0].split('"')[1].split("'")[1] if ':' in pattern else ''
            if prefix:
                callback_data_set.add(prefix + ":*")
    
    return sorted(callback_data_set)

def extract_all_handlers(file_path):
    """Извлечь все обработчики"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    handlers = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # if data == "..." or data == "..."
        if 'if data ==' in line or 'elif data ==' in line:
            # Найти все значения в условии
            matches = re.findall(r'data\s*==\s*["\']([^"\']+)["\']', line)
            for match in matches:
                handlers.append(('==', match))
        
        # if data.startswith("...")
        if 'data.startswith(' in line:
            match = re.search(r'startswith\(["\']([^"\']+)["\']', line)
            if match:
                handlers.append(('startswith', match.group(1)))
        
        i += 1
    
    return handlers

def main():
    file_path = 'bot_kie.py'
    
    print("=" * 80)
    print("ФИНАЛЬНАЯ ПРОВЕРКА CALLBACK_DATA")
    print("=" * 80)
    print()
    
    # Извлечь все callback_data
    callback_data_list = extract_all_callback_data(file_path)
    print(f"📋 Найдено уникальных callback_data: {len(callback_data_list)}")
    
    # Извлечь все обработчики
    handlers = extract_all_handlers(file_path)
    print(f"🔧 Найдено обработчиков: {len(handlers)}")
    print()
    
    # Проверить каждый callback_data
    unhandled = []
    handled = []
    
    for cb in callback_data_list:
        if cb.endswith(':*'):
            # Динамический callback_data - проверить через startswith
            prefix = cb.replace(':*', '')
            is_handled = any(h[0] == 'startswith' and h[1] == prefix for h in handlers)
            if is_handled:
                handled.append(cb)
            else:
                unhandled.append(cb)
        else:
            # Обычный callback_data - проверить точное совпадение или startswith
            is_handled = False
            # Проверить точное совпадение
            if any(h[0] == '==' and h[1] == cb for h in handlers):
                is_handled = True
            # Проверить startswith
            elif any(h[0] == 'startswith' and cb.startswith(h[1]) for h in handlers):
                is_handled = True
            
            if is_handled:
                handled.append(cb)
            else:
                unhandled.append(cb)
    
    print("=" * 80)
    print("НЕОБРАБОТАННЫЕ CALLBACK_DATA:")
    print("=" * 80)
    if unhandled:
        for cb in sorted(unhandled):
            print(f"  ❌ {cb}")
    else:
        print("  ✅ Все callback_data обработаны!")
    print()
    
    print("=" * 80)
    print("ОБРАБОТАННЫЕ CALLBACK_DATA:")
    print("=" * 80)
    for cb in sorted(handled):
        print(f"  ✅ {cb}")
    print()
    
    # Показать все обработчики
    print("=" * 80)
    print("ВСЕ ОБРАБОТЧИКИ:")
    print("=" * 80)
    for handler_type, handler_value in sorted(handlers, key=lambda x: (x[0], x[1])):
        print(f"  {handler_type}: {handler_value}")
    print()
    
    return len(unhandled) == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)



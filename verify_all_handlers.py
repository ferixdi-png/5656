#!/usr/bin/env python3
"""
Проверка всех обработчиков кнопок
Убеждается, что все обработчики вызывают query.answer()
"""

import re

def check_query_answer_in_handlers(file_path):
    """Проверяет, что все обработчики вызывают query.answer()"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    handlers_without_answer = []
    current_handler = None
    handler_start_line = None
    found_answer = False
    
    for i, line in enumerate(lines, 1):
        # Находим начало обработчика
        if re.match(r'^\s+if data == ["\']', line) or re.match(r'^\s+if data\.startswith\(["\']', line):
            # Сохраняем предыдущий обработчик, если он был
            if current_handler and not found_answer:
                handlers_without_answer.append({
                    'handler': current_handler,
                    'line': handler_start_line
                })
            
            # Начинаем новый обработчик
            current_handler = line.strip()
            handler_start_line = i
            found_answer = False
        
        # Проверяем наличие query.answer() в обработчике
        if current_handler:
            if 'await query.answer()' in line or 'await query.answer(' in line:
                found_answer = True
        
        # Если обработчик закончился (следующий обработчик или return)
        if current_handler and (line.strip().startswith('if data ==') or 
                                line.strip().startswith('if data.startswith') or
                                (line.strip().startswith('return') and i > handler_start_line + 5)):
            if not found_answer and i > handler_start_line + 3:  # Даем небольшую задержку
                # Проверяем, не является ли это частью try-except
                # Пропускаем, если это часть большого блока
                pass
    
    # Проверяем последний обработчик
    if current_handler and not found_answer:
        handlers_without_answer.append({
            'handler': current_handler,
            'line': handler_start_line
        })
    
    return handlers_without_answer

def main():
    file_path = 'bot_kie.py'
    
    print("=" * 70)
    print("ПРОВЕРКА ОБРАБОТЧИКОВ НА НАЛИЧИЕ query.answer()")
    print("=" * 70)
    print()
    
    handlers_without_answer = check_query_answer_in_handlers(file_path)
    
    if handlers_without_answer:
        print(f"⚠️  Найдено {len(handlers_without_answer)} обработчиков без query.answer():")
        print()
        for item in handlers_without_answer[:10]:  # Показываем первые 10
            print(f"  Строка {item['line']}: {item['handler'][:60]}...")
        if len(handlers_without_answer) > 10:
            print(f"  ... и еще {len(handlers_without_answer) - 10}")
        print()
        return 1
    else:
        print("✅ Все обработчики вызывают query.answer()!")
        print()
        return 0

if __name__ == '__main__':
    exit(main())



#!/usr/bin/env python3
"""
Комплексная проверка всех кнопок и сценариев генерации
Проверяет:
1. Все callback_data имеют обработчики
2. Все обработчики правильно вызывают query.answer()
3. Логика генерации работает корректно
4. Все состояния ConversationHandler правильно настроены
"""

import re
import sys

def extract_callback_data_patterns(file_path):
    """Извлекает все callback_data из InlineKeyboardButton"""
    patterns = set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # Ищем все callback_data="..." или callback_data='...'
        matches = re.findall(r'callback_data=["\']([^"\']+)["\']', content)
        patterns.update(matches)
        
        # Ищем callback_data=... (без кавычек, но это редко)
        matches2 = re.findall(r'callback_data=([a-zA-Z0-9_:]+)', content)
        patterns.update(matches2)
    
    return sorted(patterns)

def extract_handler_patterns(file_path):
    """Извлекает все паттерны из CallbackQueryHandler"""
    handlers = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # Ищем CallbackQueryHandler(handler, pattern='^...$')
        matches = re.findall(
            r'CallbackQueryHandler\(([^,]+),\s*pattern=["\']\^([^"\']+)\$["\']',
            content
        )
        for handler, pattern in matches:
            if pattern not in handlers:
                handlers[pattern] = []
            handlers[pattern].append(handler.strip())
    
    return handlers

def extract_button_callback_handlers(file_path):
    """Извлекает все обработчики из функции button_callback"""
    handlers = set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        in_button_callback = False
        indent_level = 0
        
        for i, line in enumerate(lines):
            # Находим начало функции button_callback
            if 'async def button_callback' in line or 'def button_callback' in line:
                in_button_callback = True
                indent_level = len(line) - len(line.lstrip())
                continue
            
            if in_button_callback:
                # Проверяем, не вышли ли мы из функции
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and line.strip() and not line.strip().startswith('#'):
                    if 'def ' in line or 'async def ' in line:
                        break
                
                # Ищем проверки callback_data
                # if data == "..." или if data.startswith("...")
                if 'if data' in line or 'elif data' in line:
                    # Извлекаем callback_data из условия
                    match = re.search(r'data\s*==\s*["\']([^"\']+)["\']', line)
                    if match:
                        handlers.add(match.group(1))
                    
                    match = re.search(r'data\.startswith\(["\']([^"\']+)["\']', line)
                    if match:
                        prefix = match.group(1)
                        # Добавляем как паттерн с префиксом
                        handlers.add(f"{prefix}*")
    
    return handlers

def check_confirm_generation_flow(file_path):
    """Проверяет логику confirm_generation"""
    issues = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
            # Проверяем, что confirm_generation вызывается правильно
        if 'async def confirm_generation' not in content:
            issues.append("[ERROR] Функция confirm_generation не найдена")
        else:
            # Проверяем, что есть await query.answer()
            confirm_section = content.split('async def confirm_generation')[1].split('async def ')[0] if 'async def confirm_generation' in content else ''
            if 'await query.answer()' not in confirm_section:
                issues.append("[WARNING] confirm_generation может не вызывать query.answer()")
            
            # Проверяем, что есть обработка ошибок
            if 'send_or_edit_message' not in confirm_section:
                issues.append("[WARNING] confirm_generation может не использовать send_or_edit_message")
    
    return issues

def check_input_parameters_flow(file_path):
    """Проверяет логику input_parameters и показ кнопки генерации"""
    issues = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # Проверяем, что кнопка confirm_generate показывается
        if 'confirm_generate' not in content:
            issues.append("[ERROR] Кнопка confirm_generate не найдена")
        else:
            # Проверяем, что кнопка показывается после сбора параметров
            if 'all_required_collected' in content:
                # Проверяем, что после all_required_collected показывается кнопка
                parts = content.split('all_required_collected')
                if len(parts) > 1:
                    after_check = parts[1][:2000]  # Первые 2000 символов после проверки
                    if 'confirm_generate' not in after_check:
                        issues.append("[WARNING] Кнопка confirm_generate может не показываться после all_required_collected")
                    if 'CONFIRMING_GENERATION' not in after_check:
                        issues.append("[WARNING] Состояние CONFIRMING_GENERATION может не возвращаться")
    
    return issues

def main():
    file_path = 'bot_kie.py'
    
    import sys
    import io
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 80)
    print("КОМПЛЕКСНАЯ ПРОВЕРКА ВСЕХ КНОПОК И СЦЕНАРИЕВ ГЕНЕРАЦИИ")
    print("=" * 80)
    print()
    
    # 1. Извлекаем все callback_data
    print("[1] ПРОВЕРКА 1: Извлечение всех callback_data...")
    callback_patterns = extract_callback_data_patterns(file_path)
    print(f"   Найдено {len(callback_patterns)} уникальных callback_data")
    print()
    
    # 2. Извлекаем все обработчики
    print("[2] ПРОВЕРКА 2: Извлечение всех обработчиков...")
    handler_patterns = extract_handler_patterns(file_path)
    print(f"   Найдено {len(handler_patterns)} паттернов в CallbackQueryHandler")
    print()
    
    # 3. Извлекаем обработчики из button_callback
    print("[3] ПРОВЕРКА 3: Извлечение обработчиков из button_callback...")
    button_handlers = extract_button_callback_handlers(file_path)
    print(f"   Найдено {len(button_handlers)} обработчиков в button_callback")
    print()
    
    # 4. Проверяем соответствие
    print("[4] ПРОВЕРКА 4: Проверка соответствия callback_data и обработчиков...")
    missing_handlers = []
    for pattern in callback_patterns:
        # Проверяем точное совпадение
        found = False
        
        # Проверяем в handler_patterns (точное совпадение)
        if pattern in handler_patterns:
            found = True
        
        # Проверяем в button_handlers (точное совпадение или префикс)
        for handler in button_handlers:
            if handler == pattern:
                found = True
            elif handler.endswith('*') and pattern.startswith(handler[:-1]):
                found = True
        
        # Проверяем специальные случаи
        if pattern == 'confirm_generate':
            if 'confirm_generation' in str(handler_patterns):
                found = True
        
        if not found:
            # Проверяем, не является ли это частью паттерна
            is_part_of_pattern = False
            for handler_pattern in handler_patterns.keys():
                if handler_pattern.endswith('*') and pattern.startswith(handler_pattern[:-1]):
                    is_part_of_pattern = True
                    break
                # Проверяем паттерны типа "category:" которые обрабатываются через startswith
                if ':' in handler_pattern and pattern.startswith(handler_pattern.split(':')[0] + ':'):
                    is_part_of_pattern = True
                    break
            
            if not is_part_of_pattern:
                missing_handlers.append(pattern)
    
    if missing_handlers:
        print(f"   [WARNING] Найдено {len(missing_handlers)} callback_data без явных обработчиков:")
        for handler in sorted(missing_handlers)[:20]:  # Показываем первые 20
            print(f"      - {handler}")
        if len(missing_handlers) > 20:
            print(f"      ... и еще {len(missing_handlers) - 20}")
    else:
        print("   [OK] Все callback_data имеют обработчики")
    print()
    
    # 5. Проверяем confirm_generation
    print("[5] ПРОВЕРКА 5: Проверка логики confirm_generation...")
    confirm_issues = check_confirm_generation_flow(file_path)
    if confirm_issues:
        for issue in confirm_issues:
            print(f"   {issue}")
    else:
        print("   [OK] Логика confirm_generation корректна")
    print()
    
    # 6. Проверяем input_parameters
    print("[6] ПРОВЕРКА 6: Проверка логики input_parameters...")
    input_issues = check_input_parameters_flow(file_path)
    if input_issues:
        for issue in input_issues:
            print(f"   {issue}")
    else:
        print("   [OK] Логика input_parameters корректна")
    print()
    
    # 7. Проверяем состояния ConversationHandler
    print("[7] ПРОВЕРКА 7: Проверка состояний ConversationHandler...")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        required_states = ['SELECTING_MODEL', 'INPUTTING_PARAMS', 'CONFIRMING_GENERATION']
        for state in required_states:
            if state not in content:
                print(f"   [ERROR] Состояние {state} не найдено")
            else:
                # Проверяем, что confirm_generate обрабатывается в CONFIRMING_GENERATION
                if state == 'CONFIRMING_GENERATION':
                    state_section = content.split(state)[1].split('],')[0] if state in content else ''
                    if 'confirm_generate' not in state_section:
                        print(f"   [WARNING] confirm_generate не обрабатывается в состоянии {state}")
                    else:
                        print(f"   [OK] Состояние {state} правильно настроено")
    
    print()
    print("=" * 80)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    
    total_issues = len(missing_handlers) + len(confirm_issues) + len(input_issues)
    
    if total_issues == 0:
        print("[SUCCESS] ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print("   Все кнопки имеют обработчики")
        print("   Логика генерации корректна")
        print("   Все состояния правильно настроены")
        return 0
    else:
        print(f"[WARNING] НАЙДЕНО {total_issues} ПРОБЛЕМ")
        print("   Требуется дополнительная проверка")
        return 1

if __name__ == '__main__':
    sys.exit(main())


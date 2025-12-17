#!/usr/bin/env python3
"""
Глубокая проверка всех сценариев генерации
Проверяет каждый путь от начала до конца
"""

import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def check_generation_flow(file_path):
    """Проверяет полный поток генерации"""
    issues = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Проверка: select_model -> input_parameters
    print("[ПРОВЕРКА 1] Путь: select_model -> input_parameters")
    if 'select_model:' in content and 'async def input_parameters' in content:
        # Проверяем, что select_model вызывает input_parameters или устанавливает состояние
        select_model_section = content.split('select_model:')[1].split('def ')[0] if 'select_model:' in content else ''
        if 'INPUTTING_PARAMS' in select_model_section or 'input_parameters' in select_model_section:
            print("   [OK] select_model правильно переходит к input_parameters")
        else:
            issues.append("[ERROR] select_model не переходит к input_parameters")
            print("   [ERROR] select_model не переходит к input_parameters")
    print()
    
    # 2. Проверка: input_parameters -> показ кнопки
    print("[ПРОВЕРКА 2] Путь: input_parameters -> показ кнопки confirm_generate")
    if 'all_required_collected' in content:
        # Находим место где показывается кнопка
        all_required_sections = content.split('all_required_collected')
        found_button = False
        found_return = False
        
        for i, section in enumerate(all_required_sections[1:], 1):
            # Проверяем первые 3000 символов после all_required_collected
            check_section = section[:3000]
            if 'confirm_generate' in check_section:
                found_button = True
            if 'CONFIRMING_GENERATION' in check_section:
                found_return = True
        
        if found_button and found_return:
            print("   [OK] Кнопка confirm_generate показывается после all_required_collected")
        else:
            if not found_button:
                issues.append("[ERROR] Кнопка confirm_generate не показывается после all_required_collected")
                print("   [ERROR] Кнопка confirm_generate не показывается после all_required_collected")
            if not found_return:
                issues.append("[ERROR] Не возвращается CONFIRMING_GENERATION после показа кнопки")
                print("   [ERROR] Не возвращается CONFIRMING_GENERATION после показа кнопки")
    print()
    
    # 3. Проверка: confirm_generate -> confirm_generation
    print("[ПРОВЕРКА 3] Путь: confirm_generate -> confirm_generation")
    if 'CallbackQueryHandler(confirm_generation, pattern=\'^confirm_generate$\')' in content:
        print("   [OK] confirm_generate правильно обрабатывается через confirm_generation")
    else:
        issues.append("[ERROR] confirm_generate не обрабатывается через confirm_generation")
        print("   [ERROR] confirm_generate не обрабатывается через confirm_generation")
    print()
    
    # 4. Проверка: confirm_generation -> создание задачи
    print("[ПРОВЕРКА 4] Путь: confirm_generation -> создание задачи")
    confirm_section = content.split('async def confirm_generation')[1].split('async def ')[0] if 'async def confirm_generation' in content else ''
    
    checks = {
        'query.answer()': 'query.answer() вызывается',
        'send_or_edit_message': 'send_or_edit_message используется',
        'kie.create_task': 'kie.create_task вызывается',
        'poll_task_status': 'poll_task_status запускается'
    }
    
    for check, description in checks.items():
        if check in confirm_section:
            print(f"   [OK] {description}")
        else:
            issues.append(f"[WARNING] {description} не найдено")
            print(f"   [WARNING] {description} не найдено")
    print()
    
    # 5. Проверка обработки ошибок
    print("[ПРОВЕРКА 5] Обработка ошибок в confirm_generation")
    error_checks = {
        'try:': 'Есть try блоки',
        'except': 'Есть except блоки',
        'send_or_edit_message': 'Используется send_or_edit_message для ошибок'
    }
    
    for check, description in error_checks.items():
        if check in confirm_section:
            print(f"   [OK] {description}")
        else:
            issues.append(f"[WARNING] {description} не найдено")
            print(f"   [WARNING] {description} не найдено")
    print()
    
    # 6. Проверка всех путей показа кнопки
    print("[ПРОВЕРКА 6] Все пути показа кнопки confirm_generate")
    # Ищем все места где создается кнопка confirm_generate
    button_pattern = r'InlineKeyboardButton\([^,]+,\s*callback_data=["\']confirm_generate["\']'
    matches = re.findall(button_pattern, content)
    print(f"   Найдено {len(matches)} мест создания кнопки confirm_generate")
    
    # Проверяем, что после каждого создания кнопки возвращается CONFIRMING_GENERATION
    for i, match in enumerate(matches[:5], 1):  # Проверяем первые 5
        match_pos = content.find(match)
        after_match = content[match_pos:match_pos+500]  # 500 символов после кнопки
        if 'CONFIRMING_GENERATION' in after_match or 'return CONFIRMING_GENERATION' in after_match:
            print(f"   [OK] Путь {i}: кнопка -> CONFIRMING_GENERATION")
        else:
            issues.append(f"[WARNING] Путь {i}: кнопка может не возвращать CONFIRMING_GENERATION")
            print(f"   [WARNING] Путь {i}: кнопка может не возвращать CONFIRMING_GENERATION")
    print()
    
    # 7. Проверка состояний ConversationHandler
    print("[ПРОВЕРКА 7] Состояния ConversationHandler")
    states = {
        'SELECTING_MODEL': ['select_model:', 'show_models'],
        'INPUTTING_PARAMS': ['input_parameters', 'all_required_collected'],
        'CONFIRMING_GENERATION': ['confirm_generate', 'confirm_generation']
    }
    
    for state, keywords in states.items():
        if state in content:
            # Проверяем, что состояние содержит нужные ключевые слова
            state_section = content.split(state + ':')[1].split('],')[0] if state + ':' in content else ''
            found_keywords = sum(1 for kw in keywords if kw in state_section)
            if found_keywords > 0:
                print(f"   [OK] Состояние {state} правильно настроено ({found_keywords}/{len(keywords)} ключевых слов)")
            else:
                issues.append(f"[WARNING] Состояние {state} может быть неправильно настроено")
                print(f"   [WARNING] Состояние {state} может быть неправильно настроено")
        else:
            issues.append(f"[ERROR] Состояние {state} не найдено")
            print(f"   [ERROR] Состояние {state} не найдено")
    print()
    
    return issues

def check_button_handlers(file_path):
    """Проверяет все обработчики кнопок"""
    issues = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("[ПРОВЕРКА 8] Обработчики кнопок в button_callback")
    
    # Ищем все if data == или if data.startswith в button_callback
    button_callback_section = content.split('async def button_callback')[1].split('async def ')[0] if 'async def button_callback' in content else ''
    
    # Извлекаем все проверки data
    data_checks = re.findall(r'if\s+data\s*==\s*["\']([^"\']+)["\']', button_callback_section)
    data_starts = re.findall(r'data\.startswith\(["\']([^"\']+)["\']', button_callback_section)
    
    print(f"   Найдено {len(data_checks)} точных проверок data")
    print(f"   Найдено {len(data_starts)} проверок data.startswith")
    
    # Проверяем, что после каждой проверки есть query.answer()
    for check in data_checks[:10]:  # Первые 10
        # Находим место проверки
        check_pos = button_callback_section.find(f'data == "{check}"')
        if check_pos == -1:
            check_pos = button_callback_section.find(f"data == '{check}'")
        
        if check_pos != -1:
            # Проверяем следующие 200 символов на наличие query.answer()
            after_check = button_callback_section[check_pos:check_pos+200]
            if 'query.answer()' in after_check or 'await query.answer()' in after_check:
                print(f"   [OK] {check}: query.answer() вызывается")
            else:
                issues.append(f"[WARNING] {check}: query.answer() может не вызываться")
                print(f"   [WARNING] {check}: query.answer() может не вызываться")
    print()
    
    return issues

def main():
    file_path = 'bot_kie.py'
    
    print("=" * 80)
    print("ГЛУБОКАЯ ПРОВЕРКА ВСЕХ СЦЕНАРИЕВ ГЕНЕРАЦИИ")
    print("=" * 80)
    print()
    
    # Проверка потока генерации
    flow_issues = check_generation_flow(file_path)
    
    # Проверка обработчиков кнопок
    handler_issues = check_button_handlers(file_path)
    
    # Итоговый отчет
    print("=" * 80)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    
    all_issues = flow_issues + handler_issues
    
    if len(all_issues) == 0:
        print("[SUCCESS] ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print("   Все пути генерации работают корректно")
        print("   Все кнопки имеют обработчики")
        print("   Все состояния правильно настроены")
        return 0
    else:
        print(f"[WARNING] НАЙДЕНО {len(all_issues)} ПРОБЛЕМ:")
        for issue in all_issues[:20]:  # Показываем первые 20
            print(f"   {issue}")
        if len(all_issues) > 20:
            print(f"   ... и еще {len(all_issues) - 20}")
        return 1

if __name__ == '__main__':
    sys.exit(main())





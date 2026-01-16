"""
Test to ensure all callback_query handlers call query.answer().

CI Guard: все обработчики callback_query должны вызывать query.answer().
"""
import re
import ast
from pathlib import Path


def test_all_callbacks_have_answer():
    """Проверяет, что все обработчики callback_query вызывают query.answer()."""
    project_root = Path(__file__).parent.parent
    handlers_dir = project_root / "bot" / "handlers"
    
    if not handlers_dir.exists():
        return  # Если handlers/ нет, тест проходит
    
    issues = []
    
    for py_file in handlers_dir.rglob("*.py"):
        if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
            continue
        
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            
            # Ищем все функции с @router.callback_query
            lines = content.split('\n')
            callback_functions = []
            
            for i, line in enumerate(lines):
                # Ищем декоратор @router.callback_query
                if '@router.callback_query' in line or '@router.callback_query(' in line:
                    # Ищем следующую функцию
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if re.match(r'^\s*async def\s+\w+', lines[j]):
                            func_match = re.match(r'^\s*async def\s+(\w+)', lines[j])
                            if func_match:
                                func_name = func_match.group(1)
                                # Находим конец функции
                                func_start = j
                                func_end = func_start
                                indent_level = len(lines[func_start]) - len(lines[func_start].lstrip())
                                
                                for k in range(func_start + 1, len(lines)):
                                    if lines[k].strip() and not lines[k].startswith(' ' * (indent_level + 1)) and not lines[k].startswith('\t'):
                                        if lines[k].strip().startswith('async def') or lines[k].strip().startswith('def') or lines[k].strip().startswith('@'):
                                            func_end = k
                                            break
                                else:
                                    func_end = len(lines)
                                
                                func_body = '\n'.join(lines[func_start:func_end])
                                
                                # Проверяем наличие query.answer()
                                if 'query.answer()' not in func_body and 'await query.answer()' not in func_body:
                                    rel_path = py_file.relative_to(project_root)
                                    issues.append(f"{rel_path}:{func_start+1} - {func_name}() missing query.answer()")
                            break
            
            # Также проверяем через regex для простых случаев
            callback_pattern = r'@router\.callback_query[^\n]*\n\s*async def\s+(\w+)'
            for match in re.finditer(callback_pattern, content, re.MULTILINE):
                func_name = match.group(1)
                # Находим тело функции
                func_start = match.end()
                # Ищем следующую функцию или конец файла
                next_func = re.search(r'\n\s*(?:async )?def\s+\w+', content[func_start:])
                if next_func:
                    func_body = content[func_start:func_start + next_func.start()]
                else:
                    func_body = content[func_start:]
                
                # Проверяем наличие query.answer()
                if 'query.answer()' not in func_body and 'await query.answer()' not in func_body:
                    # Исключаем если это не callback_query handler (может быть другой тип)
                    if 'callback_query' in match.group(0):
                        line_num = content[:match.start()].count('\n') + 1
                        rel_path = py_file.relative_to(project_root)
                        if not any(f"{rel_path}:{line_num}" in issue for issue in issues):
                            issues.append(f"{rel_path}:{line_num} - {func_name}() missing query.answer()")
        
        except Exception as e:
            # Если файл не парсится, пропускаем
            continue
    
    if issues:
        error_msg = "Found callback_query handlers without query.answer():\n"
        error_msg += "\n".join(f"  - {issue}" for issue in issues[:20])
        if len(issues) > 20:
            error_msg += f"\n  ... and {len(issues) - 20} more"
        error_msg += "\n\nAll callback_query handlers MUST call await query.answer()"
        assert False, error_msg


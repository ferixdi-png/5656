"""
Тест на наличие merge markers в коде
Запрещает <<<<<<<, =======, >>>>>>> в исходниках
"""

import os
import re
from pathlib import Path


def test_no_merge_markers():
    """Проверяет отсутствие merge markers во всех .py файлах"""
    project_root = Path(__file__).parent.parent
    
    merge_patterns = [
        (r'^<<<<<<<', '<<<<<<<'),
        (r'^=======', '======='),
        (r'^>>>>>>>', '>>>>>>>'),
    ]
    
    errors = []
    
    # Исключаем директории
    exclude_dirs = {
        '__pycache__', '.git', 'node_modules', '.venv', 'venv',
        'env', '.env', 'migrations', 'artifacts', 'data'
    }
    
    # Исключаем файлы
    exclude_files = {
        'test_merge_markers.py',  # Сам тест
    }
    
    for py_file in project_root.rglob('*.py'):
        # Пропускаем исключенные директории
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
        
        # Пропускаем исключенные файлы
        if py_file.name in exclude_files:
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    for pattern, marker in merge_patterns:
                        if re.match(pattern, line.strip()):
                            rel_path = py_file.relative_to(project_root)
                            errors.append(
                                f"{rel_path}:{line_num} - Found merge marker '{marker}'"
                            )
        except Exception as e:
            # Игнорируем ошибки чтения (бинарные файлы и т.д.)
            pass
    
    if errors:
        error_msg = "\n".join(f"  - {err}" for err in errors)
        raise AssertionError(
            f"Found {len(errors)} merge marker(s) in code:\n{error_msg}\n\n"
            "Please resolve all merge conflicts before committing."
        )


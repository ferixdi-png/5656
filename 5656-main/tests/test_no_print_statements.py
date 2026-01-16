"""
Test to ensure no print() statements exist outside of tests directory.

CI Guard: запрещены print() вне tests.
"""
import os
import re
from pathlib import Path


def test_no_print_statements_in_app():
    """Проверяет, что в app/ нет print() statements."""
    project_root = Path(__file__).parent.parent
    app_dir = project_root / "app"
    
    if not app_dir.exists():
        return  # Если app/ нет, тест проходит
    
    print_statements = []
    
    for py_file in app_dir.rglob("*.py"):
        # Пропускаем __pycache__
        if "__pycache__" in str(py_file):
            continue
        
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # Ищем print( но пропускаем комментарии и строки
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                
                # Проверяем print( но не print_summary и не в if __name__ == "__main__"
                if re.search(r'\bprint\s*\(', line):
                    # Исключаем if __name__ == "__main__" блоки (это CLI утилиты)
                    # Проверяем контекст - если это в if __name__ блоке, пропускаем
                    context_lines = lines[max(0, line_num-10):line_num]
                    context = '\n'.join(context_lines)
                    
                    if 'if __name__' in context or '__main__' in context:
                        # Это CLI утилита, разрешено
                        continue
                    
                    # Исключаем методы с именем print_* (например, print_summary)
                    if re.search(r'def\s+print_', context):
                        continue
                    
                    rel_path = py_file.relative_to(project_root)
                    print_statements.append(f"{rel_path}:{line_num}")
        
        except Exception as e:
            # Если файл не читается, пропускаем
            continue
    
    if print_statements:
        error_msg = "Found print() statements in app/ directory:\n"
        error_msg += "\n".join(f"  - {stmt}" for stmt in print_statements[:20])
        if len(print_statements) > 20:
            error_msg += f"\n  ... and {len(print_statements) - 20} more"
        error_msg += "\n\nUse logger instead: from app.utils.logging_config import logger"
        assert False, error_msg


def test_no_print_statements_in_bot():
    """Проверяет, что в bot/ нет print() statements."""
    project_root = Path(__file__).parent.parent
    bot_dir = project_root / "bot"
    
    if not bot_dir.exists():
        return  # Если bot/ нет, тест проходит
    
    print_statements = []
    
    for py_file in bot_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                
                if re.search(r'\bprint\s*\(', line):
                    # Проверяем контекст
                    context_lines = lines[max(0, line_num-10):line_num]
                    context = '\n'.join(context_lines)
                    
                    if 'if __name__' in context or '__main__' in context:
                        continue
                    
                    if re.search(r'def\s+print_', context):
                        continue
                    
                    rel_path = py_file.relative_to(project_root)
                    print_statements.append(f"{rel_path}:{line_num}")
        
        except Exception:
            continue
    
    if print_statements:
        error_msg = "Found print() statements in bot/ directory:\n"
        error_msg += "\n".join(f"  - {stmt}" for stmt in print_statements[:20])
        if len(print_statements) > 20:
            error_msg += f"\n  ... and {len(print_statements) - 20} more"
        error_msg += "\n\nUse logger instead: import logging; logger = logging.getLogger(__name__)"
        assert False, error_msg


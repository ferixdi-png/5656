#!/usr/bin/env python3
"""
Исправление дат в отчётах и markdown-файлах.
Заменяет захардкоженные даты на динамические.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def get_current_datetime_str() -> str:
    """Получает текущую дату и время в правильном формате."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M")


def get_current_date_str() -> str:
    """Получает текущую дату в формате YYYY-MM-DD."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d")


def fix_dates_in_file(file_path: Path) -> Tuple[bool, int]:
    """
    Исправляет даты в файле.
    
    Returns:
        (были_изменения, количество_замен)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        replacements = 0
        
        # Паттерны для замены
        patterns = [
            # "## Дата: 2024-12-19"
            (r'## Дата:\s*2024-\d{2}-\d{2}', f'## Дата: {get_current_date_str()}'),
            # "## Дата создания: 2024-12-19"
            (r'## Дата создания:\s*2024-\d{2}-\d{2}', f'## Дата создания: {get_current_date_str()}'),
            # "Дата: 2024-12-19"
            (r'Дата:\s*2024-\d{2}-\d{2}', f'Дата: {get_current_date_str()}'),
            # "## Дата: 2024-12-19"
            (r'##\s*Дата:\s*2024-\d{2}-\d{2}', f'## Дата: {get_current_date_str()}'),
            # В timestamp в JSON
            (r'"timestamp":\s*"2024-\d{2}-\d{2}[^"]*"', f'"timestamp": "{datetime.now().isoformat()}"'),
            # В Python коде: datetime.now().isoformat() - оставляем как есть, это правильно
            # Но если есть захардкоженные строки
            (r'datetime\(2024,\s*\d+,\s*\d+\)', f'datetime.now()'),
        ]
        
        for pattern, replacement in patterns:
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                replacements += len(matches)
        
        # Заменяем старые даты в формате "2024-12-19" на текущую
        old_date_pattern = r'\b2024-12-19\b'
        if re.search(old_date_pattern, content):
            content = re.sub(old_date_pattern, get_current_date_str(), content)
            replacements += len(re.findall(old_date_pattern, original_content))
        
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, replacements
        
        return False, 0
        
    except Exception as e:
        print(f"❌ Ошибка при обработке {file_path}: {e}")
        return False, 0


def fix_dates_in_python_scripts() -> Tuple[int, int]:
    """Исправляет даты в Python скриптах."""
    fixed_files = 0
    total_replacements = 0
    
    python_files = [
        root_dir / "complete_system_integration.py",
        root_dir / "final_integration_all_tasks.py",
        root_dir / "generate_full_report.py",
        root_dir / "scripts" / "full_integration_47_models.py",
        root_dir / "scripts" / "deep_analyze_kie_models.py",
        root_dir / "scripts" / "sync_kie_models.py",
        root_dir / "scripts" / "full_sync_kie_models.py",
    ]
    
    for file_path in python_files:
        if not file_path.exists():
            continue
        
        try:
            content = file_path.read_text(encoding='utf-8')
            original_content = content
            replacements = 0
            
            # Заменяем захардкоженные даты в строках
            # "timestamp": "2024-12-19..."
            content = re.sub(
                r'"timestamp":\s*"2024-\d{2}-\d{2}[^"]*"',
                f'"timestamp": "{datetime.now().isoformat()}"',
                content
            )
            replacements += len(re.findall(r'"timestamp":\s*"2024-\d{2}-\d{2}[^"]*"', original_content))
            
            # Заменяем в print/logger строках
            content = re.sub(
                r'print\(f?"[^"]*2024-12-19[^"]*"\)',
                lambda m: m.group(0).replace('2024-12-19', get_current_date_str()),
                content
            )
            
            if content != original_content:
                file_path.write_text(content, encoding='utf-8')
                fixed_files += 1
                total_replacements += replacements
                print(f"✅ Исправлен: {file_path.name} ({replacements} замен)")
        
        except Exception as e:
            print(f"❌ Ошибка в {file_path}: {e}")
    
    return fixed_files, total_replacements


def fix_dates_in_markdown_files() -> Tuple[int, int]:
    """Исправляет даты во всех markdown файлах."""
    fixed_files = 0
    total_replacements = 0
    
    # Находим все markdown файлы с отчётами
    markdown_patterns = [
        "*_REPORT.md",
        "*_CHECK.md",
        "*_SUMMARY.md",
        "*ОТЧЕТ*.md",
        "*ОТЧЁТ*.md",
        "*ИНСТРУКЦИЯ*.md",
        "DOCS.md",
        "integration_plan.md",
    ]
    
    markdown_files = []
    for pattern in markdown_patterns:
        markdown_files.extend(root_dir.glob(pattern))
    
    # Убираем дубликаты
    markdown_files = list(set(markdown_files))
    
    for file_path in markdown_files:
        if not file_path.exists():
            continue
        
        changed, replacements = fix_dates_in_file(file_path)
        if changed:
            fixed_files += 1
            total_replacements += replacements
            print(f"✅ Исправлен: {file_path.name} ({replacements} замен)")
    
    return fixed_files, total_replacements


def main():
    """Основная функция."""
    print("🔧 Исправление дат в отчётах и файлах...")
    print(f"Текущая дата: {get_current_date_str()}")
    print()
    
    # Исправляем markdown файлы
    print("📝 Исправление markdown файлов...")
    md_fixed, md_replacements = fix_dates_in_markdown_files()
    
    # Исправляем Python скрипты
    print("\n🐍 Исправление Python скриптов...")
    py_fixed, py_replacements = fix_dates_in_python_scripts()
    
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТЫ ИСПРАВЛЕНИЯ")
    print("="*80)
    print(f"Markdown файлов исправлено: {md_fixed}")
    print(f"Замен в markdown: {md_replacements}")
    print(f"Python скриптов исправлено: {py_fixed}")
    print(f"Замен в Python: {py_replacements}")
    print(f"Всего замен: {md_replacements + py_replacements}")
    print("="*80)
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)


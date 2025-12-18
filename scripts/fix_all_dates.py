#!/usr/bin/env python3
"""
Исправление всех захардкоженных дат в markdown файлах.
Заменяет на динамические даты.
"""

import re
from pathlib import Path
from datetime import datetime

root_dir = Path(__file__).parent.parent


def get_current_date() -> str:
    """Получает текущую дату в формате YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def fix_dates_in_markdown(file_path: Path) -> bool:
    """Исправляет даты в markdown файле."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        
        current_date = get_current_date()
        
        # Заменяем все варианты дат
        patterns = [
            (r'## Дата:\s*2024-\d{2}-\d{2}', f'## Дата: {current_date}'),
            (r'## Дата создания:\s*2024-\d{2}-\d{2}', f'## Дата создания: {current_date}'),
            (r'Дата:\s*2024-\d{2}-\d{2}', f'Дата: {current_date}'),
            (r'\b2024-12-19\b', current_date),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        if content != original:
            file_path.write_text(content, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f"❌ Ошибка в {file_path.name}: {e}")
        return False


def main():
    """Основная функция."""
    print(f"🔧 Исправление дат в markdown файлах...")
    print(f"Текущая дата: {get_current_date()}\n")
    
    # Находим все markdown файлы
    md_files = list(root_dir.glob("*.md"))
    
    fixed = 0
    for md_file in md_files:
        if fix_dates_in_markdown(md_file):
            fixed += 1
            print(f"✅ {md_file.name}")
    
    print(f"\n✅ Исправлено файлов: {fixed}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


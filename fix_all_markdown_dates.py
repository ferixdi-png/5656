#!/usr/bin/env python3
"""Исправление всех дат в markdown файлах."""

import re
from pathlib import Path
from datetime import datetime

root_dir = Path(__file__).parent
current_date = datetime.now().strftime("%Y-%m-%d")

print(f"🔧 Исправление дат в markdown файлах...")
print(f"Текущая дата: {current_date}\n")

md_files = list(root_dir.glob("*.md"))
fixed_count = 0

for md_file in md_files:
    try:
        content = md_file.read_text(encoding='utf-8')
        original = content
        
        # Заменяем все варианты дат
        content = re.sub(r'## Дата:\s*2024-\d{2}-\d{2}', f'## Дата: {current_date}', content)
        content = re.sub(r'## Дата создания:\s*2024-\d{2}-\d{2}', f'## Дата создания: {current_date}', content)
        content = re.sub(r'Дата:\s*2024-\d{2}-\d{2}', f'Дата: {current_date}', content)
        content = re.sub(r'\b2024-12-19\b', current_date, content)
        
        if content != original:
            md_file.write_text(content, encoding='utf-8')
            fixed_count += 1
            print(f"✅ {md_file.name}")
    except Exception as e:
        print(f"❌ Ошибка в {md_file.name}: {e}")

print(f"\n✅ Исправлено файлов: {fixed_count}")


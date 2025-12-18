#!/usr/bin/env python3
"""
Добавление PYTHONPATH в начало bot_kie.py для гарантии правильного импорта.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
bot_kie_file = root_dir / "bot_kie.py"

# Проверяем, есть ли уже добавление пути
with open(bot_kie_file, 'r', encoding='utf-8') as f:
    content = f.read()
    
    # Проверяем, есть ли уже sys.path.insert
    if 'sys.path.insert' in content or 'sys.path.append' in content:
        print("✅ sys.path уже настроен в bot_kie.py")
        sys.exit(0)
    
    # Проверяем, есть ли импорт sys
    if 'import sys' not in content:
        # Находим место после импортов
        lines = content.split('\n')
        insert_pos = 0
        
        # Ищем последний import
        for i, line in enumerate(lines):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                insert_pos = i + 1
        
        # Добавляем sys.path.insert после импортов
        lines.insert(insert_pos, '')
        lines.insert(insert_pos + 1, '# Ensure Python can find modules in the same directory')
        lines.insert(insert_pos + 2, 'import sys')
        lines.insert(insert_pos + 3, 'from pathlib import Path')
        lines.insert(insert_pos + 4, "sys.path.insert(0, str(Path(__file__).parent))")
        lines.insert(insert_pos + 5, '')
        
        new_content = '\n'.join(lines)
        
        with open(bot_kie_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ Добавлен sys.path.insert в bot_kie.py")
    else:
        print("⚠️ import sys уже есть, но sys.path не настроен")
        print("   Рекомендуется добавить вручную после импортов:")
        print("   sys.path.insert(0, str(Path(__file__).parent))")


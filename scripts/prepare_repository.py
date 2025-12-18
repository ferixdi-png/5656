#!/usr/bin/env python3
"""
Подготовка репозитория к деплою.
Проверяет структуру, создаёт необходимые файлы, убирает лишнее.
"""

import os
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent

# Необходимые файлы для работы бота
REQUIRED_FILES = [
    'bot_kie.py',
    'kie_gateway.py',
    'kie_client.py',
    'kie_models.py',
    'config_runtime.py',
    'knowledge_storage.py',
    'translations.py',
    'helpers.py',
    'error_handler_providers.py',
    'requirements.txt',
    'Dockerfile',
    'render.yaml',
]

# Необходимые папки
REQUIRED_DIRS = [
    'scripts',
    'tests',
    'data',  # Опционально, но желательно
]

# Важные файлы документации (оставить)
IMPORTANT_DOCS = [
    'README.md',
    'README_DEPLOY_RENDER.md',
    'DEPLOY_CHECKLIST.md',
    'RENDER_ENV_VARIABLES.md',
    'RENDER_ENV_SETUP.md',
]


def check_repository_structure():
    """Проверяет структуру репозитория."""
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА СТРУКТУРЫ РЕПОЗИТОРИЯ")
    print("="*80)
    
    errors = []
    warnings = []
    
    # Проверка необходимых файлов
    print("\n📄 Проверка необходимых файлов:")
    for file_name in REQUIRED_FILES:
        file_path = root_dir / file_name
        if file_path.exists():
            print(f"  ✅ {file_name}")
        else:
            errors.append(f"❌ Отсутствует: {file_name}")
            print(f"  ❌ {file_name} - НЕ НАЙДЕН!")
    
    # Проверка необходимых папок
    print("\n📁 Проверка необходимых папок:")
    for dir_name in REQUIRED_DIRS:
        dir_path = root_dir / dir_name
        if dir_path.exists() and dir_path.is_dir():
            print(f"  ✅ {dir_name}/")
        else:
            warnings.append(f"⚠️ Отсутствует папка: {dir_name}/")
            print(f"  ⚠️ {dir_name}/ - не найдена (не критично)")
    
    # Проверка .gitignore
    print("\n📋 Проверка .gitignore:")
    gitignore_path = root_dir / '.gitignore'
    if gitignore_path.exists():
        print("  ✅ .gitignore существует")
    else:
        warnings.append("⚠️ .gitignore отсутствует")
        print("  ⚠️ .gitignore отсутствует")
    
    # Итоговый отчёт
    print("\n" + "="*80)
    if errors:
        print("❌ ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ ОШИБКИ:")
        for error in errors:
            print(f"  {error}")
        return 1
    elif warnings:
        print("⚠️ ЕСТЬ ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"  {warning}")
        print("\n✅ Критических ошибок нет")
        return 0
    else:
        print("✅ ВСЁ В ПОРЯДКЕ!")
        print("✅ Репозиторий готов к деплою!")
        return 0


if __name__ == "__main__":
    sys.exit(check_repository_structure())


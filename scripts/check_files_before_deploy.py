#!/usr/bin/env python3
"""
Проверка наличия всех необходимых файлов перед деплоем на Render.
Убеждается, что все файлы присутствуют и готовы к деплою.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Список обязательных файлов для деплоя
REQUIRED_FILES = [
    "bot_kie.py",
    "kie_gateway.py",  # КРИТИЧЕСКИ ВАЖЕН!
    "kie_client.py",
    "config_runtime.py",
    "knowledge_storage.py",
    "translations.py",
    "helpers.py",
    "kie_models.py",
    "requirements.txt",
    "render.yaml",
]


def check_files_before_deploy():
    """Проверяет наличие всех необходимых файлов."""
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА ФАЙЛОВ ПЕРЕД ДЕПЛОЕМ НА RENDER")
    print("="*80)
    
    errors = []
    warnings = []
    found_files = []
    
    for file_name in REQUIRED_FILES:
        file_path = root_dir / file_name
        if file_path.exists():
            found_files.append(file_name)
            print(f"  ✅ {file_name}")
        else:
            errors.append(f"❌ {file_name} - НЕ НАЙДЕН!")
            print(f"  ❌ {file_name} - НЕ НАЙДЕН!")
    
    # Дополнительная проверка критических файлов
    critical_files = ["kie_gateway.py", "bot_kie.py", "requirements.txt"]
    for file_name in critical_files:
        file_path = root_dir / file_name
        if not file_path.exists():
            errors.append(f"❌ КРИТИЧЕСКИЙ ФАЙЛ {file_name} ОТСУТСТВУЕТ!")
            print(f"  ❌ КРИТИЧЕСКИЙ ФАЙЛ {file_name} ОТСУТСТВУЕТ!")
    
    # Проверка импорта kie_gateway в bot_kie.py
    bot_kie_file = root_dir / "bot_kie.py"
    if bot_kie_file.exists():
        with open(bot_kie_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'from kie_gateway import get_kie_gateway' in content:
                print("  ✅ bot_kie.py содержит импорт kie_gateway")
            else:
                errors.append("❌ bot_kie.py НЕ содержит импорт kie_gateway!")
                print("  ❌ bot_kie.py НЕ содержит импорт kie_gateway!")
    
    # Итоговый отчёт
    print("\n" + "="*80)
    print(f"Найдено файлов: {len(found_files)}/{len(REQUIRED_FILES)}")
    
    if errors:
        print("\n❌ ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ ОШИБКИ:")
        for error in errors:
            print(f"  {error}")
        print("\n⚠️ НЕ ДЕПЛОЙТЕ ПРОЕКТ ДО ИСПРАВЛЕНИЯ ОШИБОК!")
        print("\n📋 ИНСТРУКЦИЯ ПО ИСПРАВЛЕНИЮ:")
        print("  1. Убедитесь, что все файлы присутствуют в корне проекта")
        print("  2. Добавьте отсутствующие файлы в git:")
        print("     git add <имя_файла>")
        print("  3. Закоммитьте изменения:")
        print("     git commit -m 'Add missing files'")
        print("  4. Запушьте в репозиторий:")
        print("     git push")
        return 1
    elif warnings:
        print("\n⚠️ ЕСТЬ ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"  {warning}")
        print("\n✅ Критических ошибок нет, но рекомендуется исправить предупреждения")
        return 0
    else:
        print("\n✅ ВСЕ ФАЙЛЫ ПРИСУТСТВУЮТ!")
        print("✅ Проект готов к деплою на Render!")
        print("\n📋 СЛЕДУЮЩИЕ ШАГИ:")
        print("  1. Убедитесь, что все файлы добавлены в git:")
        print("     git status")
        print("  2. Если есть неотслеживаемые файлы, добавьте их:")
        print("     git add <имя_файла>")
        print("  3. Закоммитьте изменения:")
        print("     git commit -m 'Prepare for deploy'")
        print("  4. Запушьте в репозиторий:")
        print("     git push")
        print("  5. Render автоматически задеплоит проект")
        return 0


if __name__ == "__main__":
    sys.exit(check_files_before_deploy())


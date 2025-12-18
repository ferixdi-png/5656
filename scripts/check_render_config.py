#!/usr/bin/env python3
"""
Проверка конфигурации для Render.
Убеждается, что проект настроен как Python приложение, а не Node.js.
"""

import os
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


def check_render_config():
    """Проверяет конфигурацию для Render."""
    print("\n" + "="*80)
    print("🔧 ПРОВЕРКА КОНФИГУРАЦИИ ДЛЯ RENDER")
    print("="*80)
    
    errors = []
    warnings = []
    
    # 1. Проверка наличия package.json (не должен быть для Python проекта)
    package_json = root_dir / "package.json"
    if package_json.exists():
        errors.append("❌ package.json найден - это Node.js файл, не нужен для Python проекта!")
        print(f"  ❌ Найден {package_json} - удалите его, это Node.js файл")
    else:
        print("  ✅ package.json отсутствует (правильно для Python проекта)")
    
    # 2. Проверка наличия index.js (не должен быть для Python проекта)
    index_js = root_dir / "index.js"
    if index_js.exists():
        errors.append("❌ index.js найден - это Node.js файл, не нужен для Python проекта!")
        print(f"  ❌ Найден {index_js} - удалите его, это Node.js файл")
    else:
        print("  ✅ index.js отсутствует (правильно для Python проекта)")
    
    # 3. Проверка наличия requirements.txt (обязателен для Python проекта)
    requirements_txt = root_dir / "requirements.txt"
    if requirements_txt.exists():
        print("  ✅ requirements.txt присутствует (правильно для Python проекта)")
    else:
        errors.append("❌ requirements.txt отсутствует - обязателен для Python проекта!")
        print("  ❌ requirements.txt отсутствует")
    
    # 4. Проверка наличия bot_kie.py (обязателен для запуска)
    bot_kie_py = root_dir / "bot_kie.py"
    if bot_kie_py.exists():
        print("  ✅ bot_kie.py присутствует (правильно для запуска)")
    else:
        errors.append("❌ bot_kie.py отсутствует - обязателен для запуска!")
        print("  ❌ bot_kie.py отсутствует")
    
    # 5. Проверка наличия render.yaml
    render_yaml = root_dir / "render.yaml"
    if render_yaml.exists():
        print("  ✅ render.yaml присутствует")
        
        # Проверяем содержимое render.yaml
        with open(render_yaml, 'r', encoding='utf-8') as f:
            content = f.read()
            
            if 'npm install' in content or 'npm start' in content or 'node index.js' in content:
                errors.append("❌ render.yaml содержит Node.js команды - исправьте на Python команды!")
                print("  ❌ render.yaml содержит Node.js команды")
            else:
                print("  ✅ render.yaml содержит правильные Python команды")
            
            if 'pip install -r requirements.txt' in content:
                print("  ✅ render.yaml содержит правильный build command")
            else:
                warnings.append("⚠️ render.yaml может не содержать правильный build command")
            
            if 'python bot_kie.py' in content:
                print("  ✅ render.yaml содержит правильный start command")
            else:
                warnings.append("⚠️ render.yaml может не содержать правильный start command")
    else:
        warnings.append("⚠️ render.yaml отсутствует (не критично, можно настроить вручную)")
        print("  ⚠️ render.yaml отсутствует")
    
    # 6. Проверка наличия node_modules (не должен быть для Python проекта)
    node_modules = root_dir / "node_modules"
    if node_modules.exists():
        warnings.append("⚠️ node_modules найден - это Node.js директория, не нужна для Python проекта")
        print("  ⚠️ node_modules найден (можно удалить)")
    else:
        print("  ✅ node_modules отсутствует (правильно для Python проекта)")
    
    # Итоговый отчёт
    print("\n" + "="*80)
    if errors:
        print("❌ ОБНАРУЖЕНЫ ОШИБКИ:")
        for error in errors:
            print(f"  {error}")
        print("\n⚠️ Исправьте ошибки перед деплоем на Render!")
        return 1
    elif warnings:
        print("⚠️ ЕСТЬ ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"  {warning}")
        print("\n✅ Критических ошибок нет, но рекомендуется исправить предупреждения")
        return 0
    else:
        print("✅ ВСЁ ПРАВИЛЬНО НАСТРОЕНО!")
        print("✅ Проект готов к деплою на Render как Python приложение!")
        return 0


if __name__ == "__main__":
    sys.exit(check_render_config())


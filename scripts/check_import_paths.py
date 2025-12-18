#!/usr/bin/env python3
"""
Проверка правильности импортов и путей к модулям.
Убеждается, что все импорты корректны и файлы доступны.
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


def check_import_paths():
    """Проверяет правильность импортов."""
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА ИМПОРТОВ И ПУТЕЙ К МОДУЛЯМ")
    print("="*80)
    
    errors = []
    warnings = []
    
    # 1. Проверка наличия kie_gateway.py
    kie_gateway_file = root_dir / "kie_gateway.py"
    if kie_gateway_file.exists():
        print(f"  ✅ Файл найден: {kie_gateway_file}")
        print(f"     Регистр имени: {kie_gateway_file.name}")
    else:
        errors.append(f"❌ Файл не найден: {kie_gateway_file}")
        print(f"  ❌ Файл не найден: {kie_gateway_file}")
        return 1
    
    # 2. Проверка регистра в имени файла
    if kie_gateway_file.name == "kie_gateway.py":
        print("  ✅ Регистр имени файла правильный: kie_gateway.py")
    else:
        errors.append(f"❌ Неправильный регистр в имени файла: {kie_gateway_file.name}")
        print(f"  ❌ Неправильный регистр в имени файла: {kie_gateway_file.name}")
        print(f"     Ожидается: kie_gateway.py")
    
    # 3. Проверка импорта в bot_kie.py
    bot_kie_file = root_dir / "bot_kie.py"
    if bot_kie_file.exists():
        with open(bot_kie_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            
            # Ищем импорт kie_gateway
            import_found = False
            for i, line in enumerate(lines, 1):
                if 'from kie_gateway import' in line or 'import kie_gateway' in line:
                    import_found = True
                    print(f"  ✅ Импорт найден на строке {i}: {line.strip()}")
                    
                    # Проверяем регистр в импорте
                    if 'kie_gateway' in line and 'KIE_GATEWAY' not in line and 'Kie_Gateway' not in line:
                        print("  ✅ Регистр в импорте правильный: kie_gateway")
                    else:
                        errors.append(f"❌ Неправильный регистр в импорте на строке {i}")
                        print(f"  ❌ Неправильный регистр в импорте на строке {i}")
                    
                    # Проверяем путь импорта
                    if 'from kie_gateway' in line or 'from .kie_gateway' in line:
                        if 'from src.' in line or 'from modules.' in line:
                            warnings.append(f"⚠️ Импорт из подкаталога на строке {i}: {line.strip()}")
                            print(f"  ⚠️ Импорт из подкаталога: {line.strip()}")
                        else:
                            print("  ✅ Путь импорта правильный (из корня)")
                    break
            
            if not import_found:
                errors.append("❌ Импорт kie_gateway не найден в bot_kie.py")
                print("  ❌ Импорт kie_gateway не найден в bot_kie.py")
    else:
        errors.append("❌ bot_kie.py не найден")
        print("  ❌ bot_kie.py не найден")
        return 1
    
    # 4. Проверка структуры каталогов
    print("\n  📁 Структура каталогов:")
    print(f"     Корень проекта: {root_dir}")
    print(f"     kie_gateway.py: {kie_gateway_file.relative_to(root_dir)}")
    print(f"     bot_kie.py: {bot_kie_file.relative_to(root_dir)}")
    
    # Проверяем, нет ли подкаталогов с модулями
    src_dir = root_dir / "src"
    modules_dir = root_dir / "modules"
    
    if src_dir.exists():
        warnings.append("⚠️ Найден каталог src/ - убедитесь, что файлы не там")
        print(f"  ⚠️ Найден каталог src/")
    
    if modules_dir.exists():
        warnings.append("⚠️ Найден каталог modules/ - убедитесь, что файлы не там")
        print(f"  ⚠️ Найден каталог modules/")
    
    # 5. Попытка импорта
    print("\n  🧪 Тест импорта:")
    try:
        import kie_gateway
        print("  ✅ Импорт kie_gateway успешен")
        
        if hasattr(kie_gateway, 'get_kie_gateway'):
            print("  ✅ Функция get_kie_gateway найдена")
        else:
            errors.append("❌ Функция get_kie_gateway не найдена в модуле")
            print("  ❌ Функция get_kie_gateway не найдена в модуле")
        
        if hasattr(kie_gateway, 'MockKieGateway'):
            print("  ✅ Класс MockKieGateway найден")
        else:
            warnings.append("⚠️ Класс MockKieGateway не найден")
            print("  ⚠️ Класс MockKieGateway не найден")
        
        if hasattr(kie_gateway, 'RealKieGateway'):
            print("  ✅ Класс RealKieGateway найден")
        else:
            warnings.append("⚠️ Класс RealKieGateway не найден")
            print("  ⚠️ Класс RealKieGateway не найден")
            
    except ImportError as e:
        errors.append(f"❌ Ошибка импорта: {e}")
        print(f"  ❌ Ошибка импорта: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        errors.append(f"❌ Неожиданная ошибка: {e}")
        print(f"  ❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 6. Проверка __init__.py (если есть подкаталоги)
    init_files = list(root_dir.glob("**/__init__.py"))
    if init_files:
        print(f"\n  📄 Найдено __init__.py файлов: {len(init_files)}")
        for init_file in init_files:
            print(f"     {init_file.relative_to(root_dir)}")
    
    # Итоговый отчёт
    print("\n" + "="*80)
    if errors:
        print("❌ ОБНАРУЖЕНЫ ОШИБКИ:")
        for error in errors:
            print(f"  {error}")
        print("\n⚠️ Исправьте ошибки перед деплоем!")
        return 1
    elif warnings:
        print("⚠️ ЕСТЬ ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"  {warning}")
        print("\n✅ Критических ошибок нет, но рекомендуется проверить предупреждения")
        return 0
    else:
        print("✅ ВСЁ ПРАВИЛЬНО НАСТРОЕНО!")
        print("✅ Импорты корректны, файлы на месте!")
        return 0


if __name__ == "__main__":
    sys.exit(check_import_paths())


#!/usr/bin/env python3
"""
Проверка импорта модуля kie_gateway.
Убеждается, что все необходимые функции и классы доступны.
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


def check_kie_gateway_import():
    """Проверяет импорт kie_gateway."""
    print("\n" + "="*80)
    print("🔍 ПРОВЕРКА ИМПОРТА KIE_GATEWAY")
    print("="*80)
    
    errors = []
    warnings = []
    
    # 1. Проверка наличия файла
    kie_gateway_file = root_dir / "kie_gateway.py"
    if kie_gateway_file.exists():
        print(f"  ✅ Файл найден: {kie_gateway_file}")
    else:
        errors.append(f"❌ Файл не найден: {kie_gateway_file}")
        print(f"  ❌ Файл не найден: {kie_gateway_file}")
        return 1
    
    # 2. Проверка импорта get_kie_gateway
    try:
        from kie_gateway import get_kie_gateway
        print("  ✅ Импорт get_kie_gateway успешен")
    except ImportError as e:
        errors.append(f"❌ Не удалось импортировать get_kie_gateway: {e}")
        print(f"  ❌ Не удалось импортировать get_kie_gateway: {e}")
        return 1
    except Exception as e:
        errors.append(f"❌ Ошибка при импорте get_kie_gateway: {e}")
        print(f"  ❌ Ошибка при импорте get_kie_gateway: {e}")
        return 1
    
    # 3. Проверка импорта MockKieGateway
    try:
        from kie_gateway import MockKieGateway
        print("  ✅ Импорт MockKieGateway успешен")
    except ImportError as e:
        errors.append(f"❌ Не удалось импортировать MockKieGateway: {e}")
        print(f"  ❌ Не удалось импортировать MockKieGateway: {e}")
        return 1
    except Exception as e:
        errors.append(f"❌ Ошибка при импорте MockKieGateway: {e}")
        print(f"  ❌ Ошибка при импорте MockKieGateway: {e}")
        return 1
    
    # 4. Проверка импорта RealKieGateway
    try:
        from kie_gateway import RealKieGateway
        print("  ✅ Импорт RealKieGateway успешен")
    except ImportError as e:
        errors.append(f"❌ Не удалось импортировать RealKieGateway: {e}")
        print(f"  ❌ Не удалось импортировать RealKieGateway: {e}")
        return 1
    except Exception as e:
        errors.append(f"❌ Ошибка при импорте RealKieGateway: {e}")
        print(f"  ❌ Ошибка при импорте RealKieGateway: {e}")
        return 1
    
    # 5. Проверка импорта KieGateway (абстрактный класс)
    try:
        from kie_gateway import KieGateway
        print("  ✅ Импорт KieGateway (абстрактный класс) успешен")
    except ImportError:
        warnings.append("⚠️ KieGateway (абстрактный класс) не экспортирован (не критично)")
        print("  ⚠️ KieGateway (абстрактный класс) не экспортирован (не критично)")
    except Exception as e:
        warnings.append(f"⚠️ Ошибка при импорте KieGateway: {e}")
        print(f"  ⚠️ Ошибка при импорте KieGateway: {e}")
    
    # 6. Проверка функции get_kie_gateway
    try:
        gateway = get_kie_gateway()
        print(f"  ✅ get_kie_gateway() возвращает объект: {type(gateway).__name__}")
        
        # Проверка типа
        if isinstance(gateway, MockKieGateway):
            print("  ✅ Gateway является MockKieGateway")
        elif isinstance(gateway, RealKieGateway):
            print("  ✅ Gateway является RealKieGateway")
        else:
            warnings.append(f"⚠️ Gateway имеет неожиданный тип: {type(gateway).__name__}")
            print(f"  ⚠️ Gateway имеет неожиданный тип: {type(gateway).__name__}")
    except Exception as e:
        errors.append(f"❌ Ошибка при вызове get_kie_gateway(): {e}")
        print(f"  ❌ Ошибка при вызове get_kie_gateway(): {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 7. Проверка методов gateway
    try:
        gateway = get_kie_gateway()
        
        # Проверка наличия методов
        required_methods = ['create_task', 'get_task', 'list_models', 'healthcheck']
        for method_name in required_methods:
            if hasattr(gateway, method_name):
                print(f"  ✅ Метод {method_name} присутствует")
            else:
                errors.append(f"❌ Метод {method_name} отсутствует")
                print(f"  ❌ Метод {method_name} отсутствует")
                return 1
    except Exception as e:
        errors.append(f"❌ Ошибка при проверке методов gateway: {e}")
        print(f"  ❌ Ошибка при проверке методов gateway: {e}")
        return 1
    
    # 8. Проверка импорта в bot_kie.py
    bot_kie_file = root_dir / "bot_kie.py"
    if bot_kie_file.exists():
        with open(bot_kie_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            if 'from kie_gateway import get_kie_gateway' in content:
                print("  ✅ bot_kie.py содержит импорт get_kie_gateway")
            else:
                errors.append("❌ bot_kie.py не содержит импорт get_kie_gateway")
                print("  ❌ bot_kie.py не содержит импорт get_kie_gateway")
                return 1
            
            if 'MockKieGateway' in content or 'RealKieGateway' in content:
                print("  ✅ bot_kie.py использует MockKieGateway или RealKieGateway")
            else:
                warnings.append("⚠️ bot_kie.py не использует MockKieGateway или RealKieGateway напрямую")
                print("  ⚠️ bot_kie.py не использует MockKieGateway или RealKieGateway напрямую")
    else:
        warnings.append("⚠️ bot_kie.py не найден")
        print("  ⚠️ bot_kie.py не найден")
    
    # Итоговый отчёт
    print("\n" + "="*80)
    if errors:
        print("❌ ОБНАРУЖЕНЫ ОШИБКИ:")
        for error in errors:
            print(f"  {error}")
        print("\n⚠️ Исправьте ошибки перед использованием!")
        return 1
    elif warnings:
        print("⚠️ ЕСТЬ ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"  {warning}")
        print("\n✅ Критических ошибок нет, но рекомендуется исправить предупреждения")
        return 0
    else:
        print("✅ ВСЁ ПРАВИЛЬНО НАСТРОЕНО!")
        print("✅ Модуль kie_gateway готов к использованию!")
        return 0


if __name__ == "__main__":
    sys.exit(check_kie_gateway_import())


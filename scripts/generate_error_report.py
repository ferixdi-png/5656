#!/usr/bin/env python3
"""
Генерация отчёта об ошибках с Kie.ai и поставщиками.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def main():
    """Основная функция."""
    try:
        from error_handler_providers import get_error_handler
        
        handler = get_error_handler()
        report = handler.get_error_report(limit=1000)
        
        # Сохраняем отчёт
        report_file = root_dir / "data" / "error_report.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print("📊 ОТЧЁТ ОБ ОШИБКАХ")
        print("="*80)
        print(f"Всего ошибок: {report['total_errors']}")
        print(f"Недавних ошибок: {report['recent_errors_count']}")
        print(f"\nПо источникам:")
        for source, count in report['errors_by_source'].items():
            print(f"  {source}: {count}")
        print(f"\nПо типам:")
        for error_type, count in report['errors_by_type'].items():
            print(f"  {error_type}: {count}")
        print(f"\nОтчёт сохранён: {report_file}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


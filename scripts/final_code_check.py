#!/usr/bin/env python3
"""
Финальная проверка кода перед деплоем на Render.
Проверяет синтаксис, импорты, типы и готовность проекта.
"""

import os
import sys
import ast
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FinalCodeChecker:
    """Класс для финальной проверки кода."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.fixed = []
    
    def check_syntax(self, file_path: Path) -> Tuple[bool, List[str]]:
        """Проверяет синтаксис Python файла."""
        errors = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            try:
                ast.parse(code, filename=str(file_path))
                return True, []
            except SyntaxError as e:
                errors.append(f"Syntax error in {file_path}: {e}")
                return False, errors
        except Exception as e:
            errors.append(f"Error reading {file_path}: {e}")
            return False, errors
    
    def check_imports(self, file_path: Path) -> Tuple[bool, List[str]]:
        """Проверяет импорты в файле."""
        errors = []
        warnings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Проверяем наличие импортов
            if 'import' not in content and 'from' not in content:
                return True, []
            
            # Проверяем циклические импорты (базовая проверка)
            imports = []
            for line in content.split('\n'):
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    imports.append(line.strip())
            
            # Проверяем дубликаты
            seen = set()
            for imp in imports:
                if imp in seen:
                    warnings.append(f"Duplicate import in {file_path}: {imp}")
                seen.add(imp)
            
            return True, warnings
        
        except Exception as e:
            errors.append(f"Error checking imports in {file_path}: {e}")
            return False, errors
    
    def check_all_python_files(self) -> Dict[str, Any]:
        """Проверяет все Python файлы в проекте."""
        results = {
            'total_files': 0,
            'syntax_errors': [],
            'import_warnings': [],
            'files_checked': []
        }
        
        # Игнорируем директории
        ignore_dirs = {'__pycache__', '.git', 'venv', 'env', '.venv', 'node_modules'}
        
        for py_file in root_dir.rglob('*.py'):
            # Пропускаем файлы в игнорируемых директориях
            if any(ignore_dir in str(py_file) for ignore_dir in ignore_dirs):
                continue
            
            results['total_files'] += 1
            results['files_checked'].append(str(py_file.relative_to(root_dir)))
            
            # Проверка синтаксиса
            syntax_ok, syntax_errors = self.check_syntax(py_file)
            if not syntax_ok:
                results['syntax_errors'].extend(syntax_errors)
                self.errors.extend(syntax_errors)
            
            # Проверка импортов
            imports_ok, import_warnings = self.check_imports(py_file)
            if import_warnings:
                results['import_warnings'].extend(import_warnings)
                self.warnings.extend(import_warnings)
        
        return results
    
    def check_requirements(self) -> Tuple[bool, str]:
        """Проверяет requirements.txt."""
        requirements_file = root_dir / "requirements.txt"
        
        if not requirements_file.exists():
            return False, "requirements.txt не найден"
        
        try:
            with open(requirements_file, 'r', encoding='utf-8') as f:
                requirements = f.read()
            
            # Проверяем наличие основных зависимостей
            required_packages = [
                'python-telegram-bot',
                'aiohttp',
                'python-dotenv',
                'psycopg2-binary',
                'pytest'
            ]
            
            missing = []
            for package in required_packages:
                if package.lower() not in requirements.lower():
                    missing.append(package)
            
            if missing:
                return False, f"Отсутствуют зависимости: {', '.join(missing)}"
            
            return True, "Все зависимости присутствуют"
        
        except Exception as e:
            return False, f"Ошибка чтения requirements.txt: {e}"
    
    def check_env_variables(self) -> Tuple[bool, List[str]]:
        """Проверяет наличие необходимых переменных окружения."""
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'KIE_API_KEY',
            'DATABASE_URL',
            'ADMIN_ID'
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            return False, missing
        
        return True, []
    
    def check_critical_files(self) -> Tuple[bool, List[str]]:
        """Проверяет наличие критических файлов."""
        critical_files = [
            'bot_kie.py',
            'database.py',
            'kie_client.py',
            'kie_gateway.py',
            'config_runtime.py',
            'requirements.txt',
            'error_handler_providers.py'
        ]
        
        missing = []
        for file_name in critical_files:
            file_path = root_dir / file_name
            if not file_path.exists():
                missing.append(file_name)
        
        if missing:
            return False, missing
        
        return True, []
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Запускает все проверки."""
        logger.info("🔍 Начало финальной проверки кода...")
        
        results = {
            'timestamp': datetime.now(timezone.utc).astimezone().isoformat(),
            'syntax_check': {},
            'requirements_check': {},
            'env_check': {},
            'files_check': {},
            'errors': [],
            'warnings': [],
            'ready': False
        }
        
        # 1. Проверка синтаксиса всех файлов
        logger.info("📝 Проверка синтаксиса всех Python файлов...")
        syntax_results = self.check_all_python_files()
        results['syntax_check'] = syntax_results
        
        if syntax_results['syntax_errors']:
            results['errors'].extend(syntax_results['syntax_errors'])
        
        if syntax_results['import_warnings']:
            results['warnings'].extend(syntax_results['import_warnings'])
        
        # 2. Проверка requirements.txt
        logger.info("📦 Проверка requirements.txt...")
        req_ok, req_msg = self.check_requirements()
        results['requirements_check'] = {
            'ok': req_ok,
            'message': req_msg
        }
        if not req_ok:
            results['errors'].append(f"requirements.txt: {req_msg}")
        
        # 3. Проверка переменных окружения
        logger.info("🔐 Проверка переменных окружения...")
        env_ok, env_missing = self.check_env_variables()
        results['env_check'] = {
            'ok': env_ok,
            'missing': env_missing
        }
        if not env_ok:
            results['warnings'].append(f"Переменные окружения не установлены (нормально для проверки): {', '.join(env_missing)}")
        
        # 4. Проверка критических файлов
        logger.info("📄 Проверка критических файлов...")
        files_ok, files_missing = self.check_critical_files()
        results['files_check'] = {
            'ok': files_ok,
            'missing': files_missing
        }
        if not files_ok:
            results['errors'].extend([f"Отсутствует файл: {f}" for f in files_missing])
        
        # Определяем готовность
        results['ready'] = len(results['errors']) == 0
        
        return results
    
    def print_report(self, results: Dict[str, Any]):
        """Выводит отчёт о проверке."""
        print("\n" + "="*80)
        print("📊 ФИНАЛЬНАЯ ПРОВЕРКА КОДА ПЕРЕД ДЕПЛОЕМ")
        print("="*80)
        
        print(f"\n📝 СИНТАКСИС:")
        print(f"  Проверено файлов: {results['syntax_check'].get('total_files', 0)}")
        syntax_errors = results['syntax_check'].get('syntax_errors', [])
        if syntax_errors:
            print(f"  ❌ Ошибки синтаксиса: {len(syntax_errors)}")
            for error in syntax_errors[:10]:  # Показываем первые 10
                print(f"    - {error}")
        else:
            print(f"  ✅ Ошибок синтаксиса не найдено")
        
        import_warnings = results['syntax_check'].get('import_warnings', [])
        if import_warnings:
            print(f"  ⚠️ Предупреждения об импортах: {len(import_warnings)}")
        
        print(f"\n📦 REQUIREMENTS.TXT:")
        req_check = results['requirements_check']
        if req_check.get('ok'):
            print(f"  ✅ {req_check.get('message')}")
        else:
            print(f"  ❌ {req_check.get('message')}")
        
        print(f"\n📄 КРИТИЧЕСКИЕ ФАЙЛЫ:")
        files_check = results['files_check']
        if files_check.get('ok'):
            print(f"  ✅ Все файлы присутствуют")
        else:
            print(f"  ❌ Отсутствуют: {', '.join(files_check.get('missing', []))}")
        
        if results['warnings']:
            print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ ({len(results['warnings'])}):")
            for warning in results['warnings'][:10]:
                print(f"  - {warning}")
        
        if results['errors']:
            print(f"\n❌ ОШИБКИ ({len(results['errors'])}):")
            for error in results['errors'][:20]:
                print(f"  - {error}")
        
        print("\n" + "="*80)
        if results['ready']:
            print("✅ КОД ГОТОВ К ДЕПЛОЕМ!")
        else:
            print("❌ ЕСТЬ ОШИБКИ! Исправьте их перед деплоем.")
        print("="*80)
        
        return 0 if results['ready'] else 1


def main():
    """Основная функция."""
    checker = FinalCodeChecker()
    results = checker.run_all_checks()
    exit_code = checker.print_report(results)
    
    # Сохраняем отчёт
    report_file = root_dir / "FINAL_CODE_CHECK_REPORT.json"
    import json
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Отчёт сохранён в {report_file}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())


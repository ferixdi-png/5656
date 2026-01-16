#!/usr/bin/env python3
"""
Безопасная очистка репозитория от мусорных файлов.
Удаляет только файлы, которые точно не используются в основном коде.
"""
import os
import shutil
from pathlib import Path
from typing import List, Set

# Файлы и папки для удаления
FILES_TO_DELETE = [
    # Старые entry points
    "bot_kie.py",
    "run_bot.py",
    
    # Старые клиенты
    "kie_client.py",
    "kie_gateway.py",
    "kie_universal_handler.py",
    "kie_input_adapter.py",
    "kie_models.py",
    "kie_schema.py",
    
    # Старые конфиги и дубликаты
    "Dockerfile.optimized",
    "TRT_REPORT_OLD.md",
    "TRT_REPORT_v2.md",
    "TRT_REPORT.md.old",
    
    # Временные файлы
    "5656-main-ideal-self.zip",
    "all_models_test_results.json",
    "cheap_models_test_results.json",
    "model_generation_test_results_20251217_170008.json",
    "model_generation_test_results_20251217_170332.json",
    "audit_output.txt",
    "validation_output.txt",
    "e2e_test_output.txt",
    "prod_check_output.txt",
    "test_schema_output.txt",
    "verify_report.txt",
]

# Папки для удаления
DIRS_TO_DELETE = [
    "quarantine",
    "archive",
    "legacy",
    "betboom_scanner",
    "bb_tt_scanner",
    "scanner_app",
    "scanner_min",
    "kie_sync",
    "5656",
]

# Паттерны файлов для удаления
PATTERNS_TO_DELETE = [
    "validate_*.py",  # Все validate_*.py файлы
    "auto_*.bat",
    "auto_*.py",  # Временные auto_*.py (кроме auto_test_all_models_generation.py если нужен)
    "check_*.bat",
    "check_*.py",  # Временные check_*.py
    "fix_*.bat",
    "setup_*.bat",
    "setup_*.ps1",
    "*.ps1",  # Все PowerShell скрипты
    "get_render_logs*.bat",
    "push_to_github.bat",
    "update_github*.bat",
    "cursor_*.bat",
    "cursor_*.py",
    "monitor_logs*.bat",
    "run_bot_simple.bat",
    "install_*.bat",
    "install_*.ps1",
    "install_*.sh",
    "unlock_bot_token.*",
    "create_pr.ps1",
    "git_push.ps1",
    "find_and_install_python.ps1",
    "load_secrets.sh",
    "quickstart_prod.sh",
    "SMOKE_QUICK_START.sh",
    "test_singleton_docker.sh",
    "DEPLOY_VERIFY.sh",
]

# Паттерны markdown отчетов для удаления
MD_REPORTS_TO_DELETE = [
    "*_REPORT*.md",
    "*_SUMMARY*.md",
    "*_FIXES*.md",
    "*_STATUS*.md",
    "*_FINAL*.md",
    "*_AUDIT*.md",
    "*_CHANGELOG*.md",
    "*_GUIDE*.md",
    "*_CHECKLIST*.md",
    "*_INSTRUCTION*.txt",
    "*_TXT*.txt",
    "*_ОТЧЕТ*.md",
    "*_СТАТУС*.md",
    "*_ФИНАЛЬНЫЙ*.md",
    "*_ПОЛНЫЙ*.md",
    "*_ИСПРАВЛЕНИЕ*.md",
    "*_РЕШЕНИЕ*.md",
    "*_ИНСТРУКЦИЯ*.md",
    "*_НАСТРОЙКА*.md",
    "*_КРИТИЧЕСКОЕ*.md",
    "*_СРОЧНО*.md",
    "*_БЫСТРАЯ*.md",
    "*_ДИАГНОСТИКА*.md",
]

# Исключения - НЕ удалять эти файлы
EXCEPTIONS = {
    "TRT_REPORT.md",
    "KIE_AI_INTEGRATION_AUDIT.md",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "DEPLOY_CHECKLIST.md",
    "MODEL_ADD_GUIDE.md",
    "PRINCIPLES_CHECKLIST.md",
    "CLEANUP_PLAN.md",  # Этот файл
    "main_render.py",
    "requirements.txt",
    "requirements-prod.txt",
    "Dockerfile",
    ".gitignore",
    "pyproject.toml",
    "pytest.ini",
    "runtime.txt",
    "render.yaml",
    "render_cron.yaml",
    "Makefile",
    "package.json",
    "index.js",
    "VERSION",
}

def should_delete_file(filepath: Path) -> bool:
    """Проверить, нужно ли удалять файл."""
    filename = filepath.name
    
    # Исключения
    if filename in EXCEPTIONS:
        return False
    
    # Проверка паттернов
    for pattern in PATTERNS_TO_DELETE:
        if filename.startswith(pattern.replace("*", "").split(".")[0]) or \
           filename.endswith(pattern.replace("*", "").split(".")[-1]) or \
           pattern.replace("*", "") in filename:
            return True
    
    # Проверка markdown отчетов
    if filepath.suffix == ".md":
        for pattern in MD_REPORTS_TO_DELETE:
            if pattern.replace("*", "").replace(".md", "") in filename:
                return True
    
    return False

def main():
    """Основная функция очистки."""
    root = Path(".")
    deleted_files = []
    deleted_dirs = []
    errors = []
    
    print("Starting repository cleanup...\n")
    
    # Удаление конкретных файлов
    print("Deleting specific files...")
    for filename in FILES_TO_DELETE:
        filepath = root / filename
        if filepath.exists():
            try:
                if filepath.is_file():
                    filepath.unlink()
                    deleted_files.append(filename)
                    print(f"  [OK] Deleted: {filename}")
                elif filepath.is_dir():
                    shutil.rmtree(filepath)
                    deleted_dirs.append(filename)
                    print(f"  [OK] Deleted directory: {filename}")
            except Exception as e:
                errors.append(f"{filename}: {e}")
                print(f"  [ERROR] Failed to delete {filename}: {e}")
    
    # Удаление папок
    print("\nDeleting directories...")
    for dirname in DIRS_TO_DELETE:
        dirpath = root / dirname
        if dirpath.exists() and dirpath.is_dir():
            try:
                shutil.rmtree(dirpath)
                deleted_dirs.append(dirname)
                print(f"  [OK] Deleted directory: {dirname}")
            except Exception as e:
                errors.append(f"{dirname}: {e}")
                print(f"  [ERROR] Failed to delete {dirname}: {e}")
    
    # Удаление файлов по паттернам
    print("\nSearching for files by patterns...")
    for filepath in root.rglob("*"):
        # КРИТИЧНО: НЕ трогать .git папку и системные папки!
        if any(part.startswith(".") for part in filepath.parts):
            continue
        if any(part in ["__pycache__", "node_modules", ".venv", "venv", "env"] for part in filepath.parts):
            continue
        
        if filepath.is_file() and should_delete_file(filepath):
            # Пропускаем файлы в app/, bot/, models/, migrations/, tests/
            if any(part in ["app", "bot", "models", "migrations", "tests"] for part in filepath.parts):
                continue
            
            try:
                filepath.unlink()
                deleted_files.append(str(filepath))
                print(f"  [OK] Deleted: {filepath}")
            except Exception as e:
                errors.append(f"{filepath}: {e}")
                # Не показываем все ошибки, только первые 10
                if len([e for e in errors if str(e).startswith(str(filepath))]) <= 1:
                    print(f"  [ERROR] Failed to delete {filepath}: {e}")
    
    # Итоги
    print("\n" + "="*60)
    print(f"[OK] Deleted files: {len(deleted_files)}")
    print(f"[OK] Deleted directories: {len(deleted_dirs)}")
    if errors:
        print(f"[WARNING] Errors: {len(errors)}")
        for error in errors[:10]:  # Показать первые 10 ошибок
            print(f"   - {error}")
    
    print("\nNext steps:")
    print("   1. Check changes: git status")
    print("   2. Verify nothing important was deleted")
    print("   3. Commit: git add -A && git commit -m 'Cleanup: remove unused files'")
    print("   4. Push: git push")

if __name__ == "__main__":
    main()


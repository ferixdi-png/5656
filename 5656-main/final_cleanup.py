#!/usr/bin/env python3
"""
Финальная безопасная очистка - удаляет только файлы, которые точно не нужны.
Проверяет существование перед удалением.
"""
from pathlib import Path
import glob

root = Path(".")

# Файлы для удаления (проверяем существование)
files_to_delete = [
    "bot_kie.py",
    "run_bot.py",
    "kie_client.py",
    "kie_gateway.py",
    "kie_universal_handler.py",
    "kie_input_adapter.py",
    "kie_models.py",
    "kie_schema.py",
    "business_layer.py",
    "database.py",
    "helpers.py",
    "config.py",
    "5656-main-ideal-self.zip",
    "TRT_REPORT_OLD.md",
    "TRT_REPORT_v2.md",
    "TRT_REPORT.md.old",
]

# Паттерны для удаления
patterns = [
    "validate_*.py",
    "check_*.py",
    "auto_*.py",
    "auto_*.bat",
    "check_*.bat",
    "fix_*.bat",
    "setup_*.bat",
    "*.ps1",
    "*.sh",
    "*_REPORT*.md",
    "*_SUMMARY*.md",
    "*_FIXES*.md",
    "*_STATUS*.md",
    "*_FINAL*.md",
    "*_AUDIT*.md",
    "*test_results*.json",
    "*_output.txt",
]

# Исключения
EXCEPTIONS = {
    "TRT_REPORT.md",
    "KIE_AI_INTEGRATION_AUDIT.md",
    "README.md",
    "CHANGELOG.md",
    "main_render.py",
    "requirements.txt",
    "requirements-prod.txt",
    "Dockerfile",
    ".gitignore",
    "pyproject.toml",
    "pytest.ini",
    "safe_cleanup.py",
    "final_cleanup.py",
    "CLEANUP_PLAN.md",
}

deleted = []
errors = []

print("Final safe cleanup...\n")

# Удаление конкретных файлов
for filename in files_to_delete:
    filepath = root / filename
    if filepath.exists() and filepath.is_file():
        try:
            filepath.unlink()
            deleted.append(filename)
            print(f"  [OK] {filename}")
        except Exception as e:
            errors.append(f"{filename}: {e}")

# Удаление по паттернам
for pattern in patterns:
    matches = list(root.glob(pattern))
    for match in matches:
        # Пропускаем исключения
        if match.name in EXCEPTIONS:
            continue
        # Пропускаем файлы в app/, bot/, models/, migrations/, tests/
        if any(part in ["app", "bot", "models", "migrations", "tests"] for part in match.parts):
            continue
        # Пропускаем .git
        if ".git" in match.parts:
            continue
        
        if match.is_file() and match.exists():
            try:
                match.unlink()
                deleted.append(str(match))
                print(f"  [OK] {match.name}")
            except Exception as e:
                errors.append(f"{match}: {e}")

# Удаление папок
dirs_to_delete = ["quarantine", "archive", "legacy", "betboom_scanner", "bb_tt_scanner", "scanner_app", "scanner_min", "kie_sync", "5656"]
for dirname in dirs_to_delete:
    dirpath = root / dirname
    if dirpath.exists() and dirpath.is_dir():
        try:
            import shutil
            shutil.rmtree(dirpath)
            deleted.append(f"DIR: {dirname}")
            print(f"  [OK] {dirname}/")
        except Exception as e:
            errors.append(f"{dirname}: {e}")

print(f"\nDeleted: {len(deleted)} items")
if errors:
    print(f"Errors: {len(errors)}")


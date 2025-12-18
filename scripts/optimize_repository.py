#!/usr/bin/env python3
"""
Оптимизация репозитория для деплоя.
Удаляет лишние файлы, оставляет только необходимое.
"""

import os
import sys
from pathlib import Path
import shutil

root_dir = Path(__file__).parent.parent

# Файлы, которые ОБЯЗАТЕЛЬНО нужно сохранить
CRITICAL_FILES = {
    # Основные файлы бота
    'bot_kie.py',
    'kie_gateway.py',
    'kie_client.py',
    'kie_models.py',
    'config_runtime.py',
    'knowledge_storage.py',
    'translations.py',
    'helpers.py',
    'error_handler_providers.py',
    
    # Конфигурация
    'requirements.txt',
    'Dockerfile',
    'render.yaml',
    '.gitignore',
    
    # Важная документация
    'README.md',
    'README_DEPLOY_RENDER.md',
    'DEPLOY_CHECKLIST.md',
    'RENDER_ENV_VARIABLES.md',
    'RENDER_ENV_SETUP.md',
}

# Папки, которые нужно сохранить
CRITICAL_DIRS = {
    'scripts',
    'tests',
    'data',  # Если есть данные
}

# Паттерны файлов для удаления
DELETE_PATTERNS = [
    # Старые отчёты
    '*_ОТЧЕТ*.md',
    '*_REPORT*.md',
    '*_CHECK*.md',
    '*_SUMMARY*.md',
    '*_СТАТУС*.md',
    '*_ФИНАЛЬНЫЙ*.md',
    '*_ПОЛНЫЙ*.md',
    '*_ИСПРАВЛЕНИЕ*.md',
    '*_РЕШЕНИЕ*.md',
    '*_ИНСТРУКЦИЯ*.md',
    '*_НАСТРОЙКА*.md',
    '*_КРИТИЧЕСКОЕ*.md',
    '*_СРОЧНО*.md',
    '*_БЫСТРАЯ*.md',
    '*_ДИАГНОСТИКА*.md',
    '*_WEBHOOK*.md',
    
    # Дубликаты
    '*_new.py',
    '*_old.py',
    '*_backup.py',
    '*_copy.py',
    'enhanced_kie_gateway.py',  # Дубликат kie_gateway.py
    'universal_kie_gateway.py',  # Дубликат kie_gateway.py
    
    # Временные скрипты
    '*.bat',
    '*.sh',
    '*.ps1',
    
    # Node.js (если не нужны)
    'package.json',
    'package-lock.json',
    'index.js',
    'node_modules/',
]


def matches_pattern(name: str, pattern: str) -> bool:
    """Проверяет, соответствует ли имя файла паттерну."""
    if pattern.startswith('*') and pattern.endswith('*'):
        return pattern[1:-1] in name
    elif pattern.startswith('*'):
        return name.endswith(pattern[1:])
    elif pattern.endswith('*'):
        return name.startswith(pattern[:-1])
    else:
        return name == pattern


def should_delete(file_path: Path) -> bool:
    """Проверяет, нужно ли удалить файл."""
    name = file_path.name
    
    # Критические файлы не удаляем
    if name in CRITICAL_FILES:
        return False
    
    # Критические папки не удаляем
    if file_path.is_dir() and name in CRITICAL_DIRS:
        return False
    
    # Файлы в критических папках не удаляем
    if any(part in CRITICAL_DIRS for part in file_path.parts):
        return False
    
    # Проверяем паттерны
    for pattern in DELETE_PATTERNS:
        if matches_pattern(name, pattern):
            return True
    
    return False


def optimize_repository(dry_run=True):
    """Оптимизирует репозиторий."""
    print("\n" + "="*80)
    print("🧹 ОПТИМИЗАЦИЯ РЕПОЗИТОРИЯ")
    print("="*80)
    
    if dry_run:
        print("⚠️  РЕЖИМ ПРОВЕРКИ (dry-run) - файлы НЕ будут удалены")
    else:
        print("🗑️  РЕЖИМ УДАЛЕНИЯ - файлы БУДУТ удалены!")
    
    print()
    
    files_to_delete = []
    total_size = 0
    
    # Сканируем файлы
    for item in root_dir.rglob('*'):
        # Пропускаем .git и скрипты
        if '.git' in item.parts:
            continue
        if item.parent.name == 'scripts' and item.name == 'optimize_repository.py':
            continue
        
        if should_delete(item):
            try:
                size = item.stat().st_size if item.is_file() else 0
                files_to_delete.append((item, size))
                total_size += size
            except:
                pass
    
    # Сортируем
    files_to_delete.sort(key=lambda x: x[1], reverse=True)
    
    print(f"📊 Найдено файлов для удаления: {len(files_to_delete)}")
    print(f"📊 Общий размер: {total_size / 1024 / 1024:.2f} MB")
    print()
    
    if not files_to_delete:
        print("✅ Лишних файлов не найдено!")
        return 0
    
    print("🗑️  Файлы для удаления:")
    print()
    
    for file_path, size in files_to_delete:
        rel_path = file_path.relative_to(root_dir)
        size_str = f"{size / 1024:.1f} KB" if size > 0 else "dir"
        print(f"  ❌ {rel_path} ({size_str})")
    
    print()
    
    if dry_run:
        print("⚠️  Это был dry-run. Для реального удаления запустите:")
        print("   python scripts/optimize_repository.py --delete")
        return 0
    else:
        print("🗑️  Удаление файлов...")
        deleted = 0
        errors = 0
        
        for file_path, _ in files_to_delete:
            try:
                if file_path.is_file():
                    file_path.unlink()
                    deleted += 1
                elif file_path.is_dir():
                    shutil.rmtree(file_path)
                    deleted += 1
            except Exception as e:
                print(f"  ❌ Ошибка при удалении {file_path}: {e}")
                errors += 1
        
        print()
        print(f"✅ Удалено: {deleted} файлов/папок")
        if errors > 0:
            print(f"❌ Ошибок: {errors}")
        
        return 0 if errors == 0 else 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Оптимизация репозитория')
    parser.add_argument('--delete', action='store_true', help='Реально удалить файлы')
    args = parser.parse_args()
    
    sys.exit(optimize_repository(dry_run=not args.delete))


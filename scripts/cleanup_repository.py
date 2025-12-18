#!/usr/bin/env python3
"""
Скрипт для очистки репозитория от лишних файлов.
Удаляет временные файлы, дубликаты, старые отчёты, но сохраняет важные.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

root_dir = Path(__file__).parent.parent

# Файлы и папки, которые НУЖНО СОХРАНИТЬ
KEEP_FILES = {
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
    '.env.example',  # Если есть
    
    # Документация (только важная)
    'README.md',
    'README_DEPLOY_RENDER.md',
    'DEPLOY_CHECKLIST.md',
    
    # Скрипты
    'scripts/',
    
    # Тесты
    'tests/',
    
    # Данные (если нужны)
    'data/',
}

# Паттерны файлов для УДАЛЕНИЯ
DELETE_PATTERNS = [
    # Временные файлы
    '*.tmp',
    '*.temp',
    '*.log',
    '*.cache',
    
    # Старые отчёты (оставляем только последние)
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
    
    # Дубликаты и старые версии
    '*_new.py',
    '*_old.py',
    '*_backup.py',
    '*_copy.py',
    
    # Временные скрипты
    '*.bat',
    '*.sh',
    '*.ps1',
    
    # Node.js файлы (если не нужны)
    'package.json',
    'package-lock.json',
    'index.js',
    'node_modules/',
    
    # Python кэш
    '__pycache__/',
    '*.pyc',
    '*.pyo',
    '*.pyd',
    '.Python',
    
    # IDE
    '.vscode/',
    '.idea/',
    '*.swp',
    '*.swo',
    
    # OS
    '.DS_Store',
    'Thumbs.db',
    'desktop.ini',
]

# Исключения - файлы, которые НЕ удалять даже если попадают под паттерн
KEEP_EXCEPTIONS = [
    'README.md',
    'README_DEPLOY_RENDER.md',
    'DEPLOY_CHECKLIST.md',
    'RENDER_ENV_VARIABLES.md',
    'RENDER_ENV_SETUP.md',
    'requirements.txt',
    'Dockerfile',
    'render.yaml',
    '.gitignore',
    'bot_kie.py',
    'kie_gateway.py',
    'kie_client.py',
    'scripts/',
    'tests/',
]


def should_keep_file(file_path: Path) -> bool:
    """Проверяет, нужно ли сохранить файл."""
    name = file_path.name
    
    # Проверка исключений
    if name in KEEP_EXCEPTIONS:
        return True
    
    # Проверка важных файлов
    if name in KEEP_FILES:
        return True
    
    # Проверка папок
    if file_path.is_dir():
        if name in ['scripts', 'tests', 'data']:
            return True
        return False
    
    # Проверка расширений
    if file_path.suffix in ['.py', '.txt', '.yaml', '.yml', '.json', '.md']:
        # Проверяем, не попадает ли под паттерны удаления
        for pattern in DELETE_PATTERNS:
            if pattern.startswith('*'):
                if name.endswith(pattern[1:]):
                    return False
            elif pattern.endswith('/'):
                if file_path.is_dir() and name == pattern[:-1]:
                    return False
            else:
                if name == pattern:
                    return False
    
    return True


def cleanup_repository(dry_run=True):
    """Очищает репозиторий от лишних файлов."""
    print("\n" + "="*80)
    print("🧹 ОЧИСТКА РЕПОЗИТОРИЯ")
    print("="*80)
    
    if dry_run:
        print("⚠️  РЕЖИМ ПРОВЕРКИ (dry-run) - файлы НЕ будут удалены")
    else:
        print("🗑️  РЕЖИМ УДАЛЕНИЯ - файлы БУДУТ удалены!")
    
    print()
    
    files_to_delete = []
    total_size = 0
    
    # Сканируем все файлы
    for item in root_dir.rglob('*'):
        # Пропускаем .git
        if '.git' in item.parts:
            continue
        
        # Пропускаем скрипты и тесты
        if item.parent.name in ['scripts', 'tests']:
            continue
        
        if not should_keep_file(item):
            size = item.stat().st_size if item.is_file() else 0
            files_to_delete.append((item, size))
            total_size += size
    
    # Сортируем по размеру
    files_to_delete.sort(key=lambda x: x[1], reverse=True)
    
    print(f"📊 Найдено файлов для удаления: {len(files_to_delete)}")
    print(f"📊 Общий размер: {total_size / 1024 / 1024:.2f} MB")
    print()
    
    if not files_to_delete:
        print("✅ Лишних файлов не найдено!")
        return 0
    
    print("🗑️  Файлы для удаления:")
    print()
    
    for file_path, size in files_to_delete[:50]:  # Показываем первые 50
        rel_path = file_path.relative_to(root_dir)
        size_str = f"{size / 1024:.1f} KB" if size > 0 else "dir"
        print(f"  ❌ {rel_path} ({size_str})")
    
    if len(files_to_delete) > 50:
        print(f"  ... и ещё {len(files_to_delete) - 50} файлов")
    
    print()
    
    if dry_run:
        print("⚠️  Это был dry-run. Для реального удаления запустите:")
        print("   python scripts/cleanup_repository.py --delete")
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
                    import shutil
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
    parser = argparse.ArgumentParser(description='Очистка репозитория от лишних файлов')
    parser.add_argument('--delete', action='store_true', help='Реально удалить файлы (по умолчанию dry-run)')
    args = parser.parse_args()
    
    sys.exit(cleanup_repository(dry_run=not args.delete))


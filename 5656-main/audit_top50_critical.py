#!/usr/bin/env python3
"""
Комплексный аудит топ-50 критичных проблем в кодовой базе.
Проверяет: ошибки, race conditions, валидацию, транзакции, безопасность.
"""
import re
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

class CriticalIssue:
    def __init__(self, severity: str, category: str, file: str, line: int, 
                 description: str, code_snippet: str = "", fix_hint: str = ""):
        self.severity = severity  # P0, P1, P2
        self.category = category
        self.file = file
        self.line = line
        self.description = description
        self.code_snippet = code_snippet
        self.fix_hint = fix_hint

issues: List[CriticalIssue] = []

def scan_file(filepath: Path) -> List[CriticalIssue]:
    """Сканирует файл на критические проблемы."""
    file_issues = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Пропускаем тесты и временные файлы
        if 'test' in str(filepath).lower() or 'cleanup' in str(filepath).lower():
            return []
        
        # 1. Широкие except Exception без логирования
        for i, line in enumerate(lines, 1):
            if re.search(r'except\s+Exception\s*:', line) and 'logger' not in lines[max(0, i-3):i+3]:
                if 'pass' in line or any('pass' in lines[j] for j in range(i, min(len(lines), i+5))):
                    file_issues.append(CriticalIssue(
                        "P1", "Error Handling",
                        str(filepath), i,
                        "Silent exception handling without logging",
                        line.strip(),
                        "Add logging with exc_info=True before pass"
                    ))
        
        # 2. Отсутствие проверок на None
        for i, line in enumerate(lines, 1):
            if re.search(r'\.(from_user|message|chat|callback_query)', line):
                # Проверяем, есть ли проверка на None выше
                has_check = False
                for j in range(max(0, i-10), i):
                    if 'if' in lines[j] and ('None' in lines[j] or 'not' in lines[j]):
                        has_check = True
                        break
                if not has_check:
                    file_issues.append(CriticalIssue(
                        "P1", "Null Safety",
                        str(filepath), i,
                        "Missing None check before accessing Telegram object attribute",
                        line.strip(),
                        "Add: if not message.from_user: return"
                    ))
        
        # 3. Отсутствие транзакций в критичных операциях
        for i, line in enumerate(lines, 1):
            if re.search(r'(INSERT|UPDATE|DELETE)\s+INTO', line, re.IGNORECASE):
                # Проверяем, есть ли transaction выше
                has_transaction = False
                for j in range(max(0, i-20), i):
                    if 'transaction' in lines[j].lower() or 'async with' in lines[j]:
                        has_transaction = True
                        break
                if not has_transaction and 'app/database' in str(filepath):
                    file_issues.append(CriticalIssue(
                        "P0", "Database",
                        str(filepath), i,
                        "Database operation without transaction",
                        line.strip(),
                        "Wrap in async with conn.transaction():"
                    ))
        
        # 4. Отсутствие FOR UPDATE в критичных SELECT
        for i, line in enumerate(lines, 1):
            if re.search(r'SELECT.*FROM\s+(wallets|ledger|jobs)', line, re.IGNORECASE):
                if 'FOR UPDATE' not in line and 'balance' in line.lower():
                    # Проверяем контекст - если это перед UPDATE, нужен FOR UPDATE
                    for j in range(i, min(len(lines), i+10)):
                        if 'UPDATE' in lines[j] and 'wallets' in lines[j]:
                            file_issues.append(CriticalIssue(
                                "P0", "Race Condition",
                                str(filepath), i,
                                "SELECT before UPDATE without FOR UPDATE lock",
                                line.strip(),
                                "Add FOR UPDATE to SELECT statement"
                            ))
                            break
        
        # 5. Отсутствие ON CONFLICT в INSERT
        for i, line in enumerate(lines, 1):
            if re.search(r'INSERT\s+INTO\s+(ledger|jobs)', line, re.IGNORECASE):
                if 'ON CONFLICT' not in line:
                    # Проверяем следующие строки
                    next_lines = ''.join(lines[i-1:min(len(lines), i+3)])
                    if 'ON CONFLICT' not in next_lines:
                        file_issues.append(CriticalIssue(
                            "P1", "Idempotency",
                            str(filepath), i,
                            "INSERT without ON CONFLICT for idempotency",
                            line.strip(),
                            "Add ON CONFLICT (ref) DO NOTHING"
                        ))
        
        # 6. Отсутствие валидации входных данных
        for i, line in enumerate(lines, 1):
            if re.search(r'async def (topup|hold|charge|refund|release|get_balance)', line):
                # Проверяем, есть ли валидация user_id и amount
                func_body = ''.join(lines[i:min(len(lines), i+50)])
                if 'user_id' in func_body:
                    if not re.search(r'if.*user_id.*<=.*0|if.*not.*isinstance.*user_id', func_body):
                        file_issues.append(CriticalIssue(
                            "P1", "Input Validation",
                            str(filepath), i,
                            "Missing validation for user_id parameter",
                            line.strip(),
                            "Add: if not isinstance(user_id, int) or user_id <= 0: raise ValueError"
                        ))
        
        # 7. Отсутствие проверки на отрицательный баланс
        for i, line in enumerate(lines, 1):
            if 'balance' in line.lower() and ('UPDATE' in line or 'SET' in line):
                # Проверяем, есть ли проверка на отрицательный баланс
                func_body = ''.join(lines[max(0, i-30):min(len(lines), i+10)])
                if 'balance' in func_body and 'if.*balance.*<.*0' not in func_body:
                    if 'charge' in func_body or 'subtract' in func_body:
                        file_issues.append(CriticalIssue(
                            "P0", "Balance Safety",
                            str(filepath), i,
                            "Missing check for negative balance after operation",
                            line.strip(),
                            "Add: if balance_after < 0: raise ValueError"
                        ))
        
        # 8. Отсутствие обработки ошибок API
        for i, line in enumerate(lines, 1):
            if 'await.*kie.*api' in line.lower() or 'await.*telegram' in line.lower():
                # Проверяем, есть ли обработка ошибок
                has_try = False
                for j in range(max(0, i-5), i):
                    if 'try:' in lines[j]:
                        has_try = True
                        break
                if not has_try:
                    file_issues.append(CriticalIssue(
                        "P1", "API Error Handling",
                        str(filepath), i,
                        "API call without error handling",
                        line.strip(),
                        "Wrap in try-except with specific exception types"
                    ))
        
        # 9. Использование file_id вместо URL
        for i, line in enumerate(lines, 1):
            if 'image_url' in line or 'video_url' in line:
                if 'file_id' in line and 'convert' not in line.lower():
                    file_issues.append(CriticalIssue(
                        "P1", "KIE API",
                        str(filepath), i,
                        "Potential file_id sent as URL to KIE API",
                        line.strip(),
                        "Convert file_id to URL using bot.get_file()"
                    ))
        
        # 10. Отсутствие таймаутов
        for i, line in enumerate(lines, 1):
            if 'aiohttp' in line or 'requests' in line or 'httpx' in line:
                if 'timeout' not in line and 'timeout' not in ''.join(lines[max(0, i-3):i+3]):
                    file_issues.append(CriticalIssue(
                        "P2", "Performance",
                        str(filepath), i,
                        "HTTP request without timeout",
                        line.strip(),
                        "Add timeout parameter"
                    ))
        
    except Exception as e:
        pass
    
    return file_issues

def main():
    """Основная функция аудита."""
    root = Path(".")
    
    # Сканируем критичные директории
    critical_dirs = [
        "app/database",
        "app/services",
        "app/kie",
        "app/delivery",
        "app/storage",
        "bot/handlers",
    ]
    
    print("Starting comprehensive audit...\n")
    
    for dir_path in critical_dirs:
        dir_full = root / dir_path
        if dir_full.exists():
            for file_path in dir_full.rglob("*.py"):
                file_issues = scan_file(file_path)
                issues.extend(file_issues)
    
    # Сортируем по приоритету
    issues.sort(key=lambda x: (x.severity == "P0", x.severity == "P1", x.severity == "P2"))
    
    # Группируем по категориям
    by_category = defaultdict(list)
    for issue in issues[:50]:  # Топ-50
        by_category[issue.category].append(issue)
    
    # Выводим результаты
    print(f"Found {len(issues)} critical issues\n")
    print("="*80)
    
    for category, cat_issues in sorted(by_category.items()):
        print(f"\n## {category} ({len(cat_issues)} issues)")
        print("-"*80)
        
        for issue in cat_issues[:10]:  # Топ-10 в каждой категории
            print(f"\n[{issue.severity}] {issue.file}:{issue.line}")
            print(f"  {issue.description}")
            if issue.code_snippet:
                print(f"  Code: {issue.code_snippet[:80]}")
            if issue.fix_hint:
                print(f"  Fix: {issue.fix_hint}")
    
    # Сохраняем в файл
    report = root / "TOP50_CRITICAL_ISSUES.md"
    with open(report, 'w', encoding='utf-8') as f:
        f.write("# Топ-50 Критичных Проблем\n\n")
        f.write(f"**Всего найдено:** {len(issues)} проблем\n")
        f.write(f"**Топ-50:** {min(50, len(issues))} проблем\n\n")
        
        for i, issue in enumerate(issues[:50], 1):
            f.write(f"## {i}. [{issue.severity}] {issue.category}\n\n")
            f.write(f"**Файл:** `{issue.file}:{issue.line}`\n\n")
            f.write(f"**Проблема:** {issue.description}\n\n")
            if issue.code_snippet:
                f.write(f"**Код:**\n```python\n{issue.code_snippet}\n```\n\n")
            if issue.fix_hint:
                f.write(f"**Исправление:** {issue.fix_hint}\n\n")
            f.write("---\n\n")
    
    print(f"\n[OK] Report saved to: {report}")

if __name__ == "__main__":
    main()


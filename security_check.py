"""
Модуль для проверки безопасности API ключей и конфигурации.
"""

import os
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


def check_api_keys_security() -> Dict[str, Any]:
    """
    Проверяет безопасность хранения API ключей.
    
    Returns:
        Словарь с результатами проверки
    """
    issues = []
    warnings = []
    
    # Проверяем наличие .env файла
    env_file = Path('.env')
    if not env_file.exists():
        issues.append("Файл .env не найден. API ключи должны храниться в переменных окружения.")
    else:
        # Проверяем, что .env не добавлен в git
        gitignore = Path('.gitignore')
        if gitignore.exists():
            with open(gitignore, 'r', encoding='utf-8') as f:
                gitignore_content = f.read()
                if '.env' not in gitignore_content:
                    warnings.append("Файл .env не добавлен в .gitignore. Это может привести к утечке API ключей.")
        else:
            warnings.append("Файл .gitignore не найден. Рекомендуется добавить .env в .gitignore.")
    
    # Проверяем переменные окружения
    required_keys = ['KIE_API_KEY', 'TELEGRAM_BOT_TOKEN']
    missing_keys = []
    
    for key in required_keys:
        value = os.getenv(key)
        if not value:
            missing_keys.append(key)
        elif len(value) < 10:
            warnings.append(f"API ключ {key} слишком короткий. Возможно, он неверен.")
    
    if missing_keys:
        issues.append(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_keys)}")
    
    # Проверяем, нет ли API ключей в коде
    code_files = [
        Path('bot_kie.py'),
        Path('kie_client.py'),
        Path('kie_gateway.py')
    ]
    
    sensitive_patterns = [
        'api_key',
        'api_key =',
        'KIE_API_KEY =',
        'TELEGRAM_BOT_TOKEN ='
    ]
    
    for code_file in code_files:
        if code_file.exists():
            with open(code_file, 'r', encoding='utf-8') as f:
                content = f.read()
                for pattern in sensitive_patterns:
                    if pattern in content and 'os.getenv' not in content and 'os.environ' not in content:
                        # Проверяем контекст
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if pattern in line.lower() and 'os.getenv' not in line and 'os.environ' not in line:
                                if '=' in line and not line.strip().startswith('#'):
                                    issues.append(
                                        f"Возможная утечка API ключа в {code_file.name}, строка {i + 1}: "
                                        f"{line.strip()[:50]}..."
                                    )
    
    return {
        'secure': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'missing_keys': missing_keys
    }


def validate_api_key_format(api_key: str, key_type: str = 'KIE') -> bool:
    """
    Проверяет формат API ключа.
    
    Args:
        api_key: API ключ для проверки
        key_type: Тип ключа (KIE, TELEGRAM)
    
    Returns:
        True, если формат корректный
    """
    if not api_key:
        return False
    
    if key_type == 'KIE':
        # KIE API ключи обычно длинные строки
        return len(api_key) >= 20
    elif key_type == 'TELEGRAM':
        # Telegram токены имеют формат: число:строка
        parts = api_key.split(':')
        return len(parts) == 2 and parts[0].isdigit()
    
    return True


def get_security_report() -> str:
    """
    Возвращает отчет о безопасности.
    
    Returns:
        Текст отчета
    """
    check_result = check_api_keys_security()
    
    report_lines = ["🔒 ОТЧЕТ О БЕЗОПАСНОСТИ API КЛЮЧЕЙ\n"]
    
    if check_result['secure']:
        report_lines.append("✅ Безопасность: ОК")
    else:
        report_lines.append("❌ Безопасность: ЕСТЬ ПРОБЛЕМЫ")
    
    if check_result['issues']:
        report_lines.append("\n❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
        for issue in check_result['issues']:
            report_lines.append(f"  • {issue}")
    
    if check_result['warnings']:
        report_lines.append("\n⚠️ ПРЕДУПРЕЖДЕНИЯ:")
        for warning in check_result['warnings']:
            report_lines.append(f"  • {warning}")
    
    if check_result['missing_keys']:
        report_lines.append("\n📋 ОТСУТСТВУЮЩИЕ КЛЮЧИ:")
        for key in check_result['missing_keys']:
            report_lines.append(f"  • {key}")
    
    return "\n".join(report_lines)


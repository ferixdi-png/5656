"""
Проверка конфигурации для деплоя на Render
Проверяет все необходимые настройки перед деплоем
"""

import os
import sys
import asyncio
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RenderConfigChecker:
    """Класс для проверки конфигурации Render"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.checks_passed = 0
        self.checks_failed = 0
    
    def check_env_variable(self, name: str, required: bool = True) -> bool:
        """Проверяет наличие переменной окружения"""
        value = os.getenv(name)
        if value:
            # Не показываем значение секретных ключей
            if 'KEY' in name or 'TOKEN' in name or 'PASSWORD' in name:
                logger.info(f"✅ {name}: установлена (скрыто)")
            else:
                logger.info(f"✅ {name}: {value[:50]}...")
            return True
        else:
            if required:
                self.issues.append(f"❌ Обязательная переменная окружения отсутствует: {name}")
                logger.error(f"❌ {name}: НЕ УСТАНОВЛЕНА")
                return False
            else:
                self.warnings.append(f"⚠️  Опциональная переменная окружения отсутствует: {name}")
                logger.warning(f"⚠️  {name}: не установлена (опционально)")
                return False
    
    def check_database_connection(self) -> bool:
        """Проверяет подключение к базе данных"""
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            self.issues.append("❌ DATABASE_URL не установлен. Установите Connection в Render Dashboard")
            logger.error("❌ DATABASE_URL: не установлен")
            return False
        
        # Проверяем формат DATABASE_URL
        if not database_url.startswith('postgresql://') and not database_url.startswith('postgres://'):
            self.issues.append(f"❌ DATABASE_URL имеет неправильный формат: должен начинаться с postgresql:// или postgres://")
            logger.error(f"❌ DATABASE_URL: неправильный формат")
            return False
        
        # Пытаемся подключиться (только проверка, без реального подключения)
        try:
            # Проверяем наличие asyncpg для async подключения
            try:
                import asyncpg
                logger.info("✅ asyncpg доступен для подключения к БД")
            except ImportError:
                self.warnings.append("⚠️  asyncpg не установлен. Установите: pip install asyncpg")
                logger.warning("⚠️  asyncpg: не установлен")
            
            logger.info(f"✅ DATABASE_URL: установлен (формат правильный)")
            logger.info(f"   Host: {database_url.split('@')[1].split('/')[0] if '@' in database_url else 'unknown'}")
            return True
        except Exception as e:
            self.issues.append(f"❌ Ошибка проверки DATABASE_URL: {e}")
            logger.error(f"❌ DATABASE_URL: ошибка проверки - {e}")
            return False
    
    def check_kie_api(self) -> bool:
        """Проверяет доступность KIE API"""
        api_key = os.getenv('KIE_API_KEY')
        if not api_key:
            self.issues.append("❌ KIE_API_KEY не установлен")
            logger.error("❌ KIE_API_KEY: не установлен")
            return False
        
        # Проверяем, что можем импортировать клиент
        try:
            from kie_client import KIEClient
            client = KIEClient()
            if client.api_key:
                logger.info("✅ KIE API клиент инициализирован")
                return True
            else:
                self.issues.append("❌ KIE_API_KEY не установлен в клиенте")
                logger.error("❌ KIE API клиент: API ключ не установлен")
                return False
        except ImportError as e:
            self.issues.append(f"❌ Не удалось импортировать kie_client: {e}")
            logger.error(f"❌ KIE API клиент: ошибка импорта - {e}")
            return False
        except Exception as e:
            self.issues.append(f"❌ Ошибка инициализации KIE API клиента: {e}")
            logger.error(f"❌ KIE API клиент: ошибка - {e}")
            return False
    
    def check_health_check_server(self) -> bool:
        """Проверяет, что health check сервер настроен правильно"""
        # Проверяем наличие index.js
        if not os.path.exists('index.js'):
            self.issues.append("❌ index.js не найден. Health check сервер не будет работать")
            logger.error("❌ index.js: файл не найден")
            return False
        
        # Читаем index.js и проверяем наличие health check
        try:
            with open('index.js', 'r', encoding='utf-8') as f:
                content = f.read()
            
            checks = [
                ('startHealthCheck', 'Функция startHealthCheck'),
                ('/health', 'Endpoint /health'),
                ('PORT', 'Использование переменной PORT'),
                ('0.0.0.0', 'Слушает на 0.0.0.0 (не localhost)'),
            ]
            
            all_ok = True
            for check_str, check_name in checks:
                if check_str in content:
                    logger.info(f"✅ {check_name}: найден в index.js")
                else:
                    self.issues.append(f"❌ {check_name} не найден в index.js")
                    logger.error(f"❌ {check_name}: не найден")
                    all_ok = False
            
            return all_ok
        except Exception as e:
            self.issues.append(f"❌ Ошибка чтения index.js: {e}")
            logger.error(f"❌ index.js: ошибка чтения - {e}")
            return False
    
    def check_dockerfile(self) -> bool:
        """Проверяет Dockerfile"""
        if not os.path.exists('Dockerfile'):
            self.warnings.append("⚠️  Dockerfile не найден. Render может использовать автоматическую сборку")
            logger.warning("⚠️  Dockerfile: не найден")
            return True  # Не критично
        
        try:
            with open('Dockerfile', 'r', encoding='utf-8') as f:
                content = f.read()
            
            checks = [
                ('HEALTHCHECK', 'HEALTHCHECK команда'),
                ('PORT', 'Переменная PORT'),
                ('CMD', 'CMD команда для запуска'),
            ]
            
            all_ok = True
            for check_str, check_name in checks:
                if check_str in content:
                    logger.info(f"✅ {check_name}: найден в Dockerfile")
                else:
                    self.warnings.append(f"⚠️  {check_name} не найден в Dockerfile")
                    logger.warning(f"⚠️  {check_name}: не найден")
                    all_ok = False
            
            return all_ok
        except Exception as e:
            self.warnings.append(f"⚠️  Ошибка чтения Dockerfile: {e}")
            logger.warning(f"⚠️  Dockerfile: ошибка чтения - {e}")
            return True  # Не критично
    
    def check_package_json(self) -> bool:
        """Проверяет package.json"""
        if not os.path.exists('package.json'):
            self.issues.append("❌ package.json не найден")
            logger.error("❌ package.json: файл не найден")
            return False
        
        try:
            import json
            with open('package.json', 'r', encoding='utf-8') as f:
                package = json.load(f)
            
            # Проверяем скрипт start
            scripts = package.get('scripts', {})
            if 'start' in scripts:
                start_cmd = scripts['start']
                logger.info(f"✅ package.json start: {start_cmd}")
                if 'index.js' in start_cmd:
                    logger.info("✅ start скрипт использует index.js")
                else:
                    self.warnings.append(f"⚠️  start скрипт не использует index.js: {start_cmd}")
                    logger.warning(f"⚠️  start скрипт: {start_cmd}")
                return True
            else:
                self.issues.append("❌ Скрипт 'start' не найден в package.json")
                logger.error("❌ package.json: скрипт 'start' не найден")
                return False
        except Exception as e:
            self.issues.append(f"❌ Ошибка чтения package.json: {e}")
            logger.error(f"❌ package.json: ошибка - {e}")
            return False
    
    def check_python_files(self) -> bool:
        """Проверяет наличие необходимых Python файлов"""
        required_files = [
            'bot_kie.py',
            'kie_client.py',
            'kie_models.py',
        ]
        
        all_ok = True
        for file in required_files:
            if os.path.exists(file):
                logger.info(f"✅ {file}: найден")
            else:
                self.issues.append(f"❌ Обязательный файл не найден: {file}")
                logger.error(f"❌ {file}: не найден")
                all_ok = False
        
        return all_ok
    
    def check_database_usage(self) -> bool:
        """Проверяет, что код использует DATABASE_URL правильно"""
        try:
            # Проверяем database.py
            if os.path.exists('database.py'):
                with open('database.py', 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'DATABASE_URL' in content:
                    if 'os.getenv' in content or 'os.environ' in content:
                        logger.info("✅ database.py использует DATABASE_URL из environment")
                    else:
                        self.warnings.append("⚠️  database.py может не использовать DATABASE_URL из environment")
                        logger.warning("⚠️  database.py: проверь использование DATABASE_URL")
                else:
                    self.warnings.append("⚠️  database.py не использует DATABASE_URL")
                    logger.warning("⚠️  database.py: DATABASE_URL не найден")
            
            return True
        except Exception as e:
            self.warnings.append(f"⚠️  Ошибка проверки database.py: {e}")
            logger.warning(f"⚠️  database.py: ошибка проверки - {e}")
            return True
    
    def run_all_checks(self) -> bool:
        """Запускает все проверки"""
        logger.info("\n" + "="*80)
        logger.info("🔍 ПРОВЕРКА КОНФИГУРАЦИИ ДЛЯ RENDER")
        logger.info("="*80 + "\n")
        
        # Обязательные переменные окружения
        logger.info("📋 Проверка переменных окружения...")
        self.check_env_variable('TELEGRAM_BOT_TOKEN', required=True)
        self.check_env_variable('KIE_API_KEY', required=True)
        self.check_env_variable('DATABASE_URL', required=True)
        self.check_env_variable('ADMIN_ID', required=True)
        self.check_env_variable('PORT', required=False)  # Опционально, есть default
        
        # Опциональные переменные
        logger.info("\n📋 Проверка опциональных переменных...")
        self.check_env_variable('SUPPORT_TELEGRAM', required=False)
        self.check_env_variable('SUPPORT_TEXT', required=False)
        self.check_env_variable('PAYMENT_BANK', required=False)
        self.check_env_variable('PAYMENT_CARD_HOLDER', required=False)
        self.check_env_variable('PAYMENT_PHONE', required=False)
        
        # Проверка подключения к БД
        logger.info("\n🗄️  Проверка базы данных...")
        self.check_database_connection()
        self.check_database_usage()
        
        # Проверка KIE API
        logger.info("\n🤖 Проверка KIE API...")
        self.check_kie_api()
        
        # Проверка health check
        logger.info("\n🏥 Проверка health check сервера...")
        self.check_health_check_server()
        
        # Проверка файлов
        logger.info("\n📁 Проверка файлов...")
        self.check_python_files()
        self.check_package_json()
        self.check_dockerfile()
        
        # Итоги
        logger.info("\n" + "="*80)
        logger.info("📊 ИТОГИ ПРОВЕРКИ")
        logger.info("="*80)
        
        total_checks = len(self.issues) + len(self.warnings)
        if self.issues:
            logger.error(f"\n❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ ({len(self.issues)}):")
            for issue in self.issues:
                logger.error(f"  {issue}")
        
        if self.warnings:
            logger.warning(f"\n⚠️  ПРЕДУПРЕЖДЕНИЯ ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  {warning}")
        
        if not self.issues and not self.warnings:
            logger.info("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Код готов к деплою на Render")
            return True
        elif not self.issues:
            logger.info("\n✅ Критических проблем нет, но есть предупреждения")
            return True
        else:
            logger.error(f"\n❌ НАЙДЕНЫ КРИТИЧЕСКИЕ ПРОБЛЕМЫ! Исправьте их перед деплоем")
            return False


def main():
    """Главная функция"""
    checker = RenderConfigChecker()
    success = checker.run_all_checks()
    
    if success:
        logger.info("\n✅ Конфигурация готова к деплою")
        sys.exit(0)
    else:
        logger.error("\n❌ Исправьте критические проблемы перед деплоем")
        sys.exit(1)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
# kie_api_scraper.py - Автоматический сборщик ВСЕХ моделей Kie.ai + API настройки
# Готовый скрипт "одна кнопка" - запускай и получай полный дамп

# -*- coding: utf-8 -*-
"""
Kie.ai API Scraper
Автоматический сборщик всех моделей Kie.ai с полной документацией API
Готов к развертыванию на Render.com
"""

import sys
import os
import requests
import json
import time
from urllib.parse import urljoin
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Устанавливаем кодировку для вывода (важно для Render)
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Для старых версий Python
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

class KieApiScraper:
    def __init__(self, max_workers=5, enable_cache=True):
        # Проверка согласованности URL параметров
        self.base_url = "https://api.kie.ai/api/v1"
        self.docs_base = "https://docs.kie.ai"
        self.market_url = "https://kie.ai/ru/market"
        
        # Единые headers для всех запросов
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        self.models = []
        self.max_workers = max_workers
        self.enable_cache = enable_cache
        self.cache = {} if enable_cache else None
        
        # Метрики производительности
        self.metrics = {
            'start_time': None,
            'end_time': None,
            'total_requests': 0,
            'cached_requests': 0,
            'failed_requests': 0,
            'total_models_processed': 0,
            'categories': {}
        }
        
        # Настройка сессии с retry механизмом
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)
    
    def get_market_page(self):
        """Улучшенный парсинг главной страницы с моделями"""
        try:
            print(f"   📡 Запрос к {self.market_url}...")
            # Используем сессию с retry
            resp = self.session.get(self.market_url, timeout=10)
            resp.raise_for_status()
            print(f"   ✅ ОТВЕТ: Получен ответ со статусом {resp.status_code}")
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            print(f"   🔍 ОТВЕТ: Парсинг HTML страницы...")
            
            model_links = []
            
            # Множественные стратегии поиска моделей
            # Стратегия 1: Поиск по ссылкам с моделями
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                # Ищем ссылки на модели
                if any(keyword in href.lower() for keyword in ['model', 'api', '/ru/', 'market']):
                    title = link.get_text().strip()
                    if title and len(title) > 2:
                        full_url = urljoin(self.market_url, href)
                        model_links.append({
                            'name': title,
                            'url': full_url
                        })
            
            # Стратегия 2: Поиск карточек моделей
            cards = soup.find_all(['div', 'section', 'article'], 
                                 class_=re.compile(r'(model|api|card|feature|item|product)', re.I))
            
            for card in cards:
                # Ищем заголовок
                title_elem = (card.find('h1') or card.find('h2') or card.find('h3') or 
                             card.find('h4') or card.find(class_=re.compile(r'(title|name|heading)', re.I)))
                
                # Ищем ссылку
                link_elem = card.find('a', href=True)
                
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title and len(title) > 2:
                        if link_elem:
                            url = urljoin(self.market_url, link_elem['href'])
                        else:
                            # Если нет ссылки, создаем из названия
                            url = urljoin(self.market_url, f"/ru/market/{title.lower().replace(' ', '-')}")
                        
                        # Проверяем, нет ли дубликатов
                        if not any(m['name'] == title for m in model_links):
                            model_links.append({
                                'name': title,
                                'url': url
                            })
            
            # Стратегия 3: Поиск в JSON данных (если есть)
            script_tags = soup.find_all('script', type='application/json')
            for script in script_tags:
                try:
                    # Проверяем что script.string не None
                    if script.string is None:
                        continue
                    data = json.loads(script.string)
                    # Рекурсивный поиск моделей в JSON
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if 'model' in key.lower() or 'api' in key.lower():
                                if isinstance(value, list):
                                    for item in value:
                                        if isinstance(item, dict) and 'name' in item:
                                            model_links.append({
                                                'name': item.get('name', ''),
                                                'url': item.get('url', item.get('href', ''))
                                            })
                except (json.JSONDecodeError, AttributeError, TypeError) as e:
                    # Игнорируем ошибки парсинга JSON
                    pass
            
            # Удаляем дубликаты и пустые записи
            seen = set()
            unique_links = []
            for model in model_links:
                if model['name'] and model['name'] not in seen:
                    seen.add(model['name'])
                    unique_links.append(model)
            
            print(f"   ✅ ОТВЕТ: Найдено {len(cards)} карточек, извлечено {len(unique_links)} уникальных ссылок на модели")
            return unique_links
        except requests.RequestException as e:
            print(f"   ❌ ОТВЕТ: Ошибка при получении страницы маркета: {e}")
            return []
    
    def _extract_endpoint(self, text, model_name):
        """Улучшенное извлечение API endpoint из текста"""
        # Паттерны для поиска endpoint
        patterns = [
            r'api\.kie\.ai/api/v1/([a-zA-Z0-9\-_/]+)',
            r'/api/v1/([a-zA-Z0-9\-_/]+)',
            r'endpoint[:\s]+["\']?([a-zA-Z0-9\-_/]+)["\']?',
            r'POST[:\s]+["\']?([a-zA-Z0-9\-_/]+)["\']?',
            r'url[:\s]+["\']?.*?/([a-zA-Z0-9\-_/]+)["\']?',
            r'/([a-zA-Z0-9\-_]+)/(?:generate|create|text|image|video)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                endpoint = match.group(1)
                # Нормализуем endpoint
                if not endpoint.startswith('/'):
                    endpoint = '/' + endpoint
                if not endpoint.endswith(('/generate', '/create', '/text', '/image', '/video')):
                    # Пытаемся определить тип по названию модели
                    if any(x in model_name.lower() for x in ['video', 'veo', 'gen']):
                        endpoint = endpoint.rstrip('/') + '/generate'
                    elif any(x in model_name.lower() for x in ['image', 'img', 'dalle']):
                        endpoint = endpoint.rstrip('/') + '/generate'
                    else:
                        endpoint = endpoint.rstrip('/') + '/generate'
                return endpoint
        
        # Если не нашли, пытаемся извлечь из названия модели
        model_slug = re.sub(r'[^a-zA-Z0-9\-_]', '', model_name.lower().replace(' ', '-'))
        if model_slug:
            return f"/{model_slug}/generate"
        
        return "/generate"
    
    def _extract_json_example(self, soup, text):
        """Улучшенное извлечение JSON примера"""
        # Ищем в code блоках
        code_blocks = soup.find_all(['pre', 'code'], class_=re.compile(r'(json|code|example|request)'))
        
        for block in code_blocks:
            code = block.get_text().strip()
            # Проверяем, что это JSON
            if '{' in code and ('prompt' in code.lower() or 'input' in code.lower() or 'text' in code.lower()):
                # Пытаемся распарсить JSON
                try:
                    # Очищаем код от markdown разметки
                    code = re.sub(r'```json\s*', '', code)
                    code = re.sub(r'```\s*', '', code)
                    code = code.strip()
                    
                    # Парсим JSON для проверки
                    json.loads(code)
                    return code
                except (json.JSONDecodeError, ValueError, TypeError):
                    # Если не валидный JSON, но похож на него
                    if code.count('{') > 0 and code.count('}') > 0:
                        return code
        
        # Ищем в тексте между фигурными скобками
        json_match = re.search(r'\{[^{}]*"(?:prompt|input|text)"[^{}]*\}', text, re.I | re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return ''
    
    def _extract_parameters(self, text, soup):
        """Улучшенное извлечение параметров из документации"""
        params = {}
        
        # Ищем параметры в таблицах
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    param_name = cells[0].get_text().strip().lower()
                    param_value = cells[1].get_text().strip()
                    
                    # Извлекаем числовые значения
                    num_match = re.search(r'(\d+)', param_value)
                    if num_match and param_name in ['duration', 'width', 'height', 'steps', 'max_length', 'temperature']:
                        params[param_name] = int(num_match.group(1))
        
        # Ищем параметры в тексте через паттерны
        param_patterns = {
            'duration': [
                r'duration[:\s]*["\']?(\d+)["\']?',
                r'"duration"[:\s]*:?\s*(\d+)',
                r'duration[:\s]*=?\s*(\d+)',
            ],
            'width': [
                r'width[:\s]*["\']?(\d+)["\']?',
                r'"width"[:\s]*:?\s*(\d+)',
                r'width[:\s]*=?\s*(\d+)',
            ],
            'height': [
                r'height[:\s]*["\']?(\d+)["\']?',
                r'"height"[:\s]*:?\s*(\d+)',
                r'height[:\s]*=?\s*(\d+)',
            ],
            'steps': [
                r'steps[:\s]*["\']?(\d+)["\']?',
                r'"steps"[:\s]*:?\s*(\d+)',
                r'steps[:\s]*=?\s*(\d+)',
            ],
            'temperature': [
                r'temperature[:\s]*["\']?([\d.]+)["\']?',
                r'"temperature"[:\s]*:?\s*([\d.]+)',
            ],
            'max_length': [
                r'max[_\s]?length[:\s]*["\']?(\d+)["\']?',
                r'"max_length"[:\s]*:?\s*(\d+)',
            ],
        }
        
        for param_name, patterns in param_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    try:
                        if param_name == 'temperature':
                            params[param_name] = float(match.group(1))
                        else:
                            params[param_name] = int(match.group(1))
                        break
                    except (ValueError, TypeError, AttributeError):
                        continue
        
        return params
    
    def _extract_input_schema(self, text, soup):
        """Извлечение схемы input параметров"""
        input_schema = {}
        
        # Ищем описание параметров
        # Паттерны для обязательных полей
        required_fields = []
        
        # Ищем "required" или "обязательные"
        required_match = re.search(r'(?:required|обязательные?)[:\s]+\[?([^\]]+)\]?', text, re.I)
        if required_match:
            required_str = required_match.group(1)
            required_fields = [f.strip().strip('"\'') for f in required_str.split(',')]
        
        # Базовые обязательные поля для API
        base_required = ['prompt']
        
        # Извлекаем типы параметров
        type_patterns = {
            'prompt': r'"(?:prompt|text|input)"[:\s]*:?\s*"([^"]+)"',
            'string': r'string|str|text',
            'integer': r'int|integer|number',
            'float': r'float|double',
            'boolean': r'bool|boolean',
        }
        
        # Создаем схему на основе найденных параметров
        if 'prompt' in text.lower():
            input_schema['prompt'] = {
                'type': 'string',
                'required': True,
                'description': 'Текст запроса для модели'
            }
        
        return {
            'required': list(set(base_required + required_fields)),
            'properties': input_schema
        }
    
    def scrape_model_docs(self, model_url, model_name):
        """Улучшенный парсинг документации конкретной модели"""
        try:
            # Проверка кэша
            if self.enable_cache and model_url in self.cache:
                self.metrics['cached_requests'] += 1
                cached_data = self.cache[model_url]
                resp_text = cached_data['text']
                soup = BeautifulSoup(resp_text, 'html.parser')
            else:
                self.metrics['total_requests'] += 1
                resp = self.session.get(model_url, timeout=10)
                resp.raise_for_status()
                resp_text = resp.text
                soup = BeautifulSoup(resp_text, 'html.parser')
                
                # Сохранение в кэш
                if self.enable_cache:
                    self.cache[model_url] = {'text': resp_text}
            
            # Структура model_info согласована с финальным JSON
            model_info = {
                'name': model_name,
                'endpoint': '',
                'method': 'POST',
                'base_url': self.base_url,
                'params': {},
                'input_schema': {},
                'example': '',
                'example_request': {},
                'price': '',
                'category': ''
            }
            
            # Улучшенное извлечение endpoint
            model_info['endpoint'] = self._extract_endpoint(resp_text, model_name)
            
            # Улучшенное извлечение JSON примера
            example_json = self._extract_json_example(soup, resp_text)
            if example_json:
                model_info['example'] = example_json
                # Пытаемся распарсить в структурированный формат
                try:
                    parsed = json.loads(example_json)
                    model_info['example_request'] = parsed
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
            else:
                # Создаем базовый пример
                model_info['example'] = json.dumps({
                    "prompt": "Пример запроса",
                    **{k: v for k, v in model_info.get('params', {}).items()}
                }, ensure_ascii=False, indent=2)
                model_info['example_request'] = {"prompt": "Пример запроса"}
            
            # Улучшенное извлечение параметров
            extracted_params = self._extract_parameters(resp_text, soup)
            if extracted_params:
                model_info['params'] = extracted_params
            else:
                # Устанавливаем базовые параметры по умолчанию
                model_info['params'] = {}
            
            # Извлечение схемы input
            model_info['input_schema'] = self._extract_input_schema(resp_text, soup)
            
            # Определяем категорию модели
            category_keywords = {
                'video': ['video', 'veo', 'gen-2', 'gen-3', 'sora'],
                'image': ['image', 'dalle', 'midjourney', 'stable', 'diffusion'],
                'text': ['text', 'gpt', 'llm', 'language', 'chat'],
                'audio': ['audio', 'music', 'sound', 'tts'],
            }
            
            model_lower = model_name.lower()
            for cat, keywords in category_keywords.items():
                if any(kw in model_lower for kw in keywords):
                    model_info['category'] = cat
                    break
            
            if not model_info['category']:
                model_info['category'] = 'other'
            
            # Обновление метрик по категориям
            cat = model_info['category']
            self.metrics['categories'][cat] = self.metrics['categories'].get(cat, 0) + 1
            
            # Валидация структуры модели перед добавлением
            if self._validate_model_structure(model_info):
                self.models.append(model_info)
            else:
                self.metrics['failed_requests'] += 1
        except requests.RequestException as e:
            self.metrics['failed_requests'] += 1
            # Логируем только критичные ошибки
            if hasattr(e, 'response') and e.response and e.response.status_code >= 500:
                print(f"\n  ⚠️ Серверная ошибка для {model_name}: {e.response.status_code}")
        except Exception as e:
            self.metrics['failed_requests'] += 1
            # Тихая обработка для параллельной работы
            pass
    
    def _validate_model_structure(self, model_info):
        """Улучшенная проверка структуры модели с валидацией API"""
        required_fields = ['name', 'endpoint', 'method', 'base_url', 'params', 'example', 'category']
        optional_fields = ['input_schema', 'example_request', 'price']
        
        # Проверка наличия всех обязательных полей
        missing_fields = []
        for field in required_fields:
            if field not in model_info:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"      ❌ ОТВЕТ: Отсутствуют обязательные поля: {', '.join(missing_fields)}")
            return False
        
        # Проверка типов данных
        if not isinstance(model_info['name'], str) or not model_info['name']:
            print(f"      ❌ ОТВЕТ: Неверный тип или пустое значение для 'name'")
            return False
        
        if not isinstance(model_info['endpoint'], str) or not model_info['endpoint']:
            print(f"      ❌ ОТВЕТ: Endpoint должен быть непустой строкой")
            return False
        
        # Проверка формата endpoint
        if not model_info['endpoint'].startswith('/'):
            print(f"      ⚠️ ОТВЕТ: Endpoint должен начинаться с '/', исправляю...")
            model_info['endpoint'] = '/' + model_info['endpoint']
        
        if not isinstance(model_info['params'], dict):
            print(f"      ❌ ОТВЕТ: 'params' должен быть словарем, получен {type(model_info['params'])}")
            return False
        
        if not isinstance(model_info['base_url'], str) or model_info['base_url'] != self.base_url:
            print(f"      ❌ ОТВЕТ: 'base_url' не соответствует ожидаемому значению")
            print(f"         Ожидается: {self.base_url}")
            print(f"         Получено: {model_info['base_url']}")
            return False
        
        # Проверка example
        if not model_info.get('example'):
            print(f"      ⚠️ ОТВЕТ: Пример не найден, создаю базовый...")
            model_info['example'] = json.dumps({
                "prompt": "Пример запроса"
            }, ensure_ascii=False, indent=2)
        
        # Проверка и создание example_request если нужно
        if not model_info.get('example_request'):
            try:
                model_info['example_request'] = json.loads(model_info['example'])
            except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                model_info['example_request'] = {"prompt": "Пример запроса"}
        
        # Проверка input_schema
        if not model_info.get('input_schema'):
            model_info['input_schema'] = {
                'required': ['prompt'],
                'properties': {
                    'prompt': {
                        'type': 'string',
                        'required': True,
                        'description': 'Текст запроса'
                    }
                }
            }
        
        # Валидация API endpoint (проверка что он выглядит правильно)
        endpoint_parts = model_info['endpoint'].strip('/').split('/')
        if len(endpoint_parts) < 1:
            print(f"      ⚠️ ОТВЕТ: Endpoint слишком короткий, исправляю...")
            model_info['endpoint'] = f"/{model_info['name'].lower().replace(' ', '-')}/generate"
        
        print(f"      ✅ ОТВЕТ: Все поля присутствуют и имеют правильные типы")
        print(f"      ✅ ОТВЕТ: Endpoint валиден: {model_info['endpoint']}")
        print(f"      ✅ ОТВЕТ: Параметров: {len(model_info['params'])}")
        return True
    
    def _validate_api_endpoint(self, model):
        """Проверка корректности API endpoint и параметров"""
        issues = []
        
        # Проверка endpoint
        if not model.get('endpoint') or model['endpoint'] == '/generate':
            issues.append("Endpoint не определен или слишком общий")
        
        # Проверка что endpoint содержит название модели или специфичный путь
        endpoint_lower = model['endpoint'].lower()
        name_lower = model['name'].lower()
        name_slug = re.sub(r'[^a-z0-9]', '', name_lower)
        
        if name_slug and name_slug not in endpoint_lower.replace('-', '').replace('_', ''):
            # Это не критично, но предупреждаем
            pass
        
        # Проверка example_request
        if not model.get('example_request') or not isinstance(model['example_request'], dict):
            issues.append("example_request отсутствует или неверного формата")
        else:
            # Проверяем наличие обязательных полей
            if 'prompt' not in model['example_request']:
                issues.append("example_request не содержит поле 'prompt'")
        
        # Проверка input_schema
        if not model.get('input_schema'):
            issues.append("input_schema отсутствует")
        else:
            if 'required' not in model['input_schema']:
                issues.append("input_schema не содержит 'required'")
            if 'prompt' not in model['input_schema'].get('required', []):
                # Добавляем prompt в required если его нет
                if 'required' not in model['input_schema']:
                    model['input_schema']['required'] = []
                if 'prompt' not in model['input_schema']['required']:
                    model['input_schema']['required'].append('prompt')
        
        return issues
    
    def _fix_model_issues(self, model):
        """Исправление найденных проблем в модели"""
        fixed = False
        
        # Исправляем endpoint если он пустой
        if not model.get('endpoint') or model['endpoint'] == '/generate':
            model_slug = re.sub(r'[^a-zA-Z0-9\-_]', '', model['name'].lower().replace(' ', '-'))
            model['endpoint'] = f"/{model_slug}/generate"
            fixed = True
        
        # Исправляем example_request если его нет
        if not model.get('example_request'):
            try:
                if model.get('example'):
                    model['example_request'] = json.loads(model['example'])
                else:
                    model['example_request'] = {"prompt": "Пример запроса"}
                fixed = True
            except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                model['example_request'] = {"prompt": "Пример запроса"}
                fixed = True
        
        # Исправляем example если его нет
        if not model.get('example'):
            model['example'] = json.dumps(model.get('example_request', {"prompt": "Пример запроса"}), 
                                         ensure_ascii=False, indent=2)
            fixed = True
        
        # Исправляем input_schema
        if not model.get('input_schema'):
            model['input_schema'] = {
                'required': ['prompt'],
                'properties': {
                    'prompt': {
                        'type': 'string',
                        'required': True,
                        'description': 'Текст запроса для модели'
                    }
                }
            }
            fixed = True
        
        return fixed
    
    def validate_all_models(self):
        """Улучшенная финальная проверка всех моделей с исправлением проблем"""
        print("\n🔍 ФИНАЛЬНАЯ ПРОВЕРКА ВСЕХ МОДЕЛЕЙ...")
        print("=" * 60)
        valid_count = 0
        invalid_count = 0
        invalid_models = []
        fixed_count = 0
        
        for i, model in enumerate(self.models, 1):
            print(f"\n  📋 Проверка {i}/{len(self.models)}: {model['name']}")
            
            # Структурная валидация
            if not self._validate_model_structure(model):
                invalid_count += 1
                invalid_models.append(model['name'])
                print(f"  ❌ ОТВЕТ: Модель '{model['name']}' НЕ прошла структурную валидацию")
                continue
            
            # Проверка API endpoint и параметров
            api_issues = self._validate_api_endpoint(model)
            
            # Исправление проблем
            if api_issues:
                print(f"  🔧 ОТВЕТ: Найдены проблемы: {', '.join(api_issues)}")
                if self._fix_model_issues(model):
                    fixed_count += 1
                    print(f"  ✅ ОТВЕТ: Проблемы исправлены")
                    api_issues = self._validate_api_endpoint(model)  # Проверяем снова
            
            if not api_issues:
                valid_count += 1
                print(f"  ✅ ОТВЕТ: Модель '{model['name']}' полностью валидна")
                print(f"      🔗 Endpoint: {model['endpoint']}")
                print(f"      📝 Параметров: {len(model.get('params', {}))}")
                print(f"      📋 Input полей: {len(model.get('input_schema', {}).get('required', []))}")
            else:
                invalid_count += 1
                invalid_models.append(model['name'])
                print(f"  ⚠️ ОТВЕТ: Модель '{model['name']}' имеет проблемы: {', '.join(api_issues)}")
        
        print("\n" + "=" * 60)
        print("📊 ОТВЕТ: РЕЗУЛЬТАТЫ ФИНАЛЬНОЙ ПРОВЕРКИ:")
        print(f"  ✅ Валидных моделей: {valid_count}")
        print(f"  ❌ Невалидных моделей: {invalid_count}")
        print(f"  🔧 Исправлено моделей: {fixed_count}")
        print(f"  📦 Всего моделей: {len(self.models)}")
        
        if invalid_models:
            print(f"\n  ⚠️ Список моделей с проблемами:")
            for name in invalid_models:
                print(f"    - {name}")
        
        if invalid_count == 0:
            print("\n✅ ОТВЕТ: ВСЕ МОДЕЛИ РАБОЧИЕ И СООТВЕТСТВУЮТ ТРЕБОВАНИЯМ!")
            return True
        else:
            print(f"\n⚠️ ОТВЕТ: Обнаружено {invalid_count} моделей с проблемами из {len(self.models)}")
            return False
    
    def _print_progress(self, current, total, prefix="Прогресс"):
        """Печать прогресс-бара"""
        percent = (current / total) * 100 if total > 0 else 0
        bar_length = 40
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r  {prefix}: [{bar}] {current}/{total} ({percent:.1f}%)", end="", flush=True)
    
    def _get_statistics(self):
        """Получение статистики по моделям"""
        stats = {
            'total': len(self.models),
            'by_category': {},
            'with_endpoints': 0,
            'with_params': 0,
            'with_examples': 0
        }
        
        for model in self.models:
            # По категориям
            cat = model.get('category', 'other')
            stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1
            
            # С endpoint
            if model.get('endpoint'):
                stats['with_endpoints'] += 1
            
            # С параметрами
            if model.get('params'):
                stats['with_params'] += 1
            
            # С примерами
            if model.get('example'):
                stats['with_examples'] += 1
        
        return stats
    
    def filter_models(self, category=None, has_endpoint=None, has_params=None):
        """Фильтрация моделей по критериям"""
        filtered = self.models
        
        if category:
            filtered = [m for m in filtered if m.get('category') == category]
        
        if has_endpoint is not None:
            if has_endpoint:
                filtered = [m for m in filtered if m.get('endpoint')]
            else:
                filtered = [m for m in filtered if not m.get('endpoint')]
        
        if has_params is not None:
            if has_params:
                filtered = [m for m in filtered if m.get('params')]
            else:
                filtered = [m for m in filtered if not m.get('params')]
        
        return filtered
    
    def export_models_by_category(self, output_dir='exports'):
        """Экспорт моделей по категориям в отдельные файлы"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        stats = self._get_statistics()
        exported = {}
        
        for category, models in stats['by_category'].items():
            category_models = [m for m in self.models if m.get('category') == category]
            filename = os.path.join(output_dir, f'models_{category}.json')
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(category_models, f, ensure_ascii=False, indent=2)
            
            exported[category] = len(category_models)
            print(f"   📁 Экспортировано {len(category_models)} моделей категории '{category}' в {filename}")
        
        return exported
    
    def run_full_scrape(self):
        """Полный сбор всех моделей с ответами на каждое действие"""
        self.metrics['start_time'] = time.time()
        
        print("=" * 60)
        print("🚀 ЗАПУСК АВТОМАТИЧЕСКОГО СБОРЩИКА МОДЕЛЕЙ KIE.AI")
        print("=" * 60)
        
        # Действие 1: Сканирование маркета
        print("\n📡 ДЕЙСТВИЕ 1: Сканирование страницы маркета...")
        model_links = self.get_market_page()
        
        if not model_links:
            print("❌ ОТВЕТ: Модели не найдены. Проверьте доступность сайта.")
            return []
        
        print(f"✅ ОТВЕТ: Найдено {len(model_links)} моделей на странице маркета")
        
        # Действие 2: Парсинг документации (параллельно)
        print(f"\n📚 ДЕЙСТВИЕ 2: Парсинг документации моделей...")
        max_models = min(50, len(model_links))  # Увеличиваем лимит для большего покрытия
        print(f"✅ ОТВЕТ: Начинаем парсинг {max_models} моделей (параллельно, {self.max_workers} потоков)")
        
        # Параллельная обработка
        print(f"\n  📊 Прогресс обработки:")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.scrape_model_docs, model['url'], model['name']): model 
                for model in model_links[:max_models]
            }
            
            completed = 0
            successful = 0
            failed = 0
            
            for future in as_completed(futures):
                completed += 1
                model = futures[future]
                try:
                    future.result()  # Получаем результат (может выбросить исключение)
                    successful += 1
                    self.metrics['total_models_processed'] += 1
                except Exception as e:
                    failed += 1
                    self.metrics['failed_requests'] += 1
                    print(f"\n  ❌ Ошибка при обработке '{model['name']}': {e}")
                
                # Обновление прогресс-бара
                self._print_progress(completed, max_models, "Обработка моделей")
        
        print()  # Новая строка после прогресс-бара
        print(f"\n✅ ОТВЕТ: Парсинг завершен")
        print(f"   📊 Успешно: {successful}, Ошибок: {failed}, Всего: {len(self.models)}")
        
        # Действие 3: Валидация всех моделей
        print("\n" + "=" * 60)
        is_valid = self.validate_all_models()
        
        # Подсчет валидных моделей
        valid_count = 0
        invalid_count = 0
        for model in self.models:
            if self._validate_model_structure(model):
                valid_count += 1
            else:
                invalid_count += 1
        
        print("=" * 60)
        
        # Действие 4: Сохранение результатов
        print("\n💾 ДЕЙСТВИЕ 4: Сохранение результатов в файл...")
        output_file = 'kie_full_api.json'
        stats_file = 'kie_scraper_stats.json'
        
        try:
            # Сохранение моделей
            output_path = os.path.join(os.getcwd(), output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.models, f, ensure_ascii=False, indent=2)
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            print(f"✅ ОТВЕТ: Файл {output_file} успешно сохранен ({file_size} байт)")
            
            # Сохранение статистики
            stats_data = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'metrics': {
                    'execution_time_seconds': elapsed_time,
                    'total_requests': self.metrics['total_requests'],
                    'cached_requests': self.metrics['cached_requests'],
                    'failed_requests': self.metrics['failed_requests'],
                    'total_models': len(self.models),
                    'success_rate': f"{(len(self.models) / max_models * 100):.1f}%" if max_models > 0 else "0%"
                },
                'statistics': stats,
                'validation': {
                    'all_valid': is_valid,
                    'valid_count': valid_count,
                    'invalid_count': invalid_count
                }
            }
            
            stats_path = os.path.join(os.getcwd(), stats_file)
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            print(f"✅ ОТВЕТ: Статистика сохранена в {stats_file}")
            
        except (IOError, OSError, PermissionError) as e:
            print(f"❌ ОТВЕТ: Ошибка при сохранении файла: {e}")
            print(f"   📁 Текущая директория: {os.getcwd()}")
            return []
        except Exception as e:
            print(f"❌ ОТВЕТ: Неожиданная ошибка при сохранении: {e}")
            import traceback
            print(f"   📋 Детали: {traceback.format_exc()}")
            return []
        
        # Статистика и метрики
        self.metrics['end_time'] = time.time()
        elapsed_time = self.metrics['end_time'] - self.metrics['start_time']
        stats = self._get_statistics()
        
        # Дополнительный экспорт по категориям (опционально)
        export_categories = os.getenv('EXPORT_BY_CATEGORY', 'false').lower() == 'true'
        if export_categories and self.models:
            print("\n📦 ДЕЙСТВИЕ 5: Экспорт по категориям...")
            exported = self.export_models_by_category()
            print(f"✅ ОТВЕТ: Экспортировано {sum(exported.values())} моделей в {len(exported)} файлов")
        
        # Финальный ответ
        print("\n" + "=" * 60)
        print("🎉 ФИНАЛЬНЫЙ ОТВЕТ:")
        print(f"   ✅ Собрано моделей: {len(self.models)}")
        print(f"   ✅ Валидация: {'ПРОЙДЕНА' if is_valid else 'ЕСТЬ ОШИБКИ'}")
        print(f"   ✅ Файл сохранен: {output_file}")
        print(f"   ✅ Статистика сохранена: {stats_file}")
        if export_categories:
            print(f"   ✅ Экспорт по категориям: выполнено")
        print("\n📊 СТАТИСТИКА:")
        print(f"   ⏱️ Время выполнения: {elapsed_time:.2f} сек")
        print(f"   📡 Всего запросов: {self.metrics['total_requests']}")
        print(f"   💾 Кэшированных: {self.metrics['cached_requests']}")
        print(f"   ❌ Ошибок: {self.metrics['failed_requests']}")
        if self.metrics['total_requests'] > 0:
            cache_hit_rate = (self.metrics['cached_requests'] / self.metrics['total_requests']) * 100
            print(f"   📈 Эффективность кэша: {cache_hit_rate:.1f}%")
        print(f"\n📂 По категориям:")
        for cat, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(self.models) * 100) if self.models else 0
            print(f"   - {cat}: {count} ({percentage:.1f}%)")
        print(f"\n📋 Детали:")
        print(f"   - С endpoint: {stats['with_endpoints']} ({stats['with_endpoints']/len(self.models)*100:.1f}%)" if self.models else "   - С endpoint: 0")
        print(f"   - С параметрами: {stats['with_params']} ({stats['with_params']/len(self.models)*100:.1f}%)" if self.models else "   - С параметрами: 0")
        print(f"   - С примерами: {stats['with_examples']} ({stats['with_examples']/len(self.models)*100:.1f}%)" if self.models else "   - С примерами: 0")
        print("=" * 60)
        
        return self.models

# === ЗАПУСК ОДНОЙ КНОПКОЙ ===
if __name__ == "__main__":
    try:
        print("\n" + "=" * 60)
        print("🎯 ИНИЦИАЛИЗАЦИЯ СКРИПТА...")
        print("=" * 60)
        
        # Проверка окружения
        print(f"🐍 Python версия: {sys.version}")
        print(f"📁 Рабочая директория: {os.getcwd()}")
        print(f"🌍 Кодировка stdout: {sys.stdout.encoding}")
        
        scraper = KieApiScraper()
        print("✅ ОТВЕТ: Класс KieApiScraper инициализирован")
        print(f"   📡 Base URL: {scraper.base_url}")
        print(f"   🌐 Market URL: {scraper.market_url}")
        
        models = scraper.run_full_scrape()
        
        # Действие 5: Показ примеров
        print("\n📋 ДЕЙСТВИЕ 5: Отображение примеров моделей...")
        if models:
            print(f"✅ ОТВЕТ: Показываем первые {min(5, len(models))} моделей из {len(models)}")
            print("\n" + "=" * 60)
            for i, model in enumerate(models[:5], 1):
                try:
                    print(f"\n📦 Модель {i}: {model['name']}")
                    print(f"   🔗 Endpoint: {model['endpoint'] or 'не найден'}")
                    print(f"   📝 Method: {model['method']}")
                    print(f"   🌐 Base URL: {model['base_url']}")
                    print(f"   📂 Категория: {model.get('category', 'other')}")
                    if model.get('params'):
                        print(f"   ⚙️ Параметры: {model['params']}")
                    if model.get('input_schema'):
                        required = model['input_schema'].get('required', [])
                        if required:
                            print(f"   📋 Обязательные поля: {', '.join(required)}")
                    if model.get('example_request'):
                        print(f"   💡 Пример запроса:")
                        print(f"      {json.dumps(model['example_request'], ensure_ascii=False, indent=6)}")
                    elif model.get('example'):
                        example_str = str(model['example'])
                        print(f"   💡 Пример: {example_str[:150]}...")
                    print()
                except (KeyError, TypeError, UnicodeEncodeError) as e:
                    print(f"   ⚠️ Ошибка при выводе модели {i}: {e}")
                    continue
            
            print("=" * 60)
            print(f"\n✅ ОТВЕТ: Все действия выполнены успешно!")
        else:
            print("❌ ОТВЕТ: Модели не были собраны. Проверьте логи выше.")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ ОТВЕТ: Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        print(f"📋 Детали ошибки:\n{traceback.format_exc()}")
        sys.exit(1)


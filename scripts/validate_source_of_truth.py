#!/usr/bin/env python3
"""
🔍 ВАЛИДАТОР SOURCE_OF_TRUTH

Проверяет корректность models/KIE_SOURCE_OF_TRUTH.json:
- Обязательные поля присутствуют
- Pricing корректен
- Input schema валиден
- Нет дубликатов model_id
- Examples корректны
- Metadata актуальна

Exit codes:
- 0: Все проверки прошли
- 1: Найдены ошибки
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Set
from datetime import datetime


class ValidationError:
    """Ошибка валидации"""
    def __init__(self, severity: str, model_id: str, field: str, message: str):
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW
        self.model_id = model_id
        self.field = field
        self.message = message
    
    def __str__(self):
        return f'[{self.severity}] {self.model_id}.{self.field}: {self.message}'


class SourceOfTruthValidator:
    """Валидатор SOURCE_OF_TRUTH.json"""
    
    # Обязательные поля для каждой модели
    REQUIRED_MODEL_FIELDS = {
        'model_id', 'display_name', 'description', 'category', 
        'provider', 'endpoint', 'source_url', 'examples', 
        'input_schema', 'pricing'
    }
    
    # Обязательные поля pricing
    REQUIRED_PRICING_FIELDS = {'usd_per_gen', 'rub_per_gen', 'is_free', 'source'}
    
    # Валидные категории
    VALID_CATEGORIES = {
        'image', 'video', 'audio', 'music', 'avatar', 
        'enhance', 'other'
    }
    
    def __init__(self, source_of_truth_path: str = 'models/KIE_SOURCE_OF_TRUTH.json'):
        self.path = Path(source_of_truth_path)
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.stats = {
            'total_models': 0,
            'valid_models': 0,
            'models_with_warnings': 0,
            'models_with_errors': 0
        }
    
    def add_error(self, severity: str, model_id: str, field: str, message: str):
        """Добавить ошибку"""
        error = ValidationError(severity, model_id, field, message)
        if severity in ['CRITICAL', 'HIGH']:
            self.errors.append(error)
        else:
            self.warnings.append(error)
    
    def validate(self) -> bool:
        """
        Запустить все проверки.
        
        Returns:
            True если валидация прошла (нет критичных ошибок)
        """
        print('='*100)
        print('🔍 ВАЛИДАЦИЯ SOURCE_OF_TRUTH')
        print('='*100)
        print()
        
        # Load file
        if not self.path.exists():
            print(f'❌ CRITICAL: Файл не найден: {self.path}')
            return False
        
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f'❌ CRITICAL: Невалидный JSON: {e}')
            return False
        except Exception as e:
            print(f'❌ CRITICAL: Ошибка чтения файла: {e}')
            return False
        
        print(f'✅ Файл загружен: {self.path}')
        print()
        
        # Run validations
        self._validate_root_structure(data)
        self._validate_metadata(data)
        self._validate_models(data.get('models', {}))
        self._validate_duplicates(data.get('models', {}))
        self._validate_pricing_consistency(data.get('models', {}))
        self._validate_free_models(data.get('models', {}))
        
        # Print results
        self._print_results()
        
        return len(self.errors) == 0
    
    def _validate_root_structure(self, data: Dict):
        """Проверка корневой структуры"""
        print('📋 Проверка корневой структуры...')
        
        required_root_fields = {'version', 'total_models', 'models'}
        missing = required_root_fields - set(data.keys())
        
        if missing:
            self.add_error('CRITICAL', 'ROOT', 'structure', 
                          f'Отсутствуют обязательные поля: {missing}')
        
        # Check total_models matches
        if 'models' in data and 'total_models' in data:
            actual_count = len(data['models'])
            declared_count = data['total_models']
            if actual_count != declared_count:
                self.add_error('HIGH', 'ROOT', 'total_models',
                              f'Несоответствие: declared={declared_count}, actual={actual_count}')
        
        print(f'   Version: {data.get("version", "N/A")}')
        print(f'   Total models: {data.get("total_models", 0)}')
        print()
    
    def _validate_metadata(self, data: Dict):
        """Проверка метаданных"""
        print('📅 Проверка метаданных...')
        
        # Optional but recommended
        if 'timestamp' not in data:
            self.add_error('MEDIUM', 'ROOT', 'timestamp', 
                          'Отсутствует timestamp (рекомендуется для tracking)')
        
        if 'last_parser_run' not in data:
            self.add_error('LOW', 'ROOT', 'last_parser_run',
                          'Отсутствует last_parser_run (рекомендуется)')
        
        if 'parser_version' not in data:
            self.add_error('LOW', 'ROOT', 'parser_version',
                          'Отсутствует parser_version (рекомендуется)')
        
        print()
    
    def _validate_models(self, models: Dict[str, Any]):
        """Проверка каждой модели"""
        print(f'🔍 Проверка {len(models)} моделей...')
        self.stats['total_models'] = len(models)
        
        for model_id, model_data in models.items():
            errors_before = len(self.errors)
            warnings_before = len(self.warnings)
            
            self._validate_model(model_id, model_data)
            
            errors_added = len(self.errors) - errors_before
            warnings_added = len(self.warnings) - warnings_before
            
            if errors_added > 0:
                self.stats['models_with_errors'] += 1
            elif warnings_added > 0:
                self.stats['models_with_warnings'] += 1
            else:
                self.stats['valid_models'] += 1
        
        print()
    
    def _validate_model(self, model_id: str, model_data: Dict):
        """Проверка одной модели"""
        # Check model_id matches key
        if model_data.get('model_id') != model_id:
            self.add_error('HIGH', model_id, 'model_id',
                          f'Несоответствие: key={model_id}, value={model_data.get("model_id")}')
        
        # Check required fields
        missing_fields = self.REQUIRED_MODEL_FIELDS - set(model_data.keys())
        if missing_fields:
            self.add_error('CRITICAL', model_id, 'fields',
                          f'Отсутствуют обязательные поля: {missing_fields}')
            return  # Skip further checks if critical fields missing
        
        # Validate category
        category = model_data.get('category')
        if category not in self.VALID_CATEGORIES:
            self.add_error('HIGH', model_id, 'category',
                          f'Невалидная категория: {category}. Валидные: {self.VALID_CATEGORIES}')
        
        # Validate pricing
        self._validate_model_pricing(model_id, model_data.get('pricing', {}))
        
        # Validate input_schema
        self._validate_input_schema(model_id, model_data.get('input_schema', {}))
        
        # Validate examples
        self._validate_examples(model_id, model_data.get('examples', []))
        
        # Validate endpoint
        endpoint = model_data.get('endpoint', '')
        if not endpoint:
            self.add_error('CRITICAL', model_id, 'endpoint', 'Пустой endpoint')
        elif not endpoint.startswith('/'):
            self.add_error('MEDIUM', model_id, 'endpoint',
                          f'Endpoint должен начинаться с /: {endpoint}')
        
        # Validate source_url
        source_url = model_data.get('source_url', '')
        if not source_url.startswith('https://docs.kie.ai'):
            self.add_error('MEDIUM', model_id, 'source_url',
                          'source_url должен быть ссылкой на docs.kie.ai')
    
    def _validate_model_pricing(self, model_id: str, pricing: Dict):
        """Проверка pricing модели"""
        missing = self.REQUIRED_PRICING_FIELDS - set(pricing.keys())
        if missing:
            self.add_error('CRITICAL', model_id, 'pricing',
                          f'Отсутствуют поля pricing: {missing}')
            return
        
        # Check types
        usd = pricing.get('usd_per_gen')
        rub = pricing.get('rub_per_gen')
        is_free = pricing.get('is_free')
        
        if not isinstance(usd, (int, float)):
            self.add_error('HIGH', model_id, 'pricing.usd_per_gen',
                          f'Должен быть числом: {type(usd).__name__}')
        
        if not isinstance(rub, (int, float)):
            self.add_error('HIGH', model_id, 'pricing.rub_per_gen',
                          f'Должен быть числом: {type(rub).__name__}')
        
        if not isinstance(is_free, bool):
            self.add_error('HIGH', model_id, 'pricing.is_free',
                          f'Должен быть boolean: {type(is_free).__name__}')
        
        # Check values
        if isinstance(usd, (int, float)) and usd < 0:
            self.add_error('HIGH', model_id, 'pricing.usd_per_gen',
                          f'Отрицательная цена: {usd}')
        
        if isinstance(rub, (int, float)) and rub < 0:
            self.add_error('HIGH', model_id, 'pricing.rub_per_gen',
                          f'Отрицательная цена: {rub}')
        
        # Check free flag consistency
        if isinstance(is_free, bool) and isinstance(rub, (int, float)):
            if is_free and rub > 1.0:  # FREE модели должны быть дешевле 1 RUB
                self.add_error('MEDIUM', model_id, 'pricing.is_free',
                              f'Модель помечена FREE но стоит {rub} RUB')
    
    def _validate_input_schema(self, model_id: str, input_schema: Dict):
        """Проверка input_schema"""
        if not input_schema:
            self.add_error('HIGH', model_id, 'input_schema', 'Пустая схема')
            return
        
        # Detect schema format: V7 (flat) or V8 (nested with input field)
        # V8: has 'input' field that is a dict with 'type' and 'examples'
        # V7: fields like 'prompt', 'model' directly with type/required/examples
        
        input_field = input_schema.get('input')
        
        if input_field and isinstance(input_field, dict) and 'type' in input_field:
            # This is V8 nested format
            expected_top_level = {'model', 'callBackUrl', 'input'}
            if not expected_top_level.issubset(input_schema.keys()):
                missing = expected_top_level - set(input_schema.keys())
                self.add_error('HIGH', model_id, 'input_schema',
                              f'V8 schema: отсутствуют поля: {missing}')
            
            # Check input field structure
            if not input_field:
                self.add_error('HIGH', model_id, 'input_schema.input', 'Пустое поле input')
            else:
                # input должен иметь type и examples
                if 'type' not in input_field:
                    self.add_error('MEDIUM', model_id, 'input_schema.input.type',
                                  'Отсутствует type')
                if 'examples' not in input_field:
                    self.add_error('MEDIUM', model_id, 'input_schema.input.examples',
                                  'Отсутствует examples')
                elif not isinstance(input_field['examples'], list):
                    self.add_error('HIGH', model_id, 'input_schema.input.examples',
                                  'examples должен быть list')
        else:
            # V7 format (flat): fields directly in schema with type/required/examples structure
            # Just check it's not empty and has some field definitions
            if len(input_schema) == 0:
                self.add_error('HIGH', model_id, 'input_schema',
                              'V7 schema пустая')
            # V7 format is valid, no further checks needed
    
    def _validate_examples(self, model_id: str, examples: List):
        """Проверка examples"""
        if not examples:
            self.add_error('MEDIUM', model_id, 'examples', 'Нет примеров')
            return
        
        if not isinstance(examples, list):
            self.add_error('HIGH', model_id, 'examples',
                          f'examples должен быть list: {type(examples).__name__}')
            return
        
        # Check each example
        for i, example in enumerate(examples):
            if not isinstance(example, dict):
                self.add_error('HIGH', model_id, f'examples[{i}]',
                              'example должен быть dict')
                continue
            
            # Example должен содержать model
            # (input опционален для V7 API где параметры напрямую в example)
            if 'model' not in example:
                self.add_error('MEDIUM', model_id, f'examples[{i}].model',
                              'Отсутствует поле model')
            
            # For V8 (nested), example должен иметь input
            # For V7 (flat), параметры прямо в example
            has_input = 'input' in example
            has_direct_params = any(k not in ['model', 'callBackUrl', 'callback'] for k in example.keys())
            
            if not has_input and not has_direct_params:
                self.add_error('HIGH', model_id, f'examples[{i}]',
                              'Нет ни input поля, ни прямых параметров')
    
    def _validate_duplicates(self, models: Dict):
        """Проверка на дубликаты model_id"""
        print('🔍 Проверка дубликатов...')
        
        model_ids: Set[str] = set()
        duplicates: List[str] = []
        
        for key, model_data in models.items():
            model_id = model_data.get('model_id', key)
            if model_id in model_ids:
                duplicates.append(model_id)
                self.add_error('CRITICAL', model_id, 'model_id',
                              'Дубликат model_id')
            model_ids.add(model_id)
        
        if duplicates:
            print(f'   ❌ Найдены дубликаты: {duplicates}')
        else:
            print(f'   ✅ Дубликатов не найдено')
        
        print()
    
    def _validate_pricing_consistency(self, models: Dict):
        """Проверка консистентности pricing"""
        print('💰 Проверка консистентности pricing...')
        
        total_with_pricing = 0
        total_free = 0
        min_price = float('inf')
        max_price = 0
        
        for model_id, model_data in models.items():
            pricing = model_data.get('pricing', {})
            if not pricing:
                continue
            
            total_with_pricing += 1
            
            rub = pricing.get('rub_per_gen', 0)
            is_free = pricing.get('is_free', False)
            
            if is_free:
                total_free += 1
            
            if isinstance(rub, (int, float)) and rub > 0:
                min_price = min(min_price, rub)
                max_price = max(max_price, rub)
        
        print(f'   Моделей с pricing: {total_with_pricing}/{len(models)}')
        print(f'   FREE моделей: {total_free}')
        if min_price != float('inf'):
            print(f'   Цена: {min_price:.2f} - {max_price:.2f} RUB')
        
        print()
    
    def _validate_free_models(self, models: Dict):
        """Проверка FREE моделей"""
        print('🆓 Проверка FREE моделей...')
        
        # Collect all prices
        prices = []
        for model_id, model_data in models.items():
            pricing = model_data.get('pricing', {})
            rub = pricing.get('rub_per_gen', 0)
            is_free = pricing.get('is_free', False)
            if isinstance(rub, (int, float)) and rub > 0:
                prices.append({
                    'model_id': model_id,
                    'price': rub,
                    'is_free': is_free
                })
        
        # Sort by price
        prices.sort(key=lambda x: x['price'])
        
        # Top-5 cheapest should be FREE
        top5 = prices[:5]
        
        print(f'   Топ-5 самых дешевых:')
        for i, item in enumerate(top5, 1):
            status = '✅' if item['is_free'] else '⚠️'
            print(f'      {i}. {item["model_id"]}: {item["price"]:.2f} RUB {status}')
            
            # Warning if not marked as free
            if not item['is_free']:
                self.add_error('MEDIUM', item['model_id'], 'pricing.is_free',
                              f'Топ-5 дешевая модель ({item["price"]:.2f} RUB) не помечена is_free')
        
        print()
    
    def _print_results(self):
        """Вывод результатов валидации"""
        print('='*100)
        print('📊 РЕЗУЛЬТАТЫ ВАЛИДАЦИИ')
        print('='*100)
        print()
        
        # Stats
        print('📈 Статистика:')
        print(f'   Всего моделей: {self.stats["total_models"]}')
        print(f'   ✅ Валидных: {self.stats["valid_models"]} ({self.stats["valid_models"]/max(1,self.stats["total_models"])*100:.1f}%)')
        print(f'   ⚠️  С предупреждениями: {self.stats["models_with_warnings"]}')
        print(f'   ❌ С ошибками: {self.stats["models_with_errors"]}')
        print()
        
        # Errors
        if self.errors:
            print(f'❌ ОШИБКИ ({len(self.errors)}):')
            for error in self.errors[:20]:  # Show first 20
                print(f'   {error}')
            if len(self.errors) > 20:
                print(f'   ... и еще {len(self.errors) - 20} ошибок')
            print()
        
        # Warnings
        if self.warnings:
            print(f'⚠️  ПРЕДУПРЕЖДЕНИЯ ({len(self.warnings)}):')
            for warning in self.warnings[:10]:  # Show first 10
                print(f'   {warning}')
            if len(self.warnings) > 10:
                print(f'   ... и еще {len(self.warnings) - 10} предупреждений')
            print()
        
        # Summary
        print('='*100)
        if not self.errors and not self.warnings:
            print('✅ ВАЛИДАЦИЯ ПРОШЛА УСПЕШНО')
        elif not self.errors:
            print(f'⚠️  ВАЛИДАЦИЯ ПРОШЛА С ПРЕДУПРЕЖДЕНИЯМИ ({len(self.warnings)})')
        else:
            print(f'❌ ВАЛИДАЦИЯ НЕ ПРОШЛА ({len(self.errors)} ошибок)')
        print('='*100)


def main():
    """Main entry point"""
    validator = SourceOfTruthValidator()
    success = validator.validate()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

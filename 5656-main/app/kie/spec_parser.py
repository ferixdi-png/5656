"""
Парсер документации моделей KIE AI из Markdown файлов.

Парсит файлы *_INTEGRATION.md и извлекает:
- model_id
- endpoints (createTask, recordInfo)
- input schema (поля, типы, required/optional, options, defaults, max length)
- output parsing (resultUrls vs resultObject)
- states (waiting/success/fail)
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class InputField:
    """Поле входного параметра модели."""
    name: str
    type: str  # string, number, boolean, object
    required: bool
    description: str = ""
    max_length: Optional[int] = None
    options: Optional[List[str]] = None
    default: Optional[Any] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None


@dataclass
class ModelSpec:
    """Спецификация модели из документации."""
    model_id: str
    create_endpoint: str  # POST /api/v1/jobs/createTask
    record_endpoint: str  # GET /api/v1/jobs/recordInfo?taskId=
    input_schema: Dict[str, InputField]
    output_media_type: str  # "media_urls" или "text_object"
    states: List[str]  # ["waiting", "success", "fail"]
    title_ru: Optional[str] = None
    description: Optional[str] = None


def parse_integration_md(file_path: Path) -> Optional[ModelSpec]:
    """
    Парсит файл *_INTEGRATION.md и извлекает спецификацию модели.
    
    Args:
        file_path: Путь к файлу документации
    
    Returns:
        ModelSpec или None если не удалось распарсить
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Не удалось прочитать {file_path}: {e}")
        return None
    
    # Извлекаем model_id из заголовка или секции API Документация
    model_id = _extract_model_id(content)
    if not model_id:
        logger.warning(f"Не найден model_id в {file_path}")
        return None
    
    # Извлекаем endpoints
    create_endpoint = _extract_create_endpoint(content)
    record_endpoint = _extract_record_endpoint(content)
    
    if not create_endpoint or not record_endpoint:
        logger.warning(f"Не найдены endpoints в {file_path}")
        return None
    
    # Извлекаем input schema
    input_schema = _extract_input_schema(content)
    
    # Определяем output_media_type
    output_media_type = _extract_output_media_type(content)
    
    # Извлекаем states
    states = _extract_states(content)
    
    # Извлекаем title_ru из заголовка
    title_ru = _extract_title_ru(content, model_id)
    
    # Извлекаем описание
    description = _extract_description(content)
    
    return ModelSpec(
        model_id=model_id,
        create_endpoint=create_endpoint,
        record_endpoint=record_endpoint,
        input_schema=input_schema,
        output_media_type=output_media_type,
        states=states,
        title_ru=title_ru,
        description=description
    )


def _extract_model_id(content: str) -> Optional[str]:
    """Извлекает model_id из документации."""
    # Паттерн 1: "Модель: `google/imagen4`"
    pattern1 = r'Модель[:\s]+`([^`]+)`'
    match = re.search(pattern1, content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Паттерн 2: "**Модель**: `google/imagen4`"
    pattern2 = r'\*\*Модель\*\*[:\s]+`([^`]+)`'
    match = re.search(pattern2, content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Паттерн 3: В примере запроса "model": "google/imagen4"
    pattern3 = r'"model"\s*:\s*"([^"]+)"'
    match = re.search(pattern3, content)
    if match:
        return match.group(1).strip()
    
    # Паттерн 4: В заголовке файла или первой строке
    pattern4 = r'`([a-z0-9_\-]+/[a-z0-9_\-]+)`'
    match = re.search(pattern4, content[:500])
    if match:
        return match.group(1).strip()
    
    return None


def _extract_create_endpoint(content: str) -> str:
    """Извлекает create endpoint."""
    # По умолчанию все используют один endpoint
    pattern = r'POST\s+https://api\.kie\.ai/api/v1/jobs/createTask'
    if re.search(pattern, content, re.IGNORECASE):
        return "POST https://api.kie.ai/api/v1/jobs/createTask"
    
    # Fallback
    return "POST https://api.kie.ai/api/v1/jobs/createTask"


def _extract_record_endpoint(content: str) -> str:
    """Извлекает record endpoint."""
    # По умолчанию все используют один endpoint
    pattern = r'GET\s+https://api\.kie\.ai/api/v1/jobs/recordInfo'
    if re.search(pattern, content, re.IGNORECASE):
        return "GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId={taskId}"
    
    # Fallback
    return "GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId={taskId}"


def _extract_input_schema(content: str) -> Dict[str, InputField]:
    """Извлекает схему входных параметров из таблиц."""
    schema = {}
    
    # Ищем секцию "Обязательные параметры"
    required_section = re.search(
        r'### Обязательные параметры.*?(?=###|##|$)', 
        content, 
        re.DOTALL | re.IGNORECASE
    )
    
    # Ищем секцию "Опциональные параметры"
    optional_section = re.search(
        r'### Опциональные параметры.*?(?=###|##|$)', 
        content, 
        re.DOTALL | re.IGNORECASE
    )
    
    # Парсим таблицы параметров
    table_pattern = r'\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|'
    
    # Парсим обязательные параметры
    if required_section:
        required_table = required_section.group(0)
        for line in required_table.split('\n'):
            if '|' in line and 'input.' in line.lower():
                field = _parse_table_row(line, required=True)
                if field:
                    schema[field.name] = field
    
    # Парсим опциональные параметры
    if optional_section:
        optional_table = optional_section.group(0)
        for line in optional_table.split('\n'):
            if '|' in line and 'input.' in line.lower():
                field = _parse_table_row(line, required=False)
                if field:
                    schema[field.name] = field
    
    # Парсим секцию "Допустимые значения" для дополнительных деталей
    allowed_section = re.search(
        r'### Допустимые значения.*?(?=###|##|$)', 
        content, 
        re.DOTALL | re.IGNORECASE
    )
    
    if allowed_section:
        _enrich_schema_from_allowed_values(schema, allowed_section.group(0))
    
    return schema


def _parse_table_row(line: str, required: bool) -> Optional[InputField]:
    """Парсит строку таблицы параметров."""
    # Убираем лишние пробелы и разделяем по |
    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 4:
        return None
    
    # Формат: | `input.prompt` | string | Описание | Ограничения |
    # или: | `input.prompt` | string | Описание | Значения по умолчанию |
    
    name_part = parts[1] if len(parts) > 1 else ""
    type_part = parts[2] if len(parts) > 2 else ""
    desc_part = parts[3] if len(parts) > 3 else ""
    constraints_part = parts[4] if len(parts) > 4 else ""
    
    # Извлекаем имя поля
    name_match = re.search(r'`?input\.([^`\s|]+)`?', name_part)
    if not name_match:
        return None
    
    field_name = name_match.group(1)
    
    # Извлекаем тип
    field_type = "string"  # default
    if 'number' in type_part.lower() or 'число' in type_part.lower():
        field_type = "number"
    elif 'boolean' in type_part.lower() or 'bool' in type_part.lower():
        field_type = "boolean"
    elif 'object' in type_part.lower():
        field_type = "object"
    
    # Извлекаем ограничения
    max_length = None
    options = None
    default = None
    min_value = None
    max_value = None
    step = None
    
    # Парсим constraints_part
    if constraints_part:
        # Максимум символов
        max_match = re.search(r'максимум\s+(\d+)\s+символов?', constraints_part, re.IGNORECASE)
        if max_match:
            max_length = int(max_match.group(1))
        
        # Enum значения
        options_match = re.search(r'`([^`]+)`', constraints_part)
        if options_match:
            # Может быть несколько значений через запятую
            options_str = options_match.group(1)
            if ',' in options_str or 'или' in options_str.lower():
                # Парсим список
                options = [opt.strip().strip('"\'') for opt in re.split(r'[,или]', options_str)]
            else:
                options = [options_str.strip().strip('"\'')]
        
        # Default значение
        default_match = re.search(r'default[:\s]+`?([^`\s,]+)`?', constraints_part, re.IGNORECASE)
        if default_match:
            default_str = default_match.group(1).strip('"\'')
            # Пробуем преобразовать в нужный тип
            if field_type == "number":
                try:
                    default = float(default_str)
                    if default.is_integer():
                        default = int(default)
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Could not convert default to int: {e}")
                    default = default_str
            elif field_type == "boolean":
                default = default_str.lower() in ('true', '1', 'yes', 'да')
            else:
                default = default_str
    
    # Парсим desc_part для дополнительных ограничений
    if desc_part:
        # Диапазон для чисел
        range_match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', desc_part)
        if range_match:
            min_value = float(range_match.group(1))
            max_value = float(range_match.group(2))
        
        # Шаг
        step_match = re.search(r'шаг[:\s]+(\d+(?:\.\d+)?)', desc_part, re.IGNORECASE)
        if step_match:
            step = float(step_match.group(1))
    
    return InputField(
        name=field_name,
        type=field_type,
        required=required,
        description=desc_part,
        max_length=max_length,
        options=options,
        default=default,
        min_value=min_value,
        max_value=max_value,
        step=step
    )


def _enrich_schema_from_allowed_values(schema: Dict[str, InputField], section: str):
    """Обогащает схему данными из секции 'Допустимые значения'."""
    # Ищем блоки для каждого поля
    field_pattern = r'####\s+`?([^`\n]+)`?.*?(?=####|###|##|$)'
    
    for match in re.finditer(field_pattern, section, re.DOTALL | re.IGNORECASE):
        field_name_raw = match.group(1).strip()
        field_content = match.group(0)
        
        # Извлекаем имя поля (убираем backticks)
        field_name = re.sub(r'[`\s]', '', field_name_raw)
        
        if field_name not in schema:
            continue
        
        field = schema[field_name]
        
        # Парсим значения enum
        options_match = re.search(r'Значения[:\s]+`([^`]+)`', field_content, re.IGNORECASE)
        if options_match:
            options_str = options_match.group(1)
            # Разделяем по запятым или пробелам
            options = [opt.strip().strip('"\'') for opt in re.split(r'[,`\s]+', options_str) if opt.strip()]
            if options:
                field.options = options
        
        # Парсим default
        default_match = re.search(r'Default[:\s]+`([^`]+)`', field_content, re.IGNORECASE)
        if default_match:
            default_str = default_match.group(1).strip('"\'')
            if field.type == "number":
                try:
                    field.default = float(default_str)
                    if field.default.is_integer():
                        field.default = int(field.default)
                except (ValueError, AttributeError) as e:
                    logger.debug(f"Could not convert field.default to int: {e}")
                    field.default = default_str
            elif field.type == "boolean":
                field.default = default_str.lower() in ('true', '1', 'yes', 'да')
            else:
                field.default = default_str
        
        # Парсим max length
        max_match = re.search(r'Максимум[:\s]+(\d+)\s+символов?', field_content, re.IGNORECASE)
        if max_match:
            field.max_length = int(max_match.group(1))
        
        # Парсим диапазон
        range_match = re.search(r'Диапазон[:\s]+(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', field_content, re.IGNORECASE)
        if range_match:
            field.min_value = float(range_match.group(1))
            field.max_value = float(range_match.group(2))
        
        # Парсим шаг
        step_match = re.search(r'шаг[:\s]+(\d+(?:\.\d+)?)', field_content, re.IGNORECASE)
        if step_match:
            field.step = float(step_match.group(1))


def _extract_output_media_type(content: str) -> str:
    """Определяет тип выходных данных (media_urls или text_object)."""
    # Ищем упоминания resultUrls
    if re.search(r'resultUrls', content, re.IGNORECASE):
        return "media_urls"
    
    # Ищем упоминания resultObject
    if re.search(r'resultObject', content, re.IGNORECASE):
        return "text_object"
    
    # По умолчанию для большинства моделей это media_urls
    # Но проверяем по типу модели
    if any(keyword in content.lower() for keyword in ['video', 'image', 'audio', 'media']):
        return "media_urls"
    
    # Fallback
    return "media_urls"


def _extract_states(content: str) -> List[str]:
    """Извлекает возможные состояния задачи."""
    # Стандартные состояния для всех моделей
    states = ["waiting", "success", "fail"]
    
    # Проверяем упоминания в документации
    if re.search(r'waiting|success|fail', content, re.IGNORECASE):
        return states
    
    return states


def _extract_title_ru(content: str, model_id: str) -> str:
    """Извлекает русское название модели."""
    # Пробуем из заголовка
    title_match = re.search(r'^#\s+Интеграция\s+([^\n]+)', content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        # Убираем backticks
        title = re.sub(r'[`]', '', title)
        return title
    
    # Fallback: генерируем из model_id
    parts = model_id.split('/')
    if len(parts) == 2:
        provider, model = parts
        return f"{provider.title()} {model.replace('-', ' ').title()}"
    
    return model_id


def _extract_description(content: str) -> Optional[str]:
    """Извлекает описание модели."""
    # Ищем секцию "Обзор"
    overview_match = re.search(
        r'## 📋 Обзор\s*\n\s*\n(.+?)(?=##|$)',
        content,
        re.DOTALL
    )
    
    if overview_match:
        desc = overview_match.group(1).strip()
        # Убираем markdown форматирование
        desc = re.sub(r'[#*`]', '', desc)
        return desc[:500]  # Ограничиваем длину
    
    return None


def parse_all_integration_docs(docs_dir: Path) -> Dict[str, ModelSpec]:
    """
    Парсит все файлы *_INTEGRATION.md из директории.
    
    Args:
        docs_dir: Путь к директории с документацией
    
    Returns:
        Словарь {model_id: ModelSpec}
    """
    registry = {}
    
    if not docs_dir.exists():
        logger.error(f"Директория {docs_dir} не существует")
        return registry
    
    # Ищем все файлы *_INTEGRATION.md
    integration_files = list(docs_dir.glob("*_INTEGRATION.md"))
    
    logger.info(f"Найдено {len(integration_files)} файлов документации")
    
    for file_path in integration_files:
        spec = parse_integration_md(file_path)
        if spec:
            if spec.model_id in registry:
                logger.warning(f"Дубликат model_id {spec.model_id} в {file_path}")
            else:
                registry[spec.model_id] = spec
                logger.debug(f"Парсинг успешен: {spec.model_id}")
        else:
            logger.warning(f"Не удалось распарсить {file_path}")
    
    logger.info(f"Успешно распарсено {len(registry)} моделей")
    
    return registry


def model_spec_to_dict(spec: ModelSpec) -> Dict[str, Any]:
    """Конвертирует ModelSpec в словарь для JSON сериализации."""
    result = {
        "model_id": spec.model_id,
        "create_endpoint": spec.create_endpoint,
        "record_endpoint": spec.record_endpoint,
        "input_schema": {},
        "output_media_type": spec.output_media_type,
        "states": spec.states,
    }
    
    if spec.title_ru:
        result["title_ru"] = spec.title_ru
    
    if spec.description:
        result["description"] = spec.description
    
    # Конвертируем InputField в словари
    for field_name, field in spec.input_schema.items():
        field_dict = {
            "name": field.name,
            "type": field.type,
            "required": field.required,
            "description": field.description,
        }
        
        if field.max_length is not None:
            field_dict["max_length"] = field.max_length
        
        if field.options is not None:
            field_dict["options"] = field.options
        
        if field.default is not None:
            field_dict["default"] = field.default
        
        if field.min_value is not None:
            field_dict["min_value"] = field.min_value
        
        if field.max_value is not None:
            field_dict["max_value"] = field.max_value
        
        if field.step is not None:
            field_dict["step"] = field.step
        
        result["input_schema"][field_name] = field_dict
    
    return result








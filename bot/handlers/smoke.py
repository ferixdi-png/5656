"""Smoke generation harness for admin use."""
from __future__ import annotations

import logging
import os
import random

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.kie.generator import KieGenerator
from app.kie.builder import load_source_of_truth

router = Router(name="smoke")
logger = logging.getLogger(__name__)


def _sample_value(field_spec: dict) -> object:
    field_type = field_spec.get("type", "string")
    if "enum" in field_spec and field_spec["enum"]:
        return field_spec["enum"][0]
    if field_type in {"integer", "int"}:
        return int(field_spec.get("minimum", 1))
    if field_type in {"number", "float"}:
        return float(field_spec.get("minimum", 1))
    if field_type in {"boolean", "bool"}:
        return True
    if field_type in {"url", "link", "source_url"}:
        return "https://example.com/input"
    if field_type in {"file", "file_id", "file_url"}:
        return "https://example.com/file.png"
    return "test"


def _build_user_inputs(model_schema: dict) -> dict:
    input_schema = model_schema.get("input_schema", {})
    required_fields = input_schema.get("required", [])
    properties = input_schema.get("properties", {})
    user_inputs = {}
    for field_name in required_fields:
        field_spec = properties.get(field_name, {})
        user_inputs[field_name] = _sample_value(field_spec)
    return user_inputs


@router.message(Command("smoke"))
async def smoke_cmd(message: Message) -> None:
    allow = os.getenv("ALLOW_REAL_GENERATION", "0") == "1"
    admin_id = os.getenv("ADMIN_ID")
    if not allow or not admin_id or str(message.from_user.id) != admin_id:
        await message.answer("⚠️ Команда недоступна.")
        return

    source = load_source_of_truth()
    models = source.get("models", [])
    if not models:
        await message.answer("⚠️ Модели не найдены.")
        return

    categories = {}
    for model in models:
        category = model.get("category", "other")
        categories.setdefault(category, []).append(model)

    picks = []
    for category, items in categories.items():
        picks.append(random.choice(items))
        if len(picks) >= 3:
            break

    generator = KieGenerator()
    results = []
    for model in picks:
        model_id = model.get("model_id")
        user_inputs = _build_user_inputs(model)
        await message.answer(f"🔎 Smoke: {model_id}")
        result = await generator.generate(model_id, user_inputs)
        results.append((model_id, result.get("success"), result.get("message")))

    lines = [f"{model_id}: {'✅' if success else '❌'} {msg}" for model_id, success, msg in results]
    await message.answer("\n".join(lines))

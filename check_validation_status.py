"""Проверка статуса валидации для всех моделей"""
import re
import os
import sys
import io

# Устанавливаем UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Читаем все модели из kie_models.py
with open('kie_models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Извлекаем все ID моделей
model_ids = re.findall(r'"id":\s*"([^"]+)"', content)
model_ids = sorted(set(model_ids))

# Список моделей с валидацией (на основе существующих файлов)
validated_models = [
    "google/imagen4-fast",
    "google/imagen4-ultra", 
    "google/imagen4",
    "wan/2-2-a14b-text-to-video-turbo",
    "wan/2-2-a14b-image-to-video-turbo",
    "ideogram/v3-text-to-image",
    "ideogram/v3-edit",
    "ideogram/v3-remix",
    "ideogram/character-edit",
    "ideogram/character-remix",
    "ideogram/character",
    "kling/v2-1-master-image-to-video",
    "kling/v2-1-standard",
    "kling/v2-1-pro",
    "kling/v2-1-master-text-to-video",
    "bytedance/v1-lite-text-to-video",
    "bytedance/v1-pro-text-to-video",
    "bytedance/v1-lite-image-to-video",
    "bytedance/v1-pro-image-to-video",
    "bytedance/v1-pro-fast-image-to-video",
    "qwen/text-to-image",
    "qwen/image-to-image",
    "qwen/image-edit",
    "google/nano-banana",
    "google/nano-banana-edit",
    "nano-banana-pro",
    "seedream/4.5-text-to-image"
]

not_validated = [m for m in model_ids if m not in validated_models]

print("=" * 80)
print("СТАТУС ВАЛИДАЦИИ МОДЕЛЕЙ")
print("=" * 80)
print()

print(f"[OK] ВАЛИДИРОВАНЫ ({len(validated_models)} моделей):")
for model_id in sorted(validated_models):
    print(f"  [OK] {model_id}")

print()
print(f"[MISSING] НЕ ВАЛИДИРОВАНЫ ({len(not_validated)} моделей):")
for model_id in sorted(not_validated):
    print(f"  [MISSING] {model_id}")

print()
print("=" * 80)
print(f"ИТОГО: {len(validated_models)}/{len(model_ids)} моделей имеют валидацию")





from kie_models import KIE_MODELS, get_generation_types

new_models = [
    'topaz/video-upscale',
    'kling/v1-avatar-standard',
    'kling/ai-avatar-v1-pro',
    'bytedance/seedream-v4-text-to-image',
    'bytedance/seedream-v4-edit',
    'recraft/remove-background',
    'recraft/crisp-upscale',
    'ideogram/v3-reframe',
    'infinitalk/from-audio',
    'wan/2-2-a14b-speech-to-video-turbo',
    'bytedance/seedream',
    'qwen/text-to-image',
    'qwen/image-to-image',
    'qwen/image-edit',
    'ideogram/character-edit',
    'ideogram/character-remix',
    'ideogram/character',
    'ideogram/v3-text-to-image',
    'ideogram/v3-edit',
    'ideogram/v3-remix',
    'google/imagen4-ultra',
    'google/imagen4-fast',
    'google/imagen4'
]

model_ids = [m['id'] for m in KIE_MODELS]
found = [m for m in new_models if m in model_ids]
missing = [m for m in new_models if m not in model_ids]

print(f'Всего моделей в системе: {len(KIE_MODELS)}')
print(f'Всего категорий: {len(get_generation_types())}')
print(f'Категории: {get_generation_types()}')
print(f'\nНайдено новых моделей: {len(found)}/{len(new_models)}')
if missing:
    print(f'Отсутствуют: {missing}')
else:
    print('Все новые модели добавлены!')


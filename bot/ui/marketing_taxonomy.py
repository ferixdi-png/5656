"""Marketing taxonomy and recommendation logic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Template:
    template_id: str
    title: str
    output_type: str
    content_type: str
    keywords: List[str]


TEMPLATES: List[Template] = [
    Template(
        template_id="offer_variants",
        title="🎯 5 оффер-вариантов под продукт",
        output_type="text",
        content_type="offers",
        keywords=["offer", "promo", "cta", "sale"],
    ),
    Template(
        template_id="reels_hook",
        title="🧲 Хук для Reels (10 вариантов)",
        output_type="text",
        content_type="video",
        keywords=["hook", "reels", "shorts", "script"],
    ),
    Template(
        template_id="ad_text",
        title="🧾 Текст объявления (3 версии)",
        output_type="text",
        content_type="offers",
        keywords=["ad", "copy", "headline", "cta"],
    ),
    Template(
        template_id="content_plan",
        title="🧠 Контент-план на 7 дней",
        output_type="text",
        content_type="plan",
        keywords=["plan", "content", "calendar"],
    ),
    Template(
        template_id="sales_post",
        title="📣 Продающий пост (структура + текст)",
        output_type="text",
        content_type="text",
        keywords=["post", "sales", "story"],
    ),
    Template(
        template_id="insta_banner",
        title="🖼 Баннер 1:1 для Instagram",
        output_type="url",
        content_type="image",
        keywords=["banner", "instagram", "ad"],
    ),
    Template(
        template_id="reels_script",
        title="🎬 Сценарий Reels на 15 сек",
        output_type="text",
        content_type="video",
        keywords=["reels", "script", "shorts"],
    ),
    Template(
        template_id="usp_bundle",
        title="🧷 УТП + боли + выгоды",
        output_type="text",
        content_type="offers",
        keywords=["usp", "benefits", "pain"],
    ),
    Template(
        template_id="tone_rewrite",
        title="🔁 Переписать текст в 3 тона",
        output_type="text",
        content_type="repurpose",
        keywords=["rewrite", "tone"],
    ),
]

CONTENT_OUTPUT_MAP = {
    "video": "video",
    "image": "url",
    "text": "text",
    "offers": "text",
    "plan": "text",
    "repurpose": "text",
    "enhance": "url",
    "story": "text",
    "audio": "audio",
}

CONTENT_CATEGORY_MAP = {
    "video": {"t2v", "i2v", "v2v", "lip_sync"},
    "image": {"t2i", "i2i", "upscale", "bg_remove", "watermark_remove"},
    "text": {"general", "other"},
    "offers": {"general", "other"},
    "plan": {"general", "other"},
    "repurpose": {"general", "other"},
    "enhance": {"upscale", "bg_remove", "watermark_remove"},
    "story": {"general", "other"},
    "audio": {"music", "sfx", "tts", "stt", "audio_isolation"},
}


def template_by_id(template_id: str) -> Optional[Template]:
    return next((t for t in TEMPLATES if t.template_id == template_id), None)


def filters_for(context: Dict[str, str]) -> Dict[str, Iterable[str]]:
    content_type = context.get("content_type")
    template_id = context.get("template_id")
    template = template_by_id(template_id) if template_id else None
    output_type = None
    if template:
        output_type = template.output_type
    elif content_type:
        output_type = CONTENT_OUTPUT_MAP.get(content_type)

    categories = CONTENT_CATEGORY_MAP.get(content_type or "", set())
    return {
        "output_type": [output_type] if output_type else [],
        "categories": categories,
        "keywords": template.keywords if template else [],
    }


def score_model(model: Dict[str, str], context: Dict[str, str]) -> float:
    model_output = (model.get("output_type") or "").lower()
    model_category = (model.get("category") or "").lower()
    model_id = (model.get("model_id") or "").lower()
    description = (model.get("description") or "").lower()

    filters = filters_for(context)
    score = 0.0
    for output_type in filters.get("output_type", []):
        if output_type and model_output == output_type:
            score += 3.0

    categories = filters.get("categories", set())
    if categories and model_category in categories:
        score += 2.0

    keywords = filters.get("keywords", [])
    if keywords:
        matches = sum(1 for keyword in keywords if keyword in model_id or keyword in description)
        score += matches * 0.5

    required_fields = model.get("input_schema", {}).get("required", [])
    score += max(0.0, 2.0 - (len(required_fields) * 0.2))

    return score


def recommend_models(models: List[Dict[str, str]], context: Dict[str, str], limit: int = 5) -> List[Dict[str, str]]:
    scored = [
        (score_model(model, context), model)
        for model in models
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [model for score, model in scored[:limit] if score > 0]


def models_for_context(models: List[Dict[str, str]], context: Dict[str, str]) -> List[Dict[str, str]]:
    filters = filters_for(context)
    categories = filters.get("categories", set())
    output_types = set(filters.get("output_type", []))

    def matches(model: Dict[str, str]) -> bool:
        if categories and model.get("category") not in categories:
            return False
        if output_types and model.get("output_type") not in output_types:
            return False
        return True

    filtered = [model for model in models if matches(model)]
    return filtered or models

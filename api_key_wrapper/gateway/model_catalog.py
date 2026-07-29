"""Server-owned model catalogs shared by views, APIs, and provider clients."""

import os

from django.db import OperationalError, ProgrammingError

from .key_resolver import ENV_VAR_BY_PROVIDER, is_provider_configured


DEFAULT_CHAT_MODELS_BY_PROVIDER = {
    "openai": (
        ("gpt-4o-mini", "GPT-4o mini", "Fast, capable, and economical"),
        ("gpt-4o", "GPT-4o", "Higher-quality general-purpose model"),
    ),
    "anthropic": (
        ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "Fast Anthropic model"),
        ("claude-sonnet-4-20250514", "Claude Sonnet 4", "Balanced Anthropic model"),
    ),
    "deepseek": (
        ("deepseek-chat", "DeepSeek Chat", "General-purpose DeepSeek model"),
        ("deepseek-reasoner", "DeepSeek Reasoner", "DeepSeek reasoning model"),
    ),
}

DEFAULT_CHAT_PROVIDER = "openai"
DEFAULT_CHAT_MODEL = "gpt-4o-mini"

IMAGE_MODELS = (
    {
        "provider": "nano_banana",
        "model": "gemini-3.1-flash-image",
        "label": "Nano Banana 2",
        "description": "Best balance of quality, speed, and cost",
        "resolutions": ("512", "1K", "2K", "4K"),
        "aspect_ratios": (
            "1:1",
            "1:4",
            "1:8",
            "2:3",
            "3:2",
            "3:4",
            "4:1",
            "4:3",
            "4:5",
            "5:4",
            "8:1",
            "9:16",
            "16:9",
            "21:9",
        ),
    },
    {
        "provider": "nano_banana",
        "model": "gemini-3-pro-image",
        "label": "Nano Banana Pro",
        "description": "Professional assets and complex instructions",
        "resolutions": ("1K", "2K", "4K"),
        "aspect_ratios": ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"),
    },
    {
        "provider": "nano_banana",
        "model": "gemini-2.5-flash-image",
        "label": "Nano Banana",
        "description": "Fast 1K image generation",
        "resolutions": ("1K",),
        "aspect_ratios": ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"),
    },
)

DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"
DEFAULT_IMAGE_ASPECT_RATIO = "1:1"
DEFAULT_IMAGE_RESOLUTION = "1K"


def _find_model(catalog, provider, model):
    return next(
        (item for item in catalog if item["provider"] == provider and item["model"] == model),
        None,
    )


def _titleize_model(model_id):
    return model_id.replace("-", " ").replace("_", " ").title()


def _split_model_label(value):
    if "=" in value:
        model_id, label = value.split("=", 1)
    elif "|" in value:
        model_id, label = value.split("|", 1)
    else:
        model_id, label = value, ""
    return model_id.strip(), label.strip()


def _chat_model_env_specs(provider):
    provider_var = f"{provider.upper()}_CHAT_MODELS"
    raw = os.environ.get(provider_var, "").strip()
    if not raw:
        return []
    specs = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        model_id, label = _split_model_label(value)
        if model_id:
            specs.append((model_id, label or _titleize_model(model_id), "Configured in .env"))
    return specs


def _global_chat_model_env_specs():
    raw = os.environ.get("CHAT_MODELS", "").strip()
    if not raw:
        return []
    specs = []
    for part in raw.split(","):
        value = part.strip()
        if not value or ":" not in value:
            continue
        provider, model_spec = value.split(":", 1)
        provider = provider.strip()
        model_id, label = _split_model_label(model_spec)
        if provider and model_id:
            specs.append((provider, model_id, label or _titleize_model(model_id), "Configured in .env"))
    return specs


def _admin_model_overrides():
    try:
        from .models import ProviderModel

        return {
            (item.provider, item.model): item
            for item in ProviderModel.objects.all()
        }
    except (OperationalError, ProgrammingError):
        return {}


def _upsert_model(models, provider, model_id, label, description="", source="default"):
    key = (provider, model_id)
    current = models.get(key, {})
    models[key] = {
        "provider": provider,
        "model": model_id,
        "label": current.get("label") or label or _titleize_model(model_id),
        "description": current.get("description") or description,
        "source": current.get("source") or source,
    }


def chat_models_catalog():
    models = {}
    providers = set(DEFAULT_CHAT_MODELS_BY_PROVIDER) | set(ENV_VAR_BY_PROVIDER)

    for provider, defaults in DEFAULT_CHAT_MODELS_BY_PROVIDER.items():
        for model_id, label, description in defaults:
            _upsert_model(models, provider, model_id, label, description)

    for provider in providers:
        for model_id, label, description in _chat_model_env_specs(provider):
            _upsert_model(models, provider, model_id, label, description, source="env")

    for provider, model_id, label, description in _global_chat_model_env_specs():
        providers.add(provider)
        _upsert_model(models, provider, model_id, label, description, source="env")

    for (provider, model_id), override in _admin_model_overrides().items():
        providers.add(provider)
        if not override.is_enabled:
            models.pop((provider, model_id), None)
            continue
        _upsert_model(
            models,
            provider,
            model_id,
            override.display_name or _titleize_model(model_id),
            override.description,
            source="admin",
        )
        if override.display_name:
            models[(provider, model_id)]["label"] = override.display_name
        if override.description:
            models[(provider, model_id)]["description"] = override.description

    return tuple(models[key] for key in sorted(models))


def get_chat_model(provider, model):
    return _find_model(chat_models_catalog(), provider, model)


def get_default_chat_model():
    configured = [item for item in serialize_chat_models() if item["configured"]]
    preferred = next(
        (
            item
            for item in configured
            if item["provider"] == DEFAULT_CHAT_PROVIDER and item["model"] == DEFAULT_CHAT_MODEL
        ),
        None,
    )
    return preferred or (configured[0] if configured else get_chat_model(DEFAULT_CHAT_PROVIDER, DEFAULT_CHAT_MODEL))


def get_image_model(model):
    return next((item for item in IMAGE_MODELS if item["model"] == model), None)


def serialize_chat_models():
    return [
        {
            **item,
            "configured": is_provider_configured(item["provider"]),
        }
        for item in chat_models_catalog()
    ]


def serialize_image_models():
    return [
        {
            **item,
            "resolutions": list(item["resolutions"]),
            "aspect_ratios": list(item["aspect_ratios"]),
            "configured": is_provider_configured(item["provider"]),
        }
        for item in IMAGE_MODELS
    ]

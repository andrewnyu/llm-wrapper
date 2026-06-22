"""Server-owned model catalogs shared by views, APIs, and provider clients."""

from .key_resolver import is_provider_configured


CHAT_MODELS = (
    {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "label": "GPT-4o mini",
        "description": "Fast, capable, and economical",
    },
    {
        "provider": "openai",
        "model": "gpt-4o",
        "label": "GPT-4o",
        "description": "Higher-quality general-purpose model",
    },
    {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "label": "DeepSeek V4 Flash",
        "description": "Fast DeepSeek model",
    },
    {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "label": "DeepSeek V4 Pro",
        "description": "More capable DeepSeek model",
    },
)

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


def get_chat_model(provider, model):
    return _find_model(CHAT_MODELS, provider, model)


def get_image_model(model):
    return next((item for item in IMAGE_MODELS if item["model"] == model), None)


def serialize_chat_models():
    return [
        {
            **item,
            "configured": is_provider_configured(item["provider"]),
        }
        for item in CHAT_MODELS
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

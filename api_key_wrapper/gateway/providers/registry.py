from .anthropic import AnthropicClient
from .custom import CustomClient
from .deepseek import DeepSeekClient
from .glm import GLMClient
from .google import GoogleClient
from .kimi import KimiClient
from .nano_banana import NanoBananaClient
from .openai import OpenAIClient


PROVIDER_REGISTRY = {
    "openai": OpenAIClient(),
    "anthropic": AnthropicClient(),
    "google": GoogleClient(),
    "nano_banana": NanoBananaClient(),
    "deepseek": DeepSeekClient(),
    "glm": GLMClient(),
    "kimi": KimiClient(),
    "custom": CustomClient(),
}


def get_provider_client(provider_id: str):
    client = PROVIDER_REGISTRY.get(provider_id)
    if not client:
        raise ValueError("Provider not supported")
    return client

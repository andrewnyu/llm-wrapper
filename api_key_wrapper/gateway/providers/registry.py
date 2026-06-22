from .anthropic import AnthropicClient
from .custom import CustomClient
from .deepseek import DeepSeekClient
from .google import GoogleClient
from .nano_banana import NanoBananaClient
from .openai import OpenAIClient


PROVIDER_REGISTRY = {
    "openai": OpenAIClient(),
    "anthropic": AnthropicClient(),
    "google": GoogleClient(),
    "nano_banana": NanoBananaClient(),
    "deepseek": DeepSeekClient(),
    "custom": CustomClient(),
}


def get_provider_client(provider_id: str):
    client = PROVIDER_REGISTRY.get(provider_id)
    if not client:
        raise ValueError("Provider not supported")
    return client

import os

from .models import ProviderKey

ENV_VAR_BY_PROVIDER = {
    ProviderKey.PROVIDER_OPENAI: "OPENAI_API_KEY",
    ProviderKey.PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY",
    ProviderKey.PROVIDER_GOOGLE: "GOOGLE_API_KEY",
    ProviderKey.PROVIDER_NANO_BANANA: "NANO_BANANA_API_KEY",
    ProviderKey.PROVIDER_DEEPSEEK: "DEEPSEEK_API_KEY",
    ProviderKey.PROVIDER_CUSTOM: "CUSTOM_API_KEY",
}


def get_api_key_for_provider(provider: str) -> str:
    env_var = ENV_VAR_BY_PROVIDER.get(provider)
    if not env_var:
        raise ValueError("Provider not supported")
    value = os.environ.get(env_var, "").strip()
    if not value:
        raise ValueError(f"Missing shared API key for provider '{provider}' in {env_var}")
    return value


def is_provider_configured(provider: str) -> bool:
    env_var = ENV_VAR_BY_PROVIDER.get(provider)
    return bool(env_var and os.environ.get(env_var, "").strip())


def configured_provider_status():
    rows = []
    for provider, label in ProviderKey.PROVIDER_CHOICES:
        env_var = ENV_VAR_BY_PROVIDER.get(provider)
        configured = is_provider_configured(provider)
        rows.append(
            {
                "provider": provider,
                "label": label,
                "env_var": env_var,
                "configured": configured,
            }
        )
    return rows

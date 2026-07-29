import os

from .models import ProviderKey

ENV_VAR_BY_PROVIDER = {
    ProviderKey.PROVIDER_OPENAI: "OPENAI_API_KEY",
    ProviderKey.PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY",
    ProviderKey.PROVIDER_GOOGLE: "GOOGLE_API_KEY",
    ProviderKey.PROVIDER_NANO_BANANA: "NANO_BANANA_API_KEY",
    ProviderKey.PROVIDER_DEEPSEEK: "DEEPSEEK_API_KEY",
    ProviderKey.PROVIDER_GLM: "GLM_API_KEY",
    ProviderKey.PROVIDER_KIMI: "KIMI_API_KEY",
    ProviderKey.PROVIDER_CUSTOM: "CUSTOM_API_KEY",
}

FALLBACK_ENV_VARS_BY_PROVIDER = {
    ProviderKey.PROVIDER_NANO_BANANA: ("GOOGLE_API_KEY",),
}


def get_api_key_for_provider(provider: str) -> str:
    env_var = ENV_VAR_BY_PROVIDER.get(provider)
    if not env_var:
        raise ValueError("Provider not supported")
    env_vars = (env_var, *FALLBACK_ENV_VARS_BY_PROVIDER.get(provider, ()))
    for candidate in env_vars:
        value = os.environ.get(candidate, "").strip()
        if value:
            return value
    names = " or ".join(env_vars)
    raise ValueError(f"Missing shared API key for provider '{provider}' in {names}")


def is_provider_configured(provider: str) -> bool:
    env_var = ENV_VAR_BY_PROVIDER.get(provider)
    env_vars = (env_var, *FALLBACK_ENV_VARS_BY_PROVIDER.get(provider, ())) if env_var else ()
    return any(os.environ.get(candidate, "").strip() for candidate in env_vars)


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
                "fallback_env_vars": FALLBACK_ENV_VARS_BY_PROVIDER.get(provider, ()),
                "configured": configured,
            }
        )
    return rows

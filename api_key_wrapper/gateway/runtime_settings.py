"""Database-backed gateway settings with safe defaults before migrations run."""

from django.db import OperationalError, ProgrammingError

from .models import GatewaySettings, ProviderKey


ALL_PROVIDERS = tuple(provider for provider, _label in ProviderKey.PROVIDER_CHOICES)


def get_gateway_settings():
    try:
        settings, _created = GatewaySettings.objects.get_or_create(pk=1)
        return settings
    except (OperationalError, ProgrammingError):
        return None


def is_provider_allowed(provider):
    settings = get_gateway_settings()
    return settings is None or provider in settings.enabled_providers

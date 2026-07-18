import logging
from typing import Callable, Iterator, Optional

from api_key_wrapper.gateway.key_resolver import get_api_key_for_provider
from api_key_wrapper.gateway.model_catalog import DEFAULT_CHAT_MODEL, DEFAULT_CHAT_PROVIDER
from api_key_wrapper.gateway.providers.base import chunk_text_for_streaming
from api_key_wrapper.gateway.providers.registry import get_provider_client

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = DEFAULT_CHAT_PROVIDER
DEFAULT_MODEL = DEFAULT_CHAT_MODEL


def generate_stream(
    *,
    user,
    messages,
    model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
    **params,
) -> Iterator[str]:
    """Yield text deltas from the provider as they arrive."""
    api_key = get_api_key_for_provider(provider)
    client = get_provider_client(provider)
    return client.chat_stream(
        api_key,
        {
            "model": model,
            "messages": messages,
            "temperature": params.get("temperature"),
        },
    )


def generate(
    *,
    user,
    messages,
    stream: bool = False,
    on_token: Optional[Callable[[str], None]] = None,
    model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
    **params,
) -> str:
    """
    Blocking adapter around provider clients.

    Contract:
    generate(messages, stream=False, on_token=None, **params) -> full_text
    """
    api_key = get_api_key_for_provider(provider)

    client = get_provider_client(provider)
    result = client.chat_complete(
        api_key,
        {
            "model": model,
            "messages": messages,
            "temperature": params.get("temperature"),
        },
    )
    full_text = result.text or ""

    if stream and on_token:
        for chunk in chunk_text_for_streaming(full_text):
            on_token(chunk)

    return full_text

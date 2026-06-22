import logging
import re
from typing import Callable, Optional

from api_key_wrapper.gateway.key_resolver import get_api_key_for_provider
from api_key_wrapper.gateway.model_catalog import DEFAULT_CHAT_MODEL, DEFAULT_CHAT_PROVIDER
from api_key_wrapper.gateway.providers.registry import get_provider_client

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = DEFAULT_CHAT_PROVIDER
DEFAULT_MODEL = DEFAULT_CHAT_MODEL


def _chunk_text_for_streaming(text: str):
    # Simulated tokenization fallback for providers without streaming APIs.
    chunks = re.findall(r"\S+\s*|\n", text)
    if not chunks:
        return [text] if text else []
    return chunks


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
    Adapter around provider clients.

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
        # Existing provider wrapper does not expose a streaming callback.
        # We simulate token streaming on the server by chunking the final text.
        for chunk in _chunk_text_for_streaming(full_text):
            on_token(chunk)

    return full_text

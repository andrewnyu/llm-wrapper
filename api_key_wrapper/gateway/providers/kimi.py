import os

import requests
from django.conf import settings

from .base import ChatCompletionResult, ProviderClient, stream_openai_compatible_chat


class KimiClient(ProviderClient):
    provider_id = "kimi"

    @property
    def base_url(self):
        return os.environ.get("KIMI_BASE_URL", "https://api.moonshot.ai/v1").rstrip("/")

    def chat_stream(self, api_key, payload):
        return stream_openai_compatible_chat(
            f"{self.base_url}/chat/completions",
            api_key,
            payload,
            settings.API_REQUEST_TIMEOUT_SECONDS,
        )

    def chat_complete(self, api_key, payload):
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": payload.get("model"),
                "messages": payload.get("messages", []),
                "temperature": payload.get("temperature") if payload.get("temperature") is not None else 0.7,
            },
            timeout=settings.API_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ChatCompletionResult(text=text, usage=data.get("usage"), raw=data)

    def image_generate(self, api_key, payload):
        raise NotImplementedError("Kimi image generation is not available in this app")

    def image_edit(self, api_key, payload):
        raise NotImplementedError("Kimi image editing is not available in this app")

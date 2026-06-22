import requests
from django.conf import settings

from .base import ChatCompletionResult, ProviderClient


class OpenAIClient(ProviderClient):
    provider_id = "openai"

    def chat_complete(self, api_key, payload):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": payload.get("model"),
            "messages": payload.get("messages", []),
            "temperature": payload.get("temperature") if payload.get("temperature") is not None else 0.7,
        }
        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=settings.API_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage")
        return ChatCompletionResult(text=text, usage=usage, raw=data)

    def image_generate(self, api_key, payload):
        raise NotImplementedError("OpenAI image generation not implemented")

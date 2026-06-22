import requests
from django.conf import settings

from .base import ChatCompletionResult, ProviderClient


class DeepSeekClient(ProviderClient):
    provider_id = "deepseek"
    base_url = "https://api.deepseek.com"

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
        raise NotImplementedError("DeepSeek provider does not support images")

    def image_edit(self, api_key, payload):
        raise NotImplementedError("DeepSeek provider does not support images")

import json

import requests
from django.conf import settings

from .base import ChatCompletionResult, ProviderClient


class AnthropicClient(ProviderClient):
    provider_id = "anthropic"
    base_url = "https://api.anthropic.com/v1/messages"

    def _headers(self, api_key):
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _body(self, payload, stream=False):
        messages = []
        system_parts = []
        for message in payload.get("messages", []):
            role = message.get("role")
            content = message.get("content", "")
            if role == "system":
                system_parts.append(str(content))
            elif role in ("user", "assistant"):
                messages.append({"role": role, "content": str(content)})

        body = {
            "model": payload.get("model"),
            "messages": messages,
            "max_tokens": payload.get("max_tokens") or 4096,
            "stream": stream,
        }
        if payload.get("temperature") is not None:
            body["temperature"] = payload.get("temperature")
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        return body

    def chat_complete(self, api_key, payload):
        response = requests.post(
            self.base_url,
            headers=self._headers(api_key),
            json=self._body(payload),
            timeout=settings.API_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        text = "".join(
            item.get("text", "")
            for item in data.get("content", [])
            if item.get("type") == "text"
        )
        return ChatCompletionResult(text=text, usage=data.get("usage"), raw=data)

    def chat_stream(self, api_key, payload):
        with requests.post(
            self.base_url,
            headers=self._headers(api_key),
            json=self._body(payload, stream=True),
            stream=True,
            timeout=settings.API_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                try:
                    event = json.loads(raw_line[len("data:"):].strip())
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield delta["text"]

    def image_generate(self, api_key, payload):
        raise NotImplementedError("Anthropic provider does not support images")

    def image_edit(self, api_key, payload):
        raise NotImplementedError("Anthropic provider does not support images")

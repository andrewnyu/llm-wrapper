import requests
from django.conf import settings

from .base import ChatCompletionResult, ImageGenerationResult, ProviderClient, stream_openai_compatible_chat


class GLMClient(ProviderClient):
    provider_id = "glm"
    base_url = "https://open.bigmodel.cn/api/paas/v4"
    image_sizes = {
        "1:1": "1280x1280",
        "3:4": "1056x1568",
        "4:3": "1568x1056",
        "9:16": "960x1728",
        "16:9": "1728x960",
    }
    # GLM-Image's HD generation commonly takes around 20 seconds.  Do not use
    # the short shared chat timeout, or ordinary successful generations can
    # expire at the gateway boundary.
    image_request_timeout_seconds = 60

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
        response = requests.post(
            f"{self.base_url}/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": payload.get("model", "glm-image"),
                "prompt": payload.get("prompt", ""),
                "size": self.image_sizes.get(payload.get("aspect_ratio"), "1280x1280"),
            },
            timeout=max(
                settings.API_REQUEST_TIMEOUT_SECONDS,
                getattr(settings, "GLM_IMAGE_REQUEST_TIMEOUT_SECONDS", self.image_request_timeout_seconds),
            ),
        )
        response.raise_for_status()
        data = response.json()
        images = []
        for item in data.get("data", []) or []:
            url = item.get("url")
            b64_json = item.get("b64_json") or item.get("base64")
            if url:
                images.append({"url": url})
            elif b64_json:
                images.append({"base64": b64_json if b64_json.startswith("data:") else f"data:image/png;base64,{b64_json}"})
        return ImageGenerationResult(images=images, raw=data)

    def image_edit(self, api_key, payload):
        raise NotImplementedError("GLM image editing is not implemented")

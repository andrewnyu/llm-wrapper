import base64
from django.conf import settings

from .base import ImageGenerationResult, ProviderClient

from google import genai
import os


class NanoBananaClient(ProviderClient):
    provider_id = "nano_banana"

    def chat_complete(self, api_key, payload):
        raise NotImplementedError("Nano Banana does not support chat")

    def image_generate(self, api_key, payload):
        # ... imports and setup ...
        
        prompt = payload.get("prompt")
        aspect_ratio = payload.get("aspect_ratio", "1:1")
        n = int(payload.get("n", 1) or 1)
        model = payload.get("model", "gemini-2.5-flash-image")

        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing API key. Add a Nano Banana key in API Keys or set GOOGLE_API_KEY."
            )

        client = genai.Client(api_key=api_key)
        
        try:
            response = client.models.generate_content(
                model=model,
                contents=[prompt],
            )

            images = []
            candidates = getattr(response, "candidates", []) or []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", []) or []
                for part in parts:
                    inline = getattr(part, "inline_data", None)
                    if not inline:
                        continue
                    mime_type = getattr(inline, "mime_type", "image/png")
                    data = getattr(inline, "data", None)
                    if data is None:
                        continue
                    if isinstance(data, str):
                        encoded = data
                    else:
                        encoded = base64.b64encode(data).decode("ascii")
                    images.append({"base64": f"data:{mime_type};base64,{encoded}"})

            return ImageGenerationResult(images=images, raw=response)

        except Exception as e:
            raise Exception(f"Nano Banana Generation Error: {e}")

        

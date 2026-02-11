import base64
from django.conf import settings

from .base import ImageGenerationResult, ProviderClient

from google import genai


class NanoBananaClient(ProviderClient):
    provider_id = "nano_banana"

    def chat_complete(self, api_key, payload):
        raise NotImplementedError("Nano Banana does not support chat")

    def image_generate(self, api_key, payload):
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is required for Nano Banana. Install with: pip install google-genai"
            ) from exc

        prompt = payload.get("prompt")
        size = payload.get("size", "1024x1024")
        n = int(payload.get("n", 1) or 1)
        model = payload.get("model", "gemini-2.5-flash-image") #default model

        client = genai.Client(api_key=api_key)
        try:
            response = client.models.generate_content(
                model=model,
                prompt=[prompt]
            )
        except TypeError:
            try:
                config = genai.types.GenerateImagesConfig(
                    number_of_images=n,
                    image_size=size,
                )
                response = client.models.generate_images(
                    model=model,
                    prompt=prompt,
                    config=config,
                )
            except Exception:
                response = client.models.generate_images(
                    model=model,
                    prompt=prompt,
                )

        images = []
        raw = getattr(response, "__dict__", None) or response
        generated = getattr(response, "generated_images", None) or []
        for item in generated:
            image_obj = getattr(item, "image", None)
            image_bytes = getattr(image_obj, "image_bytes", None)
            if image_bytes:
                encoded = base64.b64encode(image_bytes).decode("ascii")
                images.append({"base64": f"data:image/png;base64,{encoded}"})

        return ImageGenerationResult(images=images, raw=raw)

import base64
import os

from .base import ImageGenerationResult, ProviderClient

from google import genai
from google.genai import types


class NanoBananaClient(ProviderClient):
    provider_id = "nano_banana"

    def chat_complete(self, api_key, payload):
        raise NotImplementedError("Nano Banana does not support chat")

    def image_generate(self, api_key, payload):
        prompt = payload.get("prompt")
        model = payload.get("model", "gemini-3.1-flash-image")

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
                config=self._generation_config(payload, model),
            )
            return ImageGenerationResult(
                images=self._extract_images(response),
                text=self._extract_text(response),
                raw=response,
            )
        except Exception as e:
            raise Exception(f"Nano Banana Generation Error: {e}")

    def image_edit(self, api_key, payload):
        prompt = payload.get("prompt")
        input_image = payload.get("input_image")
        model = payload.get("model", "gemini-3.1-flash-image")

        if not input_image:
            raise ValueError("input_image is required")

        mime_type, image_bytes = self._parse_data_url(input_image)

        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing API key. Add a Nano Banana key in API Keys or set GOOGLE_API_KEY."
            )

        client = genai.Client(api_key=api_key)

        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": mime_type, "data": image_bytes}},
                        ],
                    }
                ],
                config=self._generation_config(payload, model),
            )
            return ImageGenerationResult(
                images=self._extract_images(response),
                text=self._extract_text(response),
                raw=response,
            )
        except Exception as e:
            raise Exception(f"Nano Banana Edit Error: {e}")

    def _generation_config(self, payload, model):
        image_config = {"aspect_ratio": payload.get("aspect_ratio", "1:1")}
        if model != "gemini-2.5-flash-image":
            image_config["image_size"] = payload.get("image_size", "1K")
        return types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(**image_config),
        )

    def _parse_data_url(self, data_url):
        if not isinstance(data_url, str):
            raise ValueError("input_image must be a data URL")
        if not data_url.startswith("data:"):
            raise ValueError("input_image must be a data URL")
        try:
            header, encoded_data = data_url.split(",", 1)
        except ValueError as exc:
            raise ValueError("Malformed input_image data URL") from exc

        mime_type = "image/png"
        if ";" in header:
            mime_type = header[5:].split(";", 1)[0] or mime_type
        if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("input_image must be a PNG, JPEG, or WebP image")

        try:
            image_bytes = base64.b64decode(encoded_data, validate=True)
        except Exception as exc:
            raise ValueError("input_image contains invalid base64 data") from exc
        if len(image_bytes) > 12 * 1024 * 1024:
            raise ValueError("input_image is too large (12 MB maximum)")

        return mime_type, image_bytes

    def _extract_images(self, response):
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
        return images

    def _extract_text(self, response):
        chunks = []
        candidates = getattr(response, "candidates", []) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", []) or []
            for part in parts:
                text = getattr(part, "text", None)
                if isinstance(text, str):
                    stripped = text.strip()
                    if stripped:
                        chunks.append(stripped)
        if chunks:
            return "\n\n".join(chunks)

        response_text = getattr(response, "text", None)
        if isinstance(response_text, str):
            return response_text.strip()
        return ""

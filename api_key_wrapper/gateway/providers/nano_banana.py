import base64
import os
import requests

from .base import ImageGenerationResult, ProviderClient

from google import genai


class NanoBananaClient(ProviderClient):
    provider_id = "nano_banana"

    def chat_complete(self, api_key, payload):
        raise NotImplementedError("Nano Banana does not support chat")

    def image_generate(self, api_key, payload):
        prompt = payload.get("prompt")
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
            return ImageGenerationResult(images=self._extract_images(response), raw=response)
        except Exception as e:
            raise Exception(f"Nano Banana Generation Error: {e}")

    def image_edit(self, api_key, payload):
        prompt = payload.get("prompt")
        input_image = payload.get("input_image")
        model = payload.get("model", "gemini-2.5-flash-image")

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
            )
            return ImageGenerationResult(images=self._extract_images(response), raw=response)
        except Exception as e:
            raise Exception(f"Nano Banana Edit Error: {e}")

    def _parse_data_url(self, data_url):
        if not isinstance(data_url, str):
            raise ValueError("input_image must be a data URL or http(s) URL")
        if data_url.startswith("http://") or data_url.startswith("https://"):
            return self._download_image(data_url)
        if not data_url.startswith("data:"):
            raise ValueError("input_image must be a data URL or http(s) URL")
        try:
            header, encoded_data = data_url.split(",", 1)
        except ValueError as exc:
            raise ValueError("Malformed input_image data URL") from exc

        mime_type = "image/png"
        if ";" in header:
            mime_type = header[5:].split(";", 1)[0] or mime_type

        try:
            image_bytes = base64.b64decode(encoded_data)
        except Exception as exc:
            raise ValueError("input_image contains invalid base64 data") from exc

        return mime_type, image_bytes

    def _download_image(self, image_url):
        response = requests.get(image_url, timeout=20)
        response.raise_for_status()
        mime_type = response.headers.get("Content-Type", "image/png")
        return mime_type, response.content

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

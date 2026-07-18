import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import requests


@dataclass
class ChatCompletionResult:
    text: str
    usage: Optional[Dict[str, Any]] = None
    raw: Optional[Dict[str, Any]] = None


def chunk_text_for_streaming(text: str) -> List[str]:
    # Simulated tokenization fallback for providers without streaming APIs.
    chunks = re.findall(r"\S+\s*|\n", text)
    if not chunks:
        return [text] if text else []
    return chunks


def stream_openai_compatible_chat(url: str, api_key: str, payload: Dict[str, Any], timeout: int) -> Iterator[str]:
    """Yield text deltas from an OpenAI-compatible /chat/completions SSE stream."""
    body = {
        "model": payload.get("model"),
        "messages": payload.get("messages", []),
        "temperature": payload.get("temperature") if payload.get("temperature") is not None else 0.7,
        "stream": True,
    }
    with requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        stream=True,
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data:"):
                continue
            data = raw_line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
            if delta:
                yield delta


@dataclass
class ImageGenerationResult:
    images: List[Dict[str, str]]
    text: str = ""
    raw: Optional[Dict[str, Any]] = None


class ProviderClient:
    provider_id: str

    def chat_complete(self, api_key: str, payload: Dict[str, Any]) -> ChatCompletionResult:
        raise NotImplementedError

    def chat_stream(self, api_key: str, payload: Dict[str, Any]) -> Iterator[str]:
        # Fallback for providers without a native streaming API: run the
        # blocking completion, then replay it as word-sized chunks.
        result = self.chat_complete(api_key, payload)
        yield from chunk_text_for_streaming(result.text or "")

    def image_generate(self, api_key: str, payload: Dict[str, Any]) -> ImageGenerationResult:
        raise NotImplementedError

    def image_edit(self, api_key: str, payload: Dict[str, Any]) -> ImageGenerationResult:
        raise NotImplementedError

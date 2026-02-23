from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ChatCompletionResult:
    text: str
    usage: Optional[Dict[str, Any]] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class ImageGenerationResult:
    images: List[Dict[str, str]]
    raw: Optional[Dict[str, Any]] = None


class ProviderClient:
    provider_id: str

    def chat_complete(self, api_key: str, payload: Dict[str, Any]) -> ChatCompletionResult:
        raise NotImplementedError

    def image_generate(self, api_key: str, payload: Dict[str, Any]) -> ImageGenerationResult:
        raise NotImplementedError

    def image_edit(self, api_key: str, payload: Dict[str, Any]) -> ImageGenerationResult:
        raise NotImplementedError

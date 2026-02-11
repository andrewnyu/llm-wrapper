from .base import ChatCompletionResult, ProviderClient


class CustomClient(ProviderClient):
    provider_id = "custom"

    def chat_complete(self, api_key, payload):
        raise NotImplementedError("Custom provider not implemented")

    def image_generate(self, api_key, payload):
        raise NotImplementedError("Custom provider not implemented")

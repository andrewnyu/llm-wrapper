from .base import ChatCompletionResult, ProviderClient


class GoogleClient(ProviderClient):
    provider_id = "google"

    def chat_complete(self, api_key, payload):
        raise NotImplementedError("Google provider not implemented")

    def image_generate(self, api_key, payload):
        raise NotImplementedError("Google provider does not support images")

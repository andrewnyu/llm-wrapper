from .base import ChatCompletionResult, ProviderClient


class AnthropicClient(ProviderClient):
    provider_id = "anthropic"

    def chat_complete(self, api_key, payload):
        raise NotImplementedError("Anthropic provider not implemented")

    def image_generate(self, api_key, payload):
        raise NotImplementedError("Anthropic provider does not support images")

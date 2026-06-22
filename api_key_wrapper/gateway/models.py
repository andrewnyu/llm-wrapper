from django.conf import settings
from django.db import models


class ProviderKey(models.Model):
    PROVIDER_OPENAI = "openai"
    PROVIDER_ANTHROPIC = "anthropic"
    PROVIDER_GOOGLE = "google"
    PROVIDER_NANO_BANANA = "nano_banana"
    PROVIDER_DEEPSEEK = "deepseek"
    PROVIDER_CUSTOM = "custom"

    PROVIDER_CHOICES = [
        (PROVIDER_OPENAI, "OpenAI"),
        (PROVIDER_ANTHROPIC, "Anthropic"),
        (PROVIDER_GOOGLE, "Google"),
        (PROVIDER_NANO_BANANA, "Nano Banana"),
        (PROVIDER_DEEPSEEK, "DeepSeek"),
        (PROVIDER_CUSTOM, "Custom"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    name = models.CharField(max_length=64)
    api_key = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def masked_key(self) -> str:
        if len(self.api_key) <= 4:
            return "****"
        return f"****{self.api_key[-4:]}"

    def __str__(self) -> str:
        return f"{self.get_provider_display()} - {self.name}"

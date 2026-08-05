from django import forms

from .model_catalog import chat_models_catalog
from .models import GatewaySettings, ProviderKey
from .runtime_settings import ALL_PROVIDERS


class ProviderKeyForm(forms.ModelForm):
    class Meta:
        model = ProviderKey
        fields = ["provider", "name", "api_key"]
        widgets = {
            "api_key": forms.PasswordInput(render_value=True),
        }


class GatewaySettingsForm(forms.ModelForm):
    enabled_providers = forms.MultipleChoiceField(
        choices=ProviderKey.PROVIDER_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Allowed shared provider keys",
        help_text="Disabled providers are hidden from users and their environment keys cannot be used.",
    )

    class Meta:
        model = GatewaySettings
        fields = ["default_chat_provider", "default_chat_model", "enabled_providers"]
        widgets = {
            "default_chat_provider": forms.Select(),
            "default_chat_model": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        models = chat_models_catalog()
        provider_choices = sorted({(item["provider"], item["provider"].title()) for item in models})
        self.fields["default_chat_provider"].widget.choices = provider_choices
        self.fields["default_chat_model"].widget.choices = [
            (item["model"], f'{item["label"]} ({item["provider"]})') for item in models
        ]
        self.initial["enabled_providers"] = self.instance.enabled_providers or list(ALL_PROVIDERS)

    def clean(self):
        cleaned = super().clean()
        provider = cleaned.get("default_chat_provider")
        model = cleaned.get("default_chat_model")
        enabled = cleaned.get("enabled_providers") or []
        valid_models = {(item["provider"], item["model"]) for item in chat_models_catalog()}
        if provider and model and (provider, model) not in valid_models:
            self.add_error("default_chat_model", "Choose a model from the selected provider.")
        if provider and provider not in enabled:
            self.add_error("enabled_providers", "The default chat provider must remain allowed.")
        return cleaned

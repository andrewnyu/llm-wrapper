from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from api_key_wrapper.gateway.models import ProviderKey


@login_required
def chat_view(request):
    provider_choices = [
        choice
        for choice in ProviderKey.PROVIDER_CHOICES
        if choice[0] != "nano_banana"
    ]
    model_defaults = {
        "openai": ["gpt-4o-mini", "gpt-4o"],
        "anthropic": ["claude-3-haiku", "claude-3-sonnet"],
        "google": ["gemini-1.5-flash", "gemini-1.5-pro"],
        "custom": ["custom-model"],
    }
    return render(
        request,
        "chat/chat.html",
        {
            "provider_choices": provider_choices,
            "model_defaults": model_defaults,
        },
    )

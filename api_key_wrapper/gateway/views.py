from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render

from .forms import GatewaySettingsForm
from .key_resolver import configured_provider_status
from .runtime_settings import get_gateway_settings


@login_required
def provider_keys_list(request):
    status_rows = configured_provider_status()
    return render(request, "gateway/provider_keys_list.html", {"status_rows": status_rows})


@login_required
def provider_key_create(request):
    messages.info(request, "API keys are managed by the server .env and are not editable in UI.")
    return redirect("gateway:keys")


@login_required
def provider_key_edit(request, key_id):
    messages.info(request, "API keys are managed by the server .env and are not editable in UI.")
    return redirect("gateway:keys")


@login_required
def provider_key_delete(request, key_id):
    messages.info(request, "API keys are managed by the server .env and are not editable in UI.")
    return redirect("gateway:keys")


@user_passes_test(lambda user: user.is_staff)
def gateway_settings(request):
    gateway_config = get_gateway_settings()
    # The settings table is created by migration; this fallback keeps the page
    # usable when the server is first started before migrations are applied.
    if gateway_config is None:
        messages.error(request, "Gateway settings are unavailable. Run migrations first.")
        return redirect("gateway:keys")

    if request.method == "POST":
        form = GatewaySettingsForm(request.POST, instance=gateway_config)
        if form.is_valid():
            form.save()
            messages.success(request, "Gateway settings saved.")
            return redirect("gateway:settings")
    else:
        form = GatewaySettingsForm(instance=gateway_config)
    return render(request, "gateway/settings.html", {"form": form})

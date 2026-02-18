from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .key_resolver import configured_provider_status


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

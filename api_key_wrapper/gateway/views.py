from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProviderKeyForm
from .models import ProviderKey


@login_required
def provider_keys_list(request):
    keys = ProviderKey.objects.filter(user=request.user)
    return render(request, "gateway/provider_keys_list.html", {"keys": keys})


@login_required
def provider_key_create(request):
    form = ProviderKeyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        key = form.save(commit=False)
        key.user = request.user
        key.save()
        messages.success(request, "API key saved.")
        return redirect("gateway:keys")

    return render(request, "gateway/provider_key_form.html", {"form": form, "mode": "Add"})


@login_required
def provider_key_edit(request, key_id):
    key = get_object_or_404(ProviderKey, id=key_id, user=request.user)
    form = ProviderKeyForm(request.POST or None, instance=key)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "API key updated.")
        return redirect("gateway:keys")

    return render(request, "gateway/provider_key_form.html", {"form": form, "mode": "Edit"})


@login_required
def provider_key_delete(request, key_id):
    key = get_object_or_404(ProviderKey, id=key_id, user=request.user)
    if request.method == "POST":
        key.delete()
        messages.success(request, "API key deleted.")
        return redirect("gateway:keys")

    return render(request, "gateway/provider_key_delete.html", {"key": key})

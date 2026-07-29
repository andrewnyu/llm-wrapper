from django.contrib import admin

from .models import ProviderKey, ProviderModel


@admin.register(ProviderKey)
class ProviderKeyAdmin(admin.ModelAdmin):
    list_display = ("provider", "name", "user", "created_at")
    list_filter = ("provider",)
    search_fields = ("name", "user__email", "user__username")


@admin.register(ProviderModel)
class ProviderModelAdmin(admin.ModelAdmin):
    list_display = ("provider", "model", "display_name", "is_enabled", "updated_at")
    list_editable = ("display_name", "is_enabled")
    list_filter = ("provider", "is_enabled")
    search_fields = ("model", "display_name", "description")

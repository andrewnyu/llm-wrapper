from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import UsageEvent, UsageWallet
from .services import load_credits


class UsageWalletAdminForm(forms.ModelForm):
    load_amount = forms.DecimalField(
        required=False,
        decimal_places=4,
        max_digits=16,
        min_value=Decimal("0.0001"),
        help_text="Optional top-up amount to add credits through immutable ledger.",
    )

    class Meta:
        model = UsageWallet
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("load_amount") and not self.instance.pk:
            raise ValidationError("Load amount is only supported on existing wallets.")
        return cleaned


@admin.register(UsageWallet)
class UsageWalletAdmin(admin.ModelAdmin):
    form = UsageWalletAdminForm
    list_display = (
        "user",
        "balance_credits",
        "total_loaded_credits",
        "total_used_credits",
        "updated_at",
    )
    search_fields = ("user__email", "user__username")
    readonly_fields = (
        "user",
        "balance_credits",
        "total_loaded_credits",
        "total_used_credits",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        load_amount = form.cleaned_data.get("load_amount")
        if load_amount:
            wallet, _event = load_credits(
                user=obj.user,
                amount=load_amount,
                created_by=request.user,
                metadata={"source": "admin_wallet_form"},
            )
            messages.success(
                request,
                f"Loaded {load_amount} credits. New balance: {wallet.balance_credits}.",
            )


@admin.register(UsageEvent)
class UsageEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "event_type",
        "credits_delta",
        "unit_count",
        "feature",
        "created_by",
    )
    list_filter = ("event_type", "feature", "created_at")
    search_fields = ("user__email", "user__username", "reference_id")
    readonly_fields = ("created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

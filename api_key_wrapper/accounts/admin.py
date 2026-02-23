from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm

from api_key_wrapper.usage.services import load_credits
from .models import User, TwoFactorDevice


class AdminUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    initial_load = forms.DecimalField(
        required=False,
        initial=Decimal("10.0000"),
        min_value=Decimal("0.0000"),
        max_digits=16,
        decimal_places=4,
        help_text="Initial credits granted to the user on creation.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = AdminUserCreationForm
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2", "initial_load"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            return
        amount = form.cleaned_data.get("initial_load")
        if amount is None:
            amount = Decimal("10.0000")
        if amount > 0:
            wallet, _event = load_credits(
                user=obj,
                amount=amount,
                created_by=request.user,
                metadata={"source": "admin_user_create"},
            )
            messages.info(request, f"Granted initial credits: {wallet.balance_credits}")


admin.site.register(TwoFactorDevice)

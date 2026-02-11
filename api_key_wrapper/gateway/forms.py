from django import forms

from .models import ProviderKey


class ProviderKeyForm(forms.ModelForm):
    class Meta:
        model = ProviderKey
        fields = ["provider", "name", "api_key"]
        widgets = {
            "api_key": forms.PasswordInput(render_value=True),
        }

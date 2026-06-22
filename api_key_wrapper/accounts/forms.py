from django import forms
from django.contrib.auth.forms import PasswordChangeForm

class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput())


class TotpVerifyForm(forms.Form):
    code = forms.CharField(label="Verification code", max_length=6)


class AccountPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(label="Current password", widget=forms.PasswordInput())
    new_password1 = forms.CharField(label="New password", widget=forms.PasswordInput())
    new_password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput())

from django import forms


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput())


class TotpVerifyForm(forms.Form):
    code = forms.CharField(label="Verification code", max_length=6)

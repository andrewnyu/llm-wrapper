from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from api_key_wrapper.usage.services import get_or_create_wallet

from .forms import AccountPasswordChangeForm, LoginForm, TotpVerifyForm
from .models import TwoFactorDevice, User
from .utils import build_totp_uri, generate_totp_secret, qr_code_data_uri, verify_totp


def login_view(request):
    if request.user.is_authenticated:
        return redirect("chat:chat")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower()
        password = form.cleaned_data["password"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = None

        if user and user.check_password(password):
            device = getattr(user, "two_factor_device", None)
            if device and device.confirmed:
                request.session["pre_2fa_user_id"] = user.id
                return redirect("accounts:two_factor_verify")
            login(request, user)
            messages.info(request, "Two-factor authentication is required. Please set it up.")
            return redirect("accounts:two_factor_setup")

        messages.error(request, "Invalid email or password.")

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@login_required
def account_home(request):
    device = getattr(request.user, "two_factor_device", None)
    is_enabled = bool(device and device.confirmed)
    wallet = get_or_create_wallet(request.user)
    password_form = AccountPasswordChangeForm(request.user, request.POST or None)

    if request.method == "POST":
        if password_form.is_valid():
            updated_user = password_form.save()
            update_session_auth_hash(request, updated_user)
            messages.success(request, "Password updated.")
            return redirect("accounts:account")
        messages.error(request, "Please correct the password form errors.")

    return render(
        request,
        "accounts/account.html",
        {
            "is_enabled": is_enabled,
            "available_credits": wallet.balance_credits,
            "password_form": password_form,
        },
    )


@login_required
def two_factor_setup(request):
    device, created = TwoFactorDevice.objects.get_or_create(user=request.user)
    if device.confirmed:
        return redirect("accounts:account")

    if created or not device.secret:
        device.secret = generate_totp_secret()
        device.confirmed = False
        device.save(update_fields=["secret", "confirmed"])

    issuer = "API Key Wrapper"
    uri = build_totp_uri(request.user.email, device.secret, issuer)
    qr_data_uri = qr_code_data_uri(uri)

    form = TotpVerifyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if verify_totp(form.cleaned_data["code"], device.secret):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            messages.success(request, "Two-factor authentication enabled.")
            return redirect("accounts:account")
        messages.error(request, "Invalid verification code.")

    return render(
        request,
        "accounts/two_factor_setup.html",
        {
            "form": form,
            "qr_data_uri": qr_data_uri,
            "secret": device.secret,
        },
    )


def two_factor_verify(request):
    user_id = request.session.get("pre_2fa_user_id")
    if not user_id:
        return redirect("accounts:login")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.pop("pre_2fa_user_id", None)
        return redirect("accounts:login")

    device = getattr(user, "two_factor_device", None)
    if not device or not device.confirmed:
        request.session.pop("pre_2fa_user_id", None)
        login(request, user)
        return redirect("chat:chat")

    form = TotpVerifyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if verify_totp(form.cleaned_data["code"], device.secret):
            login(request, user)
            request.session.pop("pre_2fa_user_id", None)
            return redirect("chat:chat")
        messages.error(request, "Invalid verification code.")

    return render(request, "accounts/two_factor_verify.html", {"form": form})


@login_required
def two_factor_disable(request):
    device = getattr(request.user, "two_factor_device", None)
    if request.method == "POST":
        if device:
            device.delete()
        messages.success(request, "Two-factor authentication disabled.")
        return redirect("accounts:account")

    return render(request, "accounts/two_factor_disable.html", {"device": device})

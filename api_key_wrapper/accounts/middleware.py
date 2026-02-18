from django.http import JsonResponse
from django.shortcuts import redirect


class RequireTwoFactorMiddleware:
    """
    Require authenticated users to enable 2FA before accessing app routes.
    """

    EXEMPT_PREFIXES = (
        "/account/login/",
        "/account/logout/",
        "/account/2fa/setup/",
        "/account/2fa/verify/",
        "/static/",
        "/admin/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            device = getattr(request.user, "two_factor_device", None)
            has_confirmed_2fa = bool(device and device.confirmed)
            if not has_confirmed_2fa and not request.path.startswith(self.EXEMPT_PREFIXES):
                if request.path.startswith("/api/"):
                    return JsonResponse({"error": "Two-factor authentication is required."}, status=403)
                return redirect("accounts:two_factor_setup")
        return self.get_response(request)

import pyotp
from django.test import TestCase
from django.urls import reverse

from .models import TwoFactorDevice, User


class AuthFlowTests(TestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password=self.password,
        )

    def test_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "tester@example.com", "password": self.password},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/chat/")

    def test_login_requires_2fa(self):
        secret = pyotp.random_base32()
        TwoFactorDevice.objects.create(user=self.user, secret=secret, confirmed=True)

        response = self.client.post(
            reverse("accounts:login"),
            {"email": "tester@example.com", "password": self.password},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/account/2fa/verify/")

        code = pyotp.TOTP(secret).now()
        response = self.client.post(
            reverse("accounts:two_factor_verify"),
            {"code": code},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/chat/")

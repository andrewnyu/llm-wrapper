import pyotp
from django.test import TestCase
from django.urls import reverse

from .models import TwoFactorDevice, User
from api_key_wrapper.usage.models import UsageEvent, UsageWallet


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
        self.assertEqual(response["Location"], "/account/2fa/setup/")

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

    def test_api_blocked_until_2fa_enabled(self):
        self.client.post(
            reverse("accounts:login"),
            {"email": "tester@example.com", "password": self.password},
        )
        response = self.client.post(
            reverse("chat_complete"),
            data='{"provider":"openai","model":"gpt-4o-mini","messages":[{"role":"user","content":"Hi"}]}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Two-factor authentication is required.")

    def test_account_password_change(self):
        secret = pyotp.random_base32()
        TwoFactorDevice.objects.create(user=self.user, secret=secret, confirmed=True)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:account"),
            {
                "old_password": self.password,
                "new_password1": "NewPass123!!",
                "new_password2": "NewPass123!!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("accounts:account"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass123!!"))

    def test_admin_user_add_defaults_initial_load_to_ten(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="AdminPass123!",
        )
        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "initial_load": "",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        created = User.objects.get(username="newuser")
        wallet = UsageWallet.objects.get(user=created)
        self.assertEqual(str(wallet.balance_credits), "10.0000")

    def test_admin_user_add_respects_custom_initial_load(self):
        admin_user = User.objects.create_superuser(
            username="admin2",
            email="admin2@example.com",
            password="AdminPass123!",
        )
        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "username": "customload",
                "email": "customload@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "initial_load": "25.5000",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        created = User.objects.get(username="customload")
        wallet = UsageWallet.objects.get(user=created)
        self.assertEqual(str(wallet.balance_credits), "25.5000")

    def test_signup_creates_user_loads_default_credits_and_redirects_to_2fa_setup(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "selfsignup",
                "email": "selfsignup@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("accounts:two_factor_setup"))

        created = User.objects.get(username="selfsignup")
        wallet = UsageWallet.objects.get(user=created)
        self.assertEqual(str(wallet.balance_credits), "10.0000")

        load_event = UsageEvent.objects.filter(user=created, event_type=UsageEvent.EVENT_LOAD).latest("created_at")
        self.assertEqual(str(load_event.credits_delta), "10.0000")
        self.assertEqual(load_event.metadata.get("source"), "self_signup")

        self.assertEqual(self.client.session.get("_auth_user_id"), str(created.id))

    def test_signup_rejects_duplicate_email(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "dupeuser",
                "email": "tester@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")

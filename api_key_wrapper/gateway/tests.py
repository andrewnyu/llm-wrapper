import os
from unittest.mock import patch
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from api_key_wrapper.accounts.models import TwoFactorDevice, User
from api_key_wrapper.imaging.models import ImageJob
from api_key_wrapper.gateway.providers.base import ChatCompletionResult, ImageGenerationResult
from api_key_wrapper.usage.models import UsageEvent, UsageWallet


class ChatApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="TestPass123!",
        )
        TwoFactorDevice.objects.create(user=self.user, secret="JBSWY3DPEHPK3PXP", confirmed=True)
        UsageWallet.objects.update_or_create(
            user=self.user,
            defaults={"balance_credits": Decimal("100.0000")},
        )

    def test_chat_complete_success(self):
        self.client.login(username="tester", password="TestPass123!")

        mock_result = ChatCompletionResult(
            text="Hello from OpenAI",
            usage={"total_tokens": 100},
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("api_key_wrapper.gateway.api_views.get_provider_client") as mock_client:
                mock_client.return_value.chat_complete.return_value = mock_result
                response = self.client.post(
                    reverse("chat_complete"),
                    data='{"provider":"openai","model":"gpt-4o-mini","messages":[{"role":"user","content":"Hi"}]}',
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "Hello from OpenAI")
        self.assertIn("usage_charged", response.json())
        self.assertIn("remaining_credits", response.json())

    def test_chat_complete_rejects_when_insufficient_credits(self):
        self.client.login(username="tester", password="TestPass123!")
        wallet = UsageWallet.objects.get(user=self.user)
        wallet.balance_credits = Decimal("0.0000")
        wallet.save(update_fields=["balance_credits", "updated_at"])

        response = self.client.post(
            reverse("chat_complete"),
            data='{"provider":"openai","model":"gpt-4o-mini","messages":[{"role":"user","content":"Hi"}]}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["error"], "Insufficient credits")

    def test_chat_complete_estimates_tokens_when_usage_missing(self):
        self.client.login(username="tester", password="TestPass123!")

        mock_result = ChatCompletionResult(text="Hello from OpenAI", usage=None)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("api_key_wrapper.gateway.api_views.get_provider_client") as mock_client:
                mock_client.return_value.chat_complete.return_value = mock_result
                response = self.client.post(
                    reverse("chat_complete"),
                    data='{"provider":"openai","model":"gpt-4o-mini","messages":[{"role":"user","content":"Hi"}]}',
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        event = UsageEvent.objects.filter(user=self.user, event_type=UsageEvent.EVENT_TEXT_CONSUME).latest("created_at")
        self.assertTrue(event.metadata["token_estimated"])


class ImageApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="imager",
            email="imager@example.com",
            password="TestPass123!",
        )
        TwoFactorDevice.objects.create(user=self.user, secret="JBSWY3DPEHPK3PXP", confirmed=True)
        UsageWallet.objects.update_or_create(
            user=self.user,
            defaults={"balance_credits": Decimal("100.0000")},
        )

    def test_image_edit_success(self):
        self.client.login(username="imager", password="TestPass123!")

        mock_result = ImageGenerationResult(
            images=[{"base64": "data:image/png;base64,AAA"}],
            text="Description ready.",
        )
        with patch.dict(os.environ, {"NANO_BANANA_API_KEY": "test-key"}, clear=False):
            with patch("api_key_wrapper.gateway.api_views.get_provider_client") as mock_client:
                mock_client.return_value.image_edit.return_value = mock_result
                response = self.client.post(
                    reverse("image_edit"),
                    data='{"prompt":"add a hat","input_image":"data:image/png;base64,AAA"}',
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["images"]), 1)
        self.assertEqual(response.json()["text"], "Description ready.")
        self.assertEqual(response.json()["usage_charged"], "1.0000")
        self.assertIn("remaining_credits", response.json())
        self.assertEqual(response.json()["settings"]["model"], "gemini-3.1-flash-image")
        called_payload = mock_client.return_value.image_edit.call_args[0][1]
        self.assertEqual(called_payload["aspect_ratio"], "1:1")
        self.assertEqual(called_payload["image_size"], "1K")

    def test_image_generate_rejects_invalid_model_settings(self):
        self.client.login(username="imager", password="TestPass123!")
        response = self.client.post(
            reverse("image_generate"),
            data='{"prompt":"a dog astronaut","model":"gemini-2.5-flash-image","image_size":"4K"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Unsupported resolution for this image model")

    def test_image_edit_requires_input_image(self):
        self.client.login(username="imager", password="TestPass123!")

        response = self.client.post(
            reverse("image_edit"),
            data='{"prompt":"add a hat"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "input_image is required")

    def test_image_generate_rejects_when_insufficient_credits(self):
        self.client.login(username="imager", password="TestPass123!")
        wallet = UsageWallet.objects.get(user=self.user)
        wallet.balance_credits = Decimal("0.0000")
        wallet.save(update_fields=["balance_credits", "updated_at"])

        response = self.client.post(
            reverse("image_generate"),
            data='{"prompt":"a dog astronaut"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["error"], "Insufficient credits")

    def test_image_feedback_success_uses_default_prompt_when_missing(self):
        self.client.login(username="imager", password="TestPass123!")

        mock_result = ImageGenerationResult(images=[], text="Found typo in the headline.")
        with patch.dict(os.environ, {"NANO_BANANA_API_KEY": "test-key"}, clear=False):
            with patch("api_key_wrapper.gateway.api_views.get_provider_client") as mock_client:
                mock_client.return_value.image_edit.return_value = mock_result
                response = self.client.post(
                    reverse("image_feedback"),
                    data='{"input_image":"data:image/png;base64,AAA"}',
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "Found typo in the headline.")
        called_payload = mock_client.return_value.image_edit.call_args[0][1]
        self.assertIn("Analyze this image", called_payload["prompt"])
        job = ImageJob.objects.latest("created_at")
        self.assertEqual(job.kind, ImageJob.KIND_FEEDBACK)

    def test_image_feedback_requires_input_image(self):
        self.client.login(username="imager", password="TestPass123!")

        response = self.client.post(
            reverse("image_feedback"),
            data='{"prompt":"describe this"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "input_image is required")

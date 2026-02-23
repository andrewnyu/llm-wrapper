import os
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from api_key_wrapper.accounts.models import TwoFactorDevice, User
from api_key_wrapper.gateway.providers.base import ChatCompletionResult, ImageGenerationResult


class ChatApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="TestPass123!",
        )
        TwoFactorDevice.objects.create(user=self.user, secret="JBSWY3DPEHPK3PXP", confirmed=True)

    def test_chat_complete_success(self):
        self.client.login(username="tester", password="TestPass123!")

        mock_result = ChatCompletionResult(text="Hello from OpenAI")
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


class ImageApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="imager",
            email="imager@example.com",
            password="TestPass123!",
        )
        TwoFactorDevice.objects.create(user=self.user, secret="JBSWY3DPEHPK3PXP", confirmed=True)

    def test_image_edit_success(self):
        self.client.login(username="imager", password="TestPass123!")

        mock_result = ImageGenerationResult(
            images=[{"base64": "data:image/png;base64,AAA"}],
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

    def test_image_edit_requires_input_image(self):
        self.client.login(username="imager", password="TestPass123!")

        response = self.client.post(
            reverse("image_edit"),
            data='{"prompt":"add a hat"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "input_image is required")

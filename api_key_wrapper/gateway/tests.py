import os
from unittest.mock import patch
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from api_key_wrapper.accounts.models import TwoFactorDevice, User
from api_key_wrapper.gateway.model_catalog import get_chat_model, serialize_chat_models
from api_key_wrapper.gateway.models import ProviderModel
from api_key_wrapper.imaging.models import ImageJob
from api_key_wrapper.gateway.providers.base import ChatCompletionResult, ImageGenerationResult
from api_key_wrapper.gateway.providers.nano_banana import NanoBananaClient
from api_key_wrapper.usage.models import UsageEvent, UsageWallet


class ChatModelCatalogTests(TestCase):
    def test_configured_anthropic_key_enables_default_claude_models(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            models = serialize_chat_models()

        claude_models = [item for item in models if item["provider"] == "anthropic"]
        self.assertTrue(claude_models)
        self.assertTrue(all(item["configured"] for item in claude_models))

    def test_provider_specific_env_models_are_discovered(self):
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-key",
                "DEEPSEEK_CHAT_MODELS": "deepseek-chat=DeepSeek Chat,deepseek-custom=DeepSeek Custom",
            },
            clear=False,
        ):
            model = get_chat_model("deepseek", "deepseek-custom")

        self.assertIsNotNone(model)
        self.assertEqual(model["label"], "DeepSeek Custom")

    def test_global_env_models_are_discovered(self):
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-key",
                "CHAT_MODELS": "anthropic:claude-custom=Claude Custom",
            },
            clear=False,
        ):
            model = get_chat_model("anthropic", "claude-custom")

        self.assertIsNotNone(model)
        self.assertEqual(model["label"], "Claude Custom")

    def test_admin_display_name_overrides_catalog_label(self):
        ProviderModel.objects.create(
            provider="deepseek",
            model="deepseek-chat",
            display_name="Drew's DeepSeek",
        )

        model = get_chat_model("deepseek", "deepseek-chat")

        self.assertEqual(model["label"], "Drew's DeepSeek")

    def test_admin_can_disable_catalog_model(self):
        ProviderModel.objects.create(
            provider="deepseek",
            model="deepseek-chat",
            display_name="Hidden DeepSeek",
            is_enabled=False,
        )

        self.assertIsNone(get_chat_model("deepseek", "deepseek-chat"))


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

    def test_image_provider_failure_does_not_charge_credits(self):
        self.client.login(username="imager", password="TestPass123!")
        starting_balance = UsageWallet.objects.get(user=self.user).balance_credits

        with patch.dict(os.environ, {"NANO_BANANA_API_KEY": "test-key"}, clear=False):
            with patch("api_key_wrapper.gateway.api_views.get_provider_client") as mock_client:
                mock_client.return_value.image_generate.side_effect = RuntimeError("provider down")
                response = self.client.post(
                    reverse("image_generate"),
                    data='{"prompt":"a dog astronaut"}',
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 502)
        wallet = UsageWallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance_credits, starting_balance)
        self.assertFalse(
            UsageEvent.objects.filter(
                user=self.user,
                event_type=UsageEvent.EVENT_IMAGE_CONSUME,
            ).exists()
        )

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


class NanoBananaInputTests(TestCase):
    def test_rejects_remote_reference_urls(self):
        with self.assertRaisesMessage(ValueError, "input_image must be a data URL"):
            NanoBananaClient()._parse_data_url("http://127.0.0.1/private")

    def test_rejects_unsupported_image_types(self):
        with self.assertRaisesMessage(ValueError, "PNG, JPEG, or WebP"):
            NanoBananaClient()._parse_data_url("data:image/svg+xml;base64,PHN2Zz4=")

import os
from unittest.mock import patch
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from api_key_wrapper.accounts.models import TwoFactorDevice, User
from api_key_wrapper.gateway.key_resolver import get_api_key_for_provider, is_provider_configured
from api_key_wrapper.gateway.model_catalog import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_CHAT_PROVIDER,
    DEFAULT_IMAGE_MODEL,
    get_chat_model,
    get_default_chat_model,
    get_image_model,
    serialize_chat_models,
    serialize_image_models,
)
from api_key_wrapper.gateway.models import GatewaySettings, ProviderModel
from api_key_wrapper.imaging.models import ImageConversation, ImageJob
from api_key_wrapper.gateway.providers.base import ChatCompletionResult, ImageGenerationResult
from api_key_wrapper.gateway.providers.glm import GLMClient
from api_key_wrapper.gateway.providers.nano_banana import NanoBananaClient
from api_key_wrapper.usage.models import UsageEvent, UsageWallet


class ChatModelCatalogTests(TestCase):
    def test_chinese_models_are_the_defaults(self):
        self.assertEqual(DEFAULT_CHAT_PROVIDER, "glm")
        self.assertEqual(DEFAULT_CHAT_MODEL, "glm-5.2")
        self.assertEqual(DEFAULT_IMAGE_MODEL, "glm-image")

    def test_configured_anthropic_key_enables_default_claude_models(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            models = serialize_chat_models()

        claude_models = [item for item in models if item["provider"] == "anthropic"]
        self.assertTrue(claude_models)
        self.assertTrue(all(item["configured"] for item in claude_models))

    def test_glm_and_kimi_keys_enable_chat_models(self):
        with patch.dict(os.environ, {"GLM_API_KEY": "glm-key", "KIMI_API_KEY": "kimi-key"}, clear=False):
            models = serialize_chat_models()

        self.assertTrue(any(item["provider"] == "glm" and item["configured"] for item in models))
        self.assertTrue(any(item["provider"] == "kimi" and item["configured"] for item in models))

    def test_saved_default_chat_model_is_used_when_configured(self):
        GatewaySettings.objects.create(
            default_chat_provider="deepseek",
            default_chat_model="deepseek-chat",
            enabled_providers=["deepseek"],
        )
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=False):
            choice = get_default_chat_model()

        self.assertEqual((choice["provider"], choice["model"]), ("deepseek", "deepseek-chat"))

    def test_disabled_provider_key_cannot_be_used(self):
        GatewaySettings.objects.create(
            default_chat_provider="glm",
            default_chat_model="glm-5.2",
            enabled_providers=["glm"],
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            self.assertFalse(is_provider_configured("openai"))
            with self.assertRaisesMessage(ValueError, "disabled by an administrator"):
                get_api_key_for_provider("openai")

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

    def test_nano_banana_can_use_google_api_key_fallback(self):
        with patch.dict(os.environ, {"NANO_BANANA_API_KEY": "", "GOOGLE_API_KEY": "google-key"}, clear=False):
            self.assertTrue(is_provider_configured("nano_banana"))
            self.assertEqual(get_api_key_for_provider("nano_banana"), "google-key")

    def test_glm_key_enables_image_model(self):
        with patch.dict(os.environ, {"GLM_API_KEY": "glm-key"}, clear=False):
            image_models = serialize_image_models()

        glm_image = next(item for item in image_models if item["provider"] == "glm")
        self.assertEqual(glm_image["model"], "glm-image")
        self.assertTrue(glm_image["configured"])
        self.assertIsNotNone(get_image_model("glm-image"))


class GatewaySettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="gateway-admin",
            email="gateway-admin@example.com",
            password="TestPass123!",
            is_staff=True,
        )
        TwoFactorDevice.objects.create(user=self.user, secret="JBSWY3DPEHPK3PXP", confirmed=True)

    def test_staff_can_save_default_and_allowed_providers(self):
        self.client.login(username="gateway-admin", password="TestPass123!")
        response = self.client.post(
            reverse("gateway:settings"),
            {
                "default_chat_provider": "deepseek",
                "default_chat_model": "deepseek-chat",
                "enabled_providers": ["deepseek", "glm"],
            },
        )

        self.assertRedirects(response, reverse("gateway:settings"))
        config = GatewaySettings.objects.get(pk=1)
        self.assertEqual(config.default_chat_provider, "deepseek")
        self.assertEqual(config.default_chat_model, "deepseek-chat")
        self.assertEqual(config.enabled_providers, ["deepseek", "glm"])

    def test_non_staff_cannot_open_settings(self):
        user = User.objects.create_user(
            username="regular-user",
            email="regular-user@example.com",
            password="TestPass123!",
        )
        TwoFactorDevice.objects.create(user=user, secret="JBSWY3DPEHPK3PXP", confirmed=True)
        self.client.login(username="regular-user", password="TestPass123!")

        response = self.client.get(reverse("gateway:settings"))

        self.assertEqual(response.status_code, 302)


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
                    data='{"prompt":"add a hat","model":"gemini-3.1-flash-image","input_image":"data:image/png;base64,AAA"}',
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

    def test_image_generate_creates_conversation_when_missing(self):
        self.client.login(username="imager", password="TestPass123!")

        mock_result = ImageGenerationResult(images=[{"url": "https://example.test/cat.png"}], text="Done")
        with patch.dict(os.environ, {"GLM_API_KEY": "test-key"}, clear=False):
            with patch("api_key_wrapper.gateway.api_views.get_provider_client") as mock_client:
                mock_client.return_value.image_generate.return_value = mock_result
                response = self.client.post(
                    reverse("image_generate"),
                    data='{"prompt":"minimal cat poster"}',
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["conversation"]["kind"], ImageConversation.KIND_STUDIO)
        self.assertEqual(body["conversation"]["title"], "minimal cat poster")
        job = ImageJob.objects.get(id=body["job_id"])
        self.assertEqual(str(job.conversation_id), body["conversation"]["id"])

    def test_image_conversation_jobs_are_paginated(self):
        self.client.login(username="imager", password="TestPass123!")
        conversation = ImageConversation.objects.create(
            user=self.user,
            kind=ImageConversation.KIND_STUDIO,
            title="Paged",
        )
        first = ImageJob.objects.create(
            user=self.user,
            conversation=conversation,
            prompt="first",
            provider="nano_banana",
            kind=ImageJob.KIND_STUDIO,
            status="success",
        )
        second = ImageJob.objects.create(
            user=self.user,
            conversation=conversation,
            prompt="second",
            provider="nano_banana",
            kind=ImageJob.KIND_STUDIO,
            status="success",
        )

        response = self.client.get(
            reverse("image_conversation_jobs", kwargs={"conversation_id": conversation.id}),
            {"limit": 1},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["hasMore"])
        self.assertEqual(body["items"][0]["id"], second.id)

        response = self.client.get(
            reverse("image_conversation_jobs", kwargs={"conversation_id": conversation.id}),
            {"limit": 1, "before": body["items"][0]["createdAt"]},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["hasMore"])
        self.assertEqual(body["items"][0]["id"], first.id)

    def test_image_conversations_are_kind_filtered(self):
        self.client.login(username="imager", password="TestPass123!")
        studio = ImageConversation.objects.create(user=self.user, kind=ImageConversation.KIND_STUDIO, title="Studio")
        ImageConversation.objects.create(user=self.user, kind=ImageConversation.KIND_FEEDBACK, title="Feedback")

        response = self.client.get(reverse("image_conversations"), {"kind": "studio"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["items"]], [str(studio.id)])

    def test_image_generate_rejects_invalid_model_settings(self):
        self.client.login(username="imager", password="TestPass123!")
        response = self.client.post(
            reverse("image_generate"),
            data='{"prompt":"a dog astronaut","model":"gemini-2.5-flash-image","image_size":"4K"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Unsupported resolution for this image model")

    def test_glm_image_generate_success(self):
        self.client.login(username="imager", password="TestPass123!")

        mock_result = ImageGenerationResult(images=[{"url": "https://example.test/glm.png"}])
        with patch.dict(os.environ, {"GLM_API_KEY": "test-key"}, clear=False):
            with patch("api_key_wrapper.gateway.api_views.get_provider_client") as mock_client:
                mock_client.return_value.image_generate.return_value = mock_result
                response = self.client.post(
                    reverse("image_generate"),
                    data='{"prompt":"a sleek app icon","model":"glm-image"}',
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["images"], [{"url": "https://example.test/glm.png"}])
        self.assertEqual(response.json()["settings"]["provider"], "glm")
        called_payload = mock_client.return_value.image_generate.call_args[0][1]
        self.assertEqual(called_payload["model"], "glm-image")

    def test_glm_image_edit_rejected_as_unsupported(self):
        self.client.login(username="imager", password="TestPass123!")

        with patch.dict(os.environ, {"GLM_API_KEY": "test-key"}, clear=False):
            response = self.client.post(
                reverse("image_edit"),
                data='{"prompt":"make it blue","model":"glm-image","input_image":"data:image/png;base64,AAA"}',
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "This image model does not support reference-image edits")

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

        with patch.dict(os.environ, {"GLM_API_KEY": "test-key"}, clear=False):
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
        self.assertFalse(ImageConversation.objects.filter(user=self.user).exists())

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
        self.assertEqual(response.json()["conversation"]["kind"], ImageConversation.KIND_FEEDBACK)
        called_payload = mock_client.return_value.image_edit.call_args[0][1]
        self.assertIn("Analyze this image", called_payload["prompt"])
        job = ImageJob.objects.latest("created_at")
        self.assertEqual(job.kind, ImageJob.KIND_FEEDBACK)
        self.assertEqual(job.conversation.kind, ImageConversation.KIND_FEEDBACK)

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


class GLMProviderTests(TestCase):
    def test_image_generate_normalizes_url_results(self):
        client = GLMClient()
        with patch("api_key_wrapper.gateway.providers.glm.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {"data": [{"url": "https://example.test/image.png"}]}

            result = client.image_generate(
                "glm-key",
                {"prompt": "a clean product photo", "model": "glm-image", "aspect_ratio": "16:9"},
            )

        self.assertEqual(result.images, [{"url": "https://example.test/image.png"}])
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["json"]["model"], "glm-image")
        self.assertEqual(call_kwargs["json"]["prompt"], "a clean product photo")
        self.assertEqual(call_kwargs["json"]["size"], "1728x960")
        self.assertEqual(call_kwargs["timeout"], 60)

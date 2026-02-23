import os
from unittest.mock import patch
from decimal import Decimal

from django.test import TestCase

from api_key_wrapper.accounts.models import TwoFactorDevice, User
from api_key_wrapper.chat.models import Conversation, Message
from api_key_wrapper.usage.models import UsageWallet


class ChatApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="chatuser",
            email="chatuser@example.com",
            password="TestPass123!",
        )
        TwoFactorDevice.objects.create(user=self.user, secret="JBSWY3DPEHPK3PXP", confirmed=True)
        UsageWallet.objects.update_or_create(
            user=self.user,
            defaults={"balance_credits": Decimal("100.0000")},
        )
        self.client.login(username="chatuser", password="TestPass123!")

    def test_conversation_crud(self):
        create_res = self.client.post(
            "/api/conversations",
            data='{"title":"First"}',
            content_type="application/json",
        )
        self.assertEqual(create_res.status_code, 201)
        conversation_id = create_res.json()["id"]

        list_res = self.client.get("/api/conversations")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.json()["items"]), 1)

        rename_res = self.client.patch(
            f"/api/conversations/{conversation_id}",
            data='{"title":"Renamed"}',
            content_type="application/json",
        )
        self.assertEqual(rename_res.status_code, 200)
        self.assertEqual(rename_res.json()["title"], "Renamed")

        delete_res = self.client.delete(f"/api/conversations/{conversation_id}")
        self.assertEqual(delete_res.status_code, 200)
        self.assertFalse(Conversation.objects.exists())

    def test_message_list_endpoint(self):
        conversation = Conversation.objects.create(user=self.user, title="Demo")
        Message.objects.create(conversation=conversation, role="user", content="Hello")
        response = self.client.get(f"/api/conversations/{conversation.id}/messages")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content"], "Hello")

    def test_streaming_smoke(self):
        conversation = Conversation.objects.create(user=self.user, title="Demo")

        def fake_generate(**kwargs):
            on_token = kwargs.get("on_token")
            if on_token:
                on_token("Hi ")
                on_token("there")
            return "Hi there"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("api_key_wrapper.chat.views.generate", side_effect=fake_generate):
                response = self.client.post(
                    f"/api/conversations/{conversation.id}/messages",
                    data='{"content":"Say hi"}',
                    content_type="application/json",
                )
                payload = b"".join(response.streaming_content).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertIn("event: meta", payload)
        self.assertIn("event: delta", payload)
        self.assertIn("event: done", payload)
        self.assertIn('"usageCharged"', payload)
        self.assertIn('"remainingCredits"', payload)

        assistant = Message.objects.filter(conversation=conversation, role="assistant").latest("created_at")
        self.assertEqual(assistant.content, "Hi there")

    def test_streaming_rejects_when_insufficient_credits(self):
        conversation = Conversation.objects.create(user=self.user, title="LowCredits")
        wallet = UsageWallet.objects.get(user=self.user)
        wallet.balance_credits = Decimal("0.0000")
        wallet.save(update_fields=["balance_credits", "updated_at"])

        response = self.client.post(
            f"/api/conversations/{conversation.id}/messages",
            data='{"content":"Say hi"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["error"], "Insufficient credits")

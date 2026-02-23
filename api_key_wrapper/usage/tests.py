from decimal import Decimal

from django.test import TestCase

from api_key_wrapper.accounts.models import User
from api_key_wrapper.usage.models import UsageEvent
from api_key_wrapper.usage.services import (
    InsufficientCreditsError,
    charge_image_request,
    charge_text_tokens,
    get_or_create_wallet,
    load_credits,
)


class UsageServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="usageuser",
            email="usage@example.com",
            password="TestPass123!",
        )

    def test_load_credits_creates_event_and_updates_wallet(self):
        wallet, event = load_credits(user=self.user, amount="10")

        self.assertEqual(wallet.balance_credits, Decimal("10.0000"))
        self.assertEqual(wallet.total_loaded_credits, Decimal("10.0000"))
        self.assertEqual(event.event_type, UsageEvent.EVENT_LOAD)
        self.assertEqual(event.credits_delta, Decimal("10.0000"))

    def test_charge_image_request_decrements_wallet(self):
        load_credits(user=self.user, amount="5")

        wallet, event, charged = charge_image_request(user=self.user, feature="image_generate")
        self.assertEqual(charged, Decimal("1.0000"))
        self.assertEqual(wallet.balance_credits, Decimal("4.0000"))
        self.assertEqual(event.event_type, UsageEvent.EVENT_IMAGE_CONSUME)

    def test_charge_text_tokens_estimates_when_missing(self):
        load_credits(user=self.user, amount="5")

        wallet, event, charged = charge_text_tokens(
            user=self.user,
            feature="chat_complete",
            token_count=None,
            input_text="hello world",
            output_text="this is a longer response",
        )
        self.assertGreater(charged, Decimal("0"))
        self.assertEqual(event.event_type, UsageEvent.EVENT_TEXT_CONSUME)
        self.assertTrue(event.metadata["token_estimated"])
        self.assertLess(wallet.balance_credits, Decimal("5.0000"))

    def test_charge_fails_when_insufficient(self):
        get_or_create_wallet(self.user)
        with self.assertRaises(InsufficientCreditsError):
            charge_image_request(user=self.user, feature="image_edit")

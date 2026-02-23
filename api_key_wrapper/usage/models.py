from decimal import Decimal

from django.conf import settings
from django.db import models


class UsageWallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_wallet",
    )
    balance_credits = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal("0"))
    total_loaded_credits = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal("0"))
    total_used_credits = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"Wallet for {self.user_id}: {self.balance_credits}"


class UsageEvent(models.Model):
    EVENT_LOAD = "load"
    EVENT_IMAGE_CONSUME = "image_consume"
    EVENT_TEXT_CONSUME = "text_consume"
    EVENT_ADJUSTMENT = "adjustment"

    EVENT_CHOICES = [
        (EVENT_LOAD, "Load"),
        (EVENT_IMAGE_CONSUME, "Image Consume"),
        (EVENT_TEXT_CONSUME, "Text Consume"),
        (EVENT_ADJUSTMENT, "Adjustment"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_events",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    credits_delta = models.DecimalField(max_digits=16, decimal_places=4)
    unit_count = models.PositiveIntegerField(default=0)
    feature = models.CharField(max_length=64, blank=True, default="")
    reference_id = models.CharField(max_length=128, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_usage_events",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="usage_user_created_idx"),
            models.Index(fields=["event_type", "created_at"], name="usage_type_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.credits_delta})"

import uuid

from django.conf import settings
from django.db import models


class ImageConversation(models.Model):
    KIND_STUDIO = "studio"
    KIND_FEEDBACK = "feedback"
    KIND_CHOICES = [
        (KIND_STUDIO, "Studio"),
        (KIND_FEEDBACK, "Feedback"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="image_conversations",
    )
    title = models.CharField(max_length=120, default="New image chat")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=KIND_STUDIO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "kind", "updated_at"], name="img_conv_user_kind_upd_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class ImageJob(models.Model):
    KIND_STUDIO = ImageConversation.KIND_STUDIO
    KIND_FEEDBACK = ImageConversation.KIND_FEEDBACK
    KIND_CHOICES = ImageConversation.KIND_CHOICES

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    conversation = models.ForeignKey(
        ImageConversation,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    prompt = models.TextField()
    provider = models.CharField(max_length=32, default="nano_banana")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=KIND_STUDIO)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    result_text = models.TextField(blank=True, default="")
    result_urls = models.JSONField(default=list, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="img_job_conv_created_idx"),
            models.Index(fields=["user", "kind", "created_at"], name="img_job_user_kind_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.provider} ({self.status})"

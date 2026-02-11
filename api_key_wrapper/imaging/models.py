from django.conf import settings
from django.db import models


class ImageJob(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    prompt = models.TextField()
    provider = models.CharField(max_length=32, default="nano_banana")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    result_urls = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.provider} ({self.status})"

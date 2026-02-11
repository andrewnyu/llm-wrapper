from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return self.email or self.username


class TwoFactorDevice(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="two_factor_device")
    secret = models.CharField(max_length=64)
    confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        status = "enabled" if self.confirmed else "pending"
        return f"2FA for {self.user_id} ({status})"

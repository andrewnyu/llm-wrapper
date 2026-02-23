from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UsageWallet


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_usage_wallet(sender, instance, created, **kwargs):
    if created:
        UsageWallet.objects.get_or_create(user=instance)

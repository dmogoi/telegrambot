from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from .models import RefreshTracker, KeywordResponse, ScheduledMessage, SMSRecipient

logger = logging.getLogger(__name__)


@receiver(post_save, sender=KeywordResponse)
@receiver(post_save, sender=ScheduledMessage)
@receiver(post_save, sender=SMSRecipient)
@receiver(post_delete, sender=KeywordResponse)
@receiver(post_delete, sender=ScheduledMessage)
@receiver(post_delete, sender=SMSRecipient)
def global_refresh_handler(sender, **kwargs):
    """Safe refresh handler with auto-creation"""
    tracker, created = RefreshTracker.objects.get_or_create(pk=1)
    tracker.current_version += 1
    tracker.save()
def handle_model_change(sender, **kwargs):
    RefreshTracker.bump_version()
    logger.info("♻️ Global version bumped due to model change")

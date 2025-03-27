from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from .models import RefreshTracker, KeywordResponse, ScheduledMessage, SMSRecipient, MessageLog, SMSNotification, \
    BotStatus

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


# signals.py (Automated alerts)
from django.db.models.signals import post_save
from django.dispatch import receiver
from .tasks import send_critical_sms

@receiver(post_save, sender=BotStatus)
def check_system_health(sender, instance, **kwargs):
    if instance.health_status == 'critical':
        message = f"CRITICAL ALERT: System health {instance.health_status}"
        send_critical_sms.delay(message)

@receiver(post_save, sender=SMSNotification)
def check_sms_balance(sender, instance, **kwargs):
    if instance.status == 'failed' and 'balance' in instance.error:
        remaining = instance.error.get('balance', 0)
        if remaining < 10:
            send_critical_sms.delay(f"SMS Balance Critical: {remaining} left")

@receiver(post_save, sender=MessageLog)
def update_realtime_metrics(sender, instance, **kwargs):
    cache.incr('message_count')
    # Update rate calculations
    current_rate = cache.get('message_rate', 0)
    new_rate = (current_rate * 0.7) + (1 / 60)  # Exponential smoothing
    cache.set('message_rate', new_rate, 60)

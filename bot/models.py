from datetime import timedelta

from django.db import models  # Django ORM model base class
from django.core.exceptions import ValidationError  # To raise validation errors
import phonenumbers  # Library for phone number validation
from django.utils import timezone  # To handle time-related functionality in Django
from django.contrib.auth.models import AbstractUser


def validate_phone_number(value):
    """
    Validates the phone number format using the phonenumbers library.
    This function ensures the phone number is correctly formatted and valid.
    """
    try:
        # Parse the phone number using the phonenumbers library
        parsed = phonenumbers.parse(value, "KE")  # "KE" stands for Kenya's country code
        # Check if the parsed number is valid
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationError("Invalid phone number format. Must be a valid Kenyan number.")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.phonenumberutil.NumberParseException:
        # Raise a validation error if the phone number format is invalid
        raise ValidationError("Invalid phone number format. Must be a valid Kenyan number.")


class KeywordResponse(models.Model):
    """
    Model representing a response for a specific trigger word (keyword).
    The bot will reply with a pre-configured response when the keyword is detected.
    """
    # Choices for priority of the keyword response
    PRIORITY_CHOICES = [
        ('high', 'High Priority'),
        ('normal', 'Normal Response')
    ]

    trigger_word = models.CharField(max_length=50, unique=True)  # The word that triggers the response
    response_text = models.TextField()  # The response message sent when the trigger word is detected
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal'  # Default priority is 'normal'
    )
    icon = models.ImageField(upload_to='icons/', null=True, blank=True)

    notify_owner = models.BooleanField(default=False)  # Flag to notify the owner when the keyword is triggered


class SMSRecipient(models.Model):
    """
    Model representing a recipient for SMS notifications.
    The bot will send SMS notifications to these recipients when certain actions occur.
    """
    name = models.CharField(max_length=100)  # Recipient's name
    phone = models.CharField(
        max_length=20,
        validators=[validate_phone_number]  # Apply the phone number validation
    )
    is_active = models.BooleanField(default=True)  # Flag indicating whether the recipient is active

    def __str__(self):
        # String representation of the SMS recipient (name and phone number)
        return f"{self.name} ({self.phone})"


class SMSNotification(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending')
    ]

    recipient = models.ForeignKey(SMSRecipient, on_delete=models.CASCADE)
    message = models.TextField()
    status = models.CharField(max_length=7, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)


class ScheduledMessage(models.Model):
    content = models.TextField()
    interval_hours = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(unique=True)
    is_active = models.BooleanField(default=True)
    last_sent = models.DateTimeField(null=True, blank=True)
    is_processing = models.BooleanField(default=False)
    image = models.ImageField(upload_to='scheduled_images/', null=True, blank=True)
    next_scheduled = models.DateTimeField(null=True, blank=True)  # NEW FIELD

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Message #{self.order} ({'active' if self.is_active else 'inactive'})"

    def save(self, *args, **kwargs):
        """Automatically calculate next scheduled time"""
        if not self.next_scheduled:
            if self.last_sent:
                self.next_scheduled = self.last_sent + timezone.timedelta(hours=self.interval_hours)
            else:
                self.next_scheduled = timezone.now()
        super().save(*args, **kwargs)


class RefreshTracker(models.Model):
    last_modified = models.DateTimeField(auto_now=True)
    current_version = models.PositiveIntegerField(default=0)

    @classmethod
    def bump_version(cls):
        tracker, _ = cls.objects.get_or_create(pk=1)
        tracker.current_version += 1
        tracker.save()
        return tracker.current_version


class UserInteraction(models.Model):
    user_id = models.BigIntegerField()
    user_name = models.CharField(max_length=255)
    last_interaction = models.DateTimeField()
    message_count = models.PositiveIntegerField(default=0)


class MessageLog(models.Model):
    MESSAGE_TYPES = [
        ('keyword', 'Keyword Response'),
        ('scheduled', 'Scheduled Message'),
        ('direct', 'Direct Message')

    ]

    user_id = models.BigIntegerField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='direct')
    content = models.TextField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['message_type']),
        ]


# class BotStatus(models.Model):
#     is_connected = models.BooleanField()
#     uptime = models.DurationField()
#     timestamp = models.DateTimeField(auto_now_add=True)
#
#     @property
#     def uptime_formatted(self):
#         seconds = self.uptime.total_seconds()
#         periods = [
#             ('day', 86400),
#             ('hour', 3600),
#             ('minute', 60),
#             ('second', 1)
#         ]
#
#         strings = []
#         for period_name, period_seconds in periods:
#             if seconds >= period_seconds:
#                 period_value, seconds = divmod(seconds, period_seconds)
#                 strings.append(f"{int(period_value)} {period_name}{'s' if period_value != 1 else ''}")
#
#         return ", ".join(strings[:2])


# models.py
class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('SMS_BALANCE', 'SMS API Balance'),
        ('KEYWORD_TRIGGER', 'Keyword Activated'),
        ('MESSAGE_SENT', 'Message Delivery'),
        ('CONNECTION', 'Bot Connection'),
        ('AUTH', 'Authentication'),
        ('RATE_LIMIT', 'Rate Limiting'),
        ('SCHEDULER', 'Message Scheduler'),
    )

    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()
    icon = models.CharField(max_length=30, default='info-circle')
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['read']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"{self.get_type_display()}: {self.message[:50]}"


class User(AbstractUser):
    ROLES = (
        ('admin', 'System Administrator'),
        ('manager', 'Content Manager'),
        ('viewer', 'Read-Only Viewer'),
    )
    role = models.CharField(max_length=20, choices=ROLES, default='viewer')

    def clean(self):
        super().clean()
        # Ensure role and superuser status are in sync
        if self.role == 'admin' and not self.is_superuser:
            self.is_superuser = True
        elif self.role != 'admin' and self.is_superuser:
            raise ValidationError('Superusers must have admin role')

    def save(self, *args, **kwargs):
        self.clean()  # Enforce validation before saving
        super().save(*args, **kwargs)


class Permission(models.Model):
    name = models.CharField(max_length=100)
    codename = models.CharField(max_length=100, unique=True)


# models.py
# models.py
# models.py
class AuditLog(models.Model):
    ACTION_TYPES = (
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('USER_UPDATE', 'User Modification'),
        ('SYSTEM_EVENT', 'System Event'),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPES,
        default='SYSTEM_EVENT'  # Add default value
    )
    model_name = models.CharField(
        max_length=100,
        default='Unknown'  # Add default value
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    model_name = models.CharField(max_length=100)  # Make sure this field exists
    object_id = models.CharField(max_length=100, null=True, blank=True)
    action = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['action_type']),
            models.Index(fields=['model_name']),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.get_action_type_display()} - {self.model_name}"  # Update existing models


class BotStatus(models.Model):
    is_connected = models.BooleanField(default=False)
    uptime = models.DurationField(default=timedelta(0))
    active_users = models.PositiveIntegerField(default=0)
    message_rate = models.FloatField(default=0)
    timestamp = models.DateTimeField(auto_now=True)

    @property
    def uptime_formatted(self):
        total_seconds = int(self.uptime.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    @property
    def health_status(self):
        return 'connected' if self.is_connected else 'disconnected'
        if self.message_rate > 50 or self.active_users > 100:
            return 'warning'
        return 'healthy'

    def save(self, *args, **kwargs):
        # Auto-update uptime when saving
        if self.is_connected and self.pk:
            original = BotStatus.objects.get(pk=self.pk)
            if original.is_connected:
                self.uptime += timezone.now() - original.timestamp
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Connection States"


# class MessageLog(models.Model):
#     processed = models.BooleanField(default=False)
#     response_time = models.FloatField(null=True)  # In seconds

class SystemMetrics(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    cpu_percent = models.FloatField(default=0.0)  # Added default
    memory_percent = models.FloatField(default=0.0)  # Added default
    disk_percent = models.FloatField(default=0.0)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'System Metrics'


class DashboardConfig(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    visible_widgets = models.JSONField(default=list)
    custom_filters = models.JSONField(default=dict)

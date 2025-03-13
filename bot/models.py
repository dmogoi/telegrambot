from django.db import models  # Django ORM model base class
from django.core.exceptions import ValidationError  # To raise validation errors
import phonenumbers  # Library for phone number validation
from django.utils import timezone  # To handle time-related functionality in Django


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

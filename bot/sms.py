import requests
import logging
from django.conf import settings
from django.utils import timezone

from .models import SMSRecipient, SMSNotification, Notification
import phonenumbers
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def send_bulk_sms(message):
    try:
        logger.info("Preparing bulk SMS")
        recipients = SMSRecipient.objects.filter(is_active=True)

        if not recipients.exists():
            logger.warning("No active SMS recipients found")
            return {"status": False, "message": "No active recipients"}

        # Create notifications first
        notifications = [
            SMSNotification(recipient=recipient, message=message, status='pending')
            for recipient in recipients
        ]
        SMSNotification.objects.bulk_create(notifications)

        # Format phone numbers properly
        phones = []
        for r in recipients:
            phone = r.phone.lstrip('0')
            if not phone.startswith('254'):
                phone = f'254{phone.lstrip("+")}'
            phones.append(phone)

        phone_list = ",".join(phones)
        logger.debug(f"Formatted phone numbers: {phone_list}")

        headers = {
            "Authorization": f"Bearer {settings.MOBILESASA_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = {
            "senderID": settings.SMS_SENDER_ID,
            "message": message,
            "phones": phone_list
        }

        logger.debug(f"SMS payload: {payload}")
        response = requests.post(
            "https://api.mobilesasa.com/v1/send/bulk",
            json=payload,
            headers=headers,
            timeout=10
        )

        logger.info(f"SMS API status code: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Failed SMS API response: {response.text}")
            return {"status": False, "error": "Failed to send SMS"}

        try:
            result = response.json()
        except ValueError:
            logger.error("Invalid JSON response from SMS API")
            return {"status": False, "error": "Invalid API response"}

        logger.debug(f"SMS API response: {result}")

        SMSNotification.objects.filter(id__in=[n.id for n in notifications]).update(
            status='success',
            sent_at=timezone.now()
        )

        # Check SMS balance
        if result.get('balance', 100) < 10:
            Notification.objects.create(
                type='SMS_BALANCE',
                message=f"SMS API Balance Low: {result['balance']} credits remaining",
                icon='exclamation-triangle',
                metadata={'balance': result['balance']}
            )

        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"SMS request failed: {str(e)}")
        return {"status": False, "error": str(e)}

    except Exception as e:
        logger.error(f"Unexpected SMS error: {str(e)}")
        Notification.objects.create(
            type='SMS_ERROR',
            message=f"SMS API Error: {str(e)}",
            icon='times-circle',
            metadata={'error': str(e)}
        )
        return {"status": False, "error": str(e)}

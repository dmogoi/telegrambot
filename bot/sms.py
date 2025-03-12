# sms.py
import requests
import logging
from django.conf import settings

from .models import SMSRecipient
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
        result = response.json()
        logger.debug(f"SMS API response: {result}")

        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"SMS request failed: {str(e)}")
        return {"status": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected SMS error: {str(e)}")
        return {"status": False, "error": str(e)}

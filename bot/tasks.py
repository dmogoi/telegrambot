# tasks.py
import asyncio
import logging
import os
import random
import socket

import psutil
from telethon import TelegramClient
from django.conf import settings
from django.utils import timezone
from celery import shared_task
from .models import ScheduledMessage, SystemMetrics, BotStatus, UserInteraction, MessageLog
from asgiref.sync import sync_to_async

from .sms import send_bulk_sms

logger = logging.getLogger(__name__)


# Improved Delay with Exponential Backoff for message sending
async def send_to_all_dialogs(client, message):
    """Send message to the first 100 dialogs (including groups, channels, and users) with error handling."""
    success = 0
    failures = 0
    limit = 40  # Limit to first 100 dialogs
    counter = 0  # Counter to keep track of sent dialogs
    max_retries = 1  # Maximum number of retries
    retry_delay = 5  # Initial delay time in seconds for retrying

    async for dialog in client.iter_dialogs():
        if counter >= limit:
            break  # Stop after 100 dialogs

        retries = 0  # Retry counter for each dialog

        while retries < max_retries:
            try:
                # If the dialog is a group, channel, or user
                if dialog.is_group or dialog.is_channel or dialog.is_user:
                    if message.image:
                        # Send image with text if image exists
                        await client.send_file(dialog.id, message.image, caption=message.content)
                        logger.info(f"✅ Sent message with image to {dialog.name} ({dialog.id})")
                    else:
                        # Send just the text if no image exists
                        await client.send_message(dialog.id, message.content)
                        logger.info(f"✅ Sent text message to {dialog.name} ({dialog.id})")

                    success += 1
                    counter += 1  # Increment the counter after sending each message

                    # Wait for a random delay between messages to avoid rate limiting
                    delay_time = random.randint(30, 90)  # Delay between 30 and 90 seconds
                    logger.info(f"⏳ Waiting {delay_time}s before sending to the next user")
                    await asyncio.sleep(delay_time)  # Wait for random delay
                    break  # Exit the retry loop if the message was sent successfully
                else:
                    # Skip non-group/channel/user dialogs (if needed)
                    logger.debug(f"❌ Skipping non-group/channel dialog {dialog.name} ({dialog.id})")
                    break  # No need to retry for non-valid dialogs

            except Exception as e:
                # Handle the specific error of rate limiting (Too many requests)
                if "Too many requests" in str(e):
                    retries += 1
                    # For the first retry, use the initial retry_delay of 30 seconds.
                    # For subsequent retries, apply exponential backoff.
                    wait_time = retry_delay if retries == 1 else retry_delay * (2 ** retries)
                    logger.warning(
                        f"⚠️ Rate-limited. Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    # If another exception occurs, log and break the retry loop
                    logger.error(f"❌ Failed to send message to {dialog.name} ({dialog.id}): {str(e)}")
                    failures += 1
                    break  # Exit retry loop for other errors



    return success, failures

@shared_task
def send_critical_sms(message):
    if settings.PRODUCTION:
        send_bulk_sms(message)
    logger.critical(f"SMS Alert: {message}")
@shared_task
def process_scheduled_messages():
    """Main Celery task with persistent scheduling"""
    logger.info("🚀 Starting scheduled messages processing")

    async def runner():
        session_name = f"scheduler_{socket.gethostname()}_{os.getpid()}"
        async with TelegramClient(
                session_name,
                settings.API_ID,
                settings.API_HASH,
                connection_retries=3,
                base_logger=logger
        ) as client:
            await client.start(phone=settings.PHONE_NUMBER, max_attempts=3)

            # Get messages ordered by next scheduled time
            messages = await sync_to_async(list)(
                ScheduledMessage.objects.filter(is_active=True)
                .exclude(next_scheduled__isnull=True)
                .order_by('next_scheduled')
            )

            for msg in messages:
                now = timezone.now()

                if msg.is_processing:
                    logger.info(f"⏭️ Skipping message #{msg.order} (being processed)")
                    continue

                # Check if message is due (including overdue messages)
                if now >= msg.next_scheduled:
                    try:
                        # Mark as processing
                        msg.is_processing = True
                        await sync_to_async(msg.save)()

                        # Send message
                        logger.info(f"📤 Sending message #{msg.order}")
                        success, failures = await send_to_all_dialogs(client, msg)

                        # Update scheduling
                        msg.last_sent = timezone.now()
                        msg.next_scheduled = None  # Trigger auto-calculation on save
                        msg.is_processing = False
                        await sync_to_async(msg.save)()

                        logger.info(f"✅ Sent message #{msg.order} to {success} dialogs")
                        if failures > 0:
                            logger.warning(f"⚠️ Failed to send to {failures} dialogs")

                    except Exception as e:
                        logger.error(f"❌ Error processing message #{msg.order}: {str(e)}")
                        msg.is_processing = False
                        await sync_to_async(msg.save)()
                else:
                    logger.info(f"⏭️ Next run for message #{msg.order} at {msg.next_scheduled}")

    # Proper event loop handling
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()



@shared_task
def collect_system_metrics():
    SystemMetrics.objects.create(
        cpu_percent=psutil.cpu_percent(),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage('/').percent
    )
    return "Metrics collected"


# tasks.py
@shared_task
def update_bot_metrics():
    # Get latest status
    status = BotStatus.objects.first() or BotStatus()

    # Update metrics
    status.active_users = UserInteraction.objects.filter(
        last_interaction__gte=timezone.now() - timezone.timedelta(minutes=15)
    ).count()

    # Calculate message rate (messages per minute)
    recent_messages = MessageLog.objects.filter(
        timestamp__gte=timezone.now() - timezone.timedelta(minutes=1)
    )
    status.message_rate = recent_messages.count()

    # Update uptime
    if status.is_connected:
        status.uptime += timezone.now() - status.timestamp

    status.save()
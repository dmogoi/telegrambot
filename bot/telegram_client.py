import getpass
import logging
import asyncio
import os
import socket
import sys
import time
import re
from collections import defaultdict
from django.utils import timezone  # Correct import


from django.core.cache import cache
from telethon import TelegramClient, events
from django.conf import settings
from django.db import close_old_connections
from asgiref.sync import sync_to_async
from .models import KeywordResponse, Notification, BotStatus
from .sms import send_bulk_sms
from telethon.errors import SessionPasswordNeededError, FloodWaitError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Implements a token bucket rate limiter for controlling spam."""

    def __init__(self, max_tokens=3, refill_rate=1):
        self.tokens = defaultdict(lambda: max_tokens)
        self.last_check = defaultdict(time.time)
        self.refill_rate = refill_rate

    def allow(self, chat_id):
        """Determines if a message from a given chat is allowed."""
        now = time.time()
        elapsed = now - self.last_check[chat_id]
        self.tokens[chat_id] = min(3, self.tokens[chat_id] + elapsed * self.refill_rate)
        self.last_check[chat_id] = now

        if self.tokens[chat_id] >= 1:
            self.tokens[chat_id] -= 1
            return True
        return False


class AdvancedBot:
    def __init__(self):
        # Generate unique session name with host identifier
        self.cache_version = 1  # Add versioning
        self.cache_prefix = "bot_data_"
        self.session_name = f"bot_session_{socket.gethostname()}"
        self.client = TelegramClient(
            self.session_name,  # Use unique session name
            settings.API_ID,
            settings.API_HASH,
            connection_retries=3,  # Added retry mechanism
            device_model="BotServer v2.1"  # Custom device identifier

        )
        self.keyword_cache = {'high': [], 'normal': []}
        self.last_refresh = 0
        self._last_ping = 0
        self._monitor_task = None
        self.status_lock = asyncio.Lock()  # Add this line
        self.rate_limiter = RateLimiter()
        self.phone_regex = re.compile(r'^\+?[0-9]{9,15}$')
        logger.info("✅ Telegram client initialized")

        self.available_games = [
            "Orion Stars", "Firekirin", "Vegas", "Juwa",
            "PandaMaster", "ultrapanda", "gamevault", "vblink"
        ]
        self.two_fa_code = None  # This will store the 2FA code when we receive it

    def get_cache_key(self, key_type):
        return f"{self.cache_prefix}{key_type}_v{self.cache_version}"

    async def refresh_keywords(self, force=False):
        """Refresh cache with version control and smart invalidation"""
        cache_key_high = self.get_cache_key('high_priority')
        cache_key_normal = self.get_cache_key('normal_priority')

        # Only refresh if forced or cache is empty
        if force or not cache.get(cache_key_high):
            try:
                await sync_to_async(close_old_connections)()

                high_priority = await sync_to_async(list)(
                    KeywordResponse.objects.filter(priority='high')
                )
                normal_priority = await sync_to_async(list)(
                    KeywordResponse.objects.filter(priority='normal')
                )

                cache.set(cache_key_high, high_priority, timeout=300)
                cache.set(cache_key_normal, normal_priority, timeout=300)
                logger.info("✅ Keyword cache refreshed successfully")

            except Exception as e:
                logger.error(f"⚠️ Cache refresh error: {str(e)}")

    def get_cached_keywords(self, priority):
        return cache.get(self.get_cache_key(f'{priority}_priority')) or []

    def build_keyword_pattern(self):
        """Builds a single optimized regex pattern for keyword matching."""
        high_priority_keywords = "|".join(re.escape(kw.trigger_word.lower()) for kw in self.keyword_cache['high'])
        normal_priority_keywords = "|".join(re.escape(kw.trigger_word.lower()) for kw in self.keyword_cache['normal'])
        return high_priority_keywords, normal_priority_keywords

    async def message_handler(self, event):
        """Handles incoming messages and ensures private replies for group messages."""
        try:
            logger.debug(f"📩 Received message: {event.raw_text}")
            await self.refresh_keywords()

            chat_id = event.chat_id
            user_id = event.sender_id
            user = await event.get_sender()
            first_name = user.first_name if user else "User"
            message_text = event.raw_text.lower()

            # Advanced rate limiting to prevent spam
            if not self.rate_limiter.allow(chat_id):
                logger.debug(f"⏳ Rate limited for chat {chat_id}")
                return

            # If message is from a group, respond in private chat
            if event.is_group:
                private_message = f"Hello {first_name}, I run online fish games and we offer 100% SIGNUP BONUS. Are you interested?"
                group_notification = f"@{first_name}, check your DM 📩"

                try:
                    # Send private DM
                    await self.client.send_message(user_id, private_message)
                    logger.info(f"📤 Sent private DM to {first_name} ({user_id})")

                    # Notify user in group chat
                    await event.reply(group_notification)
                    logger.info(f"📢 Notified {first_name} in group {chat_id}")

                except Exception as e:
                    logger.error(f"⚠️ Error sending private message to {user_id}: {str(e)}")

                return  # Stop further processing for group messages

            # Handle private replies
            if "yes" in message_text:
                # Send the list of available games
                games_list = "\n".join(self.available_games)
                await self.client.send_message(user_id,
                                               f"We have the following games:\n{games_list}\nWhich one would you like to play?")
                logger.info(f"📩 Asking user {first_name} for account selection")

            if any(game.lower() in message_text for game in self.available_games):
                selected_games = [game for game in self.available_games if game.lower() in message_text]

                if selected_games:
                    # Respond that the account is being set up
                    await self.client.send_message(user_id,
                                                   f"Ok, hold on as I set up your account for {', '.join(selected_games)}.")
                    logger.info(f"📩 Setting up account for user {first_name} with games {', '.join(selected_games)}")

                    # Notify the owner about the account setup
                    sms_message = f"🚨 ALERT: {first_name} needs account setup for: {', '.join(selected_games)}"
                    result = await sync_to_async(send_bulk_sms, thread_sensitive=True)(sms_message)
                    if result.get('status'):
                        logger.info(f"✅ SMS sent successfully. Bulk ID: {result.get('bulkId', 'N/A')}")
                    else:
                        logger.error(f"⚠️ SMS sending failed: {result.get('message', 'Unknown error')}")
                else:
                    # If user selects an unavailable game
                    await self.client.send_message(user_id,
                                                   "Sorry, we don't have that account for now, but you can try what we have.")
                    logger.info(f"📩 User {first_name} selected an unavailable game")

            # Optimized keyword matching (Detect ALL matches)
            high_pattern, normal_pattern = self.build_keyword_pattern()
            high_matches = [kw for kw in self.keyword_cache['high'] if
                            re.search(rf'\b{re.escape(kw.trigger_word.lower())}\b', message_text)]
            normal_matches = [kw for kw in self.keyword_cache['normal'] if
                              re.search(rf'\b{re.escape(kw.trigger_word.lower())}\b', message_text)]

            all_matches = high_matches + normal_matches

            if all_matches:
                try:
                    # Send each keyword response separately with a 5-second delay
                    for kw in all_matches:
                        logger.info(f"📤 Sending response for keyword: {kw.trigger_word}")
                        await event.reply(kw.response_text)
                        await asyncio.sleep(5)  # Introduce a 5-second delay

                        if kw.notify_owner:
                            logger.info("📲 Initiating owner notification for keyword")
                            await self.handle_owner_notification(kw, message_text, chat_id, user_id)

                except Exception as e:
                    logger.error(f"⚠️ Error sending response: {str(e)}")

            else:
                # Immediately notify owner about a non-keyword message
                logger.info(f"📲 Notifying owner: {first_name} sent a message without a keyword")
                await self.notify_owner_non_keyword(first_name, message_text)

            """Handle incoming messages"""
            """Handle incoming messages to automatically fetch the 2FA code."""
            """Handle incoming messages to automatically fetch the 2FA code."""
            if self.two_fa_code is None:
                logger.info(f"Received message: {event.raw_text}")
                # Check if the message contains the 2FA code format
                if event.raw_text and "LOGIN CODE:" in event.raw_text:
                    # Extract 2FA code using regex
                    match = re.search(r'LOGIN CODE:\s*(\d{5})', event.raw_text)
                    if match:
                        self.two_fa_code = match.group(1)  # Store the 2FA code
                        logger.info(f"2FA Code received: {self.two_fa_code}")
                        # Now that the code is received, start auth
                        await self.client.start(phone=lambda: settings.PHONE_NUMBER,
                                                code_callback=lambda: self.two_fa_code,
                                                password=lambda: getpass.getpass("Enter password: "))
                    else:
                        logger.error("Failed to extract 2FA code from message.")
                        time.sleep(1)  # Wait for the next attempt
        except Exception as e:
            logger.error(f"❌ Error handling message: {str(e)}")

    async def handle_owner_notification(self, response, message_text, chat_id, user_id):
        """Handles sending an SMS notification when a keyword is triggered."""
        try:
            # Get the user's full name (first_name and last_name)
            user = await self.client.get_entity(user_id)
            full_name = f"{user.first_name} {user.last_name}" if user.last_name else user.first_name

            # Construct the SMS message with the user's full name
            sms_message = (
                f"🚨 ALERT: Keyword '{response.trigger_word}' triggered.\n"
                f"User: {full_name} (Telegram Name)\n"  # Display the user's name
                f"User ID: {user_id}\n"
                f"Message: {message_text[:100]}..."  # Display the first 100 characters of the message
            )

            logger.debug(f"📩 Preparing SMS: {sms_message}")

            # Send the SMS
            result = await sync_to_async(send_bulk_sms, thread_sensitive=True)(sms_message)
            if not result.get('status'):
                logger.error(f"⚠️ SMS sending failed: {result.get('message', 'Unknown error')}")
            else:
                logger.info(f"✅ SMS sent successfully. Bulk ID: {result.get('bulkId', 'N/A')}")

            Notification.objects.create(
                type='KEYWORD_TRIGGER',
                message=f"Keyword '{response.trigger_word}' triggered by {user.first_name}",
                icon='comment-alt',
                metadata={
                    'keyword': response.trigger_word,
                    'user_id': user_id,
                    'message': message_text
                }
            )

        except Exception as e:
            logger.error(f"❌ SMS notification error: {str(e)}")

    async def notify_owner_non_keyword(self, first_name, message_text):
        """Sends an SMS to the owner if a message does not contain a keyword."""
        try:
            sms_message = f"⚠️ {first_name} sent a message without a keyword. Please check.\nMessage: {message_text[:100]}..."
            logger.debug(f"📩 Sending owner SMS for non-keyword message: {sms_message}")

            result = await sync_to_async(send_bulk_sms, thread_sensitive=True)(sms_message)
            if not result.get('status'):
                logger.error(f"⚠️ SMS sending failed: {result.get('message', 'Unknown error')}")
            else:
                logger.info("📲 Owner notified about non-keyword message.")

        except Exception as e:
            logger.error(f"❌ Error notifying owner: {str(e)}")

    # async def start(self):
    #     """Starts the Telegram bot with enhanced connection handling"""
    #     try:
    #         logger.info("🔄 Initializing connection...")
    #         await self.client.connect()
    #
    #         # Validate connection state
    #         if not self.client.is_connected():
    #             await self.client.reconnect()
    #
    #         # Enhanced authorization flow
    #         if not await self.client.is_user_authorized():
    #             logger.warning("⚠️ Session not authorized. Starting auth...")
    #
    #             # Check if the script is running in a terminal (interactive input)
    #             if sys.stdin.isatty():
    #                 two_fa_code = input("Enter 2FA code: ")
    #             else:
    #                 two_fa_code = os.getenv("TELEGRAM_2FA_CODE")
    #                 if two_fa_code is None:
    #                     logger.error("❌ 2FA code is missing. Set the TELEGRAM_2FA_CODE environment variable.")
    #                     raise ValueError("2FA code is required")
    #
    #             await self.client.start(
    #                 phone=lambda: settings.PHONE_NUMBER,
    #                 code_callback=lambda: two_fa_code,
    #                 password=lambda: getpass.getpass("Enter password: ")
    #             )
    #
    #         logger.info("✅ Successfully authorized!")
    #         self.client.add_event_handler(self.message_handler, events.NewMessage(incoming=True))
    #
    #         # Maintain connection
    #         while True:
    #             try:
    #                 await self.client.run_until_disconnected()
    #             except ConnectionError:
    #                 logger.warning("⚠️ Connection lost. Reconnecting...")
    #                 await asyncio.sleep(5)
    #                 await self.client.connect()
    #
    #     except Exception as e:
    #         logger.error(f"❌ Critical connection failure: {str(e)}")
    #         await self.client.disconnect()
    #         raise

    async def start(self):
        """Main bot startup sequence with full status tracking"""
        try:
            logger.info("🔄 Initializing Telegram connection...")
            await self._connect_client()
            await self._handle_authorization()
            await self._setup_handlers()
            await self._maintain_connection()

        except Exception as e:
            logger.critical(f"🔥 Critical startup failure: {str(e)}")
            await self._shutdown_sequence()
            raise

    async def _connect_client(self):
        """Establish initial connection and update status"""
        try:
            if not self.client.is_connected():
                await self.client.connect()

            await self.update_connection_status(True)
            logger.info("✅ Successfully connected to Telegram servers")

        except ConnectionError as ce:
            logger.error(f"🔌 Connection error: {str(ce)}")
            await self.update_connection_status(False)
            raise

    async def _handle_authorization(self):
        """Complete authorization flow with status tracking"""
        try:
            if not await self.client.is_user_authorized():
                logger.warning("🔒 Starting authorization sequence...")
                await self._perform_login()

            logger.info("🔓 Authorization successful")
            await self.update_connection_status(True)

        except FloodWaitError as fwe:
            logger.error(f"⏳ Flood wait required: {fwe.seconds} seconds")
            await self.update_connection_status(False)
            await asyncio.sleep(fwe.seconds)
            await self._handle_authorization()

        except Exception as auth_error:
            logger.error(f"🔐 Authorization failed: {str(auth_error)}")
            await self.update_connection_status(False)
            raise

    async def _perform_login(self):
        """Handle login process with 2FA capture"""
        try:
            await self.client.start(
                phone=lambda: settings.PHONE_NUMBER,
                code_callback=self.get_2fa_code,
                password=lambda: getpass.getpass("Enter password: ")
            )
            logger.info("🔑 Login credentials accepted")

        except SessionPasswordNeededError:
            logger.warning("🔐 2FA code required")
            self.two_fa_code = None
            while not self.two_fa_code:
                await asyncio.sleep(1)
            await self._perform_login()

    async def _setup_handlers(self):
        """Register event handlers with connection state"""
        self.client.add_event_handler(self.message_handler, events.NewMessage(incoming=True))
        logger.info("👂 Event handlers registered")
        await self.update_connection_status(True)

    async def _maintain_connection(self):
        """Main persistent connection with real-time health checks"""
        logger.info("🌐 Entering connection maintenance loop")
        while True:
            try:
                # Add continuous verification during connection
                await self.client.run_until_disconnected()
                await self._verify_connection()  # Immediate check after disconnect
                await self.update_connection_status(False)

            except (ConnectionError, TimeoutError) as conn_error:
                logger.warning(f"⚠️ Connection error: {str(conn_error)}")
                await self.update_connection_status(False)
                await self._reconnect_sequence()

            # Add periodic verification while connected
            finally:
                if self.client.is_connected():
                    # Immediate verification check
                    if not await self._verify_connection():
                        logger.warning("🕵️♂️ Connection state mismatch detected!")
                        await self.update_connection_status(False)
                        await self._reconnect_sequence()
                    else:
                        # Force status confirmation
                        await self.update_connection_status(True)

    async def _verify_connection(self):
        """Comprehensive connection verification"""
        try:
            # Layer 1: TCP-level check
            if not self.client.is_connected():
                return False

            # Layer 2: Force API call verification
            await self.client.get_me()

            # Layer 3: Check recent activity
            last_active = self.client._sender.last_recv
            if time.time() - last_active > 30:  # 30 seconds inactivity threshold
                logger.warning("🕒 No recent activity detected")
                return False

            return True
        except Exception:
            return False

    async def _reconnect_sequence(self):
        """Managed reconnection attempts with instant status updates"""
        logger.warning("🔌 Starting reconnection sequence")
        await self.update_connection_status(False)

        for attempt in range(1, 6):
            try:
                # Full disconnect/connect cycle
                await self.client.disconnect()
                await self.client.connect()

                # Immediate verification after reconnect
                if await self._verify_connection():
                    await self.update_connection_status(True)
                    logger.info(f"✅ Reconnected after {attempt} attempts")
                    return

                await asyncio.sleep(2 ** attempt)
                await self.update_connection_status(False)

            except Exception as e:
                logger.error(f"⏳ Reconnect attempt {attempt} failed: {str(e)}")
                await self.update_connection_status(False)

        logger.critical("🚨 Permanent connection loss")
        await self.update_connection_status(False)
        raise ConnectionError("Failed to reconnect after 5 attempts")

    async def _shutdown_sequence(self):
        """Graceful shutdown procedure"""
        logger.info("🛑 Initiating shutdown sequence...")
        await self.update_connection_status(False)
        if self.client.is_connected():
            await self.client.disconnect()
        logger.info("👋 Bot shutdown complete")

    async def update_connection_status(self, is_connected: bool):
        """Atomic status update with uptime tracking and state validation"""
        try:
            async with self.status_lock:
                now = timezone.now()
                current_status = await sync_to_async(BotStatus.objects.first)()

                if not current_status:
                    current_status = await sync_to_async(BotStatus.objects.create)(
                        is_connected=is_connected,
                        timestamp=now
                    )
                    logger.info("🆕 Created new status record")
                    return

                # Only update if state actually changed
                if current_status.is_connected != is_connected:
                    # Calculate accurate uptime
                    if current_status.is_connected:
                        delta = now - current_status.timestamp
                        current_status.uptime += delta
                        logger.debug(f"⏱️ Added {delta.total_seconds()}s to uptime")

                    current_status.is_connected = is_connected
                    current_status.timestamp = now
                    await sync_to_async(current_status.save)()
                    logger.info(f"🔀 Status changed to {'CONNECTED' if is_connected else 'DISCONNECTED'}")

                # Force periodic refresh even if state appears unchanged
                else:
                    current_status.timestamp = now
                    await sync_to_async(current_status.save)()
                    logger.debug("🔄 Status timestamp refreshed")

        except Exception as e:
            logger.error(f"📴 Status update error: {str(e)}")
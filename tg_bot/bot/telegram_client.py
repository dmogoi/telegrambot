import logging
import asyncio
import time
import re
from collections import defaultdict
from telethon import TelegramClient, events
from django.conf import settings
from django.db import close_old_connections
from asgiref.sync import sync_to_async
from .models import KeywordResponse
from .sms import send_bulk_sms
from telethon.errors import SessionPasswordNeededError

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
        self.client = TelegramClient(
            'user_session',  # session name
            settings.API_ID,
            settings.API_HASH
        )
        self.keyword_cache = {'high': [], 'normal': []}
        self.last_refresh = 0
        self.rate_limiter = RateLimiter()
        self.phone_regex = re.compile(r'^\+?[0-9]{9,15}$')
        logger.info("✅ Telegram client initialized")

        self.available_games = [
            "Orion Stars", "Firekirin", "Vegas", "Juwa",
            "PandaMaster", "ultrapanda", "gamevault", "vblink"
        ]

    async def refresh_keywords(self):
        """Refresh keyword cache only if there are changes in the database."""
        try:
            logger.debug("🔄 Checking if keyword cache update is needed...")

            # Close old connections to avoid memory leaks
            await sync_to_async(close_old_connections, thread_sensitive=True)()

            latest_high_priority = await sync_to_async(
                lambda: list(KeywordResponse.objects.filter(priority='high'))
            )()
            latest_normal_priority = await sync_to_async(
                lambda: list(KeywordResponse.objects.filter(priority='normal'))
            )()

            if latest_high_priority != self.keyword_cache['high'] or latest_normal_priority != self.keyword_cache[
                'normal']:
                self.keyword_cache['high'] = latest_high_priority
                self.keyword_cache['normal'] = latest_normal_priority
                self.last_refresh = time.time()
                logger.info("✅ Keyword cache refreshed successfully")

        except Exception as e:
            logger.error(f"⚠️ Error refreshing keywords: {str(e)}")

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

    async def start(self):
        """Starts the Telegram bot and connects to Telegram API."""
        try:
            logger.info("🔄 Initializing connection...")
            await asyncio.sleep(5)
            await self.client.connect()

            # Re-auth if needed
            if not await self.client.is_user_authorized():
                print("⚠️ Not authorized. Please login.")
                await self.client.send_code_request(settings.PHONE_NUMBER)
                code = input("Enter the code sent to your phone: ")
                await self.client.sign_in(settings.PHONE_NUMBER, code)

                # Handle two-step verification (password)
                try:
                    await self.client.sign_in(password=input("Enter your 2FA password: "))
                except SessionPasswordNeededError:
                    print("Session password needed. Please provide it.")
                    await self.client.sign_in(password=input("Enter your 2FA password: "))

            logger.info("✅ Successfully authorized!")
            self.client.add_event_handler(self.message_handler, events.NewMessage(incoming=True))
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"❌ Connection failed: {str(e)}")
            raise

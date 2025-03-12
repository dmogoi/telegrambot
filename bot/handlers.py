#handlers.py
from telethon import TelegramClient, events
from django.conf import settings
import asyncio
import time

class TelegramAssistant:
    def __init__(self):
        self.client = TelegramClient(
            'my_session',
            settings.API_ID,
            settings.API_HASH
        )
        self.last_message_time = {}
        self.client.add_event_handler(
            self.handle_message,
            events.NewMessage(incoming=True)
        )  # Fixed missing parenthesis

    async def handle_message(self, event):
        try:
            # Rate limiting check
            chat_id = event.chat_id
            now = time.time()

            if chat_id in self.last_message_time:
                elapsed = now - self.last_message_time[chat_id]
                if elapsed < 5:  # 5-second delay between messages
                    return

            await event.reply("Received your message!")
            self.last_message_time[chat_id] = now

        except Exception as e:
            print(f"Error handling message: {e}")

    async def start(self):
        await self.client.start(settings.PHONE_NUMBER)
        print("✅ Connected to Telegram!")
        await self.client.run_until_disconnected()

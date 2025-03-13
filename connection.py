import os
import asyncio
import django
from telethon import TelegramClient

# Initialize Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings


async def verify_connection():
    async with TelegramClient('session_check', settings.API_ID, settings.API_HASH) as client:
        await client.connect()
        print(f"✅ Connection state: {client.is_connected()}")
        print(f"🚀 Authorization status: {await client.is_user_authorized()}")
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(verify_connection())

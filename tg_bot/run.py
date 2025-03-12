import os
import django
import logging
import asyncio

# ✅ Ensure Django settings are properly configured before importing anything else
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")  # Update "config.settings" to your actual settings module
django.setup()

# Now import bot after Django is initialized
from bot.telegram_client import AdvancedBot  # Ensure this path is correct

# Enable verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_bot():
    bot = AdvancedBot()
    await bot.start()


# Run the bot
if __name__ == "__main__":
    asyncio.run(test_bot())

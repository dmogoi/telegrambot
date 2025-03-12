import time
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = "7963457802:AAH_Itpb4p5XG_DHyNLWin0NpGqUtIpSbn0"
GROUP_CHAT_ID = "YOUR_GROUP_CHAT_ID"  # Replace with actual group ID
MESSAGE_COOLDOWN = 60  # 1 minute cooldown between responses

# Response templates
KEYWORD_RESPONSES = {
    "cashapp": "📱 CashApp tips: Use our secure link to set up your account...",
    "freeplay": "🎮 Freeplay available! Check your account balance...",
    "chime": "🏦 Chime banking support: Visit our portal for step-by-step...",
    "venmo": "💸 Venmo transactions require verification first...",
    "sent": "✅ Payment status: Allow 24-48 hours for processing...",
    "account": "🔒 Account issues? Contact support @HelpDesk...",
    "signup bonus": "🎁 Signup bonus awarded after 3 successful deposits...",
    "cashout": "💵 Minimum cashout: $50. Processed within 24h...",
}

# Global cooldown tracker
user_cooldowns = {}


async def start(update: Update, context: CallbackContext) -> None:
    """Handle /start command in both private and group chats"""
    try:
        if update.message.chat.type == "private":
            await update.message.reply_text(
                "🤖 Welcome! I'm your automated assistant. "
                "You can ask me about:\n" +
                "\n".join([f"- {kw}" for kw in KEYWORD_RESPONSES.keys()])
            )
        else:
            await update.message.reply_text(
                "🤖 Group assistant ready! Mention any of these keywords:\n" +
                "\n".join([f"- {kw}" for kw in KEYWORD_RESPONSES.keys()])
            )
    except Exception as e:
        logger.error(f"Start command error: {e}")


async def handle_all_messages(update: Update, context: CallbackContext) -> None:
    """Handle messages in both private chats and groups"""
    try:
        # Ignore messages without text
        if not update.message or not update.message.text:
            return

        user = update.message.from_user
        message_text = update.message.text.lower()
        now = time.time()
        chat_type = update.message.chat.type

        logger.info(f"Received message in {chat_type} from {user.first_name}: {message_text}")

        # Check cooldown
        if now - user_cooldowns.get(user.id, 0) < MESSAGE_COOLDOWN:
            logger.debug(f"Cooldown active for {user.id}")
            return

        # Find matching responses
        responses = [
            response
            for keyword, response in KEYWORD_RESPONSES.items()
            if keyword in message_text
        ]

        if not responses:
            logger.debug("No keyword matches found")
            return

        reply = "\n\n".join(responses)

        if chat_type == "private":
            # Direct DM response
            await update.message.reply_text(f"🔔 Direct Response:\n\n{reply}")
            user_cooldowns[user.id] = now
            logger.info(f"Sent DM response to {user.id}")

        elif chat_type in ["group", "supergroup"]:
            # Group message handling
            try:
                # Send private response
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"🔔 Group Inquiry Response:\n\n{reply}"
                )
                # Notify group
                await update.message.reply_text(
                    f"{user.first_name}, I've sent you a private message with details! 📩"
                )
                user_cooldowns[user.id] = now
                logger.info(f"Sent group response to {user.id} in {GROUP_CHAT_ID}")
            except Exception as e:
                # Fallback if user can't receive DMs
                await update.message.reply_text(
                    f"{user.first_name}, please start a chat with me first!\n"
                    f"⚠️ Temporary response: {reply}"
                )
                logger.warning(f"Failed to DM {user.id}: {e}")

    except Exception as e:
        logger.error(f"Message handling error: {e}")


async def send_group_reminder(context: CallbackContext) -> None:
    """Send scheduled messages to the group"""
    try:
        reminders = [
            "⏰ Daily Reminder: Complete your check-in for bonus points!",
            "🔥 Flash Offer: Double rewards on deposits today!",
            "📢 System Update: New features now available!",
            "🎯 Pro Tip: Use /help for quick assistance"
        ]
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=reminders[int(time.time() // 3600) % len(reminders)]
        )
        logger.info(f"Sent scheduled reminder to group {GROUP_CHAT_ID}")
    except Exception as e:
        logger.error(f"Reminder error: {e}")


def main() -> None:
    """Start the bot"""
    try:
        app = Application.builder().token(TOKEN).build()

        # Add handlers for both private and group messages
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_all_messages
        ))

        # Schedule group reminders
        app.job_queue.run_repeating(
            send_group_reminder,
            interval=3600,  # Every hour
            first=10  # Start 10 seconds after launch
        )

        logger.info("Bot starting in hybrid mode...")
        app.run_polling()

    except Exception as e:
        logger.error(f"Startup failed: {e}")


if __name__ == "__main__":
    main()
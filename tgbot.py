import asyncio
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

TOKEN = "7963457802:AAH_Itpb4p5XG_DHyNLWin0NpGqUtIpSbn0"

# Keyword-response mapping
KEYWORD_RESPONSES = {
    "cashapp": "📱 CashApp tips: Use our secure link to set up your account...",
    "freeplay": "🎮 Freeplay available! Check your account balance...",
    "chime": "🏦 Chime banking support: Visit our portal for step-by-step...",
    "venmo": "💸 Venmo transactions require verification first...",
    "sent": "✅ Payment status: Allow 24-48 hours for processing...",
    "account": "🔒 Account issues? Contact support @HelpDesk...",
    "signup bonus": "🎁 Signup bonus awarded after 3 successful deposits...",
    "cashout": "💵 Minimum cashout: $50. Processed within 24h..."
}

# Anti-spam tracking
last_message_time = {}
MESSAGE_COOLDOWN = 60  # 1-minute cooldown


async def start(update: Update, context: CallbackContext):
    """Handles the /start command."""
    await update.message.reply_text(
        "🤖 Welcome! to stacy slots... how can we help you?."
    )


async def handle_message(update: Update, context: CallbackContext):
    """Detects keywords in messages and responds to the sender."""
    now = time.time()
    user_id = update.message.from_user.id  # Ensures response goes to the sender

    # Anti-spam check
    if user_id in last_message_time and (now - last_message_time[user_id]) < MESSAGE_COOLDOWN:
        return

    message_text = update.message.text.lower()
    responses = []

    # Check for keywords
    for keyword, response in KEYWORD_RESPONSES.items():
        if keyword in message_text:
            responses.append(response)

    # Send response if any keyword is found
    if responses:
        reply = "\n\n".join(responses)
        await context.bot.send_message(chat_id=user_id, text=reply)  # Sends response to the sender
        last_message_time[user_id] = now


def main():
    """Main function to start the bot."""
    app = Application.builder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))

    # Message handler (detects text messages and responds)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()

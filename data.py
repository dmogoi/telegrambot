import os
import django

# Set up the Django environment with your project name 'config'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # 'config' is your project name
django.setup()

# Import models from the 'bot' app
from bot.models import KeywordResponse, SMSRecipient, ScheduledMessage

# Open a text file in write mode with utf-8 encoding
with open('output_data.txt', 'w', encoding='utf-8') as file:
    # Write header for KeywordResponse data
    file.write("=== Keyword Responses ===\n")
    keyword_responses = KeywordResponse.objects.all()
    for response in keyword_responses:
        file.write(f"Trigger Word: {response.trigger_word}\n")
        file.write(f"Response Text: {response.response_text}\n")
        file.write(f"Priority: {response.priority}\n")
        file.write(f"Notify Owner: {response.notify_owner}\n")
        file.write(f"Icon: {response.icon}\n")
        file.write("\n")

    # Write header for SMSRecipient data
    file.write("=== SMS Recipients ===\n")
    sms_recipients = SMSRecipient.objects.all()
    for recipient in sms_recipients:
        file.write(f"Name: {recipient.name}\n")  # Corrected line
        file.write(f"Phone: {recipient.phone}\n")
        file.write(f"Is Active: {recipient.is_active}\n")
        file.write("\n")

    # Write header for ScheduledMessage data
    file.write("=== Scheduled Messages ===\n")
    scheduled_messages = ScheduledMessage.objects.all()
    for message in scheduled_messages:
        file.write(f"Content: {message.content}\n")
        file.write(f"Interval (in hours): {message.interval_hours}\n")
        file.write(f"Order: {message.order}\n")
        file.write(f"Is Active: {message.is_active}\n")
        file.write(f"Last Sent: {message.last_sent}\n")
        file.write("\n")

print("Data has been written to 'output_data.txt'")

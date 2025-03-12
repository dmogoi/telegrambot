from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'send-scheduled-messages': {
        'task': 'bot.tasks.send_scheduled_messages',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}
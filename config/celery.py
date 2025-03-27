import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Improved scheduling configuration
app.conf.update(
    worker_pool='solo',  # Better for async tasks
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

app.conf.beat_schedule = {
    'process-scheduled-messages': {
        'task': 'bot.tasks.process_scheduled_messages',
        'schedule': 300,  # Run every 5 minutes
    },
}

# Using Celery beat for more advanced scheduling
CELERY_BEAT_SCHEDULE = {
    'send-scheduled-messages': {
        'task': 'bot.tasks.process_scheduled_messages',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    'collect-metrics-every-5-minutes': {
            'task': 'bot.tasks.collect_system_metrics',
            'schedule': 300.0,  # Every 5 minutes
        },
}

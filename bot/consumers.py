# consumers.py (WebSocket backend)
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from .models import BotStatus, UserInteraction, MessageLog, SMSNotification

# consumers.py
from django.contrib.auth.models import AnonymousUser


class AdminDashboardConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if isinstance(user, AnonymousUser) or user.role != 'admin':
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(
            "admin_dashboard",
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            "admin_dashboard",
            self.channel_name
        )

    async def send_initial_data(self):
        data = {
            'type': 'initial_data',
            'metrics': await self.get_system_metrics(),
            'notifications': await self.get_recent_notifications(),
            'user_activity': await self.get_recent_user_activity(),
            'system_health': await self.get_system_health()
        }
        await self.send_json(data)

    @database_sync_to_async
    def get_system_metrics(self):
        status = BotStatus.objects.first()
        return {
            'active_users': UserInteraction.objects.filter(
                last_interaction__gte=timezone.now() - timedelta(minutes=15)
            ).count(),  # Fixed misplaced `.count()`
            'messages_24h': MessageLog.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).count(),
            'sms_success_rate': (SMSNotification.objects.filter(status='success').count() /
                                 SMSNotification.objects.count() * 100) if SMSNotification.objects.exists() else 0,
            'uptime': str(status.uptime) if status else '00:00:00',
            'message_distribution': self.get_message_distribution()
        }

    @database_sync_to_async
    def get_message_distribution(self):
        # Implement logic for message distribution if needed
        return {}

    async def receive_json(self, content):
        if content['type'] == 'refresh':
            await self.send_initial_data()
        elif content['type'] == 'ack_notification':
            await self.ack_notification(content['id'])

    async def system_update(self, event):
        await self.send_json({
            'type': 'system_update',
            'data': event['data']
        })

    async def send_notification(self, event):
        await self.send_json({
            'type': 'new_notification',
            'notification': event['notification']
        })

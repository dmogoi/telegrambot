# api.py
import psutil
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import SystemMetrics, AuditLog, User


class RealtimeMetricsAPI(APIView):
    def get(self, request):
        metrics = SystemMetrics.objects.order_by('-timestamp').first()
        return Response({
            'cpu': psutil.cpu_percent(),
            'memory': psutil.virtual_memory().percent,
            'message_rate': metrics.message_rate if metrics else 0,
            'active_users': metrics.active_users if metrics else 0
        })


class UserManagementAPI(APIView):
    def put(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.role = request.data.get('role')
        user.save()

        AuditLog.objects.create(
            user=request.user,
            action=f"Updated user {user.username} role to {user.role}",
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({'status': 'success'})
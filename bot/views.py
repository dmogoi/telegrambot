import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.response import Response

from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, DetailView, ListView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Count, Q
from rest_framework.decorators import api_view

from .mixins import CreateAuditLogMixin, UpdateAuditLogMixin, DeleteAuditLogMixin
from .models import *

import psutil
from django.contrib import messages
from django.contrib.auth import views as auth_views, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models.functions import TruncDate
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views import generic, View

from django.conf import settings
from .forms import EmailOrUsernameAuthForm


class CustomLoginView(LoginView):
    template_name = 'bot/auth/login.html'
    authentication_form = EmailOrUsernameAuthForm
    redirect_authenticated_user = False

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return HttpResponseRedirect(self.get_success_url())
        return super().get(*args, **kwargs)


class DashboardView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'bot/dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        # Get latest system health status
        try:
            status = BotStatus.objects.latest('timestamp')
        except BotStatus.DoesNotExist:
            status = None

        # Add real-time system metrics
        context['system_metrics'] = {
            'cpu': psutil.cpu_percent(),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent

        }

        # Update context with formatted uptime
        context['uptime'] = status.uptime_formatted if status else '00:00:00'

        # User Activity Metrics
        recent_users = UserInteraction.objects.filter(
            last_interaction__gte=now - timezone.timedelta(days=1)
        ).values('user_id', 'user_name').annotate(
            message_count=Count('id'),
            active=Count('id', filter=Q(last_interaction__gte=now - timezone.timedelta(minutes=15)))
        )

        # Message Metrics
        message_stats = MessageLog.objects.filter(
            timestamp__gte=now - timezone.timedelta(days=7)
        ).annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            total=Count('id'),
            keywords=Count('id', filter=Q(message_type='keyword')),
            scheduled=Count('id', filter=Q(message_type='scheduled'))
        ).order_by('date')

        # SMS Metrics
        sms_stats = SMSNotification.objects.aggregate(
            total=Count('id'),
            success=Count('id', filter=Q(status='success')),
            failed=Count('id', filter=Q(status='failed')),
            pending=Count('id', filter=Q(status='pending'))
        )

        # System Health
        try:
            status = BotStatus.objects.latest('timestamp')
        except BotStatus.DoesNotExist:
            status = None

        context.update({
            'active_users': recent_users.count(),
            'messages_handled': MessageLog.objects.filter(
                timestamp__gte=now - timezone.timedelta(days=1)
            ).count(),
            'sms_success_rate': (sms_stats['success'] / sms_stats['total'] * 100) if sms_stats['total'] > 0 else 0,
            'uptime': status.uptime_formatted if status else 'N/A',
            'message_dates': [m['date'].strftime("%Y-%m-%d") for m in message_stats],
            'message_counts': [m['total'] for m in message_stats],
            'message_type_distribution': [
                sum(m['keywords'] for m in message_stats),
                sum(m['scheduled'] for m in message_stats),
                MessageLog.objects.filter(message_type='direct').count()
            ],
            'sms_distribution': [
                sms_stats['success'],
                sms_stats['failed'],
                sms_stats['pending']
            ],
            'connection_status': status.is_connected if status else False,
            'error_rate': MessageLog.objects.filter(
                timestamp__gte=now - timezone.timedelta(days=1),
                success=False
            ).count() / max(1, MessageLog.objects.filter(
                timestamp__gte=now - timezone.timedelta(days=1)
            ).count()) * 100,
            'recent_errors': MessageLog.objects.filter(
                success=False
            ).order_by('-timestamp')[:5],
            'recent_users': recent_users
        })
        return context


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Verify admin status through role or superuser flag"""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.role == 'admin' or user.is_superuser)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied(
            "You need administrator privileges to access this page. "
            f"Your current role: {self.request.user.role}"
        )

    def check_staff_permissions(self):
        """Override for custom staff permissions"""
        return True

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect(f'{settings.LOGIN_URL}?next={self.request.path}')
        raise PermissionDenied(self.get_permission_denied_message())

    def get_permission_denied_message(self):
        return "You need administrator privileges to access this page."


class AdminDashboardConsumer(AsyncJsonWebsocketConsumer):
    groups = ["admin_dashboard"]

    async def connect(self):
        if self.scope["user"].is_authenticated and self.scope["user"].role == 'admin':
            await self.accept()
            await self.send_initial_data()
        else:
            await self.close()

    async def send_initial_data(self):
        data = {
            'type': 'initial_data',
            'metrics': await self.get_system_metrics(),
        }
        await self.send_json(data)

    @database_sync_to_async
    def get_system_metrics(self):
        return {
            'active_users': cache.get('active_users', 0),
            'message_rate': cache.get('message_rate', 0),
        }


# User Management
class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'bot/admin/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        return User.objects.order_by('-date_joined')


# views.py
class UserUpdateView(UpdateAuditLogMixin, AdminRequiredMixin, UpdateView):
    model = User
    fields = ['role', 'is_active']
    template_name = 'bot/admin/user_form.html'
    success_url = reverse_lazy('bot:user-list')

    def form_valid(self, form):
        old_user = User.objects.get(pk=self.object.pk)
        response = super().form_valid(form)

        # Log changes
        changes = {}
        if old_user.role != self.object.role:
            changes['role'] = {
                'old': old_user.role,
                'new': self.object.role
            }
        if old_user.is_active != self.object.is_active:
            changes['active'] = {
                'old': old_user.is_active,
                'new': self.object.is_active
            }

        if changes:
            AuditLog.objects.create(
                user=self.request.user,
                action=f"Updated user {self.object.username}",
                ip_address=self.get_client_ip(),
                metadata={
                    'user_id': self.object.id,
                    'changes': changes
                }
            )

        return response

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else self.request.META.get('REMOTE_ADDR')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = User.ROLES  # Add roles to context
        return context


# Audit Logs
# views.py
# views.py (update existing views)
class UserUpdateView(UpdateAuditLogMixin, AdminRequiredMixin, UpdateView):
    model = User
    fields = ['role', 'is_active']
    template_name = 'bot/admin/user_form.html'
    success_url = reverse_lazy('bot:user-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = User.ROLES
        return context


class AuditLogListView(AdminRequiredMixin, ListView):
    model = AuditLog
    template_name = 'bot/admin/audit_log.html'
    context_object_name = 'logs'
    paginate_by = 50
    ordering = ['-timestamp']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('user')
        params = {
            'user_id': self.request.GET.get('user_id'),
            'action_type': self.request.GET.get('type'),
            'model_name': self.request.GET.get('model')
        }
        for key, value in params.items():
            if value:
                queryset = queryset.filter(**{key: value})
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_types'] = AuditLog.ACTION_TYPES
        context['models'] = AuditLog.objects.values_list(
            'model_name', flat=True
        ).distinct()
        return context


class AuditLogDetailView(AdminRequiredMixin, DetailView):
    model = AuditLog
    template_name = 'bot/admin/audit_log_detail.html'


# System Health
class SystemHealthView(AdminRequiredMixin, TemplateView):
    template_name = 'bot/admin/system_health.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get bot status
        bot_status = BotStatus.objects.first() or BotStatus()

        # Map health status to Bootstrap colors
        status_colors = {
            'critical': 'danger',
            'warning': 'warning',
            'healthy': 'success'
        }

        # Prepare status context
        context['status'] = {
            'is_connected': bot_status.is_connected,
            'uptime': bot_status.uptime,
            'active_users': bot_status.active_users,
            'message_rate': bot_status.message_rate,
            'health_status_display': bot_status.health_status.title(),
            'health_status_color': status_colors.get(bot_status.health_status, 'secondary')
        }

        # Live system metrics
        context['system'] = {
            'cpu': psutil.cpu_percent(),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent
        }

        # Historical metrics (last 24 hours)
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        metrics = SystemMetrics.objects.filter(
            timestamp__gte=twenty_four_hours_ago
        ).order_by('timestamp')

        # Prepare chart data
        context['metrics'] = {
            'labels': [m.timestamp.strftime("%Y-%m-%dT%H:%M:%S") for m in metrics],
            'cpu': [m.cpu_percent for m in metrics],
            'memory': [m.memory_percent for m in metrics],
            'disk': [m.disk_percent for m in metrics]
        }

        return context


@method_decorator(csrf_exempt, name='dispatch')
class UserManagementAPI(AdminRequiredMixin, View):
    """Secure API endpoint for user management"""

    def put(self, request, user_id):
        try:
            target_user = get_object_or_404(User, id=user_id)

            data = json.loads(request.body)
            user = User.objects.get(id=user_id)
            # Prevent non-superusers from modifying other admins
            if not request.user.is_superuser and target_user.is_superuser:
                return JsonResponse(
                    {'error': 'Only superusers can modify other admins'},
                    status=403
                )
            # Add audit logging
            AuditLog.objects.create(
                user=request.user,
                action_type='USER_UPDATE',
                details=f"Updated user {user.username}",
                ip_address=self.get_client_ip(request),
                metadata={
                    'modified_user': user.id,
                    'changes': data
                }
            )

            return JsonResponse({'status': 'success'})

        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)


# Notifications
class NotificationListView(AdminRequiredMixin, ListView):
    model = Notification
    template_name = 'bot/admin/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 25
    ordering = ['-timestamp']

    def get_queryset(self):
        return Notification.objects.filter(read=False)

    def post(self, request):
        notification_ids = request.POST.getlist('notification_ids')
        Notification.objects.filter(id__in=notification_ids).update(read=True)
        return JsonResponse({'status': 'success'})


# Realtime Metrics
class RealtimeMetricsAPI(View):
    """API endpoint for realtime metrics (keep original name)"""

    def get(self, request):
        data = {
            "active_users": cache.get('active_users'),
            "message_rate": cache.get('message_rate'),
            "system_load": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent
        }
        return JsonResponse(data)


class RealtimeMetricsView(AdminRequiredMixin, TemplateView):
    """Template view for metrics dashboard"""
    template_name = 'bot/admin/realtime_metrics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['metrics'] = SystemMetrics.objects.order_by('-timestamp')[:100]
        return context


@api_view(['GET'])
def realtime_metrics(request):
    # Get latest metrics
    status = BotStatus.objects.latest('timestamp')
    metrics = {
        'active_users': status.active_users,
        'messages_handled': MessageLog.objects.filter(
            timestamp__gte=timezone.now() - timezone.timedelta(days=1)
        ).count(),
        'uptime': status.uptime_formatted,
        'cpu': psutil.cpu_percent(),
        'memory': psutil.virtual_memory().percent,
        'disk': psutil.disk_usage('/').percent,
        'is_connected': status.is_connected
    }
    return Response({
        'cpu': psutil.cpu_percent(),
        'memory': psutil.virtual_memory().percent,
        'disk': psutil.disk_usage('/').percent,
        'is_connected': BotStatus.objects.last().is_connected,
        'uptime': BotStatus.objects.last().uptime_formatted,
        'active_users': UserInteraction.objects.active_count(),
        'messages_handled': MessageLog.objects.daily_count(),
        'sms_success_rate': SMSNotification.objects.success_rate(),
        'error_rate': MessageLog.objects.error_rate()
    })


class CustomLogoutView(auth_views.LogoutView):
    next_page = 'bot:login'  # Set your logout redirect URL
    template_name = 'bot/auth/logout.html'  # Optional custom template


# class ProfileView(LoginRequiredMixin, TemplateView):
#     template_name = 'bot/profile.html'
#
#     def post(self, request, *args, **kwargs):
#         user = request.user
#         user.first_name = request.POST.get('first_name', '')
#         user.last_name = request.POST.get('last_name', '')
#         user.save()
#         messages.success(request, 'Profile updated successfully!')
#         return redirect('bot:profile')
#
#
# class SettingsView(LoginRequiredMixin, TemplateView):
#     template_name = 'bot/settings.html'

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'bot/auth/profile.html'


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'bot/auth/settings.html'


class PasswordChangeView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('bot:settings')
        else:
            for error in form.errors.values():
                messages.error(request, error)
            return redirect('bot:settings')


# CRUD Views for Keywords
class KeywordListView(LoginRequiredMixin, generic.ListView):
    model = KeywordResponse
    template_name = 'bot/crud/keyword_list.html'
    context_object_name = 'keywords'
    paginate_by = 10  # Show 10 items per page
    ordering = ['-priority', 'trigger_word']  # Example ordering


class KeywordCreateView(CreateAuditLogMixin, LoginRequiredMixin, generic.CreateView):
    model = KeywordResponse
    fields = ['trigger_word', 'response_text', 'priority', 'notify_owner', 'icon']
    template_name = 'bot/crud/keyword_form.html'
    success_url = reverse_lazy('bot:keyword-list')


class KeywordUpdateView(UpdateAuditLogMixin, LoginRequiredMixin, generic.UpdateView):
    model = KeywordResponse
    fields = ['trigger_word', 'response_text', 'priority', 'notify_owner', 'icon']
    template_name = 'bot/crud/keyword_form.html'
    success_url = reverse_lazy('bot:keyword-list')


class KeywordDeleteView(DeleteAuditLogMixin, LoginRequiredMixin, generic.DeleteView):
    model = KeywordResponse
    template_name = 'bot/crud/keyword_confirm_delete.html'
    success_url = reverse_lazy('bot:keyword-list')


# Similar CRUD views for SMSRecipient and ScheduledMessage
# SMS Recipient CRUD Views
# For SMS Recipients
class SMSListView(LoginRequiredMixin, generic.ListView):
    model = SMSRecipient
    template_name = 'bot/crud/sms_list.html'
    context_object_name = 'recipients'
    paginate_by = 10
    ordering = ['name']


class SMSCreateView(CreateAuditLogMixin, LoginRequiredMixin, generic.CreateView):
    model = SMSRecipient
    fields = ['name', 'phone', 'is_active']
    template_name = 'bot/crud/sms_form.html'
    success_url = reverse_lazy('bot:sms-list')


class SMSUpdateView(UpdateAuditLogMixin, LoginRequiredMixin, generic.UpdateView):
    model = SMSRecipient
    fields = ['name', 'phone', 'is_active']
    template_name = 'bot/crud/sms_form.html'
    success_url = reverse_lazy('bot:sms-list')


class SMSDeleteView(DeleteAuditLogMixin, LoginRequiredMixin, generic.DeleteView):
    model = SMSRecipient
    template_name = 'bot/crud/sms_confirm_delete.html'
    success_url = reverse_lazy('bot:sms-list')


# Scheduled Message CRUD Views
# For Scheduled Messages
class ScheduledListView(LoginRequiredMixin, generic.ListView):
    model = ScheduledMessage
    template_name = 'bot/crud/scheduled_list.html'
    context_object_name = 'messages'
    paginate_by = 10
    ordering = ['order']


class ScheduledCreateView(CreateAuditLogMixin, LoginRequiredMixin, generic.CreateView):
    model = ScheduledMessage
    fields = ['content', 'interval_hours', 'order', 'is_active', 'image']
    template_name = 'bot/crud/scheduled_form.html'
    success_url = reverse_lazy('bot:scheduled-list')


class ScheduledUpdateView(UpdateAuditLogMixin, LoginRequiredMixin, generic.UpdateView):
    model = ScheduledMessage
    fields = ['content', 'interval_hours', 'order', 'is_active', 'image']
    template_name = 'bot/crud/scheduled_form.html'
    success_url = reverse_lazy('bot:scheduled-list')


class ScheduledDeleteView(DeleteAuditLogMixin, LoginRequiredMixin, generic.DeleteView):
    model = ScheduledMessage
    template_name = 'bot/crud/scheduled_confirm_delete.html'
    success_url = reverse_lazy('bot:scheduled-list')


class APIDocumentationView(TemplateView):
    template_name = 'bot/api_docs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['api_endpoints'] = {
            'metrics': f'{settings.BASE_URL}/api/metrics/',
            'users': f'{settings.BASE_URL}/api/users/'
        }
        return context

# urls.py
from django.urls import path
from rest_framework.documentation import include_docs_urls

from . import views
from .views import realtime_metrics

app_name = 'bot'

urlpatterns = [
    # Dashboard
    path('admin/dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # Authentication
    path('admin/login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('settings/', views.SettingsView.as_view(), name='settings'),
    path('password/change/', views.PasswordChangeView.as_view(), name='password-change'),

    # Core Features
    path('keywords/', views.KeywordListView.as_view(), name='keyword-list'),
    path('keywords/new/', views.KeywordCreateView.as_view(), name='keyword-create'),
    path('keywords/<int:pk>/edit/', views.KeywordUpdateView.as_view(), name='keyword-update'),
    path('keywords/<int:pk>/delete/', views.KeywordDeleteView.as_view(), name='keyword-delete'),

    path('sms/', views.SMSListView.as_view(), name='sms-list'),
    path('sms/new/', views.SMSCreateView.as_view(), name='sms-create'),
    path('sms/<int:pk>/edit/', views.SMSUpdateView.as_view(), name='sms-update'),
    path('sms/<int:pk>/delete/', views.SMSDeleteView.as_view(), name='sms-delete'),

    path('scheduled/', views.ScheduledListView.as_view(), name='scheduled-list'),
    path('scheduled/new/', views.ScheduledCreateView.as_view(), name='scheduled-create'),
    path('scheduled/<int:pk>/edit/', views.ScheduledUpdateView.as_view(), name='scheduled-update'),
    path('scheduled/<int:pk>/delete/', views.ScheduledDeleteView.as_view(), name='scheduled-delete'),

    # System Admin Features
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user-update'),
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit-log'),
    path('audit-logs/<int:pk>/', views.AuditLogDetailView.as_view(), name='audit-log-detail'),
    path('system-health/', views.SystemHealthView.as_view(), name='system-health'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('realtime-metrics/', views.RealtimeMetricsView.as_view(), name='realtime-metrics'),
    path('metrics/', realtime_metrics, name='metrics'),

    # API Endpoints

    path('api/metrics/', views.RealtimeMetricsAPI.as_view(), name='api-metrics'),
    path('api/users/<int:user_id>/', views.UserManagementAPI.as_view(), name='api-user-management'),
    path('api-docs/', include_docs_urls(title='Bot API Documentation')),

    # WebSocket
    path('ws/admin/dashboard/', views.AdminDashboardConsumer.as_asgi(), name='ws-admin-dashboard'),
]
handler403 = 'bot.handlers.permission_denied_view'
handler404 = 'bot.handlers.page_not_found_view'

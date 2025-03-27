from .models import Notification


from .models import Notification

def navbar_context(request):
    context = {}
    if request.user.is_authenticated:
        context['unread_notifications'] = Notification.objects.filter(
            read=False,
            # user=request.user  # Add this if notifications are user-specific
        ).order_by('-timestamp')[:10]
    return context


# Add this alias to maintain compatibility
notifications = navbar_context
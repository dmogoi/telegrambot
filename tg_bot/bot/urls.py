from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

urlpatterns = [
    # Your other URL patterns here...
]

# Serve media files only in DEBUG mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

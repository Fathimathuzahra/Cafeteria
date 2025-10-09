from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
     path("django-admin/", admin.site.urls),   # keep Django’s admin for debugging
    path("", include("canteen_app.urls")),  # Your custom app routes
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/organizations/', include('apps.organizations.urls')),
    path('api/contracts/', include('apps.contracts.urls')),
    path('api/charts/', include('apps.charts.urls')),
    path('api/llm/', include('apps.llm.urls')),
    path('api/billing/', include('apps.billing.urls')),
    path('api/admin/', include('apps.admin_console.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
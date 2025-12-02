from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Schema configuration
schema_view = get_schema_view(
    openapi.Info(
        title="DocBiz API",
        default_version='v1',
        description="Document Business Intelligence Platform API",
        terms_of_service="https://www.docbiz.com/terms/",
        contact=openapi.Contact(email="support@docbiz.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/organizations/', include('apps.organizations.urls')),
    path('api/contracts/', include('apps.contracts.urls')),
    path('api/charts/', include('apps.charts.urls')),
    path('api/llm/', include('apps.llm.urls')),
    path('api/billing/', include('apps.billing.urls')),
    path('api/admin/', include('apps.admin_console.urls')),
    
    # Swagger Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/docs/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
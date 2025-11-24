from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'organizations', views.OrganizationAdminViewSet, basename='admin-organizations')
router.register(r'users', views.UserAdminViewSet, basename='admin-users')
router.register(r'contracts', views.ContractAdminViewSet, basename='admin-contracts')
router.register(r'llm-usage', views.LLMUsageAdminViewSet, basename='admin-llm-usage')
router.register(r'subscriptions', views.SubscriptionAdminViewSet, basename='admin-subscriptions')
router.register(r'invoices', views.InvoiceAdminViewSet, basename='admin-invoices')

urlpatterns = [
    # Metrics and health
    path('metrics/platform/', views.PlatformMetricsView.as_view(), name='platform-metrics'),
    path('health/system/', views.SystemHealthView.as_view(), name='system-health'),
    
    # Include router URLs
    path('', include(router.urls)),
]
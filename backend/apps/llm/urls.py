from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'providers', views.LLMProviderViewSet, basename='llm-providers')
router.register(r'models', views.LLMModelViewSet, basename='llm-models')
router.register(r'usage', views.LLMUsageViewSet, basename='llm-usage')
router.register(r'quotas', views.LLMQuotaViewSet, basename='llm-quotas')
router.register(r'analytics', views.LLMAnalyticsViewSet, basename='llm-analytics')

urlpatterns = [
    # LLM requests
    path('request/', views.LLMRequestView.as_view(), name='llm-request'),
    
    # Analytics
    path('analytics/summary/', views.AnalyticsSummaryView.as_view(), name='analytics-summary'),
    path('analytics/monthly-report/', views.MonthlyReportView.as_view(), name='monthly-report'),
    
    # Quota management
    path('quotas/current/', views.LLMQuotaViewSet.as_view({'get': 'current'}), name='quota-current'),
    path('quotas/reset/', views.QuotaResetView.as_view(), name='quota-reset'),
    
    # Include router URLs
    path('', include(router.urls)),
]
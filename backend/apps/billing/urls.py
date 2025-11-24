from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'plans', views.SubscriptionPlanViewSet, basename='subscription-plans')
router.register(r'subscriptions', views.OrganizationSubscriptionViewSet, basename='organization-subscriptions')
router.register(r'invoices', views.InvoiceViewSet, basename='invoices')
router.register(r'payment-methods', views.PaymentMethodViewSet, basename='payment-methods')

urlpatterns = [
    # Usage
    path('usage/summary/', views.UsageSummaryView.as_view(), name='usage-summary'),
    
    # Webhooks
    path('webhooks/<str:processor>/', views.BillingWebhookView.as_view(), name='billing-webhook'),
    
    # Include router URLs
    path('', include(router.urls)),
]
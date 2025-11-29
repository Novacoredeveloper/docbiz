# apps/contracts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'templates', views.ContractTemplateViewSet, basename='contract-template')
router.register(r'contracts', views.ContractViewSet, basename='contract')
router.register(r'legal-references', views.LegalReferenceViewSet, basename='legal-reference')
router.register(r'llm-usage', views.LLMUsageViewSet, basename='llm-usage')

# Additional URL patterns that aren't covered by the router
urlpatterns = [
    # API routes
    path('api/', include(router.urls)),
    
    # Public signing endpoint (no authentication required)
    path('api/public/signing/<str:token>/', views.PublicSigningView.as_view(), name='public-signing'),
    
    # Contract-specific nested routes
    path('api/contracts/<int:contract_id>/parties/', include([
        path('', views.ContractPartyViewSet.as_view({
            'get': 'list', 'post': 'create'
        }), name='contract-party-list'),
        path('<int:pk>/', views.ContractPartyViewSet.as_view({
            'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
        }), name='contract-party-detail'),
    ])),
    
    path('api/contracts/<int:contract_id>/signature-fields/', include([
        path('', views.SignatureFieldViewSet.as_view({
            'get': 'list', 'post': 'create'
        }), name='signature-field-list'),
        path('<int:pk>/', views.SignatureFieldViewSet.as_view({
            'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'
        }), name='signature-field-detail'),
    ])),
]
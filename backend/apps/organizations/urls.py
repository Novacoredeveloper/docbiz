# apps/organizations/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'organizations', views.OrganizationViewSet, basename='organization')
router.register(r'contacts', views.OrganizationContactViewSet, basename='organization-contact')

# Additional URL patterns that aren't covered by the router
urlpatterns = [
    # API routes
    path('api/', include(router.urls)),
    
    # Organization invitations
    path('api/invitations/', views.OrganizationInvitationView.as_view(), name='organization-invitations'),
    
    # Organization settings
    path('api/settings/', views.OrganizationSettingsView.as_view(), name='organization-settings'),
    
    # Organization search (admin only)
    path('api/search/', views.OrganizationSearchView.as_view(), name='organization-search'),
]

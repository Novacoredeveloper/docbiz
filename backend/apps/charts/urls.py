from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'entity-links', views.ChartEntityLinkViewSet, basename='chart-entity-links')
router.register(r'tax-documents', views.TaxDocumentViewSet, basename='tax-documents')
router.register(r'licenses', views.LicenseViewSet, basename='licenses')
router.register(r'payments', views.PaymentRecordViewSet, basename='payment-records')
router.register(r'audit-logs', views.ChartAuditLogViewSet, basename='chart-audit-logs')

urlpatterns = [
    # Chart operations
    path('chart/', views.OrgChartViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update'
    }), name='org-chart'),
    
    path('chart/add-entity/', views.OrgChartViewSet.as_view({'post': 'add_entity'}), name='chart-add-entity'),
    path('chart/add-connection/', views.OrgChartViewSet.as_view({'post': 'add_connection'}), name='chart-add-connection'),
    path('chart/entity-links/', views.OrgChartViewSet.as_view({'get': 'entity_links'}), name='chart-entity-links'),
    
    # Export
    path('chart/export/', views.ChartExportView.as_view(), name='chart-export'),
    
    # Include router URLs
    path('', include(router.urls)),
]
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from datetime import timedelta

from .models import LLMProvider, LLMModel, LLMUsage, LLMQuota, LLMAnalytics
from .serializers import (
    LLMProviderSerializer, LLMModelSerializer, LLMUsageSerializer,
    LLMQuotaSerializer, LLMAnalyticsSerializer, LLMRequestSerializer
)
from .services import LLMService, AnalyticsService


class LLMProviderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['provider_type', 'is_active']
    search_fields = ['name']
    
    def get_queryset(self):
        # Only super admins can manage providers
        if self.request.user.is_superuser:
            return LLMProvider.objects.all()
        return LLMProvider.objects.filter(is_active=True)
    
    def get_serializer_class(self):
        return LLMProviderSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            from rest_framework.permissions import IsAdminUser
            return [IsAdminUser()]
        return super().get_permissions()


class LLMModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['provider', 'model_type', 'is_active']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return LLMModel.objects.all()
        return LLMModel.objects.filter(is_active=True)
    
    def get_serializer_class(self):
        return LLMModelSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            from rest_framework.permissions import IsAdminUser
            return [IsAdminUser()]
        return super().get_permissions()


class LLMUsageViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['feature', 'status', 'provider', 'model']
    search_fields = ['input_context', 'generated_content']
    ordering_fields = ['created_at', 'tokens_total', 'cost_estimated']
    
    def get_queryset(self):
        return LLMUsage.objects.filter(
            organization=self.request.user.organization
        ).select_related('provider', 'model', 'user')
    
    def get_serializer_class(self):
        return LLMUsageSerializer


class LLMQuotaViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LLMQuota.objects.filter(organization=self.request.user.organization)
    
    def get_serializer_class(self):
        return LLMQuotaSerializer
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current quota usage."""
        try:
            quota = self.get_queryset().get()
            serializer = self.get_serializer(quota)
            
            # Add usage percentage
            data = serializer.data
            if quota.monthly_token_limit:
                data['token_usage_percentage'] = min(
                    (quota.tokens_used_current_month / quota.monthly_token_limit) * 100, 
                    100
                )
            if quota.monthly_request_limit:
                data['request_usage_percentage'] = min(
                    (quota.requests_used_current_month / quota.monthly_request_limit) * 100, 
                    100
                )
            if quota.monthly_cost_limit:
                data['cost_usage_percentage'] = min(
                    (quota.cost_used_current_month / quota.monthly_cost_limit) * 100, 
                    100
                )
            
            return Response(data)
            
        except LLMQuota.DoesNotExist:
            return Response(
                {'error': 'Quota not found for organization'},
                status=status.HTTP_404_NOT_FOUND
            )


class LLMAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['period_type']
    ordering_fields = ['period_end']
    
    def get_queryset(self):
        return LLMAnalytics.objects.filter(organization=self.request.user.organization)
    
    def get_serializer_class(self):
        return LLMAnalyticsSerializer


class LLMRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Make an LLM request."""
        serializer = LLMRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            prompt = serializer.validated_data['prompt']
            feature = serializer.validated_data['feature']
            model_id = serializer.validated_data.get('model_id')
            
            try:
                llm_service = LLMService(
                    organization=request.user.organization,
                    user=request.user
                )
                
                # Get specific model if provided
                model = None
                if model_id:
                    model = LLMModel.objects.get(
                        id=model_id,
                        is_active=True
                    )
                
                result = llm_service.generate_content(
                    prompt=prompt,
                    feature=feature,
                    model=model,
                    **serializer.validated_data.get('parameters', {})
                )
                
                return Response(result)
                
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnalyticsSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get analytics summary."""
        days = int(request.query_params.get('days', 30))
        
        analytics_service = AnalyticsService(request.user.organization)
        summary = analytics_service.get_usage_summary(days=days)
        
        return Response(summary)


class MonthlyReportView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate or get monthly report."""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        
        if year:
            year = int(year)
        if month:
            month = int(month)
        
        analytics_service = AnalyticsService(request.user.organization)
        report = analytics_service.generate_monthly_report(year, month)
        
        serializer = LLMAnalyticsSerializer(report)
        return Response(serializer.data)


class QuotaResetView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Manually reset quota (admin only)."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only administrators can reset quotas'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        organization_id = request.data.get('organization_id')
        if not organization_id:
            return Response(
                {'error': 'organization_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.organizations.models import Organization
            organization = Organization.objects.get(id=organization_id)
            quota = LLMQuota.objects.get(organization=organization)
            quota.reset_usage()
            
            return Response({'message': 'Quota reset successfully'})
            
        except (Organization.DoesNotExist, LLMQuota.DoesNotExist):
            return Response(
                {'error': 'Organization or quota not found'},
                status=status.HTTP_404_NOT_FOUND
            )
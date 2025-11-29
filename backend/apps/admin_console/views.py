from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

from apps.organizations.models import Organization
from apps.users.models import User
from apps.contracts.models import Contract
from apps.llm.models import LLMUsage
from apps.billing.models import OrganizationSubscription, Invoice
from apps.llm.models import LLMProvider, LLMModel
from .serializers import (
    OrganizationAdminSerializer, UserAdminSerializer,
    ContractAdminSerializer, LLMUsageAdminSerializer,
    SubscriptionAdminSerializer, InvoiceAdminSerializer,
    PlatformMetricsSerializer
)


class OrganizationAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['subscription__plan__tier', 'subscription__status', 'is_active']
    search_fields = ['name', 'legal_name', 'primary_contact_email']
    ordering_fields = ['created_at', 'name', 'subscription__current_price']
    
    def get_queryset(self):
        return Organization.objects.all().select_related('subscription__plan')
    
    def get_serializer_class(self):
        return OrganizationAdminSerializer
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """Suspend organization."""
        organization = self.get_object()
        reason = request.data.get('reason', 'Administrative suspension')
        
        organization.is_active = False
        organization.save()
        
        # Suspend subscription
        if hasattr(organization, 'subscription'):
            organization.subscription.status = OrganizationSubscription.StatusType.SUSPENDED
            organization.subscription.save()
        
        return Response({
            'message': f'Organization {organization.name} suspended',
            'reason': reason
        })
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate organization."""
        organization = self.get_object()
        
        organization.is_active = True
        organization.save()
        
        # Reactivate subscription
        if hasattr(organization, 'subscription'):
            organization.subscription.status = OrganizationSubscription.StatusType.ACTIVE
            organization.subscription.save()
        
        return Response({
            'message': f'Organization {organization.name} activated'
        })
    
    @action(detail=True, methods=['post'])
    def update_subscription(self, request, pk=None):
        """Update organization's subscription (admin override)."""
        organization = self.get_object()
        plan_tier = request.data.get('plan_tier')
        
        if not plan_tier:
            return Response(
                {'error': 'plan_tier is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.billing.models import SubscriptionPlan
            new_plan = SubscriptionPlan.objects.get(tier=plan_tier, is_active=True)
            
            if hasattr(organization, 'subscription'):
                subscription = organization.subscription
                subscription.plan = new_plan
                subscription.current_price = new_plan.monthly_price
                subscription.save()
            else:
                OrganizationSubscription.objects.create(
                    organization=organization,
                    plan=new_plan,
                    status=OrganizationSubscription.StatusType.ACTIVE
                )
            
            return Response({
                'message': f'Subscription updated to {new_plan.name}'
            })
            
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': f'Plan with tier {plan_tier} not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class UserAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['role', 'is_active', 'email_verified', 'organization']
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['date_joined', 'last_login', 'last_activity']
    
    def get_queryset(self):
        return User.objects.all().select_related('organization')
    
    def get_serializer_class(self):
        return UserAdminSerializer
    
    @action(detail=True, methods=['post'])
    def impersonate(self, request, pk=None):
        """Generate impersonation token for user (super admin only)."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only super administrators can impersonate users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user = self.get_object()
        
        # Generate impersonation token (simplified for MVP)
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken.for_user(user)
        
        return Response({
            'token': str(token),
            'user_id': user.id,
            'email': user.email,
            'expires_in': '1 hour'
        })


class ContractAdminViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'organization', 'template']
    search_fields = ['title', 'contract_number', 'content']
    ordering_fields = ['created_at', 'sent_at', 'completed_at']
    
    def get_queryset(self):
        return Contract.objects.all().select_related('organization', 'created_by')
    
    def get_serializer_class(self):
        return ContractAdminSerializer


class LLMUsageAdminViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['feature', 'status', 'provider', 'model', 'organization']
    search_fields = ['user__email', 'input_context']
    ordering_fields = ['created_at', 'tokens_total', 'cost_estimated']
    
    def get_queryset(self):
        return LLMUsage.objects.all().select_related(
            'organization', 'user', 'provider', 'model'
        )
    
    def get_serializer_class(self):
        return LLMUsageAdminSerializer


class SubscriptionAdminViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['plan__tier', 'status', 'billing_cycle']
    search_fields = ['organization__name']
    ordering_fields = ['current_price', 'current_period_end', 'created_at']
    
    def get_queryset(self):
        return OrganizationSubscription.objects.all().select_related('organization', 'plan')
    
    def get_serializer_class(self):
        return SubscriptionAdminSerializer


class InvoiceAdminViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'organization']
    search_fields = ['organization__name', 'invoice_number']
    ordering_fields = ['invoice_date', 'due_date', 'total_amount']
    
    def get_queryset(self):
        return Invoice.objects.all().select_related('organization', 'subscription')
    
    def get_serializer_class(self):
        return InvoiceAdminSerializer


class PlatformMetricsView(APIView):
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get platform-wide metrics."""
        # Basic counts
        total_organizations = Organization.objects.count()
        active_organizations = Organization.objects.filter(is_active=True).count()
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        total_contracts = Contract.objects.count()
        
        # Subscription breakdown
        subscription_breakdown = OrganizationSubscription.objects.values(
            'plan__tier'
        ).annotate(
            count=Count('id'),
            total_revenue=Sum('current_price')
        ).order_by('plan__tier')
        
        # Recent activity
        last_30_days = timezone.now() - timedelta(days=30)
        new_organizations = Organization.objects.filter(created_at__gte=last_30_days).count()
        new_users = User.objects.filter(date_joined__gte=last_30_days).count()
        new_contracts = Contract.objects.filter(created_at__gte=last_30_days).count()
        
        # LLM usage
        llm_usage = LLMUsage.objects.filter(created_at__gte=last_30_days).aggregate(
            total_tokens=Sum('tokens_total'),
            total_cost=Sum('cost_estimated'),
            total_requests=Count('id')
        )
        
        # Revenue
        revenue_30_days = Invoice.objects.filter(
            status='paid',
            paid_at__gte=last_30_days
        ).aggregate(total_revenue=Sum('total_amount'))
        
        metrics = {
            'overview': {
                'total_organizations': total_organizations,
                'active_organizations': active_organizations,
                'total_users': total_users,
                'active_users': active_users,
                'total_contracts': total_contracts,
            },
            'recent_activity': {
                'new_organizations_30d': new_organizations,
                'new_users_30d': new_users,
                'new_contracts_30d': new_contracts,
            },
            'subscriptions': {
                'breakdown': list(subscription_breakdown),
                'total_revenue_30d': revenue_30_days['total_revenue'] or 0,
            },
            'llm_usage': {
                'total_tokens_30d': llm_usage['total_tokens'] or 0,
                'total_cost_30d': llm_usage['total_cost'] or 0,
                'total_requests_30d': llm_usage['total_requests'] or 0,
            }
        }
        
        serializer = PlatformMetricsSerializer(metrics)
        return Response(serializer.data)


class SystemHealthView(APIView):
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get system health status."""
        from django.db import connection
        from django.core.cache import cache
        
        # Database health
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_status = 'healthy'
        except Exception as e:
            db_status = f'error: {str(e)}'
        
        # Cache health
        try:
            cache.set('health_check', 'ok', 1)
            cache_status = 'healthy' if cache.get('health_check') == 'ok' else 'error'
        except Exception as e:
            cache_status = f'error: {str(e)}'
        
        # LLM providers health
        llm_providers = []
        for provider in LLMProvider.objects.filter(is_active=True):
            # Simple health check - could be enhanced with actual API calls
            llm_providers.append({
                'name': provider.name,
                'type': provider.provider_type,
                'status': 'active' if provider.is_active else 'inactive'
            })
        
        return Response({
            'database': db_status,
            'cache': cache_status,
            'llm_providers': llm_providers,
            'timestamp': timezone.now().isoformat()
        })                                 
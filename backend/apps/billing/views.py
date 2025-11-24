from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import SubscriptionPlan, OrganizationSubscription, Invoice, PaymentMethod
from .serializers import (
    SubscriptionPlanSerializer, OrganizationSubscriptionSerializer,
    InvoiceSerializer, PaymentMethodSerializer,
    UpgradeSubscriptionSerializer, UsageSummarySerializer
)
from .services import BillingService, UsageService


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing subscription plans.
    Available to all authenticated users.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['tier', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['monthly_price', 'tier']
    
    def get_queryset(self):
        return SubscriptionPlan.objects.filter(is_active=True)
    
    def get_serializer_class(self):
        return SubscriptionPlanSerializer


class OrganizationSubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organization subscriptions.
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch']  # No delete
    
    def get_queryset(self):
        return OrganizationSubscription.objects.filter(
            organization=self.request.user.organization
        )
    
    def get_serializer_class(self):
        return OrganizationSubscriptionSerializer
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Get current subscription with detailed usage information.
        """
        try:
            subscription = self.get_queryset().get()
            serializer = self.get_serializer(subscription)
            
            # Add detailed usage summary
            usage_service = UsageService(request.user.organization)
            data = serializer.data
            data['usage_summary'] = usage_service.get_usage_summary()
            
            # Add feature access information
            data['feature_access'] = {
                'external_signing': subscription.has_feature('external_signing'),
                'pdf_upload': subscription.has_feature('pdf_upload'),
                'authoritative_sources': subscription.has_feature('authoritative_sources'),
                'api_access': subscription.has_feature('api_access'),
                'custom_workflows': subscription.has_feature('custom_workflows'),
            }
            
            return Response(data)
            
        except OrganizationSubscription.DoesNotExist:
            return Response(
                {'error': 'Subscription not found for organization'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def upgrade(self, request):
        """
        Upgrade organization subscription to a higher tier.
        """
        serializer = UpgradeSubscriptionSerializer(data=request.data)
        
        if serializer.is_valid():
            target_plan_tier = serializer.validated_data['target_plan_tier']
            billing_cycle = serializer.validated_data.get('billing_cycle', 'monthly')
            
            billing_service = BillingService(request.user.organization)
            
            try:
                result = billing_service.upgrade_subscription(target_plan_tier, billing_cycle)
                return Response(result)
                
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def downgrade(self, request):
        """
        Downgrade organization subscription (effective at end of billing period).
        """
        target_plan_tier = request.data.get('target_plan_tier')
        
        if not target_plan_tier:
            return Response(
                {'error': 'target_plan_tier is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        billing_service = BillingService(request.user.organization)
        
        try:
            result = billing_service.downgrade_subscription(target_plan_tier)
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """
        Cancel organization subscription.
        """
        billing_service = BillingService(request.user.organization)
        
        try:
            result = billing_service.cancel_subscription()
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def reactivate(self, request):
        """
        Reactivate a cancelled subscription.
        """
        try:
            subscription = self.get_queryset().get()
            
            if subscription.status != OrganizationSubscription.StatusType.CANCELLED:
                return Response(
                    {'error': 'Subscription is not cancelled'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            subscription.status = OrganizationSubscription.StatusType.ACTIVE
            subscription.cancelled_at = None
            subscription.save()
            
            return Response({
                'message': 'Subscription reactivated successfully',
                'status': subscription.status
            })
            
        except OrganizationSubscription.DoesNotExist:
            return Response(
                {'error': 'Subscription not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def upgrade_options(self, request):
        """
        Get available upgrade options for current subscription.
        """
        try:
            current_subscription = self.get_queryset().get()
            current_plan = current_subscription.plan
            
            # Get all plans that are upgrades from current plan
            upgrade_plans = SubscriptionPlan.objects.filter(
                is_active=True,
                monthly_price__gt=current_plan.monthly_price
            ).order_by('monthly_price')
            
            upgrade_options = []
            for plan in upgrade_plans:
                monthly_price_increase = plan.monthly_price - current_plan.monthly_price
                annual_savings = plan.get_annual_savings() if plan.annual_price else 0
                
                upgrade_options.append({
                    'tier': plan.tier,
                    'name': plan.name,
                    'monthly_price': float(plan.monthly_price),
                    'annual_price': float(plan.annual_price) if plan.annual_price else None,
                    'monthly_price_increase': float(monthly_price_increase),
                    'annual_savings_percentage': annual_savings,
                    'features': plan.features,
                    'max_users': plan.max_users,
                    'max_entities': plan.max_entities,
                    'monthly_llm_tokens': plan.monthly_llm_tokens,
                })
            
            return Response({
                'current_plan': {
                    'tier': current_plan.tier,
                    'name': current_plan.name,
                    'monthly_price': float(current_plan.monthly_price),
                },
                'upgrade_options': upgrade_options
            })
            
        except OrganizationSubscription.DoesNotExist:
            return Response(
                {'error': 'Subscription not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing organization invoices.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['invoice_date', 'due_date', 'total_amount']
    
    def get_queryset(self):
        return Invoice.objects.filter(
            organization=self.request.user.organization
        ).select_related('subscription', 'subscription__plan')
    
    def get_serializer_class(self):
        return InvoiceSerializer
    
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """
        Mark invoice as paid (manual payment for MVP).
        """
        invoice = self.get_object()
        
        if invoice.status == Invoice.StatusType.PAID:
            return Response(
                {'error': 'Invoice is already paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method = request.data.get('payment_method', 'manual')
        transaction_id = request.data.get('transaction_id', '')
        paid_amount = request.data.get('paid_amount')
        
        try:
            # Convert paid_amount to Decimal if provided
            if paid_amount is not None:
                paid_amount = Decimal(str(paid_amount))
            
            invoice.mark_paid(payment_method, transaction_id, paid_amount)
            serializer = self.get_serializer(invoice)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get all overdue invoices for the organization.
        """
        overdue_invoices = self.get_queryset().filter(
            status=Invoice.StatusType.OPEN,
            due_date__lt=timezone.now()
        )
        
        serializer = self.get_serializer(overdue_invoices, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming invoices (due in next 30 days).
        """
        thirty_days_from_now = timezone.now() + timedelta(days=30)
        
        upcoming_invoices = self.get_queryset().filter(
            status=Invoice.StatusType.OPEN,
            due_date__gte=timezone.now(),
            due_date__lte=thirty_days_from_now
        )
        
        serializer = self.get_serializer(upcoming_invoices, many=True)
        return Response(serializer.data)


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organization payment methods.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentMethodSerializer
    
    def get_queryset(self):
        return PaymentMethod.objects.filter(
            organization=self.request.user.organization,
            is_active=True
        )
    
    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """
        Set a payment method as default for the organization.
        """
        payment_method = self.get_object()
        
        # Set all other payment methods as non-default
        PaymentMethod.objects.filter(
            organization=request.user.organization
        ).update(is_default=False)
        
        # Set this one as default
        payment_method.is_default = True
        payment_method.save()
        
        serializer = self.get_serializer(payment_method)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate a payment method.
        """
        payment_method = self.get_object()
        
        if payment_method.is_default:
            return Response(
                {'error': 'Cannot deactivate default payment method'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method.is_active = False
        payment_method.save()
        
        serializer = self.get_serializer(payment_method)
        return Response(serializer.data)


class UsageSummaryView(APIView):
    """
    API view for getting detailed usage summary.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get comprehensive usage summary for the organization.
        """
        usage_service = UsageService(request.user.organization)
        summary = usage_service.get_usage_summary()
        
        # Add subscription information
        try:
            subscription = OrganizationSubscription.objects.get(
                organization=request.user.organization
            )
            summary['subscription'] = {
                'plan_name': subscription.plan.name,
                'plan_tier': subscription.plan.tier,
                'billing_cycle': subscription.billing_cycle,
                'status': subscription.status,
                'current_period_end': subscription.current_period_end,
                'days_until_renewal': subscription.days_until_renewal(),
            }
        except OrganizationSubscription.DoesNotExist:
            summary['subscription'] = None
        
        return Response(summary)


class BillingWebhookView(APIView):
    """
    Handle webhooks from payment processors.
    For MVP, this just logs webhooks since we're using manual payments.
    """
    permission_classes = []  # No authentication for webhooks
    
    def post(self, request, processor):
        """
        Process webhook from payment processor.
        """
        from .models import BillingWebhook
        
        try:
            # Log the webhook
            webhook = BillingWebhook.objects.create(
                processor=processor,
                event_type=request.data.get('type', ''),
                event_id=request.data.get('id', ''),
                payload=request.data
            )
            
            # Process based on event type
            event_type = request.data.get('type', '')
            
            if 'invoice.payment_succeeded' in event_type:
                self._handle_payment_succeeded(request.data)
            elif 'invoice.payment_failed' in event_type:
                self._handle_payment_failed(request.data)
            elif 'customer.subscription.updated' in event_type:
                self._handle_subscription_updated(request.data)
            
            webhook.processed = True
            webhook.processed_at = timezone.now()
            webhook.save()
            
            return Response({'status': 'processed'})
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _handle_payment_succeeded(self, payload):
        """Handle successful payment webhook."""
        # In a real implementation, this would update invoice status
        # For MVP, we'll just log it
        pass
    
    def _handle_payment_failed(self, payload):
        """Handle failed payment webhook."""
        # In a real implementation, this would mark invoice as overdue
        # and potentially suspend service
        pass
    
    def _handle_subscription_updated(self, payload):
        """Handle subscription update webhook."""
        # In a real implementation, this would sync subscription status
        pass


class SubscriptionCheckView(APIView):
    """
    API view for checking subscription limits and feature access.
    Useful for frontend to conditionally enable/disable features.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Check subscription limits and feature access.
        """
        usage_service = UsageService(request.user.organization)
        
        try:
            subscription = OrganizationSubscription.objects.get(
                organization=request.user.organization
            )
            
            # Check all limits
            can_add_user = usage_service.check_user_limit()
            can_add_entity = usage_service.check_entity_limit()
            can_create_contract = usage_service.check_contract_limit()
            
            # Feature access
            feature_access = {
                'external_signing': subscription.has_feature('external_signing'),
                'pdf_upload': subscription.has_feature('pdf_upload'),
                'authoritative_sources': subscription.has_feature('authoritative_sources'),
                'api_access': subscription.has_feature('api_access'),
                'custom_workflows': subscription.has_feature('custom_workflows'),
            }
            
            # Current usage
            current_usage = {
                'users': subscription.users_count,
                'entities': subscription.entities_count,
                'contracts_this_month': subscription.contracts_used_this_month,
                'llm_tokens_this_month': subscription.llm_tokens_used_this_month,
            }
            
            # Limits
            limits = {
                'max_users': subscription.plan.max_users,
                'max_entities': subscription.plan.max_entities,
                'max_contracts_per_month': subscription.plan.max_contracts_per_month,
                'monthly_llm_tokens': subscription.plan.monthly_llm_tokens,
            }
            
            return Response({
                'subscription_status': subscription.status,
                'plan_tier': subscription.plan.tier,
                'can_add_user': can_add_user,
                'can_add_entity': can_add_entity,
                'can_create_contract': can_create_contract,
                'feature_access': feature_access,
                'current_usage': current_usage,
                'limits': limits,
                'is_active': subscription.is_active(),
                'is_trial': subscription.is_trial(),
            })
            
        except OrganizationSubscription.DoesNotExist:
            return Response(
                {'error': 'Subscription not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TrialExtensionView(APIView):
    """
    API view for extending trial periods (admin function).
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Extend trial period for organization.
        """
        # Only org admins or superusers can extend trials
        if not (request.user.is_org_admin() or request.user.is_superuser):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        extension_days = request.data.get('extension_days', 7)
        
        try:
            subscription = OrganizationSubscription.objects.get(
                organization=request.user.organization
            )
            
            if subscription.status != OrganizationSubscription.StatusType.TRIAL:
                return Response(
                    {'error': 'Organization is not in trial period'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Extend trial
            if subscription.trial_end_date:
                new_end_date = subscription.trial_end_date + timedelta(days=extension_days)
            else:
                new_end_date = timezone.now() + timedelta(days=extension_days)
            
            subscription.trial_end_date = new_end_date
            subscription.save()
            
            return Response({
                'message': f'Trial extended by {extension_days} days',
                'new_trial_end_date': new_end_date,
                'days_remaining': (new_end_date - timezone.now()).days
            })
            
        except OrganizationSubscription.DoesNotExist:
            return Response(
                {'error': 'Subscription not found'},
                status=status.HTTP_404_NOT_FOUND
            )
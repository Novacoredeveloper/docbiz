from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone

from .models import Organization, OrganizationContact
from .serializers import (
    OrganizationSerializer, OrganizationContactSerializer,
    OrganizationCreateSerializer, OrganizationUpdateSerializer
)


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organizations.
    Regular users can only access their own organization.
    Superusers can access all organizations.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['subscription__plan__tier', 'is_active']
    search_fields = ['name', 'legal_name', 'primary_contact_email', 'industry']
    ordering_fields = ['name', 'created_at', 'subscription__current_price']
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return Organization.objects.all().select_related('subscription__plan')
        elif self.request.user.organization:
            return Organization.objects.filter(id=self.request.user.organization.id)
        return Organization.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrganizationCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OrganizationUpdateSerializer
        return OrganizationSerializer
    
    def perform_create(self, serializer):
        """Only superusers can create organizations."""
        if not self.request.user.is_superuser:
            raise PermissionError("Only administrators can create organizations")
        organization = serializer.save()
        
        # Log the creation (you might want to add an audit log here)
        # AuditLog.objects.create(...)
    
    def perform_update(self, serializer):
        """Only superusers or org admins can update organizations."""
        organization = self.get_object()
        user = self.request.user
        
        if not (user.is_superuser or 
                (user.organization == organization and user.is_org_admin())):
            raise PermissionError("You don't have permission to update this organization")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Only superusers can delete organizations (soft delete)."""
        if not self.request.user.is_superuser:
            raise PermissionError("Only administrators can delete organizations")
        instance.delete()  # Soft delete via SafeDeleteModel
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate an organization (admin only)."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only administrators can activate organizations'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        organization = self.get_object()
        organization.is_active = True
        organization.save()
        
        return Response({
            'message': f'Organization {organization.name} activated',
            'is_active': organization.is_active
        })
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an organization (admin only)."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only administrators can deactivate organizations'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        organization = self.get_object()
        organization.is_active = False
        organization.save()
        
        return Response({
            'message': f'Organization {organization.name} deactivated',
            'is_active': organization.is_active
        })
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get organization statistics."""
        organization = self.get_object()
        
        # Check if user has access to this organization
        if not (request.user.is_superuser or request.user.organization == organization):
            return Response(
                {'error': 'You do not have access to this organization'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from apps.users.models import User
        from apps.contracts.models import Contract
        from apps.charts.models import OrgChart
        
        # User statistics
        user_stats = {
            'total_users': organization.users.filter(is_active=True).count(),
            'active_users': organization.users.filter(is_active=True, last_activity__gte=timezone.now() - timezone.timedelta(days=30)).count(),
            'admin_users': organization.users.filter(role='org_admin', is_active=True).count(),
        }
        
        # Contract statistics
        contract_stats = {
            'total_contracts': organization.contracts.count(),
            'draft_contracts': organization.contracts.filter(status='draft').count(),
            'sent_contracts': organization.contracts.filter(status='sent').count(),
            'signed_contracts': organization.contracts.filter(status='signed').count(),
            'completed_contracts': organization.contracts.filter(status='completed').count(),
        }
        
        # Chart statistics
        chart_stats = {}
        try:
            org_chart = organization.org_chart
            chart_data = org_chart.data
            chart_stats = {
                'total_entities': (
                    len(chart_data.get('companies', [])) +
                    len(chart_data.get('persons', [])) +
                    len(chart_data.get('trusts', [])) +
                    len(chart_data.get('groups', []))
                ),
                'companies': len(chart_data.get('companies', [])),
                'persons': len(chart_data.get('persons', [])),
                'trusts': len(chart_data.get('trusts', [])),
                'connections': len(chart_data.get('connections', [])),
            }
        except OrgChart.DoesNotExist:
            chart_stats = {'error': 'No organizational chart found'}
        
        # LLM usage statistics (from last 30 days)
        from apps.llm.models import LLMUsage
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        llm_stats = LLMUsage.objects.filter(
            organization=organization,
            created_at__gte=thirty_days_ago
        ).aggregate(
            total_requests=models.Count('id'),
            total_tokens=models.Sum('tokens_total'),
            total_cost=models.Sum('cost_estimated')
        )
        
        return Response({
            'organization': organization.name,
            'user_stats': user_stats,
            'contract_stats': contract_stats,
            'chart_stats': chart_stats,
            'llm_usage': {
                'last_30_days': {
                    'requests': llm_stats['total_requests'] or 0,
                    'tokens': llm_stats['total_tokens'] or 0,
                    'cost': float(llm_stats['total_cost'] or 0),
                }
            },
            'subscription': {
                'plan': organization.subscription.plan.name if hasattr(organization, 'subscription') else 'None',
                'status': organization.subscription.status if hasattr(organization, 'subscription') else 'None',
                'users_count': organization.subscription.users_count if hasattr(organization, 'subscription') else 0,
            } if hasattr(organization, 'subscription') else None
        })
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current user's organization."""
        if not request.user.organization:
            return Response(
                {'error': 'User is not associated with any organization'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        organization = request.user.organization
        serializer = self.get_serializer(organization)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_subscription(self, request, pk=None):
        """Update organization subscription (admin only)."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only administrators can update subscriptions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
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
                from apps.billing.models import OrganizationSubscription
                OrganizationSubscription.objects.create(
                    organization=organization,
                    plan=new_plan,
                    status='active'
                )
            
            return Response({
                'message': f'Subscription updated to {new_plan.name}',
                'new_plan': new_plan.name,
                'monthly_price': float(new_plan.monthly_price)
            })
            
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'error': f'Plan with tier {plan_tier} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Get all contacts for an organization."""
        organization = self.get_object()
        
        # Check if user has access to this organization
        if not (request.user.is_superuser or request.user.organization == organization):
            return Response(
                {'error': 'You do not have access to this organization'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        contacts = organization.contacts.filter(is_active=True)
        serializer = OrganizationContactSerializer(contacts, many=True)
        return Response(serializer.data)


class OrganizationContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organization contacts.
    Users can only access contacts from their own organization.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['contact_type', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'title']
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return OrganizationContact.objects.all()
        elif self.request.user.organization:
            return OrganizationContact.objects.filter(
                organization=self.request.user.organization
            )
        return OrganizationContact.objects.none()
    
    def get_serializer_class(self):
        return OrganizationContactSerializer
    
    def perform_create(self, serializer):
        """Set organization automatically for non-superusers."""
        if self.request.user.is_superuser:
            # Superusers can specify any organization
            serializer.save()
        else:
            # Regular users can only create contacts for their organization
            serializer.save(organization=self.request.user.organization)
    
    def perform_update(self, serializer):
        """Check permissions before updating."""
        contact = self.get_object()
        user = self.request.user
        
        if not (user.is_superuser or user.organization == contact.organization):
            raise PermissionError("You don't have permission to update this contact")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Soft delete contact."""
        instance.delete()  # SafeDeleteModel handles soft delete
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a contact."""
        contact = self.get_object()
        
        # Check permissions
        if not (request.user.is_superuser or request.user.organization == contact.organization):
            return Response(
                {'error': 'You do not have permission to modify this contact'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        contact.is_active = True
        contact.save()
        
        serializer = self.get_serializer(contact)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a contact."""
        contact = self.get_object()
        
        # Check permissions
        if not (request.user.is_superuser or request.user.organization == contact.organization):
            return Response(
                {'error': 'You do not have permission to modify this contact'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        contact.is_active = False
        contact.save()
        
        serializer = self.get_serializer(contact)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get contacts filtered by type."""
        contact_type = request.query_params.get('contact_type')
        
        if not contact_type:
            return Response(
                {'error': 'contact_type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contacts = self.get_queryset().filter(contact_type=contact_type, is_active=True)
        serializer = self.get_serializer(contacts, many=True)
        return Response(serializer.data)


class OrganizationInvitationView(APIView):
    """
    API view for inviting users to organizations.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Invite a user to join the organization.
        Only organization admins or superusers can send invitations.
        """
        from apps.users.models import User
        from django.core.mail import send_mail
        from django.conf import settings
        
        email = request.data.get('email')
        role = request.data.get('role', 'org_user')
        
        if not email:
            return Response(
                {'error': 'Email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has permission to invite
        if not (request.user.is_superuser or request.user.is_org_admin()):
            return Response(
                {'error': 'Only organization administrators can invite users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user already exists
        try:
            existing_user = User.objects.get(email=email)
            if existing_user.organization == request.user.organization:
                return Response(
                    {'error': 'User is already a member of this organization'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif existing_user.organization:
                return Response(
                    {'error': 'User is already a member of another organization'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except User.DoesNotExist:
            # User doesn't exist yet, that's fine
            pass
        
        # Check organization limits
        if hasattr(request.user.organization, 'subscription'):
            subscription = request.user.organization.subscription
            if not subscription.can_add_user():
                return Response(
                    {'error': 'Organization has reached its user limit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Generate invitation token (simplified for MVP)
        import secrets
        invitation_token = secrets.token_urlsafe(32)
        
        # Store invitation (in a real implementation, you'd have an Invitation model)
        # For MVP, we'll just send the email
        
        # Send invitation email
        try:
            send_mail(
                subject=f'Invitation to join {request.user.organization.name} on DocBiz',
                message=f'''
                You have been invited to join {request.user.organization.name} on DocBiz.
                
                Please click the following link to accept the invitation:
                {settings.FRONTEND_URL}/accept-invitation/?token={invitation_token}
                
                If you don't have an account, you'll be prompted to create one.
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            return Response({
                'message': f'Invitation sent to {email}',
                'role': role
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to send invitation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrganizationSettingsView(APIView):
    """
    API view for organization settings and configuration.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get organization settings."""
        if not request.user.organization:
            return Response(
                {'error': 'User is not associated with any organization'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        organization = request.user.organization
        
        settings_data = {
            'organization': {
                'name': organization.name,
                'legal_name': organization.legal_name,
                'primary_contact_email': organization.primary_contact_email,
                'phone_number': str(organization.phone_number) if organization.phone_number else None,
                'website': organization.website,
                'industry': organization.industry,
            },
            'address': {
                'address_line_1': organization.address_line_1,
                'address_line_2': organization.address_line_2,
                'city': organization.city,
                'state': organization.state,
                'postal_code': organization.postal_code,
                'country': organization.country.name if organization.country else None,
            },
            'features': {
                'has_org_chart': hasattr(organization, 'org_chart'),
                'total_users': organization.users.filter(is_active=True).count(),
                'total_contracts': organization.contracts.count(),
            }
        }
        
        return Response(settings_data)
    
    def put(self, request):
        """Update organization settings."""
        if not request.user.organization:
            return Response(
                {'error': 'User is not associated with any organization'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not (request.user.is_superuser or request.user.is_org_admin()):
            return Response(
                {'error': 'Only organization administrators can update settings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        organization = request.user.organization
        serializer = OrganizationUpdateSerializer(organization, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Organization settings updated successfully',
                'settings': serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OrganizationSearchView(APIView):
    """
    API view for searching organizations (admin only).
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Search organizations by various criteria."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only administrators can search organizations'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {'error': 'Search query (q) parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.db.models import Q
        
        organizations = Organization.objects.filter(
            Q(name__icontains=query) |
            Q(legal_name__icontains=query) |
            Q(primary_contact_email__icontains=query) |
            Q(industry__icontains=query)
        ).select_related('subscription__plan')
        
        serializer = OrganizationSerializer(organizations, many=True)
        
        return Response({
            'query': query,
            'results': serializer.data,
            'total_count': organizations.count()
        })
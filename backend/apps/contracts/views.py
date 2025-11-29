from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    Contract, ContractTemplate, LegalReferenceLibrary, 
    ContractParty, SignatureField, ContractEvent
)

from apps.llm.models import LLMUsage
from .serializers import (
    ContractSerializer, ContractTemplateSerializer,
    LegalReferenceSerializer, ContractPartySerializer,
    SignatureFieldSerializer, ContractEventSerializer,
    ClauseGenerationSerializer,ContractEditSerializer, 
    ContractSendSerializer,
)
from apps.llm.serializers import LLMUsageSerializer

from .llm_service import LLMService


class ContractTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['template_type', 'is_active']
    ordering_fields = ['name', 'created_at', 'version']
    
    def get_queryset(self):
        return ContractTemplate.objects.filter(
            organization=self.request.user.organization,
            is_active=True
        )
    
    def get_serializer_class(self):
        if self.action == 'create_version':
            return ContractTemplateSerializer
        return ContractTemplateSerializer
    
    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """Create a new version of the template."""
        template = self.get_object()
        new_content = request.data.get('content', template.content)
        
        new_template = template.create_new_version(new_content)
        serializer = self.get_serializer(new_template)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ContractViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['title', 'contract_number']
    filterset_fields = ['status', 'template']
    ordering_fields = ['created_at', 'sent_at', 'completed_at']
    
    def get_queryset(self):
        return Contract.objects.filter(
            organization=self.request.user.organization
        ).prefetch_related('parties', 'signature_fields', 'events')
    
    def get_serializer_class(self):
        if self.action == 'send_for_signature':
            return ContractSendSerializer
        return ContractSerializer
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organization,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def send_for_signature(self, request, pk=None):
        """Send contract for signature."""
        contract = self.get_object()
        
        try:
            contract.send_for_signature()
            
            # Create event
            ContractEvent.objects.create(
                contract=contract,
                event_type=ContractEvent.EventType.SENT,
                description=f"Contract sent for signature by {request.user.email}",
                actor=request.user,
                actor_ip=self.get_client_ip(request)
            )
            
            serializer = self.get_serializer(contract)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def generate_clause(self, request, pk=None):
        """Generate a clause using AI."""
        contract = self.get_object()
        serializer = ClauseGenerationSerializer(data=request.data)
        
        if serializer.is_valid():
            clause_type = serializer.validated_data['clause_type']
            context = serializer.validated_data.get('context', '')
            
            llm_service = LLMService()
            try:
                result = llm_service.generate_clause(
                    clause_type=clause_type,
                    context=context,
                    contract=contract,
                    user=request.user
                )
                
                return Response(result)
                
            except Exception as e:
                return Response(
                    {'error': f'AI generation failed: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def edit_with_ai(self, request, pk=None):
        """Edit contract content using AI."""
        contract = self.get_object()
        serializer = ContractEditSerializer(data=request.data)
        
        if serializer.is_valid():
            instruction = serializer.validated_data['instruction']
            content = serializer.validated_data.get('content', contract.content)
            
            llm_service = LLMService()
            try:
                result = llm_service.edit_contract(
                    instruction=instruction,
                    content=content,
                    contract=contract,
                    user=request.user
                )
                
                return Response(result)
                
            except Exception as e:
                return Response(
                    {'error': f'AI editing failed: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LegalReferenceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['title', 'citation', 'topics']
    filterset_fields = ['state', 'content_type', 'format']
    ordering_fields = ['state', 'title', 'effective_date']
    
    def get_queryset(self):
        return LegalReferenceLibrary.objects.filter(is_active=True)
    
    def get_serializer_class(self):
        return LegalReferenceSerializer


class ContractPartyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        contract_id = self.kwargs.get('contract_id')
        return ContractParty.objects.filter(
            contract_id=contract_id,
            contract__organization=self.request.user.organization
        )
    
    def get_serializer_class(self):
        return ContractPartySerializer
    
    def perform_create(self, serializer):
        contract_id = self.kwargs.get('contract_id')
        contract = Contract.objects.get(
            id=contract_id,
            organization=self.request.user.organization
        )
        serializer.save(contract=contract)


class SignatureFieldViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        contract_id = self.kwargs.get('contract_id')
        return SignatureField.objects.filter(
            contract_id=contract_id,
            contract__organization=self.request.user.organization
        )
    
    def get_serializer_class(self):
        return SignatureFieldSerializer
    
    def perform_create(self, serializer):
        contract_id = self.kwargs.get('contract_id')
        contract = Contract.objects.get(
            id=contract_id,
            organization=self.request.user.organization
        )
        serializer.save(contract=contract)


class PublicSigningView(APIView):
    """Public endpoint for external signers."""
    permission_classes = []  # No authentication required
    
    def get(self, request, token):
        """Get signing page data."""
        try:
            signature_field = SignatureField.objects.get(signing_token=token)
            contract = signature_field.contract
            
            # Check if expired
            if contract.is_expired():
                return Response(
                    {'error': 'This signing link has expired'},
                    status=status.HTTP_410_GONE
                )
            
            serializer = SignatureFieldSerializer(signature_field)
            return Response(serializer.data)
            
        except SignatureField.DoesNotExist:
            return Response(
                {'error': 'Invalid signing token'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request, token):
        """Process signature."""
        try:
            signature_field = SignatureField.objects.get(signing_token=token)
            contract = signature_field.contract
            
            # Check if expired
            if contract.is_expired():
                return Response(
                    {'error': 'This signing link has expired'},
                    status=status.HTTP_410_GONE
                )
            
            # Check if already signed
            if signature_field.is_signed():
                return Response(
                    {'error': 'This document has already been signed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process signature
            signature_data = request.data.get('signature_data')
            if not signature_data:
                return Response(
                    {'error': 'Signature data is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ip_address = self.get_client_ip(request)
            signature_field.sign(signature_data, ip_address)
            
            # Create event
            ContractEvent.objects.create(
                contract=contract,
                event_type=ContractEvent.EventType.SIGNED,
                description=f"Field '{signature_field.label}' signed by {signature_field.assigned_to.name}",
                actor_ip=ip_address,
                metadata={'field_label': signature_field.label}
            )
            
            return Response({'message': 'Successfully signed'})
            
        except SignatureField.DoesNotExist:
            return Response(
                {'error': 'Invalid signing token'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LLMUsageViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['feature', 'provider', 'model']
    ordering_fields = ['created_at', 'tokens_total', 'cost_estimated']
    
    def get_queryset(self):
        return LLMUsage.objects.filter(
            organization=self.request.user.organization,
            user=self.request.user
        )
    
    def get_serializer_class(self):
        return LLMUsageSerializer
from rest_framework import serializers
from django_countries.serializer_fields import CountryField
from phonenumber_field.serializerfields import PhoneNumberField
from .models import (
    Contract, ContractTemplate, LegalReferenceLibrary,
    ContractParty, SignatureField, ContractEvent,
    ContractStatus
)

from apps.llm.models import LLMUsage

class ContractTemplateSerializer(serializers.ModelSerializer):
    """Serializer for ContractTemplate model."""
    
    template_type_display = serializers.CharField(
        source='get_template_type_display',
        read_only=True
    )
    created_by_email = serializers.EmailField(
        source='created_by.email',
        read_only=True
    )
    organization_name = serializers.CharField(
        source='organization.name',
        read_only=True
    )
    
    class Meta:
        model = ContractTemplate
        fields = [
            'uuid',
            'organization',
            'organization_name',
            'name',
            'template_type',
            'template_type_display',
            'content',
            'description',
            'placeholders',
            'signature_blocks',
            'is_active',
            'version',
            'created_by',
            'created_by_email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'uuid',
            'organization',
            'template_type_display',
            'created_by',
            'created_by_email',
            'version',
            'created_at',
            'updated_at',
        ]
    
    def validate_name(self, value):
        """Validate template name uniqueness within organization."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            organization = request.user.organization
            existing = ContractTemplate.objects.filter(
                organization=organization,
                name=value,
                is_active=True
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    "A template with this name already exists in your organization."
                )
        return value
    
    def create(self, validated_data):
        """Create template with organization and user from request."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['organization'] = request.user.organization
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class LegalReferenceSerializer(serializers.ModelSerializer):
    """Serializer for LegalReferenceLibrary model."""
    
    content_type_display = serializers.CharField(
        source='get_content_type_display',
        read_only=True
    )
    format_display = serializers.CharField(
        source='get_format_display',
        read_only=True
    )
    
    class Meta:
        model = LegalReferenceLibrary
        fields = [
            'uuid',
            'state',
            'title',
            'citation',
            'url',
            'content_type',
            'content_type_display',
            'format',
            'format_display',
            'topics',
            'excerpt',
            'effective_date',
            'last_updated',
            'is_active',
            'created_at',
        ]
        read_only_fields = [
            'uuid',
            'content_type_display',
            'format_display',
            'last_updated',
            'created_at',
        ]


class ContractPartySerializer(serializers.ModelSerializer):
    """Serializer for ContractParty model."""
    
    party_type_display = serializers.CharField(
        source='get_party_type_display',
        read_only=True
    )
    internal_user_email = serializers.EmailField(
        source='internal_user.email',
        read_only=True
    )
    is_signed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = ContractParty
        fields = [
            'uuid',
            'contract',
            'party_type',
            'party_type_display',
            'name',
            'email',
            'internal_user',
            'internal_user_email',
            'org_chart_entity',
            'phone',
            'address',
            'role',
            'signed_at',
            'signing_ip',
            'is_signed',
        ]
        read_only_fields = [
            'uuid',
            'contract',
            'party_type_display',
            'internal_user_email',
            'signed_at',
            'signing_ip',
            'is_signed',
        ]
    
    def get_is_signed(self, obj):
        """Check if party has signed any signature fields."""
        return obj.signature_fields.filter(signed_data__isnull=False).exists()


class SignatureFieldSerializer(serializers.ModelSerializer):
    """Serializer for SignatureField model."""
    
    field_type_display = serializers.CharField(
        source='get_field_type_display',
        read_only=True
    )
    assigned_to_name = serializers.CharField(
        source='assigned_to.name',
        read_only=True
    )
    assigned_to_email = serializers.EmailField(
        source='assigned_to.email',
        read_only=True
    )
    is_signed = serializers.BooleanField(read_only=True)
    signing_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SignatureField
        fields = [
            'uuid',
            'contract',
            'field_type',
            'field_type_display',
            'label',
            'required',
            'page_number',
            'x_position',
            'y_position',
            'width',
            'height',
            'assigned_to',
            'assigned_to_name',
            'assigned_to_email',
            'signing_token',
            'signed_data',
            'signed_at',
            'metadata',
            'is_signed',
            'signing_url',
        ]
        read_only_fields = [
            'uuid',
            'contract',
            'field_type_display',
            'assigned_to_name',
            'assigned_to_email',
            'signing_token',
            'signed_data',
            'signed_at',
            'is_signed',
            'signing_url',
        ]
    
    def get_is_signed(self, obj):
        return obj.is_signed()
    
    def get_signing_url(self, obj):
        request = self.context.get('request')
        if request and obj.signing_token:
            return f"{request.build_absolute_uri('/')}contracts/api/public/signing/{obj.signing_token}/"
        return None


class ContractEventSerializer(serializers.ModelSerializer):
    """Serializer for ContractEvent model."""
    
    event_type_display = serializers.CharField(
        source='get_event_type_display',
        read_only=True
    )
    actor_email = serializers.EmailField(
        source='actor.email',
        read_only=True
    )
    
    class Meta:
        model = ContractEvent
        fields = [
            'uuid',
            'contract',
            'event_type',
            'event_type_display',
            'description',
            'metadata',
            'actor',
            'actor_email',
            'actor_ip',
            'created_at',
        ]
        read_only_fields = [
            'uuid',
            'contract',
            'event_type_display',
            'actor_email',
            'created_at',
        ]

class ContractSerializer(serializers.ModelSerializer):
    """Serializer for Contract model - used for read operations."""
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    created_by_email = serializers.EmailField(
        source='created_by.email',
        read_only=True
    )
    template_name = serializers.CharField(
        source='template.name',
        read_only=True
    )
    
    # Nested serializers
    parties = ContractPartySerializer(many=True, read_only=True)
    signature_fields = SignatureFieldSerializer(many=True, read_only=True)
    events = ContractEventSerializer(many=True, read_only=True)
    
    # Computed fields
    is_expired = serializers.BooleanField(read_only=True)
    signing_progress = serializers.SerializerMethodField()
    total_signature_fields = serializers.SerializerMethodField()
    signed_signature_fields = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'uuid',
            'organization',
            'title',
            'contract_number',
            'template',
            'template_name',
            'content',
            'final_content',
            'original_pdf',
            'pdf_overlay_schema',
            'status',
            'status_display',
            'created_at',
            'sent_at',
            'expires_at',
            'completed_at',
            'created_by',
            'created_by_email',
            'llm_usage_count',
            'last_llm_usage',
            'metadata',
            'parties',
            'signature_fields',
            'events',
            'is_expired',
            'signing_progress',
            'total_signature_fields',
            'signed_signature_fields',
        ]
        read_only_fields = [
            'uuid',
            'organization',
            'status_display',
            'created_by_email',
            'template_name',
            'is_expired',
            'signing_progress',
            'total_signature_fields',
            'signed_signature_fields',
            'created_at',
            'sent_at',
            'expires_at',
            'completed_at',
            'llm_usage_count',
            'last_llm_usage',
        ]
    
    def get_signing_progress(self, obj):
        total = obj.signature_fields.count()
        if total == 0:
            return 0
        signed = obj.signature_fields.filter(signed_data__isnull=False).count()
        return (signed / total) * 100
    
    def get_total_signature_fields(self, obj):
        return obj.signature_fields.count()
    
    def get_signed_signature_fields(self, obj):
        return obj.signature_fields.filter(signed_data__isnull=False).count()


class ContractCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new contracts."""
    
    class Meta:
        model = Contract
        fields = [
            'title',
            'template',
            'content',
            'original_pdf',
            'metadata',
        ]
    
    def validate(self, attrs):
        """Validate contract creation data."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            # Ensure template belongs to user's organization
            template = attrs.get('template')
            if template and template.organization != request.user.organization:
                raise serializers.ValidationError({
                    'template': 'Template does not belong to your organization.'
                })
        return attrs
    
    def create(self, validated_data):
        """Create contract with organization and user from request."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['organization'] = request.user.organization
            validated_data['created_by'] = request.user
        
        # Generate contract number if not provided
        if not validated_data.get('contract_number'):
            # This will be handled by the model's clean method
            pass
        
        return super().create(validated_data)


class ContractSendSerializer(serializers.Serializer):
    """Serializer for sending contract for signature."""
    
    message = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional message to include with the contract"
    )
    expiration_days = serializers.IntegerField(
        min_value=1,
        max_value=90,
        default=30,
        help_text="Number of days until contract expires"
    )
    
    def validate(self, attrs):
        """Validate send contract data."""
        # Additional validation can be added here
        return attrs


class ClauseGenerationSerializer(serializers.Serializer):
    """Serializer for generating clauses using AI."""
    
    clause_type = serializers.ChoiceField(
        choices=[
            ('indemnification', 'Indemnification Clause'),
            ('confidentiality', 'Confidentiality Clause'),
            ('termination', 'Termination Clause'),
            ('governing_law', 'Governing Law Clause'),
            ('limitation_liability', 'Limitation of Liability Clause'),
            ('warranties', 'Warranties Clause'),
            ('payment_terms', 'Payment Terms Clause'),
            ('intellectual_property', 'Intellectual Property Clause'),
            ('dispute_resolution', 'Dispute Resolution Clause'),
            ('custom', 'Custom Clause'),
        ],
        help_text="Type of clause to generate"
    )
    context = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Additional context for clause generation"
    )
    jurisdiction = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Jurisdiction for legal compliance"
    )
    length = serializers.ChoiceField(
        choices=[
            ('short', 'Short'),
            ('medium', 'Medium'),
            ('long', 'Long'),
        ],
        default='medium',
        help_text="Desired length of the clause"
    )
    
    def validate(self, attrs):
        """Validate clause generation data."""
        # Add any additional validation here
        return attrs


class ContractEditSerializer(serializers.Serializer):
    """Serializer for editing contract content using AI."""
    
    instruction = serializers.CharField(
        help_text="Instructions for how to edit the contract"
    )
    content = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Contract content to edit (uses current content if not provided)"
    )
    preserve_formatting = serializers.BooleanField(
        default=True,
        help_text="Whether to preserve existing formatting"
    )
    
    def validate(self, attrs):
        """Validate contract edit data."""
        if not attrs.get('instruction').strip():
            raise serializers.ValidationError({
                'instruction': 'Instruction cannot be empty.'
            })
        return attrs


class PublicSigningSerializer(serializers.Serializer):
    """Serializer for public signing endpoint."""
    
    signature_data = serializers.CharField(
        help_text="Signature data (base64 encoded image or text)"
    )
    consent_given = serializers.BooleanField(
        required=True,
        help_text="User consent for electronic signature"
    )
    
    def validate(self, attrs):
        """Validate signing data."""
        if not attrs.get('consent_given'):
            raise serializers.ValidationError({
                'consent_given': 'Electronic signature consent is required.'
            })
        return attrs


class ContractBulkActionSerializer(serializers.Serializer):
    """Serializer for bulk contract actions."""
    
    contracts = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text="List of contract UUIDs to act upon"
    )
    action = serializers.ChoiceField(
        choices=[
            ('send', 'Send for Signature'),
            ('cancel', 'Cancel'),
            ('archive', 'Archive'),
        ],
        help_text="Action to perform on selected contracts"
    )
    
    def validate_contracts(self, value):
        """Validate that contracts exist and belong to user's organization."""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            organization = request.user.organization
            existing_contracts = Contract.objects.filter(
                uuid__in=value,
                organization=organization
            ).values_list('uuid', flat=True)
            
            missing_contracts = set(value) - set(existing_contracts)
            if missing_contracts:
                raise serializers.ValidationError(
                    f"Contracts not found: {', '.join(str(uuid) for uuid in missing_contracts)}"
                )
        
        return value


class ContractStatsSerializer(serializers.Serializer):
    """Serializer for contract statistics."""
    
    total_contracts = serializers.IntegerField()
    draft_contracts = serializers.IntegerField()
    sent_contracts = serializers.IntegerField()
    signed_contracts = serializers.IntegerField()
    completed_contracts = serializers.IntegerField()
    expired_contracts = serializers.IntegerField()
    
    avg_signing_time_hours = serializers.FloatField()
    completion_rate = serializers.FloatField()
    
    llm_usage_total = serializers.IntegerField()
    llm_usage_this_month = serializers.IntegerField()
    llm_cost_estimated = serializers.FloatField()


# Minimal serializers for nested relationships
class ContractMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for contract references."""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Contract
        fields = ['uuid', 'title', 'contract_number', 'status', 'status_display']


class ContractTemplateMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for template references."""
    
    class Meta:
        model = ContractTemplate
        fields = ['uuid', 'name', 'template_type']


class LegalReferenceMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for legal reference references."""
    
    class Meta:
        model = LegalReferenceLibrary
        fields = ['uuid', 'title', 'citation', 'state']
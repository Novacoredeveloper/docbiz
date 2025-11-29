from django.db import models
from django.core.exceptions import ValidationError
from safedelete.models import SafeDeleteModel
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField
from django.utils.translation import gettext_lazy as _
import uuid
import json
from datetime import timedelta
from django.utils import timezone
from enum import Enum


class ContractStatus(Enum):
    DRAFT = 'draft'
    SENT = 'sent'
    VIEWED = 'viewed'
    SIGNED = 'signed'
    COMPLETED = 'completed'
    EXPIRED = 'expired'
    DECLINED = 'declined'
    CANCELLED = 'cancelled'


class ContractTemplate(SafeDeleteModel):
    """Contract templates with placeholders and signature blocks."""
    
    class TemplateType(models.TextChoices):
        STANDARD = 'standard', _('Standard Contract')
        NDA = 'nda', _('Non-Disclosure Agreement')
        EMPLOYMENT = 'employment', _('Employment Agreement')
        SERVICE = 'service', _('Service Agreement')
        PARTNERSHIP = 'partnership', _('Partnership Agreement')
        CUSTOM = 'custom', _('Custom Template')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='contract_templates',
        verbose_name=_('Organization')
    )
    name = models.CharField(max_length=255, verbose_name=_('Template Name'))
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        default=TemplateType.STANDARD,
        verbose_name=_('Template Type')
    )
    
    # Template content
    content = models.TextField(verbose_name=_('Template Content'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    
    # Placeholders configuration
    placeholders = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Placeholders'),
        help_text=_('List of placeholder fields in the template')
    )
    
    # Signature blocks configuration
    signature_blocks = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Signature Blocks'),
        help_text=_('Configuration for signature blocks')
    )
    
    # Metadata
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    version = models.PositiveIntegerField(default=1, verbose_name=_('Version'))
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='created_templates',
        verbose_name=_('Created By')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'contract_templates'
        verbose_name = _('Contract Template')
        verbose_name_plural = _('Contract Templates')
        ordering = ['-created_at']
        unique_together = ['organization', 'name', 'version']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['template_type']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version}"
    
    def create_new_version(self, new_content=None):
        """Create a new version of this template."""
        new_template = ContractTemplate(
            organization=self.organization,
            name=self.name,
            template_type=self.template_type,
            content=new_content or self.content,
            description=self.description,
            placeholders=self.placeholders,
            signature_blocks=self.signature_blocks,
            created_by=self.created_by,
            version=self.version + 1
        )
        new_template.save()
        return new_template


class LegalReferenceLibrary(SafeDeleteModel):
    """Authoritative legal reference library for grounding LLM outputs."""
    
    class ReferenceType(models.TextChoices):
        STATUTE = 'statute', _('Statute')
        REGULATION = 'regulation', _('Regulation')
        CASE_LAW = 'case_law', _('Case Law')
        GUIDELINE = 'guideline', _('Guideline')
        FORM = 'form', _('Standard Form')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    state = models.CharField(max_length=100, verbose_name=_('State/Jurisdiction'))
    title = models.CharField(max_length=500, verbose_name=_('Title'))
    citation = models.CharField(max_length=200, blank=True, verbose_name=_('Citation'))
    url = models.URLField(verbose_name=_('Source URL'))
    
    # Content and metadata
    content_type = models.CharField(
        max_length=20,
        choices=ReferenceType.choices,
        default=ReferenceType.STATUTE,
        verbose_name=_('Content Type')
    )
    format = models.CharField(
        max_length=10,
        choices=[
            ('html', 'HTML'),
            ('pdf', 'PDF'),
            ('text', 'Text'),
            ('portal', 'Web Portal'),
        ],
        default='html',
        verbose_name=_('Format')
    )
    
    # Topics and categorization
    topics = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Topics'),
        help_text=_('List of relevant topics: formation, operating_agreements, etc.')
    )
    
    # Content excerpt (for search and display)
    excerpt = models.TextField(blank=True, verbose_name=_('Content Excerpt'))
    
    # Effective dates
    effective_date = models.DateField(null=True, blank=True, verbose_name=_('Effective Date'))
    last_updated = models.DateField(auto_now=True, verbose_name=_('Last Updated'))
    
    # Metadata
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'legal_references'
        verbose_name = _('Legal Reference')
        verbose_name_plural = _('Legal References')
        ordering = ['state', 'title']
        indexes = [
            models.Index(fields=['state', 'content_type']),
            models.Index(fields=['topics']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.state} - {self.title}"


class Contract(SafeDeleteModel):
    """Main contract model with signing workflow."""
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='contracts',
        verbose_name=_('Organization')
    )
    
    # Contract identification
    title = models.CharField(max_length=255, verbose_name=_('Contract Title'))
    contract_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Contract Number')
    )
    
    # Source (template or upload)
    template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_contracts',
        verbose_name=_('Source Template')
    )
    
    # Content storage
    content = models.TextField(verbose_name=_('Contract Content'))
    final_content = models.TextField(blank=True, verbose_name=_('Final Signed Content'))
    
    # For uploaded PDFs
    original_pdf = models.FileField(
        upload_to='contracts/original/',
        null=True,
        blank=True,
        verbose_name=_('Original PDF')
    )
    pdf_overlay_schema = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('PDF Overlay Schema'),
        help_text=_('Field positions and metadata for PDF overlays')
    )
    
    # Status and workflow
    status = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.name.title()) for tag in ContractStatus],
        default=ContractStatus.DRAFT.value,
        verbose_name=_('Contract Status')
    )
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Sent At'))
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Expires At'))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Completed At'))
    
    # Creator and metadata
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='created_contracts',
        verbose_name=_('Created By')
    )
    
    # LLM usage tracking
    llm_usage_count = models.PositiveIntegerField(default=0, verbose_name=_('LLM Usage Count'))
    last_llm_usage = models.DateTimeField(null=True, blank=True, verbose_name=_('Last LLM Usage'))
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Metadata'))
    
    class Meta:
        db_table = 'contracts'
        verbose_name = _('Contract')
        verbose_name_plural = _('Contracts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['contract_number']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.contract_number})"
    
    def clean(self):
        """Validate contract data."""
        if not self.contract_number:
            # Generate contract number if not provided
            self.contract_number = self.generate_contract_number()
    
    def generate_contract_number(self):
        """Generate unique contract number."""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        org_prefix = self.organization.name[:3].upper() if self.organization else 'DOC'
        return f"{org_prefix}-{timestamp}-{uuid.uuid4().hex[:8].upper()}"
    
    def send_for_signature(self):
        """Send contract for signature."""
        if self.status != ContractStatus.DRAFT.value:
            raise ValidationError("Only draft contracts can be sent for signature")
        
        # Validate all signature fields are assigned
        unassigned_fields = self.signature_fields.filter(assigned_to__isnull=True)
        if unassigned_fields.exists():
            raise ValidationError("All signature fields must be assigned before sending")
        
        self.status = ContractStatus.SENT.value
        self.sent_at = timezone.now()
        
        # Set expiration (default 30 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        
        # Generate signing tokens
        for field in self.signature_fields.all():
            field.generate_signing_token()
        
        self.save()
        
        # TODO: Send notification emails
        return True
    
    def is_expired(self):
        """Check if contract has expired."""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False
    
    def get_signing_url(self, signature_field):
        """Get signing URL for a specific signature field."""
        if not signature_field.signing_token:
            signature_field.generate_signing_token()
            signature_field.save()
        
        return f"/sign/{signature_field.signing_token}"


class ContractParty(SafeDeleteModel):
    """Parties involved in a contract."""
    
    class PartyType(models.TextChoices):
        INTERNAL = 'internal', _('Internal Party')
        EXTERNAL = 'external', _('External Party')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='parties',
        verbose_name=_('Contract')
    )
    party_type = models.CharField(
        max_length=20,
        choices=PartyType.choices,
        verbose_name=_('Party Type')
    )
    
    # Party identification
    name = models.CharField(max_length=255, verbose_name=_('Party Name'))
    email = models.EmailField(verbose_name=_('Email'))
    
    # For internal parties - link to org chart entities
    internal_user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Internal User')
    )
    org_chart_entity = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Org Chart Entity'),
        help_text=_('Reference to organization chart entity')
    )
    
    # Contact information
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('Phone'))
    address = models.TextField(blank=True, verbose_name=_('Address'))
    
    # Role in contract
    role = models.CharField(max_length=100, verbose_name=_('Role in Contract'))
    
    # Signing information
    signed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Signed At'))
    signing_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('Signing IP'))
    
    class Meta:
        db_table = 'contract_parties'
        verbose_name = _('Contract Party')
        verbose_name_plural = _('Contract Parties')
        ordering = ['party_type', 'name']
        indexes = [
            models.Index(fields=['contract', 'party_type']),
            models.Index(fields=['email']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.role}) - {self.contract.title}"


class SignatureField(SafeDeleteModel):
    """Signature fields within a contract."""
    
    class FieldType(models.TextChoices):
        SIGNATURE = 'signature', _('Signature')
        INITIAL = 'initial', _('Initial')
        DATE = 'date', _('Date')
        TEXT = 'text', _('Text')
        CHECKBOX = 'checkbox', _('Checkbox')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='signature_fields',
        verbose_name=_('Contract')
    )
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices,
        default=FieldType.SIGNATURE,
        verbose_name=_('Field Type')
    )
    
    # Field identification
    label = models.CharField(max_length=255, verbose_name=_('Field Label'))
    required = models.BooleanField(default=True, verbose_name=_('Required'))
    
    # Position and display (for PDF overlays)
    page_number = models.PositiveIntegerField(default=1, verbose_name=_('Page Number'))
    x_position = models.FloatField(verbose_name=_('X Position'))
    y_position = models.FloatField(verbose_name=_('Y Position'))
    width = models.FloatField(default=200, verbose_name=_('Width'))
    height = models.FloatField(default=50, verbose_name=_('Height'))
    
    # Assignment
    assigned_to = models.ForeignKey(
        ContractParty,
        on_delete=models.CASCADE,
        related_name='signature_fields',
        verbose_name=_('Assigned To')
    )
    
    # Signing data
    signing_token = EncryptedCharField(
        max_length=100,
        blank=True,
        verbose_name=_('Signing Token')
    )
    signed_data = EncryptedTextField(blank=True, verbose_name=_('Signed Data'))
    signed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Signed At'))
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Metadata'))
    
    class Meta:
        db_table = 'signature_fields'
        verbose_name = _('Signature Field')
        verbose_name_plural = _('Signature Fields')
        ordering = ['page_number', 'y_position', 'x_position']
        indexes = [
            models.Index(fields=['contract', 'assigned_to']),
            models.Index(fields=['signing_token']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.label} - {self.assigned_to.name}"
    
    def generate_signing_token(self):
        """Generate secure signing token."""
        import secrets
        self.signing_token = secrets.token_urlsafe(32)
        return self.signing_token
    
    def is_signed(self):
        """Check if field has been signed."""
        return bool(self.signed_data and self.signed_at)
    
    def sign(self, data, ip_address=None):
        """Sign the field with provided data."""
        if self.is_signed():
            raise ValidationError("Field has already been signed")
        
        self.signed_data = data
        self.signed_at = timezone.now()
        self.save()
        
        # Update party signing information if this is a signature field
        if self.field_type == FieldType.SIGNATURE:
            self.assigned_to.signed_at = timezone.now()
            self.assigned_to.signing_ip = ip_address
            self.assigned_to.save()
        
        # Check if contract is fully signed
        self.contract.check_completion()


class ContractEvent(SafeDeleteModel):
    """Audit trail for contract events."""
    
    class EventType(models.TextChoices):
        CREATED = 'created', _('Created')
        SENT = 'sent', _('Sent for Signature')
        VIEWED = 'viewed', _('Viewed')
        SIGNED = 'signed', _('Signed')
        COMPLETED = 'completed', _('Completed')
        EXPIRED = 'expired', _('Expired')
        DECLINED = 'declined', _('Declined')
        CANCELLED = 'cancelled', _('Cancelled')
        MODIFIED = 'modified', _('Modified')
        AI_GENERATED = 'ai_generated', _('AI Generated')
        AI_EDITED = 'ai_edited', _('AI Edited')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name=_('Contract')
    )
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        verbose_name=_('Event Type')
    )
    
    # Event details
    description = models.TextField(verbose_name=_('Event Description'))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Event Metadata'))
    
    # Actor information
    actor = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Actor')
    )
    actor_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('Actor IP'))
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'contract_events'
        verbose_name = _('Contract Event')
        verbose_name_plural = _('Contract Events')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contract', 'event_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.contract.title} - {self.get_event_type_display()}"

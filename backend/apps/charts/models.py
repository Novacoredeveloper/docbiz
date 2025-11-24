from django.db import models
from django.core.exceptions import ValidationError
from safedelete.models import SafeDeleteModel
from django.utils.translation import gettext_lazy as _
import uuid
import json
from django.contrib.postgres.fields import ArrayField


class OrgChart(SafeDeleteModel):
    """
    Single organizational chart per organization (MVP constraint).
    This is the centerpoint for modeling corporate structures.
    """
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.OneToOneField(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='org_chart',
        verbose_name=_('Organization')
    )
    
    # Chart data stored as JSON for flexibility
    data = models.JSONField(
        default=dict,
        verbose_name=_('Chart Data'),
        help_text=_('Structured JSON containing companies, persons, trusts, groups, and notes')
    )
    
    # Versioning and metadata
    version = models.PositiveIntegerField(default=1, verbose_name=_('Version'))
    last_modified_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Last Modified By')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'org_charts'
        verbose_name = _('Organizational Chart')
        verbose_name_plural = _('Organizational Charts')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['organization']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"Org Chart - {self.organization.name}"
    
    def clean(self):
        """Validate chart data structure."""
        if self.data:
            self._validate_chart_data()
    
    def _validate_chart_data(self):
        """Validate the structure of chart JSON data."""
        required_sections = ['companies', 'persons', 'trusts', 'groups', 'notes']
        
        for section in required_sections:
            if section not in self.data:
                self.data[section] = []
            
            if not isinstance(self.data[section], list):
                raise ValidationError(f"'{section}' must be a list")
    
    def get_companies(self):
        """Get all companies from chart data."""
        return self.data.get('companies', [])
    
    def get_persons(self):
        """Get all persons from chart data."""
        return self.data.get('persons', [])
    
    def get_trusts(self):
        """Get all trusts from chart data."""
        return self.data.get('trusts', [])
    
    def get_groups(self):
        """Get all groups from chart data."""
        return self.data.get('groups', [])
    
    def get_notes(self):
        """Get all notes from chart data."""
        return self.data.get('notes', [])
    
    def add_company(self, company_data):
        """Add a company to the chart."""
        companies = self.get_companies()
        
        # Generate ID if not provided
        if 'id' not in company_data:
            company_data['id'] = f"company_{uuid.uuid4().hex[:8]}"
        
        companies.append(company_data)
        self.data['companies'] = companies
        self.save()
        
        return company_data['id']
    
    def add_person(self, person_data):
        """Add a person to the chart."""
        persons = self.get_persons()
        
        if 'id' not in person_data:
            person_data['id'] = f"person_{uuid.uuid4().hex[:8]}"
        
        persons.append(person_data)
        self.data['persons'] = persons
        self.save()
        
        return person_data['id']
    
    def add_trust(self, trust_data):
        """Add a trust to the chart."""
        trusts = self.get_trusts()
        
        if 'id' not in trust_data:
            trust_data['id'] = f"trust_{uuid.uuid4().hex[:8]}"
        
        trusts.append(trust_data)
        self.data['trusts'] = trusts
        self.save()
        
        return trust_data['id']
    
    def add_connection(self, source_id, target_id, connection_type, metadata=None):
        """Add a connection between entities."""
        connections = self.data.get('connections', [])
        
        connection = {
            'id': f"conn_{uuid.uuid4().hex[:8]}",
            'source': source_id,
            'target': target_id,
            'type': connection_type,
            'metadata': metadata or {}
        }
        
        connections.append(connection)
        self.data['connections'] = connections
        self.save()
        
        return connection['id']
    
    def validate_connection(self, source_id, target_id, connection_type):
        """Validate if a connection is allowed based on business rules."""
        source_type = self._get_entity_type(source_id)
        target_type = self._get_entity_type(target_id)
        
        # Connection rules from specification
        allowed_connections = {
            'company': ['company', 'person', 'trust'],
            'person': ['company', 'trust'],
            'trust': ['company', 'person']
        }
        
        if (source_type in allowed_connections and 
            target_type in allowed_connections[source_type]):
            
            # Specific role validation for person->trust
            if source_type == 'person' and target_type == 'trust':
                valid_roles = ['grantor', 'beneficiary', 'manager', 'trustee']
                connection_data = self._get_connection_data(connection_type)
                if connection_data.get('role') not in valid_roles:
                    raise ValidationError(
                        f"Person to Trust connection must have a valid role: {valid_roles}"
                    )
            
            return True
        
        raise ValidationError(
            f"Connection from {source_type} to {target_type} is not allowed"
        )
    
    def _get_entity_type(self, entity_id):
        """Get the type of an entity by ID."""
        for entity_type in ['companies', 'persons', 'trusts', 'groups']:
            entities = self.data.get(entity_type, [])
            for entity in entities:
                if entity.get('id') == entity_id:
                    return entity_type[:-1]  # Remove 's' for singular
        raise ValidationError(f"Entity with ID {entity_id} not found")
    
    def _get_connection_data(self, connection_type):
        """Extract connection data from connection type string."""
        # connection_type format: "role:beneficiary" or just "connection"
        if ':' in connection_type:
            role_part, value = connection_type.split(':', 1)
            if role_part == 'role':
                return {'role': value}
        return {}


class ChartEntityLink(SafeDeleteModel):
    """
    Links from chart entities to other system modules (tax docs, licensing, payments, contracts).
    """
    
    class LinkType(models.TextChoices):
        TAX_DOCS = 'tax_docs', _('Tax Documents')
        LICENSING = 'licensing', _('Licensing')
        PAYMENTS = 'payments', _('Payments')
        CONTRACTS = 'contracts', _('Contracts')
        DOCUMENTS = 'documents', _('Documents')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    org_chart = models.ForeignKey(
        OrgChart,
        on_delete=models.CASCADE,
        related_name='entity_links',
        verbose_name=_('Organizational Chart')
    )
    
    # Reference to entity in the chart
    entity_id = models.CharField(max_length=100, verbose_name=_('Entity ID'))
    entity_type = models.CharField(
        max_length=20,
        choices=[
            ('company', _('Company')),
            ('person', _('Person')),
            ('trust', _('Trust')),
            ('group', _('Group')),
        ],
        verbose_name=_('Entity Type')
    )
    
    # Link details
    link_type = models.CharField(
        max_length=20,
        choices=LinkType.choices,
        verbose_name=_('Link Type')
    )
    target_id = models.CharField(
        max_length=100,
        verbose_name=_('Target ID'),
        help_text=_('ID of the linked resource in the target system')
    )
    
    # Metadata
    title = models.CharField(max_length=255, verbose_name=_('Link Title'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Metadata'))
    
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name=_('Created By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chart_entity_links'
        verbose_name = _('Chart Entity Link')
        verbose_name_plural = _('Chart Entity Links')
        ordering = ['entity_type', 'entity_id', 'link_type']
        indexes = [
            models.Index(fields=['org_chart', 'entity_id']),
            models.Index(fields=['link_type', 'target_id']),
            models.Index(fields=['uuid']),
        ]
        unique_together = ['org_chart', 'entity_id', 'link_type', 'target_id']
    
    def __str__(self):
        return f"{self.entity_type}:{self.entity_id} -> {self.get_link_type_display()}:{self.target_id}"


class ChartAuditLog(SafeDeleteModel):
    """
    Audit log for chart modifications and operations.
    """
    
    class ActionType(models.TextChoices):
        CREATE = 'create', _('Create')
        UPDATE = 'update', _('Update')
        DELETE = 'delete', _('Delete')
        CONNECT = 'connect', _('Connect')
        DISCONNECT = 'disconnect', _('Disconnect')
        IMPORT = 'import', _('Import')
        EXPORT = 'export', _('Export')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    org_chart = models.ForeignKey(
        OrgChart,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name=_('Organizational Chart')
    )
    
    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        verbose_name=_('Action Type')
    )
    
    # Entity information
    entity_type = models.CharField(
        max_length=20,
        choices=[
            ('company', _('Company')),
            ('person', _('Person')),
            ('trust', _('Trust')),
            ('group', _('Group')),
            ('note', _('Note')),
            ('connection', _('Connection')),
            ('chart', _('Entire Chart')),
        ],
        verbose_name=_('Entity Type')
    )
    entity_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Entity ID')
    )
    
    # Change details
    changes = models.JSONField(
        default=dict,
        verbose_name=_('Changes'),
        help_text=_('Detailed information about what was changed')
    )
    
    # Actor information
    actor = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name=_('Actor')
    )
    actor_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('Actor IP Address')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chart_audit_logs'
        verbose_name = _('Chart Audit Log')
        verbose_name_plural = _('Chart Audit Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['org_chart', 'created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.get_action_type_display()} {self.entity_type} {self.entity_id} by {self.actor.email}"


# Supporting modules (simplified for MVP)

class TaxDocument(SafeDeleteModel):
    """Tax documents metadata for companies."""
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='tax_documents',
        verbose_name=_('Organization')
    )
    
    # Reference to chart entity
    entity_id = models.CharField(max_length=100, verbose_name=_('Entity ID'))
    entity_type = models.CharField(
        max_length=20,
        default='company',
        verbose_name=_('Entity Type')
    )
    
    # Document metadata
    document_type = models.CharField(
        max_length=50,
        choices=[
            ('corporate_tax', _('Corporate Tax Return')),
            ('sales_tax', _('Sales Tax Return')),
            ('payroll_tax', _('Payroll Tax Return')),
            ('property_tax', _('Property Tax Statement')),
            ('other', _('Other Tax Document')),
        ],
        verbose_name=_('Document Type')
    )
    
    title = models.CharField(max_length=255, verbose_name=_('Document Title'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    
    # Filing information
    tax_year = models.PositiveIntegerField(verbose_name=_('Tax Year'))
    filing_date = models.DateField(null=True, blank=True, verbose_name=_('Filing Date'))
    due_date = models.DateField(null=True, blank=True, verbose_name=_('Due Date'))
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', _('Draft')),
            ('filed', _('Filed')),
            ('approved', _('Approved')),
            ('rejected', _('Rejected')),
            ('amended', _('Amended')),
        ],
        default='draft',
        verbose_name=_('Status')
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Metadata'))
    
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name=_('Created By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tax_documents'
        verbose_name = _('Tax Document')
        verbose_name_plural = _('Tax Documents')
        ordering = ['-tax_year', '-filing_date']
        indexes = [
            models.Index(fields=['organization', 'entity_id']),
            models.Index(fields=['tax_year', 'status']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.document_type} - {self.entity_id} ({self.tax_year})"


class License(SafeDeleteModel):
    """Licensing metadata for companies."""
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='licenses',
        verbose_name=_('Organization')
    )
    
    # Reference to chart entity
    entity_id = models.CharField(max_length=100, verbose_name=_('Entity ID'))
    
    # License information
    license_type = models.CharField(max_length=100, verbose_name=_('License Type'))
    license_number = models.CharField(max_length=100, verbose_name=_('License Number'))
    issuing_authority = models.CharField(max_length=255, verbose_name=_('Issuing Authority'))
    
    # Dates
    issue_date = models.DateField(verbose_name=_('Issue Date'))
    expiration_date = models.DateField(verbose_name=_('Expiration Date'))
    renewal_date = models.DateField(null=True, blank=True, verbose_name=_('Renewal Date'))
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', _('Active')),
            ('expired', _('Expired')),
            ('suspended', _('Suspended')),
            ('revoked', _('Revoked')),
            ('pending', _('Pending Renewal')),
        ],
        default='active',
        verbose_name=_('Status')
    )
    
    # Additional details
    description = models.TextField(blank=True, verbose_name=_('Description'))
    restrictions = models.TextField(blank=True, verbose_name=_('Restrictions'))
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Metadata'))
    
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name=_('Created By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'licenses'
        verbose_name = _('License')
        verbose_name_plural = _('Licenses')
        ordering = ['expiration_date', 'entity_id']
        indexes = [
            models.Index(fields=['organization', 'entity_id']),
            models.Index(fields=['license_type', 'status']),
            models.Index(fields=['expiration_date']),
            models.Index(fields=['uuid']),
        ]
        unique_together = ['organization', 'entity_id', 'license_number']
    
    def __str__(self):
        return f"{self.license_type} - {self.entity_id} ({self.license_number})"
    
    def is_expired(self):
        """Check if license is expired."""
        from django.utils import timezone
        return self.expiration_date < timezone.now().date() if self.expiration_date else False
    
    def days_until_expiration(self):
        """Calculate days until expiration."""
        from django.utils import timezone
        if self.expiration_date:
            delta = self.expiration_date - timezone.now().date()
            return delta.days
        return None


class PaymentRecord(SafeDeleteModel):
    """Payment metadata for companies."""
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='payment_records',
        verbose_name=_('Organization')
    )
    
    # Reference to chart entity
    entity_id = models.CharField(max_length=100, verbose_name=_('Entity ID'))
    
    # Payment information
    payment_type = models.CharField(
        max_length=50,
        choices=[
            ('invoice', _('Invoice Payment')),
            ('recurring', _('Recurring Payment')),
            ('tax', _('Tax Payment')),
            ('license_fee', _('License Fee')),
            ('other', _('Other Payment')),
        ],
        verbose_name=_('Payment Type')
    )
    
    description = models.CharField(max_length=255, verbose_name=_('Description'))
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Amount')
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_('Currency')
    )
    
    # Dates
    payment_date = models.DateField(verbose_name=_('Payment Date'))
    due_date = models.DateField(null=True, blank=True, verbose_name=_('Due Date'))
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('paid', _('Paid')),
            ('overdue', _('Overdue')),
            ('cancelled', _('Cancelled')),
            ('failed', _('Failed')),
        ],
        default='pending',
        verbose_name=_('Status')
    )
    
    # Reference numbers
    invoice_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Invoice Number')
    )
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Transaction ID')
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Metadata'))
    
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name=_('Created By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_records'
        verbose_name = _('Payment Record')
        verbose_name_plural = _('Payment Records')
        ordering = ['-payment_date', 'entity_id']
        indexes = [
            models.Index(fields=['organization', 'entity_id']),
            models.Index(fields=['payment_type', 'status']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.payment_type} - {self.entity_id} - {self.amount} {self.currency}"
    
    def is_overdue(self):
        """Check if payment is overdue."""
        from django.utils import timezone
        return (self.due_date and 
                self.due_date < timezone.now().date() and 
                self.status == 'pending')
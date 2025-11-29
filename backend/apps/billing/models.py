from django.db import models
from django.core.exceptions import ValidationError
from safedelete.models import SafeDeleteModel
from encrypted_model_fields.fields import EncryptedCharField
from django.utils.translation import gettext_lazy as _
import uuid
from decimal import Decimal
from django.utils import timezone


class SubscriptionPlan(SafeDeleteModel):
    """
    Subscription plans with tier-based features and limits.
    """
    
    class TierType(models.TextChoices):
        FREE = 'free', _('Free')
        BASIC = 'basic', _('Basic')
        BUSINESS = 'business', _('Business')
        ENTERPRISE = 'enterprise', _('Enterprise')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100, verbose_name=_('Plan Name'))
    tier = models.CharField(
        max_length=20,
        choices=TierType.choices,
        unique=True,
        verbose_name=_('Tier')
    )
    
    # Pricing
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Monthly Price (USD)')
    )
    annual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Annual Price (USD)'),
        help_text=_('20% discount applied if provided')
    )
    
    # Feature limits
    max_users = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Maximum Users'),
        help_text=_('Null means unlimited')
    )
    max_entities = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Maximum Chart Entities'),
        help_text=_('Null means unlimited')
    )
    max_contracts_per_month = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Maximum Contracts/Month'),
        help_text=_('Null means unlimited')
    )
    
    # LLM limits
    monthly_llm_tokens = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_('Monthly LLM Tokens')
    )
    
    # Feature flags
    external_signing = models.BooleanField(
        default=False,
        verbose_name=_('External Signing')
    )
    pdf_upload = models.BooleanField(
        default=False,
        verbose_name=_('PDF Upload')
    )
    authoritative_sources = models.BooleanField(
        default=False,
        verbose_name=_('All Authoritative Sources')
    )
    api_access = models.BooleanField(
        default=False,
        verbose_name=_('API Access')
    )
    custom_workflows = models.BooleanField(
        default=False,
        verbose_name=_('Custom Workflows')
    )
    
    # Support levels
    support_level = models.CharField(
        max_length=20,
        choices=[
            ('community', _('Community Support')),
            ('standard', _('Standard Support')),
            ('priority', _('Priority Support')),
            ('dedicated', _('Dedicated Support')),
        ],
        default='community',
        verbose_name=_('Support Level')
    )
    
    # Metadata
    description = models.TextField(blank=True, verbose_name=_('Description'))
    features = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Feature List')
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscription_plans'
        verbose_name = _('Subscription Plan')
        verbose_name_plural = _('Subscription Plans')
        ordering = ['monthly_price']
        indexes = [
            models.Index(fields=['tier', 'is_active']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.name} (${self.monthly_price}/month)"
    
    def clean(self):
        """Validate plan configuration."""
        # Ensure annual price is less than monthly * 12
        if self.annual_price and self.monthly_price:
            expected_annual = self.monthly_price * 12 * Decimal('0.8')  # 20% discount
            if self.annual_price > expected_annual:
                raise ValidationError(
                    f"Annual price should be at least 20% cheaper than monthly. "
                    f"Expected: ${expected_annual:.2f}, Provided: ${self.annual_price:.2f}"
                )
    
    def get_annual_savings(self):
        """Calculate annual savings percentage."""
        if self.annual_price and self.monthly_price:
            monthly_total = self.monthly_price * 12
            savings = monthly_total - self.annual_price
            return (savings / monthly_total) * 100
        return 0
    
    def can_upgrade_to(self, target_plan):
        """Check if this plan can upgrade to target plan."""
        price_order = {
            self.TierType.FREE: 0,
            self.TierType.BASIC: 1,
            self.TierType.BUSINESS: 2,
            self.TierType.ENTERPRISE: 3
        }
        return price_order[target_plan.tier] > price_order[self.tier]


class OrganizationSubscription(SafeDeleteModel):
    """
    Organization's current subscription and billing information.
    """
    
    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', _('Monthly')
        ANNUAL = 'annual', _('Annual')
    
    class StatusType(models.TextChoices):
        ACTIVE = 'active', _('Active')
        TRIAL = 'trial', _('Trial')
        PAST_DUE = 'past_due', _('Past Due')
        CANCELLED = 'cancelled', _('Cancelled')
        SUSPENDED = 'suspended', _('Suspended')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.OneToOneField(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name=_('Organization')
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name=_('Subscription Plan')
    )
    
    # Billing details
    billing_cycle = models.CharField(
        max_length=10,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
        verbose_name=_('Billing Cycle')
    )
    status = models.CharField(
        max_length=20,
        choices=StatusType.choices,
        default=StatusType.ACTIVE,
        verbose_name=_('Status')
    )
    
    # Pricing
    current_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Current Price')
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_('Currency')
    )
    
    # Dates
    start_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Start Date')
    )
    trial_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Trial End Date')
    )
    current_period_start = models.DateTimeField(
        verbose_name=_('Current Period Start')
    )
    current_period_end = models.DateTimeField(
        verbose_name=_('Current Period End')
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Cancelled At')
    )
    
    # Usage tracking
    users_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Current Users Count')
    )
    entities_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Current Entities Count')
    )
    contracts_used_this_month = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Contracts Used This Month')
    )
    llm_tokens_used_this_month = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_('LLM Tokens Used This Month')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'organization_subscriptions'
        verbose_name = _('Organization Subscription')
        verbose_name_plural = _('Organization Subscriptions')
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['current_period_end']),
            models.Index(fields=['status']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.plan.name} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Set period dates if not set."""
        if not self.current_period_start:
            self.current_period_start = timezone.now()
        
        if not self.current_period_end:
            if self.billing_cycle == self.BillingCycle.MONTHLY:
                self.current_period_end = self.current_period_start + timedelta(days=30)
            else:
                self.current_period_end = self.current_period_start + timedelta(days=365)
        
        # Set current price based on billing cycle
        if not self.current_price:
            if self.billing_cycle == self.BillingCycle.MONTHLY:
                self.current_price = self.plan.monthly_price
            else:
                self.current_price = self.plan.annual_price or self.plan.monthly_price * 12 * Decimal('0.8')
        
        super().save(*args, **kwargs)
    
    def is_trial(self):
        """Check if subscription is in trial period."""
        return (self.status == self.StatusType.TRIAL and 
                self.trial_end_date and 
                timezone.now() < self.trial_end_date)
    
    def is_active(self):
        """Check if subscription is active."""
        return self.status in [self.StatusType.ACTIVE, self.StatusType.TRIAL]
    
    def days_until_renewal(self):
        """Calculate days until subscription renewal."""
        delta = self.current_period_end - timezone.now()
        return max(0, delta.days)
    
    def can_add_user(self):
        """Check if organization can add another user."""
        if not self.plan.max_users:
            return True
        return self.users_count < self.plan.max_users
    
    def can_add_entity(self):
        """Check if organization can add another entity."""
        if not self.plan.max_entities:
            return True
        return self.entities_count < self.plan.max_entities
    
    def can_create_contract(self):
        """Check if organization can create another contract this month."""
        if not self.plan.max_contracts_per_month:
            return True
        return self.contracts_used_this_month < self.plan.max_contracts_per_month
    
    def has_feature(self, feature):
        """Check if subscription includes a specific feature."""
        feature_map = {
            'external_signing': self.plan.external_signing,
            'pdf_upload': self.plan.pdf_upload,
            'authoritative_sources': self.plan.authoritative_sources,
            'api_access': self.plan.api_access,
            'custom_workflows': self.plan.custom_workflows,
        }
        return feature_map.get(feature, False)
    
    def update_usage_metrics(self):
        """Update usage metrics from actual data."""
        from apps.organizations.models import Organization
        from apps.contracts.models import Contract
        from apps.llm.models import LLMUsage
        
        # Update users count
        self.users_count = self.organization.users.filter(is_active=True).count()
        
        # Update entities count (from org chart)
        if hasattr(self.organization, 'org_chart'):
            chart_data = self.organization.org_chart.data
            self.entities_count = (
                len(chart_data.get('companies', [])) +
                len(chart_data.get('persons', [])) +
                len(chart_data.get('trusts', [])) +
                len(chart_data.get('groups', []))
            )
        
        # Update contracts used this month
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        self.contracts_used_this_month = Contract.objects.filter(
            organization=self.organization,
            created_at__gte=start_of_month
        ).count()
        
        # Update LLM tokens used this month
        self.llm_tokens_used_this_month = LLMUsage.objects.filter(
            organization=self.organization,
            created_at__gte=start_of_month
        ).aggregate(total_tokens=models.Sum('tokens_total'))['total_tokens'] or 0
        
        self.save()


class Invoice(SafeDeleteModel):
    """
    Billing invoices for organizations.
    """
    
    class StatusType(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        OPEN = 'open', _('Open')
        PAID = 'paid', _('Paid')
        VOID = 'void', _('Void')
        UNCOLLECTIBLE = 'uncollectible', _('Uncollectible')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_('Organization')
    )
    subscription = models.ForeignKey(
        OrganizationSubscription,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name=_('Subscription')
    )
    
    # Invoice identification
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Invoice Number')
    )
    status = models.CharField(
        max_length=20,
        choices=StatusType.choices,
        default=StatusType.DRAFT,
        verbose_name=_('Status')
    )
    
    # Amounts
    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Amount Due')
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Amount Paid')
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Tax Amount')
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Total Amount')
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name=_('Currency')
    )
    
    # Dates
    invoice_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Invoice Date')
    )
    due_date = models.DateTimeField(
        verbose_name=_('Due Date')
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Paid At')
    )
    
    # Line items
    line_items = models.JSONField(
        default=list,
        verbose_name=_('Line Items')
    )
    
    # Payment information
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Payment Method')
    )
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Transaction ID')
    )
    
    # Metadata
    notes = models.TextField(blank=True, verbose_name=_('Notes'))
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'invoices'
        verbose_name = _('Invoice')
        verbose_name_plural = _('Invoices')
        ordering = ['-invoice_date']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['due_date']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.organization.name}"
    
    def clean(self):
        """Validate invoice data."""
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        
        if not self.due_date:
            self.due_date = self.invoice_date + timedelta(days=30)
    
    def generate_invoice_number(self):
        """Generate unique invoice number."""
        timestamp = timezone.now().strftime('%Y%m%d')
        count = Invoice.objects.filter(
            invoice_date__date=timezone.now().date()
        ).count() + 1
        return f"INV-{timestamp}-{count:04d}"
    
    def is_overdue(self):
        """Check if invoice is overdue."""
        return (self.status == self.StatusType.OPEN and 
                timezone.now() > self.due_date)
    
    def mark_paid(self, payment_method, transaction_id, paid_amount=None):
        """Mark invoice as paid."""
        self.status = self.StatusType.PAID
        self.payment_method = payment_method
        self.transaction_id = transaction_id
        self.paid_at = timezone.now()
        
        if paid_amount:
            self.amount_paid = paid_amount
        else:
            self.amount_paid = self.total_amount
        
        self.save()


class PaymentMethod(SafeDeleteModel):
    """
    Payment methods for organizations.
    """
    
    class MethodType(models.TextChoices):
        CARD = 'card', _('Credit Card')
        BANK = 'bank', _('Bank Transfer')
        PAYPAL = 'paypal', _('PayPal')
        MANUAL = 'manual', _('Manual Payment')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='payment_methods',
        verbose_name=_('Organization')
    )
    
    method_type = models.CharField(
        max_length=20,
        choices=MethodType.choices,
        verbose_name=_('Method Type')
    )
    
    # Payment details (encrypted)
    last_four = models.CharField(
        max_length=4,
        blank=True,
        verbose_name=_('Last Four Digits')
    )
    brand = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Card/Bank Brand')
    )
    expiry_month = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Expiry Month')
    )
    expiry_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Expiry Year')
    )
    
    # Status
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Default Method')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active')
    )
    
    # Provider data
    provider_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Provider ID')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_methods'
        verbose_name = _('Payment Method')
        verbose_name_plural = _('Payment Methods')
        ordering = ['-is_default', 'created_at']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['method_type']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.get_method_type_display()} - {self.last_four} - {self.organization.name}"
    
    def clean(self):
        """Validate payment method data."""
        if self.is_default:
            # Ensure only one default method per organization
            existing_default = PaymentMethod.objects.filter(
                organization=self.organization,
                is_default=True,
                is_active=True
            ).exclude(pk=self.pk)
            if existing_default.exists():
                raise ValidationError('There can only be one default payment method per organization')


class BillingWebhook(SafeDeleteModel):
    """
    Webhook events from payment processors.
    """
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Webhook data
    processor = models.CharField(
        max_length=50,
        verbose_name=_('Payment Processor')
    )
    event_type = models.CharField(
        max_length=100,
        verbose_name=_('Event Type')
    )
    event_id = models.CharField(
        max_length=100,
        verbose_name=_('Event ID')
    )
    
    # Payload
    payload = models.JSONField(
        verbose_name=_('Webhook Payload')
    )
    
    # Processing status
    processed = models.BooleanField(
        default=False,
        verbose_name=_('Processed')
    )
    processing_error = models.TextField(
        blank=True,
        verbose_name=_('Processing Error')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Processed At')
    )
    
    class Meta:
        db_table = 'billing_webhooks'
        verbose_name = _('Billing Webhook')
        verbose_name_plural = _('Billing Webhooks')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['processor', 'event_type']),
            models.Index(fields=['processed']),
            models.Index(fields=['created_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.processor} - {self.event_type} - {self.event_id}"
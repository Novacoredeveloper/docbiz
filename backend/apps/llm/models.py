from django.db import models
from django.core.exceptions import ValidationError
from safedelete.models import SafeDeleteModel
from encrypted_model_fields.fields import EncryptedCharField
from django.utils.translation import gettext_lazy as _
import uuid
from decimal import Decimal


class LLMProvider(SafeDeleteModel):
    """
    Configuration for different LLM providers.
    """
    
    class ProviderType(models.TextChoices):
        OPENAI = 'openai', _('OpenAI')
        ANTHROPIC = 'anthropic', _('Anthropic')
        AZURE = 'azure', _('Azure OpenAI')
        GOOGLE = 'google', _('Google AI')
        CUSTOM = 'custom', _('Custom Endpoint')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100, verbose_name=_('Provider Name'))
    provider_type = models.CharField(
        max_length=20,
        choices=ProviderType.choices,
        verbose_name=_('Provider Type')
    )
    
    # API Configuration
    base_url = models.URLField(
        blank=True,
        verbose_name=_('Base URL'),
        help_text=_('Leave blank for default provider URLs')
    )
    api_key = EncryptedCharField(
        max_length=255,
        blank=True,
        verbose_name=_('API Key')
    )
    api_version = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('API Version')
    )
    
    # Rate limiting
    requests_per_minute = models.PositiveIntegerField(
        default=60,
        verbose_name=_('Requests per Minute')
    )
    tokens_per_minute = models.PositiveIntegerField(
        default=100000,
        verbose_name=_('Tokens per Minute')
    )
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    is_default = models.BooleanField(default=False, verbose_name=_('Default Provider'))
    
    # Metadata
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Provider Configuration')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'llm_providers'
        verbose_name = _('LLM Provider')
        verbose_name_plural = _('LLM Providers')
        ordering = ['name']
        indexes = [
            models.Index(fields=['provider_type', 'is_active']),
            models.Index(fields=['is_default']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"
    
    def clean(self):
        """Validate provider configuration."""
        if self.is_default:
            # Ensure only one default provider
            existing_default = LLMProvider.objects.filter(
                is_default=True, 
                is_active=True
            ).exclude(pk=self.pk)
            if existing_default.exists():
                raise ValidationError('There can only be one default LLM provider')
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class LLMModel(SafeDeleteModel):
    """
    Available LLM models with pricing and capabilities.
    """
    
    class ModelType(models.TextChoices):
        CHAT = 'chat', _('Chat Completion')
        COMPLETION = 'completion', _('Text Completion')
        EMBEDDING = 'embedding', _('Embeddings')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.CASCADE,
        related_name='models',
        verbose_name=_('Provider')
    )
    name = models.CharField(max_length=100, verbose_name=_('Model Name'))
    model_type = models.CharField(
        max_length=20,
        choices=ModelType.choices,
        default=ModelType.CHAT,
        verbose_name=_('Model Type')
    )
    
    # Model capabilities
    context_window = models.PositiveIntegerField(
        default=4096,
        verbose_name=_('Context Window'),
        help_text=_('Maximum context length in tokens')
    )
    max_output_tokens = models.PositiveIntegerField(
        default=1024,
        verbose_name=_('Max Output Tokens')
    )
    supports_functions = models.BooleanField(
        default=False,
        verbose_name=_('Supports Function Calling')
    )
    supports_vision = models.BooleanField(
        default=False,
        verbose_name=_('Supports Vision')
    )
    
    # Pricing (per 1K tokens)
    input_price = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name=_('Input Price per 1K tokens')
    )
    output_price = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name=_('Output Price per 1K tokens')
    )
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    is_default = models.BooleanField(default=False, verbose_name=_('Default Model'))
    
    # Metadata
    description = models.TextField(blank=True, verbose_name=_('Description'))
    capabilities = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Capabilities')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'llm_models'
        verbose_name = _('LLM Model')
        verbose_name_plural = _('LLM Models')
        ordering = ['provider', 'name']
        indexes = [
            models.Index(fields=['provider', 'is_active']),
            models.Index(fields=['model_type']),
            models.Index(fields=['is_default']),
            models.Index(fields=['uuid']),
        ]
        unique_together = ['provider', 'name']
    
    def __str__(self):
        return f"{self.provider.name} - {self.name}"
    
    def calculate_cost(self, input_tokens, output_tokens):
        """Calculate cost for token usage."""
        input_cost = (Decimal(input_tokens) / 1000) * self.input_price
        output_cost = (Decimal(output_tokens) / 1000) * self.output_price
        return input_cost + output_cost


class LLMUsage(SafeDeleteModel):
    """
    Comprehensive tracking of all LLM usage across the platform.
    """
    
    class FeatureType(models.TextChoices):
        CLAUSE_GENERATION = 'clause_gen', _('Clause Generation')
        CONTRACT_EDIT = 'edit', _('Contract Editing')
        CONTRACT_REVIEW = 'review', _('Contract Review')
        CLAUSE_SUGGESTION = 'suggestion', _('Clause Suggestion')
        LEGAL_RESEARCH = 'research', _('Legal Research')
        DOCUMENT_SUMMARY = 'summary', _('Document Summary')
        ENTITY_EXTRACTION = 'entity_extraction', _('Entity Extraction')
        COMPLIANCE_CHECK = 'compliance_check', _('Compliance Check')
        RISK_ASSESSMENT = 'risk_assessment', _('Risk Assessment')
    
    class StatusType(models.TextChoices):
        SUCCESS = 'success', _('Success')
        ERROR = 'error', _('Error')
        RATE_LIMITED = 'rate_limited', _('Rate Limited')
        QUOTA_EXCEEDED = 'quota_exceeded', _('Quota Exceeded')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='llm_usage',
        verbose_name=_('Organization')
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='llm_usage',
        verbose_name=_('User')
    )
    
    # LLM provider and model
    provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.CASCADE,
        related_name='usage',
        verbose_name=_('Provider')
    )
    model = models.ForeignKey(
        LLMModel,
        on_delete=models.CASCADE,
        related_name='usage',
        verbose_name=_('Model')
    )
    
    # Feature and context
    feature = models.CharField(
        max_length=30,
        choices=FeatureType.choices,
        verbose_name=_('Feature')
    )
    status = models.CharField(
        max_length=20,
        choices=StatusType.choices,
        default=StatusType.SUCCESS,
        verbose_name=_('Status')
    )
    
    # Token usage
    tokens_prompt = models.PositiveIntegerField(default=0, verbose_name=_('Prompt Tokens'))
    tokens_completion = models.PositiveIntegerField(default=0, verbose_name=_('Completion Tokens'))
    tokens_total = models.PositiveIntegerField(default=0, verbose_name=_('Total Tokens'))
    
    # Cost tracking
    cost_estimated = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name=_('Estimated Cost')
    )
    cost_calculated = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0,
        verbose_name=_('Calculated Cost')
    )
    
    # Request tracking
    provider_request_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Provider Request ID')
    )
    model_used = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Actual Model Used'),
        help_text=_('Model actually used by provider (may differ from requested)')
    )
    
    # Timing
    request_duration = models.FloatField(
        default=0,
        verbose_name=_('Request Duration (seconds)')
    )
    time_to_first_token = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Time to First Token (seconds)')
    )
    
    # Content (encrypted for privacy)
    input_context = models.TextField(
        blank=True,
        verbose_name=_('Input Context'),
        help_text=_('First 1000 characters of input')
    )
    generated_content = models.TextField(
        blank=True,
        verbose_name=_('Generated Content'),
        help_text=_('First 1000 characters of generated content')
    )
    
    # Error information
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message')
    )
    error_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Error Code')
    )
    
    # Related objects
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='llm_usage',
        verbose_name=_('Contract')
    )
    legal_references = models.ManyToManyField(
        'contracts.LegalReferenceLibrary',
        blank=True,
        verbose_name=_('Legal References Used')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'llm_usage'
        verbose_name = _('LLM Usage')
        verbose_name_plural = _('LLM Usage')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['user', 'feature']),
            models.Index(fields=['provider', 'model']),
            models.Index(fields=['feature', 'status']),
            models.Index(fields=['contract']),
            models.Index(fields=['created_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.feature} - {self.tokens_total} tokens"
    
    def save(self, *args, **kwargs):
        """Calculate totals and costs before saving."""
        # Calculate total tokens
        self.tokens_total = self.tokens_prompt + self.tokens_completion
        
        # Calculate cost based on model pricing
        if self.model and self.tokens_total > 0:
            self.cost_calculated = self.model.calculate_cost(
                self.tokens_prompt, 
                self.tokens_completion
            )
        
        # If estimated cost not set, use calculated cost
        if self.cost_estimated == 0 and self.cost_calculated > 0:
            self.cost_estimated = self.cost_calculated
        
        # Truncate content for storage
        if self.input_context and len(self.input_context) > 1000:
            self.input_context = self.input_context[:1000] + "..."
        if self.generated_content and len(self.generated_content) > 1000:
            self.generated_content = self.generated_content[:1000] + "..."
        
        super().save(*args, **kwargs)


class LLMQuota(SafeDeleteModel):
    """
    Token quotas for organizations based on subscription tiers.
    """
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.OneToOneField(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='llm_quota',
        verbose_name=_('Organization')
    )
    
    # Token limits
    monthly_token_limit = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Monthly Token Limit'),
        help_text=_('Null means unlimited')
    )
    tokens_used_current_month = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_('Tokens Used This Month')
    )
    
    # Request limits
    monthly_request_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Monthly Request Limit')
    )
    requests_used_current_month = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Requests Used This Month')
    )
    
    # Cost limits
    monthly_cost_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Monthly Cost Limit (USD)')
    )
    cost_used_current_month = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Cost Used This Month (USD)')
    )
    
    # Reset tracking
    last_reset_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Last Reset At')
    )
    next_reset_at = models.DateTimeField(
        verbose_name=_('Next Reset At')
    )
    
    # Override settings
    is_suspended = models.BooleanField(
        default=False,
        verbose_name=_('Suspended')
    )
    suspend_reason = models.TextField(
        blank=True,
        verbose_name=_('Suspend Reason')
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
        db_table = 'llm_quotas'
        verbose_name = _('LLM Quota')
        verbose_name_plural = _('LLM Quotas')
        indexes = [
            models.Index(fields=['organization']),
            models.Index(fields=['next_reset_at']),
            models.Index(fields=['is_suspended']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"Quota - {self.organization.name}"
    
    def save(self, *args, **kwargs):
        """Set next reset date if not set."""
        if not self.next_reset_at:
            from django.utils import timezone
            from datetime import timedelta
            
            # Set to first day of next month
            now = timezone.now()
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            
            self.next_reset_at = next_month
        
        super().save(*args, **kwargs)
    
    def reset_usage(self):
        """Reset monthly usage counters."""
        self.tokens_used_current_month = 0
        self.requests_used_current_month = 0
        self.cost_used_current_month = 0
        self.last_reset_at = timezone.now()
        
        # Set next reset to first day of next month
        now = timezone.now()
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        
        self.next_reset_at = next_month
        self.save()
    
    def can_make_request(self, estimated_tokens=0, estimated_cost=0):
        """Check if organization can make a new LLM request."""
        if self.is_suspended:
            return False, "LLM usage is suspended for this organization"
        
        # Check token limit
        if (self.monthly_token_limit and 
            self.tokens_used_current_month + estimated_tokens > self.monthly_token_limit):
            return False, "Monthly token limit exceeded"
        
        # Check request limit
        if (self.monthly_request_limit and 
            self.requests_used_current_month + 1 > self.monthly_request_limit):
            return False, "Monthly request limit exceeded"
        
        # Check cost limit
        if (self.monthly_cost_limit and 
            self.cost_used_current_month + estimated_cost > self.monthly_cost_limit):
            return False, "Monthly cost limit exceeded"
        
        return True, "OK"
    
    def record_usage(self, tokens_prompt, tokens_completion, cost):
        """Record usage and update counters."""
        self.tokens_used_current_month += tokens_prompt + tokens_completion
        self.requests_used_current_month += 1
        self.cost_used_current_month += cost
        self.save()


class LLMAnalytics(SafeDeleteModel):
    """
    Aggregated analytics for LLM usage reporting.
    """
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='llm_analytics',
        verbose_name=_('Organization')
    )
    
    # Time period
    period_start = models.DateTimeField(verbose_name=_('Period Start'))
    period_end = models.DateTimeField(verbose_name=_('Period End'))
    period_type = models.CharField(
        max_length=10,
        choices=[
            ('daily', _('Daily')),
            ('weekly', _('Weekly')),
            ('monthly', _('Monthly')),
        ],
        verbose_name=_('Period Type')
    )
    
    # Usage aggregates
    total_requests = models.PositiveIntegerField(default=0, verbose_name=_('Total Requests'))
    successful_requests = models.PositiveIntegerField(default=0, verbose_name=_('Successful Requests'))
    failed_requests = models.PositiveIntegerField(default=0, verbose_name=_('Failed Requests'))
    
    # Token aggregates
    total_tokens = models.PositiveBigIntegerField(default=0, verbose_name=_('Total Tokens'))
    prompt_tokens = models.PositiveBigIntegerField(default=0, verbose_name=_('Prompt Tokens'))
    completion_tokens = models.PositiveBigIntegerField(default=0, verbose_name=_('Completion Tokens'))
    
    # Cost aggregates
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Total Cost')
    )
    
    # Feature breakdown
    feature_breakdown = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Feature Breakdown')
    )
    
    # Provider breakdown
    provider_breakdown = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Provider Breakdown')
    )
    
    # Performance metrics
    avg_response_time = models.FloatField(default=0, verbose_name=_('Average Response Time'))
    success_rate = models.FloatField(default=0, verbose_name=_('Success Rate'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'llm_analytics'
        verbose_name = _('LLM Analytics')
        verbose_name_plural = _('LLM Analytics')
        ordering = ['-period_end']
        indexes = [
            models.Index(fields=['organization', 'period_end']),
            models.Index(fields=['period_type', 'period_end']),
            models.Index(fields=['uuid']),
        ]
        unique_together = ['organization', 'period_start', 'period_end', 'period_type']
    
    def __str__(self):
        return f"Analytics - {self.organization.name} - {self.period_start.date()} to {self.period_end.date()}"
    
    def calculate_success_rate(self):
        """Calculate success rate."""
        if self.total_requests > 0:
            return (self.successful_requests / self.total_requests) * 100
        return 0
    
    def save(self, *args, **kwargs):
        """Calculate derived metrics before saving."""
        self.success_rate = self.calculate_success_rate()
        super().save(*args, **kwargs)
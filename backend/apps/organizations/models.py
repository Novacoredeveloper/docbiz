from django.db import models
from django.core.exceptions import ValidationError
from safedelete.models import SafeDeleteModel
from phonenumber_field.modelfields import PhoneNumberField
from django_countries.fields import CountryField
from django.utils.translation import gettext_lazy as _
import uuid


class Organization(SafeDeleteModel):
    class SubscriptionTier(models.TextChoices):
        FREE = 'free', _('Free')
        BASIC = 'basic', _('Basic')
        BUSINESS = 'business', _('Business')
        ENTERPRISE = 'enterprise', _('Enterprise')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255, verbose_name=_('Organization Name'))
    subscription_tier = models.CharField(
        max_length=20,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.FREE,
        verbose_name=_('Subscription Tier')
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    
    # Organization details
    legal_name = models.CharField(max_length=255, blank=True, verbose_name=_('Legal Name'))
    website = models.URLField(blank=True, verbose_name=_('Website'))
    industry = models.CharField(max_length=100, blank=True, verbose_name=_('Industry'))
    
    # Contact information
    primary_contact_email = models.EmailField(blank=True, verbose_name=_('Primary Contact Email'))
    phone_number = PhoneNumberField(blank=True, verbose_name=_('Phone Number'))
    
    # Address
    address_line_1 = models.CharField(max_length=255, blank=True, verbose_name=_('Address Line 1'))
    address_line_2 = models.CharField(max_length=255, blank=True, verbose_name=_('Address Line 2'))
    city = models.CharField(max_length=100, blank=True, verbose_name=_('City'))
    state = models.CharField(max_length=100, blank=True, verbose_name=_('State/Province'))
    postal_code = models.CharField(max_length=20, blank=True, verbose_name=_('Postal Code'))
    country = CountryField(blank=True, verbose_name=_('Country'))
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_('Metadata'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'organizations'
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')
        ordering = ['name']
        indexes = [
            models.Index(fields=['subscription_tier', 'is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['uuid']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_subscription_tier_display()})"
    
    def clean(self):
        """Validate organization data."""
        if self.subscription_tier == self.SubscriptionTier.FREE:
            # Add free tier limitations validation
            pass
    
    def get_max_entities(self):
        """Get maximum entities allowed based on subscription tier."""
        limits = {
            self.SubscriptionTier.FREE: 10,
            self.SubscriptionTier.BASIC: 50,
            self.SubscriptionTier.BUSINESS: 200,
            self.SubscriptionTier.ENTERPRISE: None,  # Unlimited
        }
        return limits.get(self.subscription_tier)
    
    def get_max_users(self):
        """Get maximum users allowed based on subscription tier."""
        limits = {
            self.SubscriptionTier.FREE: 1,
            self.SubscriptionTier.BASIC: 3,
            self.SubscriptionTier.BUSINESS: 10,
            self.SubscriptionTier.ENTERPRISE: None,  # Unlimited
        }
        return limits.get(self.subscription_tier)
    
    def can_add_user(self):
        """Check if organization can add another user."""
        max_users = self.get_max_users()
        if max_users is None:  # Unlimited
            return True
        current_users = self.users.filter(is_active=True).count()
        return current_users < max_users
    
    def can_add_entity(self):
        """Check if organization can add another entity to org chart."""
        max_entities = self.get_max_entities()
        if max_entities is None:  # Unlimited
            return True
        
        # This would need to check the actual org chart entities count
        # For now, return True - actual validation will be in the chart app
        return True


class OrganizationContact(SafeDeleteModel):
    class ContactType(models.TextChoices):
        PRIMARY = 'primary', _('Primary Contact')
        BILLING = 'billing', _('Billing Contact')
        LEGAL = 'legal', _('Legal Contact')
        TECHNICAL = 'technical', _('Technical Contact')
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='contacts',
        verbose_name=_('Organization')
    )
    contact_type = models.CharField(
        max_length=20,
        choices=ContactType.choices,
        verbose_name=_('Contact Type')
    )
    first_name = models.CharField(max_length=100, verbose_name=_('First Name'))
    last_name = models.CharField(max_length=100, verbose_name=_('Last Name'))
    email = models.EmailField(verbose_name=_('Email'))
    phone = PhoneNumberField(blank=True, verbose_name=_('Phone Number'))
    title = models.CharField(max_length=100, blank=True, verbose_name=_('Job Title'))
    
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'organization_contacts'
        verbose_name = _('Organization Contact')
        verbose_name_plural = _('Organization Contacts')
        ordering = ['contact_type', 'last_name', 'first_name']
        unique_together = ['organization', 'contact_type']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_contact_type_display()}"
    
    def clean(self):
        """Validate unique contact type per organization."""
        if self.contact_type and self.organization:
            existing = OrganizationContact.objects.filter(
                organization=self.organization,
                contact_type=self.contact_type,
                is_active=True
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    f'{self.get_contact_type_display()} already exists for this organization'
                )
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
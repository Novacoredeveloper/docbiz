from rest_framework import serializers
from django_countries.serializer_fields import CountryField
from phonenumber_field.serializerfields import PhoneNumberField
from .models import Organization, OrganizationContact


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for Organization model - used for read operations."""
    
    # Custom field representations
    subscription_tier_display = serializers.CharField(
        source='get_subscription_tier_display', 
        read_only=True
    )
    country = CountryField()
    phone_number = PhoneNumberField()
    
    # Computed fields
    max_users = serializers.SerializerMethodField()
    max_entities = serializers.SerializerMethodField()
    current_user_count = serializers.SerializerMethodField()
    can_add_user = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = [
            'uuid',
            'name',
            'subscription_tier',
            'subscription_tier_display',
            'is_active',
            'legal_name',
            'website',
            'industry',
            'primary_contact_email',
            'phone_number',
            'address_line_1',
            'address_line_2',
            'city',
            'state',
            'postal_code',
            'country',
            'metadata',
            'max_users',
            'max_entities',
            'current_user_count',
            'can_add_user',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'uuid',
            'subscription_tier_display',
            'max_users',
            'max_entities',
            'current_user_count',
            'can_add_user',
            'created_at',
            'updated_at',
        ]
    
    def get_max_users(self, obj):
        return obj.get_max_users()
    
    def get_max_entities(self, obj):
        return obj.get_max_entities()
    
    def get_current_user_count(self, obj):
        return obj.users.filter(is_active=True).count()
    
    def get_can_add_user(self, obj):
        return obj.can_add_user()


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new organizations."""
    
    country = CountryField()
    phone_number = PhoneNumberField(required=False)
    
    class Meta:
        model = Organization
        fields = [
            'name',
            'legal_name',
            'website',
            'industry',
            'primary_contact_email',
            'phone_number',
            'address_line_1',
            'address_line_2',
            'city',
            'state',
            'postal_code',
            'country',
            'metadata',
        ]
    
    def validate_name(self, value):
        """Validate organization name is unique."""
        if Organization.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(
                "An organization with this name already exists."
            )
        return value
    
    def validate_primary_contact_email(self, value):
        """Validate primary contact email is unique."""
        if value and Organization.objects.filter(primary_contact_email__iexact=value).exists():
            raise serializers.ValidationError(
                "An organization with this primary contact email already exists."
            )
        return value
    
    def create(self, validated_data):
        """Create organization with additional logic."""
        # Set subscription tier to FREE by default for new organizations
        validated_data['subscription_tier'] = Organization.SubscriptionTier.FREE
        validated_data['is_active'] = True
        
        organization = Organization.objects.create(**validated_data)
        
        # You might want to create default contacts or settings here
        # self.create_default_contacts(organization)
        
        return organization
    
    def create_default_contacts(self, organization):
        """Create default contacts for new organization."""
        # Create a primary contact if email was provided
        if organization.primary_contact_email:
            OrganizationContact.objects.create(
                organization=organization,
                contact_type=OrganizationContact.ContactType.PRIMARY,
                first_name="Primary",
                last_name="Contact",
                email=organization.primary_contact_email,
                title="Primary Contact"
            )


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating organizations."""
    
    country = CountryField()
    phone_number = PhoneNumberField(required=False)
    
    class Meta:
        model = Organization
        fields = [
            'name',
            'legal_name',
            'website',
            'industry',
            'primary_contact_email',
            'phone_number',
            'address_line_1',
            'address_line_2',
            'city',
            'state',
            'postal_code',
            'country',
            'metadata',
            'is_active',
        ]
        read_only_fields = ['is_active']  # Only admins can change is_active via actions
    
    def validate_name(self, value):
        """Validate organization name is unique, excluding current instance."""
        instance = self.instance
        if instance and Organization.objects.filter(name__iexact=value).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError(
                "An organization with this name already exists."
            )
        return value
    
    def validate_primary_contact_email(self, value):
        """Validate primary contact email is unique, excluding current instance."""
        instance = self.instance
        if value and instance and Organization.objects.filter(
            primary_contact_email__iexact=value
        ).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError(
                "An organization with this primary contact email already exists."
            )
        return value
    
    def update(self, instance, validated_data):
        """Update organization with additional logic."""
        # Handle contact updates if primary contact email changes
        old_email = instance.primary_contact_email
        new_email = validated_data.get('primary_contact_email')
        
        organization = super().update(instance, validated_data)
        
        # Update primary contact if email changed
        if new_email and old_email != new_email:
            self.update_primary_contact(organization, new_email)
        
        return organization
    
    def update_primary_contact(self, organization, new_email):
        """Update or create primary contact when email changes."""
        try:
            primary_contact = organization.contacts.get(
                contact_type=OrganizationContact.ContactType.PRIMARY
            )
            primary_contact.email = new_email
            primary_contact.save()
        except OrganizationContact.DoesNotExist:
            # Create primary contact if it doesn't exist
            OrganizationContact.objects.create(
                organization=organization,
                contact_type=OrganizationContact.ContactType.PRIMARY,
                first_name="Primary",
                last_name="Contact",
                email=new_email,
                title="Primary Contact"
            )


class OrganizationContactSerializer(serializers.ModelSerializer):
    """Serializer for OrganizationContact model."""
    
    phone = PhoneNumberField(required=False)
    contact_type_display = serializers.CharField(
        source='get_contact_type_display', 
        read_only=True
    )
    organization_name = serializers.CharField(
        source='organization.name', 
        read_only=True
    )
    
    class Meta:
        model = OrganizationContact
        fields = [
            'uuid',
            'organization',
            'organization_name',
            'contact_type',
            'contact_type_display',
            'first_name',
            'last_name',
            'email',
            'phone',
            'title',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'uuid',
            'organization_name',
            'contact_type_display',
            'created_at',
            'updated_at',
        ]
    
    def validate(self, attrs):
        """Validate contact data."""
        # Ensure unique contact type per organization
        contact_type = attrs.get('contact_type')
        organization = attrs.get('organization') or self.instance.organization if self.instance else None
        
        if contact_type and organization:
            existing = OrganizationContact.objects.filter(
                organization=organization,
                contact_type=contact_type,
                is_active=True
            )
            
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'contact_type': f'{dict(OrganizationContact.ContactType.choices).get(contact_type)} already exists for this organization'
                })
        
        return attrs
    
    def create(self, validated_data):
        """Create contact with validation."""
        # Ensure the user has permission to create contacts for this organization
        request = self.context.get('request')
        if request and not request.user.is_superuser:
            # For non-superusers, ensure they're creating for their own organization
            user_org = request.user.organization
            contact_org = validated_data.get('organization')
            
            if user_org != contact_org:
                raise serializers.ValidationError({
                    'organization': 'You can only create contacts for your own organization'
                })
        
        return super().create(validated_data)


class OrganizationStatsSerializer(serializers.Serializer):
    """Serializer for organization statistics."""
    
    organization = serializers.CharField()
    
    user_stats = serializers.DictField()
    contract_stats = serializers.DictField()
    chart_stats = serializers.DictField()
    llm_usage = serializers.DictField()
    subscription = serializers.DictField(allow_null=True)


class OrganizationSettingsSerializer(serializers.Serializer):
    """Serializer for organization settings."""
    
    organization = serializers.DictField()
    address = serializers.DictField()
    features = serializers.DictField()


class OrganizationInvitationSerializer(serializers.Serializer):
    """Serializer for organization invitations."""
    
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[
            ('org_user', 'Organization User'),
            ('org_admin', 'Organization Admin'),
        ],
        default='org_user'
    )


class OrganizationSearchSerializer(serializers.ModelSerializer):
    """Serializer for organization search results."""
    
    subscription_tier_display = serializers.CharField(
        source='get_subscription_tier_display', 
        read_only=True
    )
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = [
            'uuid',
            'name',
            'legal_name',
            'subscription_tier',
            'subscription_tier_display',
            'is_active',
            'primary_contact_email',
            'industry',
            'user_count',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_user_count(self, obj):
        return obj.users.filter(is_active=True).count()


class OrganizationSubscriptionUpdateSerializer(serializers.Serializer):
    """Serializer for updating organization subscription."""
    
    plan_tier = serializers.ChoiceField(
        choices=[(tier.value, tier.label) for tier in Organization.SubscriptionTier]
    )


class OrganizationContactTypeSerializer(serializers.Serializer):
    """Serializer for contact type filtering."""
    
    contact_type = serializers.ChoiceField(
        choices=[(type.value, type.label) for type in OrganizationContact.ContactType]
    )


# Nested serializers for related objects
class OrganizationMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for organization references."""
    
    class Meta:
        model = Organization
        fields = ['uuid', 'name', 'subscription_tier']


class OrganizationContactMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for contact references."""
    
    class Meta:
        model = OrganizationContact
        fields = ['uuid', 'first_name', 'last_name', 'email', 'contact_type']


# Bulk operation serializers
class OrganizationBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk organization updates."""
    
    organizations = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    is_active = serializers.BooleanField(required=False)
    subscription_tier = serializers.ChoiceField(
        choices=[(tier.value, tier.label) for tier in Organization.SubscriptionTier],
        required=False
    )
    
    def validate_organizations(self, value):
        """Validate that organizations exist."""
        existing_orgs = Organization.objects.filter(uuid__in=value).values_list('uuid', flat=True)
        missing_orgs = set(value) - set(existing_orgs)
        
        if missing_orgs:
            raise serializers.ValidationError(
                f"Organizations not found: {', '.join(str(uuid) for uuid in missing_orgs)}"
            )
        
        return value


class OrganizationContactBulkSerializer(serializers.Serializer):
    """Serializer for bulk contact operations."""
    
    contacts = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    is_active = serializers.BooleanField(required=False)
    
    def validate_contacts(self, value):
        """Validate that contacts exist."""
        existing_contacts = OrganizationContact.objects.filter(uuid__in=value).values_list('uuid', flat=True)
        missing_contacts = set(value) - set(existing_contacts)
        
        if missing_contacts:
            raise serializers.ValidationError(
                f"Contacts not found: {', '.join(str(uuid) for uuid in missing_contacts)}"
            )
        
        return value
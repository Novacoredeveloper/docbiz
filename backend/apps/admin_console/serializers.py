from rest_framework import serializers
from apps.organizations.models import Organization
from apps.users.models import User
from apps.contracts.models import Contract, LLMUsage
from apps.billing.models import OrganizationSubscription, Invoice


class OrganizationAdminSerializer(serializers.ModelSerializer):
    subscription_status = serializers.CharField(source='subscription.status', read_only=True)
    subscription_plan = serializers.CharField(source='subscription.plan.name', read_only=True)
    user_count = serializers.SerializerMethodField()
    contract_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = [
            'id', 'uuid', 'name', 'legal_name', 'primary_contact_email',
            'subscription_status', 'subscription_plan', 'is_active',
            'user_count', 'contract_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']
    
    def get_user_count(self, obj):
        return obj.users.filter(is_active=True).count()
    
    def get_contract_count(self, obj):
        return obj.contracts.count()


class UserAdminSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    last_activity_days = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'uuid', 'email', 'first_name', 'last_name', 'role',
            'organization', 'organization_name', 'is_active', 'email_verified',
            'last_login', 'last_activity', 'last_activity_days', 'date_joined'
        ]
        read_only_fields = ['id', 'uuid', 'date_joined']
    
    def get_last_activity_days(self, obj):
        if obj.last_activity:
            delta = timezone.now() - obj.last_activity
            return delta.days
        return None


class ContractAdminSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    
    class Meta:
        model = Contract
        fields = [
            'id', 'uuid', 'organization', 'organization_name', 'title',
            'contract_number', 'status', 'created_by', 'created_by_email',
            'created_at', 'sent_at', 'completed_at', 'llm_usage_count'
        ]
        read_only_fields = ['id', 'uuid', 'created_at']


class LLMUsageAdminSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)
    
    class Meta:
        model = LLMUsage
        fields = [
            'id', 'uuid', 'organization', 'organization_name', 'user', 'user_email',
            'provider', 'provider_name', 'model', 'model_name', 'feature', 'status',
            'tokens_total', 'cost_estimated', 'request_duration', 'created_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at']


class SubscriptionAdminSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    days_until_renewal = serializers.SerializerMethodField()
    
    class Meta:
        model = OrganizationSubscription
        fields = [
            'id', 'uuid', 'organization', 'organization_name', 'plan', 'plan_name',
            'billing_cycle', 'status', 'current_price', 'current_period_start',
            'current_period_end', 'days_until_renewal', 'users_count',
            'contracts_used_this_month', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']
    
    def get_days_until_renewal(self, obj):
        return obj.days_until_renewal()


class InvoiceAdminSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'uuid', 'organization', 'organization_name', 'subscription',
            'plan_name', 'invoice_number', 'status', 'total_amount', 'amount_paid',
            'invoice_date', 'due_date', 'paid_at', 'is_overdue'
        ]
        read_only_fields = ['id', 'uuid']
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()


class PlatformMetricsSerializer(serializers.Serializer):
    overview = serializers.DictField()
    recent_activity = serializers.DictField()
    subscriptions = serializers.DictField()
    llm_usage = serializers.DictField()
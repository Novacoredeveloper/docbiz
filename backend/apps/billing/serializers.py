from rest_framework import serializers
from .models import (
    SubscriptionPlan, OrganizationSubscription, 
    Invoice, PaymentMethod
)


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    annual_savings = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'uuid', 'name', 'tier', 'monthly_price', 'annual_price',
            'max_users', 'max_entities', 'max_contracts_per_month',
            'monthly_llm_tokens', 'external_signing', 'pdf_upload',
            'authoritative_sources', 'api_access', 'custom_workflows',
            'support_level', 'description', 'features', 'is_active',
            'annual_savings', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']
    
    def get_annual_savings(self, obj):
        return obj.get_annual_savings()


class OrganizationSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_tier = serializers.CharField(source='plan.tier', read_only=True)
    is_trial = serializers.SerializerMethodField()
    days_until_renewal = serializers.SerializerMethodField()
    
    class Meta:
        model = OrganizationSubscription
        fields = [
            'id', 'uuid', 'organization', 'plan', 'plan_name', 'plan_tier',
            'billing_cycle', 'status', 'current_price', 'currency',
            'start_date', 'trial_end_date', 'current_period_start',
            'current_period_end', 'cancelled_at', 'users_count',
            'entities_count', 'contracts_used_this_month',
            'llm_tokens_used_this_month', 'metadata', 'is_trial',
            'days_until_renewal', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'uuid', 'organization', 'created_at', 'updated_at',
            'users_count', 'entities_count', 'contracts_used_this_month',
            'llm_tokens_used_this_month'
        ]
    
    def get_is_trial(self, obj):
        return obj.is_trial()
    
    def get_days_until_renewal(self, obj):
        return obj.days_until_renewal()


class InvoiceSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'uuid', 'organization', 'organization_name', 'subscription',
            'plan_name', 'invoice_number', 'status', 'amount_due', 'amount_paid',
            'tax_amount', 'total_amount', 'currency', 'invoice_date', 'due_date',
            'paid_at', 'line_items', 'payment_method', 'transaction_id', 'notes',
            'metadata', 'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()


class PaymentMethodSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'uuid', 'organization', 'organization_name', 'method_type',
            'last_four', 'brand', 'expiry_month', 'expiry_year', 'is_default',
            'is_active', 'provider_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'organization', 'created_at', 'updated_at']


class UpgradeSubscriptionSerializer(serializers.Serializer):
    target_plan_tier = serializers.ChoiceField(choices=SubscriptionPlan.TierType.choices)
    billing_cycle = serializers.ChoiceField(
        choices=OrganizationSubscription.BillingCycle.choices,
        default='monthly'
    )


class UsageSummarySerializer(serializers.Serializer):
    users = serializers.DictField()
    entities = serializers.DictField()
    contracts = serializers.DictField()
    llm_tokens = serializers.DictField()
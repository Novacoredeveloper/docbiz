from rest_framework import serializers
from .models import (
    LLMProvider, LLMModel, LLMUsage, 
    LLMQuota, LLMAnalytics
)


class LLMProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMProvider
        fields = [
            'id', 'uuid', 'name', 'provider_type', 'base_url',
            'api_version', 'requests_per_minute', 'tokens_per_minute',
            'is_active', 'is_default', 'config', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']


class LLMModelSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    
    class Meta:
        model = LLMModel
        fields = [
            'id', 'uuid', 'provider', 'provider_name', 'name', 'model_type',
            'context_window', 'max_output_tokens', 'supports_functions',
            'supports_vision', 'input_price', 'output_price', 'is_active',
            'is_default', 'description', 'capabilities', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']


class LLMUsageSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)
    contract_title = serializers.CharField(
        source='contract.title', 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = LLMUsage
        fields = [
            'id', 'uuid', 'organization', 'user', 'user_email',
            'provider', 'provider_name', 'model', 'model_name',
            'feature', 'status', 'tokens_prompt', 'tokens_completion',
            'tokens_total', 'cost_estimated', 'cost_calculated',
            'provider_request_id', 'model_used', 'request_duration',
            'time_to_first_token', 'input_context', 'generated_content',
            'error_message', 'error_code', 'contract', 'contract_title',
            'legal_references', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at']


class LLMQuotaSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = LLMQuota
        fields = [
            'id', 'uuid', 'organization', 'organization_name',
            'monthly_token_limit', 'tokens_used_current_month',
            'monthly_request_limit', 'requests_used_current_month',
            'monthly_cost_limit', 'cost_used_current_month',
            'last_reset_at', 'next_reset_at', 'is_suspended',
            'suspend_reason', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']


class LLMAnalyticsSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = LLMAnalytics
        fields = [
            'id', 'uuid', 'organization', 'organization_name',
            'period_start', 'period_end', 'period_type',
            'total_requests', 'successful_requests', 'failed_requests',
            'total_tokens', 'prompt_tokens', 'completion_tokens',
            'total_cost', 'feature_breakdown', 'provider_breakdown',
            'avg_response_time', 'success_rate', 'created_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at']


class LLMRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=True)
    feature = serializers.ChoiceField(choices=LLMUsage.FeatureType.choices)
    model_id = serializers.IntegerField(required=False)
    parameters = serializers.DictField(required=False, default=dict)
    
    def validate_parameters(self, value):
        """Validate LLM parameters."""
        allowed_params = ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty']
        return {k: v for k, v in value.items() if k in allowed_params}
from django.contrib import admin
from .models import LLMProvider, LLMModel, LLMUsage, LLMQuota, LLMAnalytics


@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider_type', 'is_active', 'is_default', 'requests_per_minute']
    list_filter = ['provider_type', 'is_active', 'is_default']
    search_fields = ['name', 'base_url']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider_type', 'is_active', 'is_default')
        }),
        ('API Configuration', {
            'fields': ('base_url', 'api_key', 'api_version')
        }),
        ('Rate Limiting', {
            'fields': ('requests_per_minute', 'tokens_per_minute')
        }),
        ('Advanced', {
            'fields': ('config', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'model_type', 'is_active', 'is_default', 'input_price', 'output_price']
    list_filter = ['provider', 'model_type', 'is_active', 'is_default']
    search_fields = ['name', 'description']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('provider', 'name', 'model_type', 'is_active', 'is_default')
        }),
        ('Capabilities', {
            'fields': ('context_window', 'max_output_tokens', 'supports_functions', 'supports_vision')
        }),
        ('Pricing', {
            'fields': ('input_price', 'output_price')
        }),
        ('Metadata', {
            'fields': ('description', 'capabilities', 'uuid', 'created_at', 'updated_at')
        }),
    )


@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    list_display = ['user', 'feature', 'provider', 'model', 'tokens_total', 'cost_estimated', 'created_at']
    list_filter = ['feature', 'status', 'provider', 'created_at']
    search_fields = ['user__email', 'input_context', 'generated_content']
    readonly_fields = ['uuid', 'created_at']
    fieldsets = (
        ('Usage Information', {
            'fields': ('organization', 'user', 'provider', 'model', 'feature', 'status')
        }),
        ('Token Usage', {
            'fields': ('tokens_prompt', 'tokens_completion', 'tokens_total')
        }),
        ('Cost Tracking', {
            'fields': ('cost_estimated', 'cost_calculated')
        }),
        ('Performance', {
            'fields': ('request_duration', 'time_to_first_token')
        }),
        ('Content', {
            'fields': ('input_context', 'generated_content'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message', 'error_code'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('provider_request_id', 'model_used', 'metadata', 'uuid', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LLMQuota)
class LLMQuotaAdmin(admin.ModelAdmin):
    list_display = ['organization', 'monthly_token_limit', 'tokens_used_current_month', 'is_suspended']
    list_filter = ['is_suspended', 'created_at']
    search_fields = ['organization__name']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    fieldsets = (
        ('Organization', {
            'fields': ('organization', 'is_suspended', 'suspend_reason')
        }),
        ('Token Limits', {
            'fields': ('monthly_token_limit', 'tokens_used_current_month')
        }),
        ('Request Limits', {
            'fields': ('monthly_request_limit', 'requests_used_current_month')
        }),
        ('Cost Limits', {
            'fields': ('monthly_cost_limit', 'cost_used_current_month')
        }),
        ('Reset Information', {
            'fields': ('last_reset_at', 'next_reset_at')
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at', 'updated_at')
        }),
    )


@admin.register(LLMAnalytics)
class LLMAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['organization', 'period_start', 'period_end', 'period_type', 'total_requests', 'total_cost']
    list_filter = ['period_type', 'period_start', 'period_end']
    search_fields = ['organization__name']
    readonly_fields = ['uuid', 'created_at']
    fieldsets = (
        ('Period Information', {
            'fields': ('organization', 'period_start', 'period_end', 'period_type')
        }),
        ('Usage Summary', {
            'fields': ('total_requests', 'successful_requests', 'failed_requests')
        }),
        ('Token Usage', {
            'fields': ('total_tokens', 'prompt_tokens', 'completion_tokens')
        }),
        ('Cost Summary', {
            'fields': ('total_cost', 'avg_response_time', 'success_rate')
        }),
        ('Breakdowns', {
            'fields': ('feature_breakdown', 'provider_breakdown'),
            'classes': ('collapse',)
        }),
    )
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    SubscriptionPlan, OrganizationSubscription, 
    Invoice, PaymentMethod, BillingWebhook
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'tier', 'monthly_price', 'annual_price', 
        'max_users', 'max_entities', 'is_active', 'created_at'
    ]
    list_filter = ['tier', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    list_editable = ['is_active', 'monthly_price']
    ordering = ['monthly_price']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'tier', 'description', 'is_active')
        }),
        ('Pricing', {
            'fields': ('monthly_price', 'annual_price')
        }),
        ('Feature Limits', {
            'fields': ('max_users', 'max_entities', 'max_contracts_per_month', 'monthly_llm_tokens')
        }),
        ('Feature Flags', {
            'fields': (
                'external_signing', 'pdf_upload', 'authoritative_sources',
                'api_access', 'custom_workflows'
            )
        }),
        ('Support & Features', {
            'fields': ('support_level', 'features')
        }),
        ('Metadata', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('subscriptions')
    
    def subscription_count(self, obj):
        return obj.subscriptions.count()
    subscription_count.short_description = 'Active Subscriptions'


@admin.register(OrganizationSubscription)
class OrganizationSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'plan', 'status', 'billing_cycle', 
        'current_price', 'is_active', 'days_until_renewal', 
        'created_at'
    ]
    list_filter = [
        'status', 'billing_cycle', 'plan__tier', 
        'created_at', 'current_period_end'
    ]
    search_fields = [
        'organization__name', 'organization__legal_name',
        'plan__name'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 'users_count',
        'entities_count', 'contracts_used_this_month', 
        'llm_tokens_used_this_month'
    ]
    list_select_related = ['organization', 'plan']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Organization & Plan', {
            'fields': ('organization', 'plan')
        }),
        ('Billing Details', {
            'fields': (
                'billing_cycle', 'status', 'current_price', 'currency'
            )
        }),
        ('Dates', {
            'fields': (
                'start_date', 'trial_end_date', 'current_period_start',
                'current_period_end', 'cancelled_at'
            )
        }),
        ('Usage Metrics', {
            'fields': (
                'users_count', 'entities_count', 'contracts_used_this_month',
                'llm_tokens_used_this_month'
            )
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active(self, obj):
        return obj.is_active()
    is_active.boolean = True
    is_active.short_description = 'Active'
    
    def days_until_renewal(self, obj):
        return obj.days_until_renewal()
    days_until_renewal.short_description = 'Days Until Renewal'
    
    def usage_percentage(self, obj):
        """Calculate overall usage percentage"""
        if not obj.plan.max_users:
            return "Unlimited"
        
        user_usage = (obj.users_count / obj.plan.max_users * 100) if obj.plan.max_users else 0
        entity_usage = (obj.entities_count / obj.plan.max_entities * 100) if obj.plan.max_entities else 0
        
        return f"Users: {user_usage:.1f}%, Entities: {entity_usage:.1f}%"
    usage_percentage.short_description = 'Usage %'
    
    actions = ['cancel_subscriptions', 'activate_subscriptions', 'generate_invoices']
    
    def cancel_subscriptions(self, request, queryset):
        """Admin action to cancel subscriptions"""
        updated = queryset.update(
            status=OrganizationSubscription.StatusType.CANCELLED,
            cancelled_at=timezone.now()
        )
        self.message_user(request, f'{updated} subscriptions cancelled.')
    cancel_subscriptions.short_description = "Cancel selected subscriptions"
    
    def activate_subscriptions(self, request, queryset):
        """Admin action to activate subscriptions"""
        updated = queryset.update(
            status=OrganizationSubscription.StatusType.ACTIVE,
            cancelled_at=None
        )
        self.message_user(request, f'{updated} subscriptions activated.')
    activate_subscriptions.short_description = "Activate selected subscriptions"
    
    def generate_invoices(self, request, queryset):
        """Admin action to generate invoices for subscriptions"""
        from .services import BillingService
        generated = 0
        
        for subscription in queryset:
            try:
                billing_service = BillingService(subscription.organization)
                billing_service.create_invoice()
                generated += 1
            except Exception as e:
                self.message_user(
                    request, 
                    f'Failed to generate invoice for {subscription.organization}: {str(e)}', 
                    level='ERROR'
                )
        
        self.message_user(request, f'{generated} invoices generated.')
    generate_invoices.short_description = "Generate invoices for selected subscriptions"


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'organization', 'subscription_plan',
        'status', 'total_amount', 'amount_paid', 'is_overdue',
        'invoice_date', 'due_date', 'paid_at'
    ]
    list_filter = [
        'status', 'invoice_date', 'due_date', 'paid_at',
        'subscription__plan__tier'
    ]
    search_fields = [
        'invoice_number', 'organization__name', 
        'organization__legal_name', 'transaction_id'
    ]
    readonly_fields = [
        'uuid', 'invoice_number', 'created_at', 'updated_at',
        'is_overdue'
    ]
    list_select_related = ['organization', 'subscription', 'subscription__plan']
    ordering = ['-invoice_date']
    
    fieldsets = (
        ('Invoice Information', {
            'fields': (
                'organization', 'subscription', 'invoice_number', 'status'
            )
        }),
        ('Amounts', {
            'fields': (
                'amount_due', 'amount_paid', 'tax_amount', 'total_amount', 'currency'
            )
        }),
        ('Dates', {
            'fields': ('invoice_date', 'due_date', 'paid_at')
        }),
        ('Line Items', {
            'fields': ('line_items',),
            'classes': ('collapse',)
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'transaction_id', 'notes')
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subscription_plan(self, obj):
        return obj.subscription.plan.name if obj.subscription else 'N/A'
    subscription_plan.short_description = 'Plan'
    
    def is_overdue(self, obj):
        return obj.is_overdue()
    is_overdue.boolean = True
    is_overdue.short_description = 'Overdue'
    
    def amount_remaining(self, obj):
        return obj.total_amount - obj.amount_paid
    amount_remaining.short_description = 'Amount Remaining'
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    organization_link.admin_order_field = 'organization__name'
    
    actions = ['mark_as_paid', 'mark_as_void', 'send_reminders']
    
    def mark_as_paid(self, request, queryset):
        """Admin action to mark invoices as paid"""
        updated = 0
        for invoice in queryset:
            if invoice.status != Invoice.StatusType.PAID:
                invoice.mark_paid('admin_manual', f'admin_{request.user.id}')
                updated += 1
        
        self.message_user(request, f'{updated} invoices marked as paid.')
    mark_as_paid.short_description = "Mark selected invoices as paid"
    
    def mark_as_void(self, request, queryset):
        """Admin action to mark invoices as void"""
        updated = queryset.update(status=Invoice.StatusType.VOID)
        self.message_user(request, f'{updated} invoices marked as void.')
    mark_as_void.short_description = "Mark selected invoices as void"
    
    def send_reminders(self, request, queryset):
        """Admin action to send payment reminders"""
        overdue_invoices = queryset.filter(
            status=Invoice.StatusType.OPEN,
            due_date__lt=timezone.now()
        )
        
        # In a real implementation, this would send actual emails
        self.message_user(
            request, 
            f'Payment reminders would be sent for {overdue_invoices.count()} invoices.'
        )
    send_reminders.short_description = "Send payment reminders for selected invoices"


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'method_type', 'last_four', 'brand',
        'is_default', 'is_active', 'created_at'
    ]
    list_filter = ['method_type', 'is_default', 'is_active', 'created_at']
    search_fields = [
        'organization__name', 'last_four', 'brand', 'provider_id'
    ]
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    list_select_related = ['organization']
    
    fieldsets = (
        ('Organization', {
            'fields': ('organization',)
        }),
        ('Payment Method Details', {
            'fields': (
                'method_type', 'last_four', 'brand',
                'expiry_month', 'expiry_year'
            )
        }),
        ('Status', {
            'fields': ('is_default', 'is_active')
        }),
        ('Provider Information', {
            'fields': ('provider_id',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    organization_link.admin_order_field = 'organization__name'
    
    actions = ['set_as_default', 'deactivate_methods']
    
    def set_as_default(self, request, queryset):
        """Admin action to set payment method as default"""
        if queryset.count() != 1:
            self.message_user(
                request, 
                'Please select exactly one payment method to set as default.', 
                level='ERROR'
            )
            return
        
        payment_method = queryset.first()
        
        # Remove default from other methods
        PaymentMethod.objects.filter(
            organization=payment_method.organization
        ).update(is_default=False)
        
        # Set selected as default
        payment_method.is_default = True
        payment_method.save()
        
        self.message_user(request, f'Payment method set as default for {payment_method.organization}.')
    set_as_default.short_description = "Set as default payment method"
    
    def deactivate_methods(self, request, queryset):
        """Admin action to deactivate payment methods"""
        # Don't allow deactivating default methods
        non_default_methods = queryset.filter(is_default=False)
        updated = non_default_methods.update(is_active=False)
        
        if updated < queryset.count():
            self.message_user(
                request, 
                f'Skipped {queryset.count() - updated} default payment methods.', 
                level='WARNING'
            )
        
        self.message_user(request, f'{updated} payment methods deactivated.')
    deactivate_methods.short_description = "Deactivate selected payment methods"


@admin.register(BillingWebhook)
class BillingWebhookAdmin(admin.ModelAdmin):
    list_display = [
        'processor', 'event_type', 'event_id', 'processed',
        'created_at', 'processed_at'
    ]
    list_filter = ['processor', 'event_type', 'processed', 'created_at']
    search_fields = ['event_id', 'event_type', 'processor']
    readonly_fields = [
        'uuid', 'created_at', 'processed_at', 'payload_preview'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Webhook Information', {
            'fields': ('processor', 'event_type', 'event_id')
        }),
        ('Processing Status', {
            'fields': ('processed', 'processing_error', 'processed_at')
        }),
        ('Payload', {
            'fields': ('payload_preview',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('uuid', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def payload_preview(self, obj):
        """Display a preview of the webhook payload"""
        import json
        try:
            formatted_payload = json.dumps(obj.payload, indent=2)
            return format_html('<pre>{}</pre>', formatted_payload)
        except:
            return str(obj.payload)
    payload_preview.short_description = 'Payload Preview'
    
    def has_add_permission(self, request):
        """Prevent manual creation of webhooks"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of webhooks"""
        return False
    
    actions = ['reprocess_webhooks']
    
    def reprocess_webhooks(self, request, queryset):
        """Admin action to reprocess failed webhooks"""
        failed_webhooks = queryset.filter(processed=False)
        reprocessed = 0
        
        for webhook in failed_webhooks:
            # In a real implementation, this would re-trigger webhook processing
            # For now, just mark as processed
            webhook.processed = True
            webhook.processing_error = "Manually reprocessed by admin"
            webhook.processed_at = timezone.now()
            webhook.save()
            reprocessed += 1
        
        self.message_user(request, f'{reprocessed} webhooks reprocessed.')
    reprocess_webhooks.short_description = "Reprocess selected webhooks"


# Custom admin views for billing analytics
class BillingAnalyticsAdmin(admin.ModelAdmin):
    """Virtual admin for billing analytics - not tied to a specific model"""
    
    def has_module_permission(self, request):
        """Show this in the admin index"""
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Register the billing analytics view
#admin.site.register([BillingAnalyticsAdmin])


# Custom admin filters
class OverdueInvoiceFilter(admin.SimpleListFilter):
    """Filter for overdue invoices"""
    title = 'overdue status'
    parameter_name = 'overdue'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Overdue'),
            ('no', 'Not Overdue'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(
                status=Invoice.StatusType.OPEN,
                due_date__lt=timezone.now()
            )
        if self.value() == 'no':
            return queryset.exclude(
                status=Invoice.StatusType.OPEN,
                due_date__lt=timezone.now()
            )


class TrialSubscriptionFilter(admin.SimpleListFilter):
    """Filter for trial subscriptions"""
    title = 'trial status'
    parameter_name = 'trial'
    
    def lookups(self, request, model_admin):
        return (
            ('active', 'Active Trial'),
            ('expired', 'Expired Trial'),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'active':
            return queryset.filter(
                status=OrganizationSubscription.StatusType.TRIAL,
                trial_end_date__gt=now
            )
        if self.value() == 'expired':
            return queryset.filter(
                status=OrganizationSubscription.StatusType.TRIAL,
                trial_end_date__lte=now
            )
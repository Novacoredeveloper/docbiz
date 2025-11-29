from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Organization, OrganizationContact


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'legal_name', 'subscription_status', 
        'subscription_plan', 'user_count', 'is_active',
        'created_at', 'action_buttons'
    ]
    list_filter = [
        'is_active', 'subscription__plan__tier', 
        'subscription__status', 'industry', 'created_at'
    ]
    search_fields = [
        'name', 'legal_name', 'primary_contact_email',
        'website', 'industry', 'city', 'state'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 
        'user_count_display', 'subscription_info',
        'address_display'
    ]
    list_select_related = ['subscription', 'subscription__plan']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'legal_name', 'is_active'
            )
        }),
        ('Contact Information', {
            'fields': (
                'primary_contact_email', 'phone_number', 'website', 'industry'
            )
        }),
        ('Address', {
            'fields': (
                'address_line_1', 'address_line_2', 'city',
                'state', 'postal_code', 'country'
            )
        }),
        ('Statistics', {
            'fields': ('user_count_display', 'subscription_info'),
            'classes': ('collapse',)
        }),
        ('Address Display', {
            'fields': ('address_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subscription_status(self, obj):
        """Display subscription status with color coding."""
        if hasattr(obj, 'subscription'):
            status = obj.subscription.status
            color = {
                'active': 'green',
                'trial': 'blue', 
                'past_due': 'orange',
                'cancelled': 'red',
                'suspended': 'gray'
            }.get(status, 'black')
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, status.upper()
            )
        return "No Subscription"
    subscription_status.short_description = 'Status'
    
    def subscription_plan(self, obj):
        """Display subscription plan."""
        if hasattr(obj, 'subscription'):
            return obj.subscription.plan.name
        return "No Plan"
    subscription_plan.short_description = 'Plan'
    
    def user_count(self, obj):
        """Display user count."""
        return obj.users.filter(is_active=True).count()
    user_count.short_description = 'Users'
    
    def user_count_display(self, obj):
        """Detailed user count for detail view."""
        from apps.users.models import User
        users = obj.users.filter(is_active=True)
        role_counts = users.values('role').annotate(count=models.Count('id'))
        
        role_display = "<br>".join([
            f"{role['role'].title()}: {role['count']}" 
            for role in role_counts
        ])
        
        return format_html(
            "<b>Active Users:</b> {}<br><b>Role Breakdown:</b><br>{}",
            users.count(), role_display
        )
    user_count_display.short_description = 'User Statistics'
    
    def subscription_info(self, obj):
        """Display detailed subscription information."""
        if not hasattr(obj, 'subscription'):
            return "No subscription"
        
        sub = obj.subscription
        return format_html(
            "<b>Plan:</b> {}<br>"
            "<b>Billing Cycle:</b> {}<br>"
            "<b>Price:</b> ${}/{}<br>"
            "<b>Period:</b> {} to {}<br>"
            "<b>Users:</b> {}/{}<br>"
            "<b>Entities:</b> {}/{}",
            sub.plan.name,
            sub.billing_cycle,
            sub.current_price, sub.currency,
            sub.current_period_start.strftime('%Y-%m-%d'),
            sub.current_period_end.strftime('%Y-%m-%d'),
            sub.users_count, 
            sub.plan.max_users or 'Unlimited',
            getattr(obj, 'entities_count', 'N/A'),
            sub.plan.max_entities or 'Unlimited'
        )
    subscription_info.short_description = 'Subscription Details'
    
    def address_display(self, obj):
        """Display formatted address."""
        address_parts = [
            obj.address_line_1,
            obj.address_line_2,
            f"{obj.city}, {obj.state} {obj.postal_code}",
            obj.country.name if obj.country else None
        ]
        address_parts = [part for part in address_parts if part]
        
        return format_html("<br>".join(address_parts))
    address_display.short_description = 'Formatted Address'
    
    def action_buttons(self, obj):
        """Add action buttons to list view."""
        buttons = []
        
        # View users button
        users_url = reverse('admin:users_user_changelist') + f'?organization__id__exact={obj.id}'
        buttons.append(
            f'<a href="{users_url}" class="button" style="padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px; margin: 2px;">Users</a>'
        )
        
        # View contracts button
        contracts_url = reverse('admin:contracts_contract_changelist') + f'?organization__id__exact={obj.id}'
        buttons.append(
            f'<a href="{contracts_url}" class="button" style="padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px; margin: 2px;">Contracts</a>'
        )
        
        # View chart button
        from apps.charts.models import OrgChart
        try:
            chart = OrgChart.objects.get(organization=obj)
            chart_url = reverse('admin:charts_orgchart_change', args=[chart.id])
            buttons.append(
                f'<a href="{chart_url}" class="button" style="padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px; margin: 2px;">Chart</a>'
            )
        except OrgChart.DoesNotExist:
            pass
        
        return format_html(" ".join(buttons))
    action_buttons.short_description = 'Actions'
    action_buttons.allow_tags = True
    
    actions = [
        'activate_organizations', 'deactivate_organizations',
        'update_subscription_tier', 'export_organization_data'
    ]
    
    def activate_organizations(self, request, queryset):
        """Admin action to activate organizations."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} organizations activated.')
    activate_organizations.short_description = "Activate selected organizations"
    
    def deactivate_organizations(self, request, queryset):
        """Admin action to deactivate organizations."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} organizations deactivated.')
    deactivate_organizations.short_description = "Deactivate selected organizations"
    
    def update_subscription_tier(self, request, queryset):
        """Admin action to update subscription tiers."""
        from apps.billing.models import SubscriptionPlan
        
        # Get available plans for selection
        plans = SubscriptionPlan.objects.filter(is_active=True)
        
        # In a real implementation, you'd show a form to select the plan
        # For now, we'll use the first available plan as an example
        if plans.exists():
            new_plan = plans.first()
            updated = 0
            
            for org in queryset:
                if hasattr(org, 'subscription'):
                    org.subscription.plan = new_plan
                    org.subscription.current_price = new_plan.monthly_price
                    org.subscription.save()
                    updated += 1
            
            self.message_user(
                request, 
                f'{updated} organization subscriptions updated to {new_plan.name}.'
            )
        else:
            self.message_user(
                request, 
                'No active subscription plans found.', 
                level='ERROR'
            )
    update_subscription_tier.short_description = "Update subscription tier"
    
    def export_organization_data(self, request, queryset):
        """Admin action to export organization data."""
        # In a real implementation, this would generate a CSV or PDF report
        self.message_user(
            request, 
            f'Export functionality would be triggered for {queryset.count()} organizations.'
        )
    export_organization_data.short_description = "Export organization data"


@admin.register(OrganizationContact)
class OrganizationContactAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'contact_type', 'full_name', 
        'email', 'phone', 'is_active', 'created_at'
    ]
    list_filter = [
        'contact_type', 'is_active', 'organization', 
        'created_at'
    ]
    search_fields = [
        'first_name', 'last_name', 'email', 'phone',
        'title', 'organization__name'
    ]
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    list_select_related = ['organization']
    ordering = ['organization', 'contact_type', 'last_name', 'first_name']
    
    fieldsets = (
        ('Organization', {
            'fields': ('organization',)
        }),
        ('Contact Information', {
            'fields': (
                'contact_type', 'first_name', 'last_name', 'email', 'phone', 'title'
            )
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        """Display full name."""
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Name'
    full_name.admin_order_field = 'last_name'
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    organization_link.admin_order_field = 'organization__name'
    
    def contact_type_display(self, obj):
        """Display contact type with icon."""
        icons = {
            'primary': '⭐',
            'billing': '💰', 
            'legal': '⚖️',
            'operations': '⚙️'
        }
        icon = icons.get(obj.contact_type, '📞')
        return f"{icon} {obj.get_contact_type_display()}"
    contact_type_display.short_description = 'Type'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization')
    
    actions = [
        'activate_contacts', 'deactivate_contacts',
        'export_contacts', 'convert_to_primary'
    ]
    
    def activate_contacts(self, request, queryset):
        """Admin action to activate contacts."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} contacts activated.')
    activate_contacts.short_description = "Activate selected contacts"
    
    def deactivate_contacts(self, request, queryset):
        """Admin action to deactivate contacts."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} contacts deactivated.')
    deactivate_contacts.short_description = "Deactivate selected contacts"
    
    def export_contacts(self, request, queryset):
        """Admin action to export contacts."""
        # In a real implementation, this would generate a CSV file
        self.message_user(
            request, 
            f'Contact export would be triggered for {queryset.count()} contacts.'
        )
    export_contacts.short_description = "Export selected contacts"
    
    def convert_to_primary(self, request, queryset):
        """Admin action to convert contacts to primary type."""
        # First, deactivate existing primary contacts for these organizations
        organizations = queryset.values_list('organization', flat=True).distinct()
        OrganizationContact.objects.filter(
            organization__in=organizations,
            contact_type='primary',
            is_active=True
        ).update(is_active=False)
        
        # Then set selected contacts as primary
        updated = queryset.update(contact_type='primary', is_active=True)
        self.message_user(request, f'{updated} contacts converted to primary.')
    convert_to_primary.short_description = "Convert to primary contact"


# Custom admin filters
class UserCountFilter(admin.SimpleListFilter):
    """Filter organizations by user count."""
    title = 'user count'
    parameter_name = 'user_count'
    
    def lookups(self, request, model_admin):
        return (
            ('0', 'No users'),
            ('1-10', '1-10 users'),
            ('11-50', '11-50 users'),
            ('51+', '51+ users'),
        )
    
    def queryset(self, request, queryset):
        from apps.users.models import User
        from django.db.models import Count
        
        if self.value() == '0':
            return queryset.annotate(user_count=Count('users')).filter(user_count=0)
        elif self.value() == '1-10':
            return queryset.annotate(user_count=Count('users')).filter(user_count__range=(1, 10))
        elif self.value() == '11-50':
            return queryset.annotate(user_count=Count('users')).filter(user_count__range=(11, 50))
        elif self.value() == '51+':
            return queryset.annotate(user_count=Count('users')).filter(user_count__gte=51)


class SubscriptionStatusFilter(admin.SimpleListFilter):
    """Filter organizations by subscription status."""
    title = 'subscription status'
    parameter_name = 'subscription_status'
    
    def lookups(self, request, model_admin):
        return (
            ('active', 'Active'),
            ('trial', 'Trial'),
            ('past_due', 'Past Due'),
            ('cancelled', 'Cancelled'),
            ('none', 'No Subscription'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(subscription__isnull=True)
        elif self.value():
            return queryset.filter(subscription__status=self.value())


# Add custom filters to OrganizationAdmin
OrganizationAdmin.list_filter.extend([UserCountFilter, SubscriptionStatusFilter])


# Inline admin for contacts
class OrganizationContactInline(admin.TabularInline):
    """Inline admin for organization contacts."""
    model = OrganizationContact
    extra = 1
    fields = ['contact_type', 'first_name', 'last_name', 'email', 'phone', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)


# Add inline to OrganizationAdmin
OrganizationAdmin.inlines = [OrganizationContactInline]


# Custom admin views for organization analytics
class OrganizationAnalyticsAdmin(admin.ModelAdmin):
    """Virtual admin for organization analytics - not tied to a specific model."""
    
    def has_module_permission(self, request):
        """Show this in the admin index."""
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Register the analytics view
#admin.site.register([OrganizationAnalyticsAdmin])
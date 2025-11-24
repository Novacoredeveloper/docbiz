from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    OrgChart, ChartEntityLink, ChartAuditLog,
    TaxDocument, License, PaymentRecord
)


@admin.register(OrgChart)
class OrgChartAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'version', 'entity_counts', 
        'last_modified_by', 'updated_at', 'created_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['organization__name', 'organization__legal_name']
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 
        'entity_counts_display', 'data_preview'
    ]
    list_select_related = ['organization', 'last_modified_by']
    
    fieldsets = (
        ('Organization', {
            'fields': ('organization', 'last_modified_by')
        }),
        ('Chart Data', {
            'fields': ('data_preview',),
            'classes': ('collapse',)
        }),
        ('Versioning', {
            'fields': ('version',)
        }),
        ('Statistics', {
            'fields': ('entity_counts_display',)
        }),
        ('Metadata', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def entity_counts(self, obj):
        """Display entity counts in list view."""
        companies = len(obj.get_companies())
        persons = len(obj.get_persons())
        trusts = len(obj.get_trusts())
        groups = len(obj.get_groups())
        connections = len(obj.data.get('connections', []))
        
        return f"C:{companies} P:{persons} T:{trusts} G:{groups} Conn:{connections}"
    entity_counts.short_description = 'Entities'
    
    def entity_counts_display(self, obj):
        """Detailed entity counts for detail view."""
        companies = len(obj.get_companies())
        persons = len(obj.get_persons())
        trusts = len(obj.get_trusts())
        groups = len(obj.get_groups())
        notes = len(obj.get_notes())
        connections = len(obj.data.get('connections', []))
        
        return format_html(
            "<b>Entity Counts:</b><br>"
            "Companies: {}<br>"
            "Persons: {}<br>"
            "Trusts: {}<br>"
            "Groups: {}<br>"
            "Notes: {}<br>"
            "Connections: {}",
            companies, persons, trusts, groups, notes, connections
        )
    entity_counts_display.short_description = 'Entity Statistics'
    
    def data_preview(self, obj):
        """Display a preview of the chart data."""
        import json
        try:
            formatted_data = json.dumps(obj.data, indent=2)
            return format_html('<pre style="max-height: 400px; overflow: auto;">{}</pre>', formatted_data)
        except:
            return str(obj.data)
    data_preview.short_description = 'Chart Data Preview'
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    organization_link.admin_order_field = 'organization__name'
    
    actions = ['duplicate_chart', 'export_chart_data']
    
    def duplicate_chart(self, request, queryset):
        """Admin action to duplicate charts."""
        duplicated = 0
        for chart in queryset:
            # Create a new chart with the same data but new version
            new_chart = OrgChart.objects.create(
                organization=chart.organization,
                data=chart.data,
                version=chart.version + 1,
                last_modified_by=request.user
            )
            duplicated += 1
        
        self.message_user(request, f'{duplicated} charts duplicated.')
    duplicate_chart.short_description = "Duplicate selected charts"
    
    def export_chart_data(self, request, queryset):
        """Admin action to export chart data."""
        # In a real implementation, this would generate a file download
        self.message_user(
            request, 
            f'Export functionality would be triggered for {queryset.count()} charts.'
        )
    export_chart_data.short_description = "Export chart data"


@admin.register(ChartEntityLink)
class ChartEntityLinkAdmin(admin.ModelAdmin):
    list_display = [
        'entity_type', 'entity_id', 'link_type', 
        'target_id', 'title', 'created_by', 'created_at'
    ]
    list_filter = ['entity_type', 'link_type', 'created_at']
    search_fields = [
        'entity_id', 'target_id', 'title', 'description',
        'org_chart__organization__name'
    ]
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    list_select_related = ['org_chart', 'created_by']
    
    fieldsets = (
        ('Chart Reference', {
            'fields': ('org_chart',)
        }),
        ('Entity Information', {
            'fields': ('entity_type', 'entity_id')
        }),
        ('Link Details', {
            'fields': ('link_type', 'target_id', 'title', 'description')
        }),
        ('Creator', {
            'fields': ('created_by',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def org_chart_organization(self, obj):
        return obj.org_chart.organization.name
    org_chart_organization.short_description = 'Organization'
    org_chart_organization.admin_order_field = 'org_chart__organization__name'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'org_chart__organization', 'created_by'
        )


@admin.register(ChartAuditLog)
class ChartAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'org_chart', 'action_type', 'entity_type', 
        'entity_id', 'actor', 'created_at'
    ]
    list_filter = ['action_type', 'entity_type', 'created_at']
    search_fields = [
        'entity_id', 'actor__email', 'description',
        'org_chart__organization__name'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'changes_preview', 
        'actor_ip_display'
    ]
    list_select_related = ['org_chart', 'actor']
    
    fieldsets = (
        ('Chart Reference', {
            'fields': ('org_chart',)
        }),
        ('Action Details', {
            'fields': ('action_type', 'entity_type', 'entity_id', 'description')
        }),
        ('Changes', {
            'fields': ('changes_preview',),
            'classes': ('collapse',)
        }),
        ('Actor Information', {
            'fields': ('actor', 'actor_ip_display')
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def changes_preview(self, obj):
        """Display a formatted preview of changes."""
        import json
        try:
            formatted_changes = json.dumps(obj.changes, indent=2)
            return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', formatted_changes)
        except:
            return str(obj.changes)
    changes_preview.short_description = 'Changes Preview'
    
    def actor_ip_display(self, obj):
        return obj.actor_ip or 'N/A'
    actor_ip_display.short_description = 'Actor IP'
    
    def org_chart_organization(self, obj):
        return obj.org_chart.organization.name
    org_chart_organization.short_description = 'Organization'
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of audit logs."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs (maintain audit trail)."""
        return request.user.is_superuser  # Only superusers can delete audit logs


@admin.register(TaxDocument)
class TaxDocumentAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'entity_id', 'document_type', 
        'tax_year', 'status', 'filing_date', 'due_date',
        'is_overdue', 'created_at'
    ]
    list_filter = [
        'document_type', 'status', 'tax_year', 
        'filing_date', 'created_at'
    ]
    search_fields = [
        'entity_id', 'title', 'description',
        'organization__name'
    ]
    readonly_fields = ['uuid', 'created_at', 'updated_at', 'is_overdue_display']
    list_select_related = ['organization', 'created_by']
    
    fieldsets = (
        ('Organization', {
            'fields': ('organization', 'created_by')
        }),
        ('Entity Reference', {
            'fields': ('entity_id', 'entity_type')
        }),
        ('Document Details', {
            'fields': ('document_type', 'title', 'description')
        }),
        ('Tax Year & Dates', {
            'fields': ('tax_year', 'filing_date', 'due_date')
        }),
        ('Status', {
            'fields': ('status', 'is_overdue_display')
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_overdue(self, obj):
        return obj.is_overdue()
    is_overdue.boolean = True
    is_overdue.short_description = 'Overdue'
    
    def is_overdue_display(self, obj):
        if obj.is_overdue():
            return format_html(
                '<span style="color: red; font-weight: bold;">OVERDUE</span>'
            )
        return "On Time"
    is_overdue_display.short_description = 'Overdue Status'
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    
    actions = ['mark_as_filed', 'mark_as_approved']
    
    def mark_as_filed(self, request, queryset):
        """Admin action to mark tax documents as filed."""
        updated = queryset.update(
            status='filed',
            filing_date=timezone.now().date()
        )
        self.message_user(request, f'{updated} tax documents marked as filed.')
    mark_as_filed.short_description = "Mark selected as filed"
    
    def mark_as_approved(self, request, queryset):
        """Admin action to mark tax documents as approved."""
        updated = queryset.update(status='approved')
        self.message_user(request, f'{updated} tax documents marked as approved.')
    mark_as_approved.short_description = "Mark selected as approved"


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'entity_id', 'license_type', 
        'license_number', 'status', 'expiration_date',
        'is_expired', 'days_until_expiration', 'created_at'
    ]
    list_filter = [
        'license_type', 'status', 'expiration_date', 
        'issue_date', 'created_at'
    ]
    search_fields = [
        'entity_id', 'license_number', 'issuing_authority',
        'description', 'organization__name'
    ]
    readonly_fields = [
        'uuid', 'created_at', 'updated_at', 
        'is_expired_display', 'days_until_expiration_display'
    ]
    list_select_related = ['organization', 'created_by']
    
    fieldsets = (
        ('Organization', {
            'fields': ('organization', 'created_by')
        }),
        ('Entity Reference', {
            'fields': ('entity_id',)
        }),
        ('License Details', {
            'fields': (
                'license_type', 'license_number', 'issuing_authority',
                'description', 'restrictions'
            )
        }),
        ('Dates', {
            'fields': ('issue_date', 'expiration_date', 'renewal_date')
        }),
        ('Status', {
            'fields': ('status', 'is_expired_display', 'days_until_expiration_display')
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'
    
    def is_expired_display(self, obj):
        if obj.is_expired():
            return format_html(
                '<span style="color: red; font-weight: bold;">EXPIRED</span>'
            )
        return "Active"
    is_expired_display.short_description = 'Expiration Status'
    
    def days_until_expiration(self, obj):
        days = obj.days_until_expiration()
        if days is None:
            return "N/A"
        return days
    days_until_expiration.short_description = 'Days Until Expiration'
    
    def days_until_expiration_display(self, obj):
        days = obj.days_until_expiration()
        if days is None:
            return "No expiration date set"
        
        if days < 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">Expired {} days ago</span>',
                abs(days)
            )
        elif days <= 30:
            return format_html(
                '<span style="color: orange; font-weight: bold;">{} days</span>',
                days
            )
        else:
            return f"{days} days"
    days_until_expiration_display.short_description = 'Expiration Countdown'
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    
    actions = ['renew_licenses', 'mark_as_suspended']
    
    def renew_licenses(self, request, queryset):
        """Admin action to renew licenses."""
        from datetime import timedelta
        
        renewed = 0
        for license in queryset:
            if license.status == 'active':
                # Extend expiration by 1 year
                license.expiration_date = license.expiration_date + timedelta(days=365)
                license.renewal_date = timezone.now().date()
                license.save()
                renewed += 1
        
        self.message_user(request, f'{renewed} licenses renewed.')
    renew_licenses.short_description = "Renew selected licenses"
    
    def mark_as_suspended(self, request, queryset):
        """Admin action to mark licenses as suspended."""
        updated = queryset.update(status='suspended')
        self.message_user(request, f'{updated} licenses marked as suspended.')
    mark_as_suspended.short_description = "Mark selected as suspended"


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'entity_id', 'payment_type',
        'description', 'amount', 'currency', 'status',
        'payment_date', 'is_overdue', 'created_at'
    ]
    list_filter = [
        'payment_type', 'status', 'payment_date', 
        'due_date', 'created_at'
    ]
    search_fields = [
        'entity_id', 'description', 'invoice_number',
        'transaction_id', 'organization__name'
    ]
    readonly_fields = ['uuid', 'created_at', 'updated_at', 'is_overdue_display']
    list_select_related = ['organization', 'created_by']
    
    fieldsets = (
        ('Organization', {
            'fields': ('organization', 'created_by')
        }),
        ('Entity Reference', {
            'fields': ('entity_id',)
        }),
        ('Payment Details', {
            'fields': (
                'payment_type', 'description', 'amount', 'currency'
            )
        }),
        ('Dates', {
            'fields': ('payment_date', 'due_date')
        }),
        ('Status & References', {
            'fields': ('status', 'invoice_number', 'transaction_id')
        }),
        ('Overdue Status', {
            'fields': ('is_overdue_display',)
        }),
        ('Metadata', {
            'fields': ('metadata', 'uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_overdue(self, obj):
        return obj.is_overdue()
    is_overdue.boolean = True
    is_overdue.short_description = 'Overdue'
    
    def is_overdue_display(self, obj):
        if obj.is_overdue():
            return format_html(
                '<span style="color: red; font-weight: bold;">OVERDUE</span>'
            )
        return "On Time"
    is_overdue_display.short_description = 'Overdue Status'
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    
    actions = ['mark_as_paid', 'mark_as_overdue']
    
    def mark_as_paid(self, request, queryset):
        """Admin action to mark payments as paid."""
        updated = queryset.update(
            status='paid',
            payment_date=timezone.now().date()
        )
        self.message_user(request, f'{updated} payments marked as paid.')
    mark_as_paid.short_description = "Mark selected as paid"
    
    def mark_as_overdue(self, request, queryset):
        """Admin action to mark payments as overdue."""
        updated = queryset.filter(status='pending').update(status='overdue')
        self.message_user(request, f'{updated} payments marked as overdue.')
    mark_as_overdue.short_description = "Mark selected as overdue"


# Custom admin filters
class OverdueFilter(admin.SimpleListFilter):
    """Filter for overdue items."""
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
                due_date__lt=timezone.now().date(),
                status__in=['draft', 'pending']
            )
        if self.value() == 'no':
            return queryset.exclude(
                due_date__lt=timezone.now().date(),
                status__in=['draft', 'pending']
            )


class ExpiringSoonFilter(admin.SimpleListFilter):
    """Filter for items expiring soon."""
    title = 'expiring soon'
    parameter_name = 'expiring_soon'
    
    def lookups(self, request, model_admin):
        return (
            ('30', 'Within 30 days'),
            ('60', 'Within 60 days'),
            ('90', 'Within 90 days'),
        )
    
    def queryset(self, request, queryset):
        if self.value():
            days = int(self.value())
            target_date = timezone.now().date() + timezone.timedelta(days=days)
            return queryset.filter(
                expiration_date__lte=target_date,
                expiration_date__gte=timezone.now().date(),
                status='active'
            )


# Add custom filters to relevant admins
TaxDocumentAdmin.list_filter.append(OverdueFilter)
LicenseAdmin.list_filter.append(OverdueFilter)
LicenseAdmin.list_filter.append(ExpiringSoonFilter)
PaymentRecordAdmin.list_filter.append(OverdueFilter)
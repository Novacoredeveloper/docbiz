from django.contrib import admin
from .models import (
    Contract, ContractTemplate, LegalReferenceLibrary,
    ContractParty, SignatureField, ContractEvent, LLMUsage
)


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'organization', 'version', 'is_active']
    list_filter = ['template_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(LegalReferenceLibrary)
class LegalReferenceLibraryAdmin(admin.ModelAdmin):
    list_display = ['title', 'state', 'content_type', 'is_active']
    list_filter = ['state', 'content_type', 'is_active']
    search_fields = ['title', 'citation', 'topics']
    readonly_fields = ['uuid', 'last_updated']


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ['title', 'contract_number', 'organization', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'organization']
    search_fields = ['title', 'contract_number']
    readonly_fields = ['uuid', 'created_at', 'sent_at', 'completed_at']
    filter_horizontal = []


@admin.register(ContractParty)
class ContractPartyAdmin(admin.ModelAdmin):
    list_display = ['name', 'contract', 'party_type', 'role', 'signed_at']
    list_filter = ['party_type', 'signed_at']
    search_fields = ['name', 'email']
    readonly_fields = ['uuid']


@admin.register(SignatureField)
class SignatureFieldAdmin(admin.ModelAdmin):
    list_display = ['label', 'contract', 'field_type', 'assigned_to', 'is_signed']
    list_filter = ['field_type', 'required', 'signed_at']
    search_fields = ['label', 'assigned_to__name']
    readonly_fields = ['uuid', 'signed_at']
    
    def is_signed(self, obj):
        return obj.is_signed()
    is_signed.boolean = True


@admin.register(ContractEvent)
class ContractEventAdmin(admin.ModelAdmin):
    list_display = ['contract', 'event_type', 'actor', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['contract__title', 'description']
    readonly_fields = ['uuid', 'created_at']


@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    list_display = ['user', 'feature', 'provider', 'tokens_total', 'created_at']
    list_filter = ['feature', 'provider', 'created_at']
    search_fields = ['user__email', 'contract__title']
    readonly_fields = ['uuid', 'created_at']
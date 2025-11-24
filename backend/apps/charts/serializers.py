from rest_framework import serializers
from .models import (
    OrgChart, ChartEntityLink, ChartAuditLog,
    TaxDocument, License, PaymentRecord
)


class OrgChartSerializer(serializers.ModelSerializer):
    entity_counts = serializers.SerializerMethodField()
    last_modified_by_email = serializers.CharField(source='last_modified_by.email', read_only=True)
    
    class Meta:
        model = OrgChart
        fields = [
            'id', 'uuid', 'organization', 'data', 'version',
            'last_modified_by', 'last_modified_by_email',
            'created_at', 'updated_at', 'entity_counts'
        ]
        read_only_fields = ['id', 'uuid', 'organization', 'created_at', 'updated_at']
    
    def get_entity_counts(self, obj):
        """Get counts of different entity types."""
        return {
            'companies': len(obj.get_companies()),
            'persons': len(obj.get_persons()),
            'trusts': len(obj.get_trusts()),
            'groups': len(obj.get_groups()),
            'notes': len(obj.get_notes()),
            'connections': len(obj.data.get('connections', []))
        }


class ChartUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgChart
        fields = ['data', 'version']
    
    def validate_data(self, value):
        """Validate chart data structure."""
        required_sections = ['companies', 'persons', 'trusts', 'groups', 'notes']
        
        for section in required_sections:
            if section not in value:
                value[section] = []
            
            if not isinstance(value[section], list):
                raise serializers.ValidationError(f"'{section}' must be a list")
        
        return value


class EntityOperationSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=[
        ('company', 'Company'),
        ('person', 'Person'),
        ('trust', 'Trust'),
        ('group', 'Group'),
    ])
    entity_data = serializers.DictField()


class ConnectionSerializer(serializers.Serializer):
    source_id = serializers.CharField(max_length=100)
    target_id = serializers.CharField(max_length=100)
    connection_type = serializers.CharField(max_length=50)
    metadata = serializers.DictField(required=False, default=dict)


class ChartEntityLinkSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    
    class Meta:
        model = ChartEntityLink
        fields = [
            'id', 'uuid', 'org_chart', 'entity_id', 'entity_type',
            'link_type', 'target_id', 'title', 'description',
            'metadata', 'created_by', 'created_by_email',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'org_chart', 'created_by', 'created_at', 'updated_at']


class ChartAuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source='actor.email', read_only=True)
    
    class Meta:
        model = ChartAuditLog
        fields = [
            'id', 'uuid', 'org_chart', 'action_type', 'entity_type',
            'entity_id', 'changes', 'actor', 'actor_email', 'actor_ip',
            'created_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at']


class TaxDocumentSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = TaxDocument
        fields = [
            'id', 'uuid', 'organization', 'entity_id', 'entity_type',
            'document_type', 'title', 'description', 'tax_year',
            'filing_date', 'due_date', 'status', 'metadata',
            'created_by', 'created_by_email', 'is_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'organization', 'created_by', 'created_at', 'updated_at']
    
    def get_is_overdue(self, obj):
        """Check if tax document is overdue."""
        from django.utils import timezone
        return (obj.due_date and 
                obj.due_date < timezone.now().date() and 
                obj.status in ['draft', 'pending'])


class LicenseSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    is_expired = serializers.SerializerMethodField()
    days_until_expiration = serializers.SerializerMethodField()
    
    class Meta:
        model = License
        fields = [
            'id', 'uuid', 'organization', 'entity_id',
            'license_type', 'license_number', 'issuing_authority',
            'issue_date', 'expiration_date', 'renewal_date', 'status',
            'description', 'restrictions', 'metadata',
            'created_by', 'created_by_email', 'is_expired', 'days_until_expiration',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'organization', 'created_by', 'created_at', 'updated_at']
    
    def get_is_expired(self, obj):
        return obj.is_expired()
    
    def get_days_until_expiration(self, obj):
        return obj.days_until_expiration()


class PaymentRecordSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentRecord
        fields = [
            'id', 'uuid', 'organization', 'entity_id',
            'payment_type', 'description', 'amount', 'currency',
            'payment_date', 'due_date', 'status',
            'invoice_number', 'transaction_id', 'metadata',
            'created_by', 'created_by_email', 'is_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'organization', 'created_by', 'created_at', 'updated_at']
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()
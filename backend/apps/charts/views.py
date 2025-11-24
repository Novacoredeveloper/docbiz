from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
import uuid
import json

from .models import (
    OrgChart, ChartEntityLink, ChartAuditLog,
    TaxDocument, License, PaymentRecord
)
from .serializers import (
    OrgChartSerializer, ChartUpdateSerializer,
    ChartEntityLinkSerializer, ChartAuditLogSerializer,
    TaxDocumentSerializer, LicenseSerializer, PaymentRecordSerializer,
    EntityOperationSerializer, ConnectionSerializer
)


class OrgChartViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organizational charts.
    Each organization has exactly one chart (MVP constraint).
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'put', 'patch']  # No create/delete (one per org)
    
    def get_queryset(self):
        return OrgChart.objects.filter(organization=self.request.user.organization)
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return ChartUpdateSerializer
        return OrgChartSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Get the organization's chart, create if doesn't exist."""
        try:
            chart = self.get_queryset().get()
            serializer = self.get_serializer(chart)
            return Response(serializer.data)
        except OrgChart.DoesNotExist:
            # Create chart if it doesn't exist
            chart = OrgChart.objects.create(
                organization=request.user.organization,
                last_modified_by=request.user,
                data={
                    'companies': [],
                    'persons': [],
                    'trusts': [],
                    'groups': [],
                    'notes': [],
                    'connections': []
                }
            )
            # Log the creation
            ChartAuditLog.objects.create(
                org_chart=chart,
                action_type=ChartAuditLog.ActionType.CREATE,
                entity_type='chart',
                changes={'initial_data': chart.data},
                actor=request.user,
                actor_ip=self.get_client_ip(request)
            )
            serializer = self.get_serializer(chart)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update the entire chart with audit logging."""
        chart = self.get_queryset().get()
        serializer = self.get_serializer(chart, data=request.data)
        
        if serializer.is_valid():
            # Store previous data for audit
            previous_data = chart.data
            
            # Log the update
            ChartAuditLog.objects.create(
                org_chart=chart,
                action_type=ChartAuditLog.ActionType.UPDATE,
                entity_type='chart',
                changes={
                    'previous_data': previous_data,
                    'new_data': serializer.validated_data['data']
                },
                actor=request.user,
                actor_ip=self.get_client_ip(request)
            )
            
            serializer.save(last_modified_by=request.user)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def add_entity(self, request):
        """Add an entity to the chart."""
        serializer = EntityOperationSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                chart = self.get_queryset().get()
                entity_type = serializer.validated_data['entity_type']
                entity_data = serializer.validated_data['entity_data']
                
                # Validate entity type
                valid_entity_types = ['company', 'person', 'trust', 'group']
                if entity_type not in valid_entity_types:
                    return Response(
                        {'error': f'Invalid entity type. Must be one of: {valid_entity_types}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Add entity based on type
                if entity_type == 'company':
                    entity_id = chart.add_company(entity_data)
                elif entity_type == 'person':
                    entity_id = chart.add_person(entity_data)
                elif entity_type == 'trust':
                    entity_id = chart.add_trust(entity_data)
                elif entity_type == 'group':
                    entity_id = f"group_{uuid.uuid4().hex[:8]}"
                    groups = chart.get_groups()
                    entity_data['id'] = entity_id
                    groups.append(entity_data)
                    chart.data['groups'] = groups
                    chart.save()
                
                # Log the creation
                ChartAuditLog.objects.create(
                    org_chart=chart,
                    action_type=ChartAuditLog.ActionType.CREATE,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    changes={'entity_data': entity_data},
                    actor=request.user,
                    actor_ip=self.get_client_ip(request)
                )
                
                return Response({
                    'entity_id': entity_id,
                    'entity_type': entity_type,
                    'message': f'{entity_type.title()} added successfully'
                })
                
            except OrgChart.DoesNotExist:
                return Response(
                    {'error': 'Organization chart not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def update_entity(self, request):
        """Update an existing entity in the chart."""
        entity_id = request.data.get('entity_id')
        entity_type = request.data.get('entity_type')
        entity_data = request.data.get('entity_data')
        
        if not all([entity_id, entity_type, entity_data]):
            return Response(
                {'error': 'entity_id, entity_type, and entity_data are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            chart = self.get_queryset().get()
            
            # Find and update the entity
            entities = chart.data.get(f'{entity_type}s', [])
            entity_index = next(
                (i for i, entity in enumerate(entities) if entity.get('id') == entity_id),
                None
            )
            
            if entity_index is None:
                return Response(
                    {'error': f'{entity_type} with ID {entity_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Store previous data for audit
            previous_data = entities[entity_index].copy()
            
            # Update entity
            entities[entity_index].update(entity_data)
            chart.data[f'{entity_type}s'] = entities
            chart.save()
            
            # Log the update
            ChartAuditLog.objects.create(
                org_chart=chart,
                action_type=ChartAuditLog.ActionType.UPDATE,
                entity_type=entity_type,
                entity_id=entity_id,
                changes={
                    'previous_data': previous_data,
                    'new_data': entities[entity_index]
                },
                actor=request.user,
                actor_ip=self.get_client_ip(request)
            )
            
            return Response({
                'entity_id': entity_id,
                'entity_type': entity_type,
                'message': f'{entity_type.title()} updated successfully'
            })
            
        except OrgChart.DoesNotExist:
            return Response(
                {'error': 'Organization chart not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def delete_entity(self, request):
        """Delete an entity from the chart."""
        entity_id = request.data.get('entity_id')
        entity_type = request.data.get('entity_type')
        
        if not all([entity_id, entity_type]):
            return Response(
                {'error': 'entity_id and entity_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            chart = self.get_queryset().get()
            
            # Find and remove the entity
            entities = chart.data.get(f'{entity_type}s', [])
            entity_index = next(
                (i for i, entity in enumerate(entities) if entity.get('id') == entity_id),
                None
            )
            
            if entity_index is None:
                return Response(
                    {'error': f'{entity_type} with ID {entity_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Store deleted data for audit
            deleted_entity = entities[entity_index]
            
            # Remove entity
            entities.pop(entity_index)
            chart.data[f'{entity_type}s'] = entities
            
            # Also remove any connections involving this entity
            connections = chart.data.get('connections', [])
            chart.data['connections'] = [
                conn for conn in connections 
                if conn.get('source') != entity_id and conn.get('target') != entity_id
            ]
            
            chart.save()
            
            # Log the deletion
            ChartAuditLog.objects.create(
                org_chart=chart,
                action_type=ChartAuditLog.ActionType.DELETE,
                entity_type=entity_type,
                entity_id=entity_id,
                changes={'deleted_entity': deleted_entity},
                actor=request.user,
                actor_ip=self.get_client_ip(request)
            )
            
            return Response({
                'entity_id': entity_id,
                'entity_type': entity_type,
                'message': f'{entity_type.title()} deleted successfully'
            })
            
        except OrgChart.DoesNotExist:
            return Response(
                {'error': 'Organization chart not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def add_connection(self, request):
        """Add a connection between entities."""
        serializer = ConnectionSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                chart = self.get_queryset().get()
                source_id = serializer.validated_data['source_id']
                target_id = serializer.validated_data['target_id']
                connection_type = serializer.validated_data['connection_type']
                metadata = serializer.validated_data.get('metadata', {})
                
                # Validate connection
                chart.validate_connection(source_id, target_id, connection_type)
                
                # Add connection
                connection_id = chart.add_connection(
                    source_id, target_id, connection_type, metadata
                )
                
                # Log the connection
                ChartAuditLog.objects.create(
                    org_chart=chart,
                    action_type=ChartAuditLog.ActionType.CONNECT,
                    entity_type='connection',
                    entity_id=connection_id,
                    changes={
                        'source_id': source_id,
                        'target_id': target_id,
                        'connection_type': connection_type,
                        'metadata': metadata
                    },
                    actor=request.user,
                    actor_ip=self.get_client_ip(request)
                )
                
                return Response({
                    'connection_id': connection_id,
                    'message': 'Connection added successfully'
                })
                
            except OrgChart.DoesNotExist:
                return Response(
                    {'error': 'Organization chart not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def delete_connection(self, request):
        """Delete a connection from the chart."""
        connection_id = request.data.get('connection_id')
        
        if not connection_id:
            return Response(
                {'error': 'connection_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            chart = self.get_queryset().get()
            
            # Find and remove the connection
            connections = chart.data.get('connections', [])
            connection_index = next(
                (i for i, conn in enumerate(connections) if conn.get('id') == connection_id),
                None
            )
            
            if connection_index is None:
                return Response(
                    {'error': f'Connection with ID {connection_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Store deleted connection for audit
            deleted_connection = connections[connection_index]
            
            # Remove connection
            connections.pop(connection_index)
            chart.data['connections'] = connections
            chart.save()
            
            # Log the deletion
            ChartAuditLog.objects.create(
                org_chart=chart,
                action_type=ChartAuditLog.ActionType.DISCONNECT,
                entity_type='connection',
                entity_id=connection_id,
                changes={'deleted_connection': deleted_connection},
                actor=request.user,
                actor_ip=self.get_client_ip(request)
            )
            
            return Response({
                'connection_id': connection_id,
                'message': 'Connection deleted successfully'
            })
            
        except OrgChart.DoesNotExist:
            return Response(
                {'error': 'Organization chart not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def entity_links(self, request):
        """Get all links for a specific entity."""
        entity_id = request.query_params.get('entity_id')
        if not entity_id:
            return Response(
                {'error': 'entity_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            chart = self.get_queryset().get()
            links = ChartEntityLink.objects.filter(
                org_chart=chart,
                entity_id=entity_id
            )
            serializer = ChartEntityLinkSerializer(links, many=True)
            return Response(serializer.data)
            
        except OrgChart.DoesNotExist:
            return Response(
                {'error': 'Organization chart not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def search_entities(self, request):
        """Search entities in the chart by name or properties."""
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return Response(
                {'error': 'Search query (q) parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            chart = self.get_queryset().get()
            results = []
            
            # Search in all entity types
            entity_types = ['companies', 'persons', 'trusts', 'groups']
            
            for entity_type in entity_types:
                entities = chart.data.get(entity_type, [])
                for entity in entities:
                    # Search in name and other string fields
                    entity_text = json.dumps(entity).lower()
                    if query.lower() in entity_text:
                        results.append({
                            'entity_type': entity_type[:-1],  # Remove 's'
                            'entity_id': entity.get('id'),
                            'name': entity.get('name') or entity.get('title') or entity.get('id'),
                            'data': entity
                        })
            
            return Response({
                'query': query,
                'results': results,
                'total_count': len(results)
            })
            
        except OrgChart.DoesNotExist:
            return Response(
                {'error': 'Organization chart not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ChartEntityLinkViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing links from chart entities to other system modules.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['entity_type', 'link_type']
    search_fields = ['entity_id', 'title', 'description']
    
    def get_queryset(self):
        chart = OrgChart.objects.filter(organization=self.request.user.organization).first()
        if chart:
            return ChartEntityLink.objects.filter(org_chart=chart)
        return ChartEntityLink.objects.none()
    
    def get_serializer_class(self):
        return ChartEntityLinkSerializer
    
    def perform_create(self, serializer):
        chart = OrgChart.objects.get(organization=self.request.user.organization)
        serializer.save(org_chart=chart, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        """Get all links for a specific entity."""
        entity_id = request.query_params.get('entity_id')
        entity_type = request.query_params.get('entity_type')
        
        if not entity_id or not entity_type:
            return Response(
                {'error': 'entity_id and entity_type parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        links = self.get_queryset().filter(
            entity_id=entity_id,
            entity_type=entity_type
        )
        serializer = self.get_serializer(links, many=True)
        return Response(serializer.data)


class TaxDocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tax documents metadata.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['entity_id', 'document_type', 'status', 'tax_year']
    search_fields = ['title', 'description']
    ordering_fields = ['tax_year', 'filing_date', 'due_date']
    
    def get_queryset(self):
        return TaxDocument.objects.filter(organization=self.request.user.organization)
    
    def get_serializer_class(self):
        return TaxDocumentSerializer
    
    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue tax documents."""
        from django.utils import timezone
        overdue_docs = self.get_queryset().filter(
            due_date__lt=timezone.now().date(),
            status__in=['draft', 'pending']
        )
        serializer = self.get_serializer(overdue_docs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        """Get tax documents for a specific entity."""
        entity_id = request.query_params.get('entity_id')
        if not entity_id:
            return Response(
                {'error': 'entity_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        docs = self.get_queryset().filter(entity_id=entity_id)
        serializer = self.get_serializer(docs, many=True)
        return Response(serializer.data)


class LicenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing licenses metadata.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['entity_id', 'license_type', 'status']
    search_fields = ['license_number', 'issuing_authority', 'description']
    ordering_fields = ['expiration_date', 'issue_date']
    
    def get_queryset(self):
        return License.objects.filter(organization=self.request.user.organization)
    
    def get_serializer_class(self):
        return LicenseSerializer
    
    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get licenses expiring in the next 30 days."""
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_from_now = timezone.now().date() + timedelta(days=30)
        expiring_licenses = self.get_queryset().filter(
            expiration_date__lte=thirty_days_from_now,
            status='active'
        )
        serializer = self.get_serializer(expiring_licenses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        """Get licenses for a specific entity."""
        entity_id = request.query_params.get('entity_id')
        if not entity_id:
            return Response(
                {'error': 'entity_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        licenses = self.get_queryset().filter(entity_id=entity_id)
        serializer = self.get_serializer(licenses, many=True)
        return Response(serializer.data)


class PaymentRecordViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payment records metadata.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['entity_id', 'payment_type', 'status']
    search_fields = ['description', 'invoice_number', 'transaction_id']
    ordering_fields = ['payment_date', 'due_date', 'amount']
    
    def get_queryset(self):
        return PaymentRecord.objects.filter(organization=self.request.user.organization)
    
    def get_serializer_class(self):
        return PaymentRecordSerializer
    
    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue payments."""
        from django.utils import timezone
        overdue_payments = self.get_queryset().filter(
            status='pending',
            due_date__lt=timezone.now().date()
        )
        serializer = self.get_serializer(overdue_payments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        """Get payment records for a specific entity."""
        entity_id = request.query_params.get('entity_id')
        if not entity_id:
            return Response(
                {'error': 'entity_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payments = self.get_queryset().filter(entity_id=entity_id)
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)


class ChartAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing chart audit logs.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['action_type', 'entity_type']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        chart = OrgChart.objects.filter(organization=self.request.user.organization).first()
        if chart:
            return ChartAuditLog.objects.filter(org_chart=chart)
        return ChartAuditLog.objects.none()
    
    def get_serializer_class(self):
        return ChartAuditLogSerializer


class ChartExportView(APIView):
    """
    API view for exporting chart data.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Export chart data in various formats."""
        format_type = request.query_params.get('format', 'json')
        
        try:
            chart = OrgChart.objects.get(organization=request.user.organization)
            
            if format_type == 'json':
                return Response({
                    'chart': chart.data,
                    'metadata': {
                        'organization': chart.organization.name,
                        'exported_at': timezone.now().isoformat(),
                        'version': chart.version,
                        'last_modified_by': chart.last_modified_by.email if chart.last_modified_by else None,
                        'last_modified_at': chart.updated_at.isoformat()
                    }
                })
            elif format_type == 'summary':
                # Return a summary of the chart
                summary = {
                    'total_entities': {
                        'companies': len(chart.get_companies()),
                        'persons': len(chart.get_persons()),
                        'trusts': len(chart.get_trusts()),
                        'groups': len(chart.get_groups()),
                        'notes': len(chart.get_notes()),
                    },
                    'total_connections': len(chart.data.get('connections', [])),
                    'entity_types_breakdown': self._get_entity_types_breakdown(chart),
                }
                return Response(summary)
            else:
                return Response(
                    {'error': f'Unsupported format: {format_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except OrgChart.DoesNotExist:
            return Response(
                {'error': 'Organization chart not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _get_entity_types_breakdown(self, chart):
        """Get breakdown of entity types and subtypes."""
        breakdown = {}
        
        for entity_type in ['companies', 'persons', 'trusts']:
            entities = chart.data.get(entity_type, [])
            type_counts = {}
            
            for entity in entities:
                entity_subtype = entity.get('type') or entity.get('role') or 'unknown'
                type_counts[entity_subtype] = type_counts.get(entity_subtype, 0) + 1
            
            breakdown[entity_type] = type_counts
        
        return breakdown


class EntityDetailView(APIView):
    """
    API view for getting detailed information about a specific entity.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, entity_id):
        """Get comprehensive information about an entity."""
        entity_type = request.query_params.get('entity_type')
        
        if not entity_type:
            return Response(
                {'error': 'entity_type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            chart = OrgChart.objects.get(organization=request.user.organization)
            
            # Find the entity
            entities = chart.data.get(f'{entity_type}s', [])
            entity = next(
                (e for e in entities if e.get('id') == entity_id),
                None
            )
            
            if not entity:
                return Response(
                    {'error': f'{entity_type} with ID {entity_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get entity links
            links = ChartEntityLink.objects.filter(
                org_chart=chart,
                entity_id=entity_id,
                entity_type=entity_type
            )
            
            # Get related documents
            tax_docs = TaxDocument.objects.filter(
                organization=request.user.organization,
                entity_id=entity_id
            )
            
            licenses = License.objects.filter(
                organization=request.user.organization,
                entity_id=entity_id
            )
            
            payments = PaymentRecord.objects.filter(
                organization=request.user.organization,
                entity_id=entity_id
            )
            
            # Get connections involving this entity
            connections = []
            for conn in chart.data.get('connections', []):
                if conn.get('source') == entity_id or conn.get('target') == entity_id:
                    connections.append(conn)
            
            return Response({
                'entity': entity,
                'entity_type': entity_type,
                'links': ChartEntityLinkSerializer(links, many=True).data,
                'tax_documents': TaxDocumentSerializer(tax_docs, many=True).data,
                'licenses': LicenseSerializer(licenses, many=True).data,
                'payments': PaymentRecordSerializer(payments, many=True).data,
                'connections': connections,
            })
            
        except OrgChart.DoesNotExist:
            return Response(
                {'error': 'Organization chart not found'},
                status=status.HTTP_404_NOT_FOUND
            )
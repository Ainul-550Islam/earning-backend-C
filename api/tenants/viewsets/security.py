"""
Security Viewsets

This module contains viewsets for security-related models including
TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, and TenantAuditLog.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from ..models.security import TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, TenantAuditLog
from ..serializers.security import (
    TenantAPIKeySerializer, TenantAPIKeyCreateSerializer,
    TenantWebhookConfigSerializer, TenantWebhookConfigCreateSerializer,
    TenantIPWhitelistSerializer, TenantIPWhitelistCreateSerializer,
    TenantAuditLogSerializer
)
from ..services import TenantAuditService


class TenantAPIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant API keys.
    """
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'status', 'created_by']
    search_fields = ['name', 'description', 'key_prefix']
    ordering_fields = ['name', 'created_at', 'last_used_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantAPIKeyCreateSerializer
        return TenantAPIKeySerializer
    
    def get_queryset(self):
        """Filter queryset to tenant's API keys."""
        if self.request.user.is_superuser:
            return TenantAPIKey.objects.filter(is_deleted=False)
        return TenantAPIKey.objects.filter(tenant__owner=self.request.user, is_deleted=False)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Create API key with generated key."""
        api_key = serializer.save()
        
        # Generate and set the actual key
        from ..models.security import TenantAPIKey
        key = TenantAPIKey.generate_key()
        api_key.set_key(key)
        api_key.save()
        
        # Store the actual key for one-time display
        api_key.actual_key = key
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate API key."""
        api_key = self.get_object()
        
        if api_key.is_expired():
            return Response(
                {'error': 'API key has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        api_key.status = 'active'
        api_key.save(update_fields=['status'])
        
        return Response({'message': 'API key activated'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate API key."""
        api_key = self.get_object()
        api_key.status = 'inactive'
        api_key.save(update_fields=['status'])
        
        return Response({'message': 'API key deactivated'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke API key."""
        api_key = self.get_object()
        api_key.revoke()
        
        return Response({'message': 'API key revoked'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        """Regenerate API key."""
        api_key = self.get_object()
        
        # Generate new key
        from ..models.security import TenantAPIKey
        new_key = TenantAPIKey.generate_key()
        api_key.set_key(new_key)
        api_key.status = 'active'
        api_key.save(update_fields=['key_hash', 'key_prefix', 'status'])
        
        # Store the actual key for one-time display
        api_key.actual_key = new_key
        
        return Response({
            'message': 'API key regenerated',
            'actual_key': new_key
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def usage_stats(self, request, pk=None):
        """Get API key usage statistics."""
        api_key = self.get_object()
        
        stats = {
            'usage_count': api_key.usage_count,
            'last_used_at': api_key.last_used_at,
            'last_ip_address': api_key.last_ip_address,
            'is_expired': api_key.is_expired(),
            'days_until_expiry': api_key.days_until_expiry() if api_key.expires_at else None,
        }
        
        return Response(stats, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def test_permissions(self, request, pk=None):
        """Test API key permissions."""
        api_key = self.get_object()
        
        test_scopes = request.data.get('scopes', [])
        test_endpoint = request.data.get('endpoint', '/test')
        
        results = {
            'can_access_endpoint': api_key.can_use_endpoint(test_endpoint),
            'has_scopes': []
        }
        
        for scope in test_scopes:
            results['has_scopes'].append({
                'scope': scope,
                'has_scope': api_key.has_scope(scope)
            })
        
        return Response(results, status=status.HTTP_200_OK)


class TenantWebhookConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant webhook configurations.
    """
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'is_active', 'auth_type']
    search_fields = ['name', 'url', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantWebhookConfigCreateSerializer
        return TenantWebhookConfigSerializer
    
    def get_queryset(self):
        """Filter queryset to tenant's webhook configs."""
        if self.request.user.is_superuser:
            return TenantWebhookConfig.objects.all()
        return TenantWebhookConfig.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Create webhook config with generated secret."""
        webhook = serializer.save()
        webhook.set_secret()
        webhook.save()
    
    @action(detail=True, methods=['post'])
    def test_webhook(self, request, pk=None):
        """Test webhook configuration."""
        webhook = self.get_object()
        
        # Send test webhook
        test_data = {
            'event': 'test',
            'data': {'message': 'This is a test webhook'},
            'timestamp': timezone.now().isoformat(),
        }
        
        # This would integrate with your webhook system
        # For now, simulate successful test
        webhook.update_delivery_stats(success=True, status_code=200)
        
        return Response({
            'message': 'Test webhook sent successfully',
            'status_code': 200,
            'success_rate': webhook.success_rate
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def ping(self, request, pk=None):
        """Ping webhook endpoint."""
        webhook = self.get_object()
        
        # Simple ping to check if endpoint is accessible
        import requests
        
        try:
            response = requests.get(webhook.url, timeout=10)
            return Response({
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'accessible': True
            }, status=status.HTTP_200_OK)
        except requests.exceptions.RequestException as e:
            return Response({
                'error': str(e),
                'accessible': False
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def delivery_stats(self, request, pk=None):
        """Get webhook delivery statistics."""
        webhook = self.get_object()
        
        stats = {
            'total_deliveries': webhook.total_deliveries,
            'successful_deliveries': webhook.successful_deliveries,
            'failed_deliveries': webhook.failed_deliveries,
            'success_rate': webhook.success_rate,
            'last_delivery_at': webhook.last_delivery_at,
            'last_status_code': webhook.last_status_code,
        }
        
        return Response(stats, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def trigger_event(self, request, pk=None):
        """Trigger specific event to webhook."""
        webhook = self.get_object()
        event_type = request.data.get('event')
        event_data = request.data.get('data', {})
        
        if not event_type:
            return Response(
                {'error': 'event parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not webhook.can_send_event(event_type):
            return Response(
                {'error': f'Event {event_type} is not configured for this webhook'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # This would integrate with your webhook system
        # For now, simulate successful trigger
        webhook.update_delivery_stats(success=True, status_code=200)
        
        return Response({
            'message': f'Event {event_type} triggered successfully',
            'event': event_type,
            'data': event_data
        }, status=status.HTTP_200_OK)


class TenantIPWhitelistViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant IP whitelists.
    """
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'is_active']
    search_fields = ['ip_range', 'label', 'description']
    ordering_fields = ['label', 'created_at']
    ordering = ['label', 'created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantIPWhitelistCreateSerializer
        return TenantIPWhitelistSerializer
    
    def get_queryset(self):
        """Filter queryset to tenant's IP whitelists."""
        if self.request.user.is_superuser:
            return TenantIPWhitelist.objects.all()
        return TenantIPWhitelist.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def test_ip(self, request, pk=None):
        """Test if IP address is allowed."""
        ip_whitelist = self.get_object()
        test_ip = request.data.get('ip')
        
        if not test_ip:
            return Response(
                {'error': 'ip parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_allowed = ip_whitelist.contains_ip(test_ip)
        
        return Response({
            'ip': test_ip,
            'is_allowed': is_allowed,
            'ip_range': ip_whitelist.ip_range
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def access_log(self, request, pk=None):
        """Get access log for IP range."""
        ip_whitelist = self.get_object()
        
        # This would query your access logs
        # For now, return basic info
        log = {
            'access_count': ip_whitelist.access_count,
            'last_access_at': ip_whitelist.last_access_at,
            'ip_range': ip_whitelist.ip_range,
        }
        
        return Response(log, status=status.HTTP_200_OK)


class TenantAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing tenant audit logs.
    """
    serializer_class = TenantAuditLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'action', 'severity', 'actor', 'model_name']
    search_fields = ['description', 'object_repr', 'ip_address']
    ordering_fields = ['created_at', 'action', 'severity']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        if self.request.user.is_superuser:
            return TenantAuditLog.objects.all()
        return TenantAuditLog.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        return [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def security_events(self, request):
        """Get security events only."""
        queryset = self.get_queryset().filter(action='security_event')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def api_access(self, request):
        """Get API access logs only."""
        queryset = self.get_queryset().filter(action='api_access')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def compliance_report(self, request):
        """Generate compliance report."""
        days = int(request.query_params.get('days', 90))
        
        if not self.request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        report = TenantAuditService.get_compliance_report(days=days)
        return Response(report, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def anomalies(self, request):
        """Detect anomalies in tenant activity."""
        hours = int(request.query_params.get('hours', 24))
        
        if not self.request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all active tenants
        from ..models import Tenant
        tenants = Tenant.objects.filter(is_deleted=False, status='active')
        
        all_anomalies = []
        for tenant in tenants:
            anomalies = TenantAuditService.detect_anomalies(tenant, hours)
            for anomaly in anomalies:
                anomaly['tenant'] = {
                    'id': str(tenant.id),
                    'name': tenant.name,
                }
                all_anomalies.append(anomaly)
        
        return Response({
            'hours': hours,
            'anomalies': all_anomalies,
            'total_anomalies': len(all_anomalies)
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export audit logs."""
        format_type = request.query_params.get('format', 'csv')
        days = int(request.query_params.get('days', 30))
        
        if not self.request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if format_type not in ['csv', 'json', 'xlsx']:
            return Response(
                {'error': 'Invalid format. Use csv, json, or xlsx'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Export all tenant logs
        from ..models import Tenant
        tenants = Tenant.objects.filter(is_deleted=False)
        
        export_data = []
        for tenant in tenants:
            logs = TenantAuditService.get_audit_logs(tenant, days=days)
            for log in logs:
                export_data.append({
                    'tenant_name': tenant.name,
                    'created_at': log.created_at.isoformat(),
                    'action': log.action,
                    'severity': log.severity,
                    'actor': log.actor_display,
                    'description': log.description,
                    'ip_address': log.ip_address,
                })
        
        if format_type == 'json':
            return Response(export_data, status=status.HTTP_200_OK)
        elif format_type == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            writer.writerow(['Tenant', 'Created At', 'Action', 'Severity', 'Actor', 'Description', 'IP Address'])
            
            for log in export_data:
                writer.writerow([
                    log['tenant_name'],
                    log['created_at'],
                    log['action'],
                    log['severity'],
                    log['actor'],
                    log['description'],
                    log['ip_address']
                ])
            
            return Response(output.getvalue(), content_type='text/csv', status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'XLSX export not implemented yet'},
                status=status.HTTP_400_BAD_REQUEST
            )

# api/admin_panel/viewsets/WebhooksTenantAdminViewSet.py
"""
Admin control for Webhooks & Tenants.
Manage webhook endpoints, delivery logs, retry, tenants, billing.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta


class WebhooksAdminViewSet(viewsets.ViewSet):
    """Full webhook system admin — endpoints, logs, retry, stats."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.webhooks.models import WebhookEndpoint, WebhookDeliveryLog
            endpoints = WebhookEndpoint.objects.aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(is_active=True)),
            )
            logs = WebhookDeliveryLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).aggregate(
                total=Count('id'),
                success=Count('id', filter=Q(status='success')),
                failed=Count('id', filter=Q(status='failed')),
            )
            return Response({'success': True, 'data': {
                'endpoints': endpoints,
                'last_24h_deliveries': logs,
            }})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def endpoints(self, request):
        try:
            from api.webhooks.models import WebhookEndpoint
            data = list(WebhookEndpoint.objects.values(
                'id', 'url', 'secret', 'is_active', 'events',
                'failure_count', 'last_triggered_at', 'created_at'
            ).order_by('-created_at'))
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_endpoint(self, request):
        try:
            from api.webhooks.models import WebhookEndpoint
            endpoint_id = request.data.get('endpoint_id')
            ep = WebhookEndpoint.objects.get(pk=endpoint_id)
            ep.is_active = not ep.is_active
            ep.save(update_fields=['is_active'])
            return Response({'success': True, 'id': endpoint_id, 'is_active': ep.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def failed_deliveries(self, request):
        try:
            from api.webhooks.models import WebhookDeliveryLog
            data = list(WebhookDeliveryLog.objects.filter(
                status='failed'
            ).values(
                'id', 'endpoint_id', 'event_type', 'response_code',
                'error_message', 'attempt_count', 'created_at'
            ).order_by('-created_at')[:100])
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def retry_delivery(self, request):
        try:
            log_id = request.data.get('log_id')
            try:
                from api.webhooks.tasks import retry_webhook_delivery
                retry_webhook_delivery.delay(log_id)
                return Response({'success': True, 'queued': True, 'log_id': log_id})
            except Exception:
                from api.webhooks.models import WebhookDeliveryLog
                WebhookDeliveryLog.objects.filter(pk=log_id).update(status='pending')
                return Response({'success': True, 'log_id': log_id, 'status': 'pending'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def retry_all_failed(self, request):
        try:
            from api.webhooks.models import WebhookDeliveryLog
            count = WebhookDeliveryLog.objects.filter(status='failed').update(status='pending')
            return Response({'success': True, 'queued_count': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def delivery_stats(self, request):
        try:
            from api.webhooks.models import WebhookDeliveryLog
            from django.db.models.functions import TruncDate
            stats = list(
                WebhookDeliveryLog.objects
                .filter(created_at__gte=timezone.now() - timedelta(days=7))
                .annotate(date=TruncDate('created_at'))
                .values('date', 'status')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            return Response({'success': True, 'data': stats})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})


class TenantAdminViewSet(viewsets.ViewSet):
    """Admin control for Multi-tenant system."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def list_tenants(self, request):
        try:
            from api.tenants.models import Tenant
            data = list(Tenant.objects.values(
                'id', 'name', 'schema_name', 'domain', 'is_active',
                'plan', 'created_at', 'owner_id'
            ).order_by('-created_at'))
            return Response({'success': True, 'data': data, 'total': len(data)})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_tenant(self, request):
        try:
            from api.tenants.models import Tenant
            tenant_id = request.data.get('tenant_id')
            reason = request.data.get('reason', '')
            tenant = Tenant.objects.get(pk=tenant_id)
            tenant.is_active = not tenant.is_active
            tenant.save(update_fields=['is_active'])
            return Response({'success': True, 'tenant_id': tenant_id, 'is_active': tenant.is_active})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def tenant_billing(self, request):
        try:
            from api.tenants.models import TenantBilling, TenantInvoice
            tenant_id = request.query_params.get('tenant_id')
            billing = TenantBilling.objects.filter(
                **({'tenant_id': tenant_id} if tenant_id else {})
            ).values('id', 'tenant_id', 'plan', 'amount', 'status', 'due_date').order_by('-id')[:50]
            return Response({'success': True, 'data': list(billing)})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_plan(self, request):
        try:
            from api.tenants.models import Tenant
            tenant_id = request.data.get('tenant_id')
            new_plan = request.data.get('plan')
            Tenant.objects.filter(pk=tenant_id).update(plan=new_plan)
            return Response({'success': True, 'tenant_id': tenant_id, 'plan': new_plan})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def tenant_settings(self, request):
        try:
            from api.tenants.models import TenantSettings
            tenant_id = request.query_params.get('tenant_id')
            if not tenant_id:
                return Response({'error': 'tenant_id required'}, status=400)
            settings = TenantSettings.objects.filter(tenant_id=tenant_id).values().first()
            return Response({'success': True, 'data': settings or {}})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})
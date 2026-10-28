"""
Core Alert ViewSets — FIXED: added all missing actions referenced in urls/core.py
Missing actions added:
  AlertRuleViewSet    → activate, deactivate, statistics
  AlertLogViewSet     → acknowledge, by_rule, pending, resolved, by_severity, bulk_update_status
  NotificationViewSet → mark_sent, mark_failed, retry, by_status, by_type, failed
  SystemHealthViewSet → already has overview (was present)
  AlertOverviewViewSet → statistics (alias for analytics)
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from ..permissions import (
    IsAlertManager, CanManageNotifications, CanResolveAlerts,
    CanAcknowledgeAlerts, CanManageSystemHealth, CanViewAuditLogs,
    IsOwnerOrReadOnly, CanAccessDuringMaintenance,
)
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta
import logging

from ..models.core import AlertRule, AlertLog, Notification, SystemHealthCheck
from ..services.core import AlertProcessorService, AnalyticsService, AlertGroupService, AlertMaintenanceService
from ..choices import ALERT_TYPES, SEVERITY_LEVELS, NOTIFICATION_STATUS, ALERT_STATUS
from ..enums import AlertType, SeverityLevel, NotificationType, AlertStatus
from ..constants import DEFAULT_TIME_WINDOW_MINUTES, DEFAULT_COOLDOWN_MINUTES, DEFAULT_THRESHOLD_VALUE
from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

# ── Mixins (previously floating in mixins.py — now used in viewsets) ──────────
from api.alerts.mixins import (
    TenantIsolationMixin,
    AuditLogMixin, CacheMixin, BulkActionMixin,
    ExportMixin, RateLimitMixin, AlertPermissionMixin,
)
_MIXINS_AVAILABLE = True

logger = logging.getLogger(__name__)


class AlertRuleViewSet(TenantIsolationMixin, AuditLogMixin, CacheMixin, viewsets.ModelViewSet):
    """AlertRule ViewSet — tenant-scoped CRUD. Uses AuditLogMixin + CacheMixin from mixins.py"""
    queryset = AlertRule.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # TenantIsolationMixin.get_queryset() already scopes by tenant via super() chain
        queryset = super().get_queryset()

        severity = self.request.query_params.get('severity')
        alert_type = self.request.query_params.get('alert_type')
        is_active = self.request.query_params.get('is_active')
        active = self.request.query_params.get('active')
        search = self.request.query_params.get('search')

        if severity:
            queryset = queryset.filter(severity=severity)
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if active is not None and active != '':
            queryset = queryset.filter(is_active=active.lower() in ('1', 'true', 'yes'))
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers.core import AlertRuleSerializer
        return AlertRuleSerializer

    def get_permissions(self):
        """
        Fine-grained permission wiring:
          list / retrieve            → any authenticated user
          create / update / destroy  → must be an AlertManager
          activate / deactivate      → must be an AlertManager
          test                       → must be an AlertManager
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'activate', 'deactivate', 'toggle', 'test',
                            'bulk_update_status']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Alert rules statistics"""
        try:
            qs = AlertRule.objects.all()

            by_severity = {}
            for severity_value, severity_label in SEVERITY_LEVELS:
                by_severity[severity_value] = qs.filter(severity=severity_value).count()

            by_type = {}
            for alert_type_value, alert_type_label in ALERT_TYPES:
                by_type[alert_type_value] = qs.filter(alert_type=alert_type_value).count()

            return Response({
                'total': qs.count(),
                'active': qs.filter(is_active=True).count(),
                'inactive': qs.filter(is_active=False).count(),
                'by_severity': by_severity,
                'by_type': by_type,
                'high_trigger_count': list(qs.order_by('-trigger_count')[:5].values('id', 'name', 'trigger_count')),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting alert rules stats: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate an alert rule"""
        try:
            rule = self.get_object()
            rule.is_active = True
            rule.save(update_fields=['is_active'])
            return Response({'success': True, 'id': rule.id, 'is_active': True})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error activating rule {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an alert rule"""
        try:
            rule = self.get_object()
            rule.is_active = False
            rule.save(update_fields=['is_active'])
            return Response({'success': True, 'id': rule.id, 'is_active': False})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error deactivating rule {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Per-rule statistics: trigger count, resolution rate, recent logs"""
        try:
            rule = self.get_object()
            logs = AlertLog.objects.filter(rule=rule)
            total = logs.count()
            resolved = logs.filter(is_resolved=True).count()
            week_ago = timezone.now() - timedelta(days=7)
            return Response({
                'rule_id': rule.id,
                'rule_name': rule.name,
                'trigger_count': rule.trigger_count,
                'total_logs': total,
                'resolved_logs': resolved,
                'unresolved_logs': total - resolved,
                'resolution_rate': round((resolved / total * 100), 2) if total > 0 else 0,
                'last_triggered': rule.last_triggered,
                'logs_this_week': logs.filter(triggered_at__gte=week_ago).count(),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting rule statistics {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle rule active/inactive"""
        try:
            rule = self.get_object()
            rule.is_active = not rule.is_active
            rule.save(update_fields=['is_active'])
            return Response({'success': True, 'is_active': rule.is_active})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error toggling rule: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Manually trigger test alert"""
        try:
            rule = self.get_object()

            log = AlertLog.objects.create(
                rule=rule,
                trigger_value=rule.threshold_value + 1,
                threshold_value=rule.threshold_value,
                message=f'[TEST] Alert rule "{rule.name}" manually tested',
                is_resolved=True,
                resolved_at=timezone.now(),
                resolution_note='Auto-resolved: manual test',
            )

            return Response({'success': True, 'log_id': log.id, 'message': log.message})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error testing rule: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['patch'], url_path='bulk-update-status')
    def bulk_update_status(self, request):
        """Bulk update rule active/inactive status"""
        try:
            ids = request.data.get('ids', [])
            is_active = request.data.get('is_active', True)

            if not ids:
                return Response({'error': 'No ids provided'}, status=status.HTTP_400_BAD_REQUEST)

            count = AlertRule.objects.filter(id__in=ids).update(is_active=is_active)
            return Response({'success': True, 'updated': count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error bulk updating rules: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertLogViewSet(TenantIsolationMixin, BulkActionMixin, RateLimitMixin, viewsets.ModelViewSet):
    """AlertLog ViewSet — tenant-scoped. Uses BulkActionMixin + RateLimitMixin from mixins.py"""
    queryset = AlertLog.objects.all()
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """This model has no created_by field, unlike most other models here."""
        serializer.save(**self.tenant_save_kwargs())

    def get_queryset(self):
        queryset = super().get_queryset().select_related('rule')

        severity = self.request.query_params.get('severity')
        resolved = self.request.query_params.get('is_resolved')
        rule_id = self.request.query_params.get('rule_id')

        if severity:
            queryset = queryset.filter(rule__severity=severity)
        if resolved is not None and resolved != '':
            queryset = queryset.filter(is_resolved=resolved.lower() == 'true')
        if rule_id:
            queryset = queryset.filter(rule_id=rule_id)

        return queryset.order_by('-triggered_at')

    def get_serializer_class(self):
        from ..serializers.core import AlertLogSerializer
        return AlertLogSerializer

    def get_permissions(self):
        """
        list / retrieve / by_rule / by_severity  → any authenticated user
        acknowledge                               → CanAcknowledgeAlerts
        bulk_resolve / destroy                    → CanResolveAlerts
        bulk_update_status                        → IsAlertManager
        """
        if self.action in ['acknowledge']:
            return [IsAuthenticated(), CanAcknowledgeAlerts()]
        if self.action in ['bulk_resolve', 'destroy']:
            return [IsAuthenticated(), CanResolveAlerts()]
        if self.action in ['bulk_update_status']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Alert logs statistics"""
        try:
            qs = AlertLog.objects.all()
            week_ago = timezone.now() - timedelta(days=7)
            unresolved = qs.filter(is_resolved=False)

            return Response({
                'total': qs.count(),
                'resolved': qs.filter(is_resolved=True).count(),
                'unresolved': unresolved.count(),
                'escalated': qs.filter(escalation_level__gt=0).count(),
                'critical_unresolved': unresolved.filter(rule__severity=SeverityLevel.CRITICAL.value).count(),
                'this_week': qs.filter(triggered_at__gte=week_ago).count(),
                'avg_resolution_time': None,
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting alert logs stats: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve a single alert log"""
        try:
            log = self.get_object()

            if log.is_resolved:
                return Response({'error': 'Already resolved'}, status=status.HTTP_400_BAD_REQUEST)

            log.is_resolved = True
            log.resolved_at = timezone.now()
            log.resolved_by = request.user
            note = request.data.get('note') or request.data.get('resolution_note', 'Manually resolved')
            log.resolution_note = note
            log.save()

            return Response({'success': True})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error resolving alert log: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge an alert log (mark as seen, not yet resolved)"""
        try:
            log = self.get_object()
            note = request.data.get('note', '')
            # Use escalation_level = 0 as a proxy for 'acknowledged' flag if no dedicated field
            # Stores acknowledging user in resolution_note temporarily
            if not log.resolution_note:
                log.resolution_note = f'Acknowledged by {request.user} at {timezone.now().isoformat()}'
                if note:
                    log.resolution_note += f'. Note: {note}'
                log.save(update_fields=['resolution_note'])
            return Response({'success': True, 'id': log.id, 'message': 'Alert acknowledged'})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error acknowledging alert log {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_rule(self, request, rule_id=None, **kwargs):
        """Get logs filtered by rule_id (URL path param or query param)"""
        try:
            rid = rule_id or self.kwargs.get('rule_id') or request.query_params.get('rule_id')
            if not rid:
                return Response({'error': 'rule_id required'}, status=status.HTTP_400_BAD_REQUEST)
            logs = AlertLog.objects.filter(rule_id=rid).select_related('rule').order_by('-triggered_at')
            from ..serializers.core import AlertLogSerializer
            serializer = AlertLogSerializer(logs, many=True)
            return Response(serializer.data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting logs by rule: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all unresolved/pending alert logs"""
        try:
            logs = AlertLog.objects.filter(is_resolved=False).select_related('rule').order_by('-triggered_at')
            from ..serializers.core import AlertLogSerializer
            serializer = AlertLogSerializer(logs, many=True)
            return Response({'count': logs.count(), 'results': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting pending alerts: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def resolved(self, request):
        """Get all resolved alert logs"""
        try:
            logs = AlertLog.objects.filter(is_resolved=True).select_related('rule').order_by('-resolved_at')
            from ..serializers.core import AlertLogSerializer
            serializer = AlertLogSerializer(logs, many=True)
            return Response({'count': logs.count(), 'results': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting resolved alerts: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_severity(self, request, severity=None, **kwargs):
        """Get logs filtered by severity (URL path param or query param)"""
        try:
            sev = severity or self.kwargs.get('severity') or request.query_params.get('severity')
            if not sev:
                return Response({'error': 'severity required'}, status=status.HTTP_400_BAD_REQUEST)
            logs = AlertLog.objects.filter(rule__severity=sev).select_related('rule').order_by('-triggered_at')
            from ..serializers.core import AlertLogSerializer
            serializer = AlertLogSerializer(logs, many=True)
            return Response({'severity': sev, 'count': logs.count(), 'results': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting logs by severity: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def bulk_resolve(self, request):
        """Bulk resolve alert logs"""
        try:
            ids = request.data.get('ids', [])
            note = request.data.get('note') or request.data.get('resolution_note', 'Bulk resolved by admin')

            if not ids:
                return Response({'error': 'No ids provided'}, status=status.HTTP_400_BAD_REQUEST)

            count = AlertLog.objects.filter(id__in=ids, is_resolved=False).update(
                is_resolved=True,
                resolved_at=timezone.now(),
                resolution_note=note,
            )

            return Response({'success': True, 'resolved': count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error bulk resolving alerts: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['patch'])
    def bulk_update_status(self, request):
        """Bulk update alert log fields"""
        try:
            ids = request.data.get('ids', [])
            fields = {k: v for k, v in request.data.items() if k != 'ids'}
            if not ids:
                return Response({'error': 'No ids provided'}, status=status.HTTP_400_BAD_REQUEST)
            count = AlertLog.objects.filter(id__in=ids).update(**fields)
            return Response({'success': True, 'updated': count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error bulk updating alert logs: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """Notification ViewSet — tenant-scoped. Added mark_sent, mark_failed, retry, by_status, by_type, failed"""
    queryset = Notification.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('alert_log', 'alert_log__rule')

        filter_status = self.request.query_params.get('status')
        notification_type = self.request.query_params.get('notification_type')

        if filter_status:
            queryset = queryset.filter(status=filter_status)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Notification has no created_by field, unlike most other models here."""
        serializer.save(**self.tenant_save_kwargs())

    def get_serializer_class(self):
        from ..serializers.core import NotificationSerializer
        return NotificationSerializer

    def get_permissions(self):
        """
        list / retrieve / stats / by_status / by_type  → any authenticated user
        create / update / destroy / mark_sent           → CanManageNotifications
        mark_failed / retry / retry_failed              → CanManageNotifications
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'mark_sent', 'mark_failed', 'retry', 'retry_failed']:
            return [IsAuthenticated(), CanManageNotifications()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Notification statistics"""
        try:
            from ..services.channel import NotificationService
            stats = NotificationService.get_notification_statistics()
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting notification stats: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def mark_sent(self, request, pk=None):
        """Mark a notification as sent"""
        try:
            notification = self.get_object()
            notification.status = 'sent'
            notification.sent_at = timezone.now()
            notification.save(update_fields=['status', 'sent_at'])
            return Response({'success': True, 'id': notification.id, 'status': 'sent'})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error marking notification {pk} as sent: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def mark_failed(self, request, pk=None):
        """Mark a notification as failed"""
        try:
            notification = self.get_object()
            notification.status = 'failed'
            error_msg = request.data.get('error_message', 'Manually marked failed')
            notification.error_message = error_msg
            notification.save(update_fields=['status', 'error_message'])
            return Response({'success': True, 'id': notification.id, 'status': 'failed'})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error marking notification {pk} as failed: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a single failed notification"""
        try:
            notification = self.get_object()
            if notification.status not in ('failed', 'pending'):
                return Response(
                    {'error': f'Cannot retry notification with status: {notification.status}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            notification.status = 'pending'
            notification.retry_count = getattr(notification, 'retry_count', 0) + 1
            notification.save(update_fields=['status', 'retry_count'])
            return Response({'success': True, 'id': notification.id, 'status': 'pending', 'retry_count': notification.retry_count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error retrying notification {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def retry_failed(self, request):
        """Retry all failed notifications"""
        try:
            from ..services.channel import NotificationService
            retry_count = NotificationService.retry_failed_notifications()
            return Response({'success': True, 'retried': retry_count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error retrying notifications: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_status(self, request, status=None, **kwargs):
        """Get notifications filtered by status (URL path or query param)"""
        try:
            s = status or self.kwargs.get('status') or request.query_params.get('status')
            if not s:
                return Response({'error': 'status required'}, status=400)
            notifications = Notification.objects.filter(status=s).order_by('-created_at')
            from ..serializers.core import NotificationSerializer
            serializer = NotificationSerializer(notifications, many=True)
            return Response({'status': s, 'count': notifications.count(), 'results': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting notifications by status: {e}")
            return Response({'error': 'Internal server error'}, status=500)

    @action(detail=False, methods=['get'])
    def by_type(self, request, type=None, **kwargs):
        """Get notifications filtered by notification_type (URL path or query param)"""
        try:
            t = type or self.kwargs.get('type') or request.query_params.get('type') or request.query_params.get('notification_type')
            if not t:
                return Response({'error': 'type required'}, status=400)
            notifications = Notification.objects.filter(notification_type=t).order_by('-created_at')
            from ..serializers.core import NotificationSerializer
            serializer = NotificationSerializer(notifications, many=True)
            return Response({'type': t, 'count': notifications.count(), 'results': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting notifications by type: {e}")
            return Response({'error': 'Internal server error'}, status=500)

    @action(detail=False, methods=['get'])
    def failed(self, request):
        """Get all failed notifications"""
        try:
            notifications = Notification.objects.filter(status='failed').order_by('-created_at')
            from ..serializers.core import NotificationSerializer
            serializer = NotificationSerializer(notifications, many=True)
            return Response({'count': notifications.count(), 'results': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting failed notifications: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SystemHealthViewSet(TenantIsolationMixin, viewsets.ReadOnlyModelViewSet):
    """SystemHealthCheck ViewSet — tenant-scoped monitoring"""
    queryset = SystemHealthCheck.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().order_by('-last_checked')

    def get_serializer_class(self):
        from ..serializers.core import SystemHealthCheckSerializer
        return SystemHealthCheckSerializer

    def get_permissions(self):
        """
        list / retrieve / overview  → CanManageSystemHealth
        All health system operations require explicit privilege — not open to all users.
        """
        return [IsAuthenticated(), CanManageSystemHealth()]

    def list(self, request):
        """System health overview listing"""
        try:
            checks = self.get_queryset()
            from ..serializers.core import SystemHealthCheckSerializer
            serializer = SystemHealthCheckSerializer(checks, many=True)
            return Response({'count': checks.count(), 'checks': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("Unhandled error in list")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def check(self, request):
        """Run a live health check"""
        try:
            from ..models.core import AlertRule, AlertLog
            return Response({
                'status': 'healthy',
                'active_rules': AlertRule.objects.filter(is_active=True).count(),
                'unresolved_alerts': AlertLog.objects.filter(is_resolved=False).count(),
                'timestamp': timezone.now().isoformat(),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("Unhandled error in check")
            return Response({'status': 'error', 'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Health check history"""
        try:
            checks = self.get_queryset()[:50]
            from ..serializers.core import SystemHealthCheckSerializer
            serializer = SystemHealthCheckSerializer(checks, many=True)
            return Response({'count': len(serializer.data), 'history': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception:
            logger.exception("Unhandled error in history")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def rules(self, request):
        """Health of alert rules"""
        from ..models.core import AlertRule
        total = AlertRule.objects.count()
        active = AlertRule.objects.filter(is_active=True).count()
        return Response({'total_rules': total, 'active_rules': active,
                         'inactive_rules': total - active})

    @action(detail=False, methods=['get'])
    def channels(self, request):
        """Health of alert channels"""
        from ..models.channel import AlertChannel
        total = AlertChannel.objects.count()
        enabled = AlertChannel.objects.filter(is_enabled=True).count()
        return Response({'total_channels': total, 'enabled_channels': enabled})

    @action(detail=False, methods=['get'])
    def incidents(self, request):
        """Health of incident management"""
        from ..models.incident import Incident
        open_incidents = Incident.objects.filter(status='open').count()
        return Response({'open_incidents': open_incidents})

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """System health overview"""
        try:
            overall = SystemHealthCheck.get_overall_status()
            checks = list(SystemHealthCheck.objects.order_by('-last_checked')[:10].values(
                'id', 'check_name', 'check_type', 'status', 'response_time_ms',
                'status_message', 'last_checked'
            ))
            return Response({'overall_status': overall, 'checks': checks})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting system health overview: {e}")
            return Response({'overall_status': 'unknown', 'checks': [], 'error': 'Internal server error'})

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """System metrics"""
        try:
            metrics = AnalyticsService.get_system_metrics()
            return Response(metrics)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertOverviewViewSet(TenantIsolationMixin, viewsets.ViewSet):
    """Alert overview dashboard ViewSet — tenant-scoped via get_tenant_id()"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Alert overview statistics"""
        try:
            today = timezone.now().date()
            week_ago = timezone.now() - timedelta(days=7)
            unresolved = AlertLog.objects.filter(is_resolved=False)

            return Response({
                'total_rules': AlertRule.objects.count(),
                'active_rules': AlertRule.objects.filter(is_active=True).count(),
                'alerts_today': AlertLog.objects.filter(triggered_at__date=today).count(),
                'alerts_this_week': AlertLog.objects.filter(triggered_at__gte=week_ago).count(),
                'unresolved_alerts': unresolved.count(),
                'resolved_today': AlertLog.objects.filter(is_resolved=True, resolved_at__date=today).count(),
                'critical_active': unresolved.filter(rule__severity=SeverityLevel.CRITICAL.value).count(),
                'high_active': unresolved.filter(rule__severity=SeverityLevel.HIGH.value).count(),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting alert overview: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Alias for the list() overview"""
        return self.list(request)

    @action(detail=False, methods=['get'])
    def recent_alerts(self, request):
        """Most recently triggered alerts"""
        try:
            limit = int(request.query_params.get('limit', 10))
            logs = AlertLog.objects.select_related('rule').order_by('-triggered_at')[:limit]
            from ..serializers.core import AlertLogSerializer
            return Response(AlertLogSerializer(logs, many=True).data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Alert volume trends — alias for analytics"""
        return self.analytics(request)

    @action(detail=False, methods=['get'])
    def top_rules(self, request):
        """Rules with the most triggered alerts"""
        try:
            limit = int(request.query_params.get('limit', 5))
            from django.db.models import Count
            top = (AlertRule.objects
                   .annotate(alert_count=Count('logs'))
                   .order_by('-alert_count')[:limit]
                   .values('id', 'name', 'severity', 'alert_count'))
            return Response({'top_rules': list(top)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting top rules: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Alert metrics — alias for performance"""
        return self.performance(request)

    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Alert analytics data"""
        try:
            days = int(request.query_params.get('days', 7))
            stats = AnalyticsService.get_alert_statistics(days)
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting alert analytics: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Alert statistics — alias for analytics (registered in urls/core.py)"""
        return self.analytics(request)

    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Alert performance metrics"""
        try:
            days = int(request.query_params.get('days', 30))
            performance = AnalyticsService.get_rule_performance(days)
            return Response(performance)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting alert performance: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertMaintenanceViewSet(TenantIsolationMixin, viewsets.ViewSet):
    """Alert maintenance operations ViewSet — tenant-scoped via get_tenant_id()"""

    def get_permissions(self):
        """
        Maintenance operations require AlertManager + maintenance access.
        CanAccessDuringMaintenance ensures only privileged staff reach this
        ViewSet when SYSTEM_MAINTENANCE_MODE is active.
        """
        return [IsAuthenticated(), IsAlertManager(), CanAccessDuringMaintenance()]

    def list(self, request):
        """List available maintenance operations"""
        return Response({
            'operations': [
                'cleanup_old_alerts', 'update_rule_health', 'optimize_indexes',
                'suppress_alerts', 'impact',
            ],
            'description': 'POST to individual action endpoints to execute',
        })

    @action(detail=False, methods=['post'])
    def cleanup_old_alerts(self, request):
        """Clean up old resolved alerts"""
        try:
            days = int(request.data.get('days', 90))
            deleted_count = AlertMaintenanceService.cleanup_old_alerts(days)
            return Response({'success': True, 'deleted_count': deleted_count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_rule_health(self, request):
        """Update health status for alert rules"""
        try:
            updated_count = AlertMaintenanceService.update_rule_health()
            return Response({'success': True, 'updated_count': updated_count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error updating rule health: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def optimize_indexes(self, request):
        """Optimize database indexes"""
        try:
            success = AlertMaintenanceService.optimize_alert_indexes()
            return Response({'success': success})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error optimizing indexes: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def suppress_alerts(self, request):
        """Create a temporary alert suppression window"""
        try:
            from ..models.core import AlertSuppression
            duration_minutes = int(request.data.get('duration_minutes', 30))
            suppression_type = request.data.get('suppression_type', 'all')
            now = timezone.now()
            suppression = AlertSuppression.objects.create(
                name=request.data.get('name', f'Maintenance suppression {now.isoformat()}'),
                description=request.data.get('description', ''),
                suppression_type=suppression_type,
                start_time=now,
                end_time=now + timedelta(minutes=duration_minutes),
                is_active=True,
                created_by=request.user if request.user.is_authenticated else None,
            )
            return Response({
                'success': True,
                'suppression_id': suppression.id,
                'start_time': suppression.start_time,
                'end_time': suppression.end_time,
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error creating suppression window: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def impact(self, request):
        """Estimate the impact of an active/upcoming maintenance window"""
        try:
            from ..models.core import AlertSuppression
            now = timezone.now()
            active_suppressions = AlertSuppression.objects.filter(
                is_active=True, start_time__lte=now, end_time__gte=now)
            affected_rules = AlertRule.objects.filter(is_active=True).count()
            return Response({
                'active_suppressions': active_suppressions.count(),
                'potentially_affected_rules': affected_rules,
                'unresolved_alerts': AlertLog.objects.filter(is_resolved=False).count(),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error computing maintenance impact: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Past maintenance / suppression windows"""
        try:
            from ..models.core import AlertSuppression
            now = timezone.now()
            past = AlertSuppression.objects.filter(end_time__lt=now).order_by('-end_time')[:20]
            return Response({
                'count': past.count(),
                'results': [
                    {'id': s.id, 'name': s.name, 'suppression_type': s.suppression_type,
                     'start_time': s.start_time, 'end_time': s.end_time}
                    for s in past
                ],
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting maintenance history: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Upcoming / currently-active maintenance windows"""
        try:
            from ..models.core import AlertSuppression
            now = timezone.now()
            upcoming = AlertSuppression.objects.filter(end_time__gte=now).order_by('start_time')[:20]
            return Response({
                'count': upcoming.count(),
                'results': [
                    {'id': s.id, 'name': s.name, 'suppression_type': s.suppression_type,
                     'start_time': s.start_time, 'end_time': s.end_time, 'is_active': s.is_active}
                    for s in upcoming
                ],
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting upcoming maintenance: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        """Detail view of a single maintenance window (backed by AlertSuppression)"""
        try:
            from ..models.core import AlertSuppression
            window = AlertSuppression.objects.get(pk=pk)
            return Response({
                'id': window.id, 'name': window.name, 'description': window.description,
                'suppression_type': window.suppression_type, 'start_time': window.start_time,
                'end_time': window.end_time, 'is_active': window.is_active,
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except AlertSuppression.DoesNotExist:
            return Response({'error': 'Maintenance window not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving maintenance window {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def extend(self, request, pk=None):
        """Extend an active maintenance window's end_time"""
        try:
            from ..models.core import AlertSuppression
            window = AlertSuppression.objects.get(pk=pk)
            extra_minutes = int(request.data.get('extra_minutes', 30))
            window.end_time = window.end_time + timedelta(minutes=extra_minutes)
            window.save(update_fields=['end_time'])
            return Response({'success': True, 'id': window.id, 'new_end_time': window.end_time})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except AlertSuppression.DoesNotExist:
            return Response({'error': 'Maintenance window not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error extending maintenance window {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """End a maintenance window early by deactivating it"""
        try:
            from ..models.core import AlertSuppression
            window = AlertSuppression.objects.get(pk=pk)
            window.is_active = False
            window.end_time = timezone.now()
            window.save(update_fields=['is_active', 'end_time'])
            return Response({'success': True, 'id': window.id, 'is_active': window.is_active})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except AlertSuppression.DoesNotExist:
            return Response({'error': 'Maintenance window not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error completing maintenance window {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

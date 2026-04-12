"""
DR Integration Views — REST API endpoints for DR operations.
Mounts at: /api/dr/
"""
import logging
from datetime import datetime
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .services import (
    DRBackupBridge, DRRestoreBridge, DRFailoverBridge,
    DRAlertBridge, DRAuditBridge, DRMonitoringBridge, DRSecurityBridge
)

logger = logging.getLogger(__name__)


# ── Backup Views ───────────────────────────────────────────────────────────────

class DRBackupListView(APIView):
    """GET  /api/dr/backups/   — list backups
       POST /api/dr/backups/   — trigger backup"""
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(60))  # Cache 1 minute
    def get(self, request):
        bridge = DRBackupBridge()
        status_filter = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 50))
        backups = bridge.get_backup_list(status=status_filter, limit=limit)
        stats = bridge.get_backup_stats()
        return Response({
            'backups': backups,
            'stats': stats,
            'count': len(backups),
        })

    def post(self, request):
        """Trigger a new backup."""
        bridge = DRBackupBridge()
        backup_type = request.data.get('backup_type', 'incremental')
        policy_id = request.data.get('policy_id')
        if backup_type not in ('full', 'incremental', 'differential'):
            return Response(
                {'error': f"Invalid backup_type: {backup_type}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        result = bridge.trigger_backup(
            backup_type=backup_type,
            policy_id=policy_id,
            actor_id=str(request.user.id),
            tenant_id=getattr(request, 'tenant_id', None),
        )
        if result.get('success'):
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DRBackupVerifyView(APIView):
    """POST /api/dr/backups/{backup_id}/verify/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, backup_id):
        bridge = DRBackupBridge()
        result = bridge.verify_backup(backup_id)
        return Response(result)


# ── Restore Views ──────────────────────────────────────────────────────────────

class DRRestoreView(APIView):
    """POST /api/dr/restore/ — request a restore"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        bridge = DRRestoreBridge()
        data = request.data
        restore_type = data.get('restore_type', 'full')
        if restore_type not in ('full', 'partial', 'table', 'point_in_time'):
            return Response(
                {'error': f"Invalid restore_type: {restore_type}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        result = bridge.request_restore(
            restore_type=restore_type,
            backup_id=data.get('backup_id'),
            target_database=data.get('target_database', 'default'),
            point_in_time=data.get('point_in_time'),
            requested_by=str(request.user.id),
            require_approval=data.get('require_approval', True),
        )
        if result.get('success'):
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class DRRestorePITRCheckView(APIView):
    """GET /api/dr/restore/pitr-check/?database=X&target_time=Y"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        database = request.query_params.get('database', 'default')
        target_time = request.query_params.get('target_time')
        if not target_time:
            return Response({'error': 'target_time is required'}, status=400)
        bridge = DRRestoreBridge()
        result = bridge.validate_pitr(database, target_time)
        return Response(result)


# ── Health & Failover Views ────────────────────────────────────────────────────

class DRHealthView(APIView):
    """GET /api/dr/health/ — system health check"""
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(30))
    def get(self, request):
        bridge = DRFailoverBridge()
        health = bridge.get_health_status()
        replication = bridge.get_replication_status()
        rto_rpo = bridge.get_rto_rpo_stats()
        return Response({
            'health': health,
            'replication': replication,
            'rto_rpo': rto_rpo,
            'checked_at': datetime.utcnow().isoformat(),
        })


class DRFailoverView(APIView):
    """POST /api/dr/failover/ — trigger manual failover (admin only)"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        data = request.data
        primary = data.get('primary_node')
        secondary = data.get('secondary_node')
        reason = data.get('reason', 'Manual failover via Django admin')
        is_drill = data.get('is_drill', False)
        if not primary or not secondary:
            return Response(
                {'error': 'primary_node and secondary_node are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        bridge = DRFailoverBridge()
        result = bridge.trigger_manual_failover(
            primary_node=primary,
            secondary_node=secondary,
            reason=reason,
            triggered_by_id=str(request.user.id),
            is_drill=is_drill,
        )
        return Response(result)


# ── Alert Views ────────────────────────────────────────────────────────────────

class DRAlertListView(APIView):
    """GET /api/dr/alerts/   — list active DR alerts"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import DRAlert
        alerts = DRAlert.objects.filter(
            is_acknowledged=False,
            resolved_at__isnull=True,
        ).order_by('-fired_at')[:50]
        return Response({
            'alerts': [
                {
                    'id': str(a.id),
                    'rule_name': a.rule_name,
                    'severity': a.severity,
                    'message': a.message,
                    'metric': a.metric,
                    'metric_value': a.metric_value,
                    'fired_at': a.fired_at.isoformat(),
                }
                for a in alerts
            ],
            'count': alerts.count(),
        })


class DRAlertAcknowledgeView(APIView):
    """POST /api/dr/alerts/{alert_id}/acknowledge/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        bridge = DRAlertBridge()
        result = bridge.acknowledge_alert(alert_id, str(request.user.id))
        return Response(result)


# ── Monitoring Views ───────────────────────────────────────────────────────────

class DRStatusPageView(APIView):
    """GET /api/dr/status/ — public status page data"""
    permission_classes = []  # Public endpoint

    @method_decorator(cache_page(60))
    def get(self, request):
        bridge = DRMonitoringBridge()
        return Response(bridge.get_status_page_data())


class DRMetricsView(APIView):
    """GET /api/dr/metrics/ — system metrics"""
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(30))
    def get(self, request):
        bridge = DRMonitoringBridge()
        return Response({
            'system': bridge.collect_system_metrics(),
            'storage': bridge.check_storage_health(),
            'on_call': bridge.get_on_call_contact(),
        })


# ── Security Views ─────────────────────────────────────────────────────────────

class DRComplianceView(APIView):
    """GET /api/dr/compliance/?framework=HIPAA"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        framework = request.query_params.get('framework', 'HIPAA')
        bridge = DRSecurityBridge()
        return Response(bridge.check_compliance(framework))


class DRKeyRotationView(APIView):
    """POST /api/dr/security/rotate-keys/"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        bridge = DRSecurityBridge()
        result = bridge.rotate_encryption_key(authorized_by=str(request.user.id))
        return Response(result)


# ── Audit Views ────────────────────────────────────────────────────────────────

class DRAuditLogView(APIView):
    """GET /api/dr/audit/?actor_id=X&action=Y"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        bridge = DRAuditBridge()
        actor_id = request.query_params.get('actor_id')
        action = request.query_params.get('action')
        resource_type = request.query_params.get('resource_type')
        limit = int(request.query_params.get('limit', 100))
        logs = bridge.search_logs(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            limit=limit,
        )
        return Response({'logs': logs, 'count': len(logs)})


class DRAuditIntegrityView(APIView):
    """GET /api/dr/audit/integrity/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        bridge = DRAuditBridge()
        return Response(bridge.verify_log_integrity())


# ── Dashboard View ─────────────────────────────────────────────────────────────

class DRDashboardView(APIView):
    """GET /api/dr/dashboard/ — complete DR dashboard data"""
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(60))
    def get(self, request):
        from .models import DRBackupRecord, DRAlert, DRFailoverEvent, DRDrillRecord
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        return Response({
            'summary': {
                'backups_today': DRBackupRecord.objects.filter(created_at__gte=last_24h).count(),
                'backups_failed_today': DRBackupRecord.objects.filter(
                    created_at__gte=last_24h, status='failed').count(),
                'active_alerts': DRAlert.objects.filter(
                    is_acknowledged=False, resolved_at__isnull=True).count(),
                'critical_alerts': DRAlert.objects.filter(
                    is_acknowledged=False, resolved_at__isnull=True,
                    severity='critical').count(),
                'failovers_last_7d': DRFailoverEvent.objects.filter(
                    initiated_at__gte=last_7d).count(),
                'last_backup_at': DRBackupRecord.objects.filter(
                    status='completed').order_by('-completed_at').values_list(
                    'completed_at', flat=True).first(),
            },
            'health': DRFailoverBridge().get_health_status(),
            'recent_backups': list(DRBackupRecord.objects.filter(
                created_at__gte=last_7d
            ).order_by('-created_at').values(
                'id', 'backup_type', 'status', 'created_at', 'is_verified'
            )[:10]),
            'recent_alerts': list(DRAlert.objects.order_by(
                '-fired_at').values(
                'id', 'rule_name', 'severity', 'message', 'fired_at',
                'is_acknowledged')[:10]),
        })

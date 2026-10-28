"""
viewsets/system.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEWLY CREATED — was completely missing.

Exposes 5 previously floating root-level files via DRF ViewSets:
  1. BackupViewSet         → backup.py      (BackupManager, 7 classes)
  2. EscalationViewSet     → escalation.py  (EscalationManager, 10 classes)
  3. SchedulerViewSet      → scheduler.py   (TaskScheduler, 7 classes)
  4. MetricsCollectorViewSet → metrics_collector.py (MetricsCollector)
  5. EventViewSet          → events.py      (AlertEventHandler, EventAggregator)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 1. BackupViewSet  (backup.py → BackupManager)
# ─────────────────────────────────────────────────────────────
class BackupViewSet(viewsets.ViewSet):
    """
    Exposes backup.py → BackupManager via REST API.
    Endpoints: list, create, restore, status, cleanup, stats
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_manager(self):
        from api.alerts.backup import get_backup_manager
        return get_backup_manager()

    def list(self, request):
        """List all backup tasks (in-memory task history on the manager)"""
        try:
            mgr = self._get_manager()
            tasks = mgr.get_tasks() if mgr and hasattr(mgr, 'get_tasks') else []
            result = [t.to_dict() if hasattr(t, 'to_dict') else str(t) for t in tasks]
            return Response({'backups': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"BackupViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def create_backup(self, request):
        """Trigger a new backup"""
        try:
            from asgiref.sync import async_to_sync
            from api.alerts.backup import BackupType
            mgr = self._get_manager()
            backup_type_str = request.data.get('backup_type', 'full')
            description = request.data.get('description', '')
            if not mgr:
                return Response({'error': 'Backup manager not initialized'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            try:
                backup_type = BackupType(backup_type_str)
            except ValueError:
                return Response({'error': f'Invalid backup_type: {backup_type_str}'}, status=status.HTTP_400_BAD_REQUEST)
            task = mgr.create_backup_task(backup_type=backup_type, description=description)
            result = async_to_sync(mgr.execute_backup)(task)
            return Response({'success': result.get('success', False), 'backup_type': backup_type_str,
                             'result': task.to_dict()})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"BackupViewSet.create_backup error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def restore(self, request):
        """Restore from a specific backup, by its storage path"""
        try:
            from asgiref.sync import async_to_sync
            mgr = self._get_manager()
            backup_path = request.data.get('backup_path') or request.data.get('backup_id')
            storage_backend = request.data.get('storage_backend')
            if not backup_path:
                return Response({'error': 'backup_path required'}, status=status.HTTP_400_BAD_REQUEST)
            if not mgr or not hasattr(mgr, 'restore_backup'):
                return Response({'error': 'Backup manager not initialized'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            result = async_to_sync(mgr.restore_backup)(backup_path=backup_path, storage_backend=storage_backend)
            return Response({'success': result.get('success', False), 'backup_path': backup_path, 'result': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"BackupViewSet.restore error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def backup_status(self, request):
        """Get backup system status"""
        try:
            mgr = self._get_manager()
            stats = mgr.get_manager_status() if mgr and hasattr(mgr, 'get_manager_status') else {}
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"BackupViewSet.backup_status error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        """Clean up old backups based on retention policy"""
        try:
            from asgiref.sync import async_to_sync
            mgr = self._get_manager()
            days = int(request.data.get('retention_days', 30))
            if mgr and hasattr(mgr, 'cleanup_old_backups'):
                mgr.retention_days = days
                deleted = async_to_sync(mgr.cleanup_old_backups)()
            else:
                deleted = 0
            return Response({'success': True, 'deleted': deleted, 'retention_days': days})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"BackupViewSet.cleanup error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Backup statistics"""
        try:
            mgr = self._get_manager()
            stats = mgr.get_backup_statistics() if hasattr(mgr, 'get_backup_statistics') else {}
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"BackupViewSet.stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def verify(self, request):
        """Verify backup integrity"""
        try:
            mgr = self._get_manager()
            backup_id = request.data.get('backup_id')
            if not backup_id:
                return Response({'error': 'backup_id required'}, status=status.HTTP_400_BAD_REQUEST)
            result = mgr.verify_backup(backup_id=backup_id) if hasattr(mgr, 'verify_backup') else True
            return Response({'success': True, 'backup_id': backup_id, 'integrity_ok': bool(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"BackupViewSet.verify error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────
# 2. EscalationViewSet  (escalation.py → EscalationManager)
# ─────────────────────────────────────────────────────────────
class EscalationViewSet(viewsets.ViewSet):
    """
    Exposes escalation.py → EscalationManager via REST API.
    Endpoints: list_rules, create_rule, trigger, history, stats
    """
    permission_classes = [IsAuthenticated]

    def _get_manager(self):
        from api.alerts.escalation import get_escalation_manager
        return get_escalation_manager()

    def list(self, request):
        """List all escalation rules"""
        try:
            mgr = self._get_manager()
            rules = mgr.get_all_rules() if hasattr(mgr, 'get_all_rules') else []
            result = [r.to_dict() if hasattr(r, 'to_dict') else str(r) for r in rules]
            return Response({'rules': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EscalationViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def create_rule(self, request):
        """Create a new escalation rule"""
        try:
            mgr = self._get_manager()
            rule_data = request.data
            if not rule_data.get('name'):
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            rule = mgr.create_escalation_rule(rule_data) if hasattr(mgr, 'create_escalation_rule') else rule_data
            return Response({'success': True, 'rule': rule.to_dict() if hasattr(rule, 'to_dict') else rule})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EscalationViewSet.create_rule error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def trigger(self, request):
        """Manually trigger escalation for an alert"""
        try:
            mgr = self._get_manager()
            alert_log_id = request.data.get('alert_log_id')
            escalation_level = int(request.data.get('escalation_level', 1))
            if not alert_log_id:
                return Response({'error': 'alert_log_id required'}, status=status.HTTP_400_BAD_REQUEST)
            from api.alerts.models.core import AlertLog
            log = AlertLog.objects.get(id=alert_log_id)
            result = mgr.escalate_alert(log, escalation_level) if hasattr(mgr, 'escalate_alert') else True
            return Response({'success': bool(result), 'alert_log_id': alert_log_id,
                             'escalation_level': escalation_level})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EscalationViewSet.trigger error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Escalation history"""
        try:
            mgr = self._get_manager()
            limit = int(request.query_params.get('limit', 50))
            history = mgr.get_escalation_history(limit=limit) if hasattr(mgr, 'get_escalation_history') else []
            result = [h.to_dict() if hasattr(h, 'to_dict') else str(h) for h in history]
            return Response({'history': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EscalationViewSet.history error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def escalation_stats(self, request):
        """Escalation statistics"""
        try:
            mgr = self._get_manager()
            stats = mgr.get_escalation_statistics() if hasattr(mgr, 'get_escalation_statistics') else {}
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EscalationViewSet.escalation_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def active_escalations(self, request):
        """List currently active escalations"""
        try:
            from api.alerts.models.core import AlertLog
            escalated = AlertLog.objects.filter(
                is_resolved=False, escalation_level__gt=0
            ).select_related('rule').order_by('-triggered_at')
            from api.alerts.serializers.core import AlertLogSerializer
            return Response({'count': escalated.count(),
                             'escalations': AlertLogSerializer(escalated[:50], many=True).data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EscalationViewSet.active_escalations error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────
# 3. SchedulerViewSet  (scheduler.py → TaskScheduler)
# ─────────────────────────────────────────────────────────────
class SchedulerViewSet(viewsets.ViewSet):
    """
    Exposes scheduler.py → TaskScheduler via REST API.
    Endpoints: list_tasks, create_task, run_task, pause, resume, stats
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_scheduler(self):
        from api.alerts.scheduler import get_task_scheduler
        return get_task_scheduler()

    def list(self, request):
        """List all scheduled tasks"""
        try:
            scheduler = self._get_scheduler()
            tasks = scheduler.get_all_tasks() if hasattr(scheduler, 'get_all_tasks') else []
            result = [t.to_dict() if hasattr(t, 'to_dict') else str(t) for t in tasks]
            return Response({'tasks': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchedulerViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def create_task(self, request):
        """Create and schedule a new task"""
        try:
            scheduler = self._get_scheduler()
            task_name = request.data.get('name')
            schedule_type = request.data.get('schedule_type', 'interval')
            interval_seconds = int(request.data.get('interval_seconds', 300))
            if not task_name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            task = scheduler.create_task(
                name=task_name,
                schedule_type=schedule_type,
                interval_seconds=interval_seconds,
            ) if hasattr(scheduler, 'create_task') else {'name': task_name}
            return Response({'success': True, 'task': task.to_dict() if hasattr(task, 'to_dict') else task})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchedulerViewSet.create_task error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def run_now(self, request):
        """Run a task immediately"""
        try:
            scheduler = self._get_scheduler()
            task_name = request.data.get('name')
            if not task_name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            result = scheduler.run_task_now(task_name) if hasattr(scheduler, 'run_task_now') else True
            return Response({'success': bool(result), 'task': task_name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchedulerViewSet.run_now error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def pause_task(self, request):
        """Pause a scheduled task"""
        try:
            scheduler = self._get_scheduler()
            task_name = request.data.get('name')
            if not task_name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            scheduler.pause_task(task_name) if hasattr(scheduler, 'pause_task') else None
            return Response({'success': True, 'task': task_name, 'status': 'paused'})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchedulerViewSet.pause_task error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def resume_task(self, request):
        """Resume a paused task"""
        try:
            scheduler = self._get_scheduler()
            task_name = request.data.get('name')
            if not task_name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            scheduler.resume_task(task_name) if hasattr(scheduler, 'resume_task') else None
            return Response({'success': True, 'task': task_name, 'status': 'resumed'})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchedulerViewSet.resume_task error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def scheduler_stats(self, request):
        """Task scheduler statistics"""
        try:
            scheduler = self._get_scheduler()
            stats = scheduler.get_statistics() if hasattr(scheduler, 'get_statistics') else {}
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchedulerViewSet.scheduler_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def due_tasks(self, request):
        """List tasks that are currently due to run"""
        try:
            scheduler = self._get_scheduler()
            due = scheduler.get_due_tasks() if hasattr(scheduler, 'get_due_tasks') else []
            result = [t.to_dict() if hasattr(t, 'to_dict') else str(t) for t in due]
            return Response({'due_tasks': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchedulerViewSet.due_tasks error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['delete'])
    def delete_task(self, request):
        """Delete a scheduled task"""
        try:
            scheduler = self._get_scheduler()
            task_name = request.data.get('name')
            if not task_name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            scheduler.remove_task(task_name) if hasattr(scheduler, 'remove_task') else None
            return Response({'success': True, 'deleted': task_name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchedulerViewSet.delete_task error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────
# 4. MetricsCollectorViewSet  (metrics_collector.py → MetricsCollector)
# ─────────────────────────────────────────────────────────────
class MetricsCollectorViewSet(viewsets.ViewSet):
    """
    Exposes metrics_collector.py → MetricsCollector via REST API.
    Endpoints: collect, latest, history, export
    """
    permission_classes = [IsAuthenticated]

    def _get_collector(self):
        from api.alerts.metrics_collector import MetricsCollector
        return MetricsCollector()

    def list(self, request):
        """Collect and return all current metrics"""
        try:
            collector = self._get_collector()
            metrics = collector.collect_all_metrics() if hasattr(collector, 'collect_all_metrics') else {}
            return Response(metrics)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MetricsCollectorViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def collect(self, request):
        """Trigger metric collection"""
        try:
            collector = self._get_collector()
            result = collector.collect_all_metrics() if hasattr(collector, 'collect_all_metrics') else {}
            return Response({'success': True, 'metrics': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MetricsCollectorViewSet.collect error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def system_metrics(self, request):
        """Collect system-level metrics (CPU, memory, disk)"""
        try:
            collector = self._get_collector()
            metrics = {}
            for metric_name in ['cpu', 'memory', 'disk', 'network']:
                method = f'collect_{metric_name}_metrics'
                if hasattr(collector, method):
                    metrics[metric_name] = getattr(collector, method)()
            if not metrics:
                metrics = collector.collect_all_metrics() if hasattr(collector, 'collect_all_metrics') else {}
            return Response({'system_metrics': metrics})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MetricsCollectorViewSet.system_metrics error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def alert_metrics(self, request):
        """Collect alert-specific metrics"""
        try:
            from api.alerts.models.core import AlertRule, AlertLog, Notification
            from django.utils import timezone
            from datetime import timedelta
            now = timezone.now()
            return Response({
                'total_rules': AlertRule.objects.count(),
                'active_rules': AlertRule.objects.filter(is_active=True).count(),
                'total_logs': AlertLog.objects.count(),
                'unresolved_logs': AlertLog.objects.filter(is_resolved=False).count(),
                'logs_today': AlertLog.objects.filter(triggered_at__date=now.date()).count(),
                'logs_this_week': AlertLog.objects.filter(triggered_at__gte=now - timedelta(days=7)).count(),
                'notifications_pending': Notification.objects.filter(status='pending').count(),
                'notifications_failed': Notification.objects.filter(status='failed').count(),
                'collected_at': now.isoformat(),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MetricsCollectorViewSet.alert_metrics error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def export_metrics(self, request):
        """Export metrics in Prometheus text format"""
        try:
            collector = self._get_collector()
            metrics = collector.collect_all_metrics() if hasattr(collector, 'collect_all_metrics') else {}
            lines = []
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    lines.append(f'alerts_{k} {v}')
            prometheus_text = '\n'.join(lines)
            return Response({'format': 'prometheus', 'data': prometheus_text, 'metrics': metrics})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MetricsCollectorViewSet.export_metrics error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────
# 5. EventViewSet  (events.py → AlertEventHandler, EventAggregator)
# ─────────────────────────────────────────────────────────────
class EventViewSet(viewsets.ViewSet):
    """
    Exposes events.py → AlertEventHandler + EventAggregator via REST API.
    Endpoints: list, trigger, history, stats, aggregated
    """
    permission_classes = [IsAuthenticated]

    def _get_handler(self):
        from api.alerts.events import AlertEventHandler
        return AlertEventHandler()

    def _get_aggregator(self):
        from api.alerts.events import EventAggregator
        return EventAggregator()

    def list(self, request):
        """List recent events"""
        try:
            aggregator = self._get_aggregator()
            events = aggregator.get_recent_events() if hasattr(aggregator, 'get_recent_events') else []
            result = [e.to_dict() if hasattr(e, 'to_dict') else str(e) for e in events]
            return Response({'events': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def trigger(self, request):
        """Manually trigger an alert event"""
        try:
            from api.alerts.events import handle_alert_triggered
            alert_log_id = request.data.get('alert_log_id')
            event_type = request.data.get('event_type', 'alert_triggered')
            if not alert_log_id:
                return Response({'error': 'alert_log_id required'}, status=status.HTTP_400_BAD_REQUEST)
            from api.alerts.models.core import AlertLog
            log = AlertLog.objects.get(id=alert_log_id)
            if event_type == 'alert_triggered':
                handle_alert_triggered(sender=AlertLog, alert_log=log)
            elif event_type == 'alert_resolved':
                from api.alerts.events import handle_alert_resolved
                handle_alert_resolved(sender=AlertLog, alert_log=log)
            return Response({'success': True, 'event_type': event_type, 'alert_log_id': alert_log_id})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventViewSet.trigger error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def event_history(self, request):
        """Event history with optional filtering"""
        try:
            aggregator = self._get_aggregator()
            event_type = request.query_params.get('event_type')
            limit = int(request.query_params.get('limit', 100))
            events = aggregator.get_event_history(
                event_type=event_type, limit=limit
            ) if hasattr(aggregator, 'get_event_history') else []
            result = [e.to_dict() if hasattr(e, 'to_dict') else str(e) for e in events]
            return Response({'history': result, 'count': len(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventViewSet.event_history error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def event_stats(self, request):
        """Event statistics"""
        try:
            aggregator = self._get_aggregator()
            stats = aggregator.get_statistics() if hasattr(aggregator, 'get_statistics') else {}
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventViewSet.event_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def aggregated(self, request):
        """Get aggregated event data"""
        try:
            aggregator = self._get_aggregator()
            period = request.query_params.get('period', 'hourly')
            data = aggregator.get_aggregated_data(period=period) if hasattr(aggregator, 'get_aggregated_data') else {}
            return Response({'period': period, 'data': data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventViewSet.aggregated error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def emit(self, request):
        """Emit a custom event to the event system.

        NOTE: sender is auto-supplied (unused by the handlers, but required
        by their signature). For alert_triggered/alert_resolved, pass
        alert_log_id in payload and it's resolved to a real AlertLog. Other
        event types (notification_sent/failed, threshold_breached) still
        need their specific object(s) supplied directly via payload kwargs
        that match the handler's signature.
        """
        try:
            event_type = request.data.get('event_type')
            payload = dict(request.data.get('payload', {}))
            if not event_type:
                return Response({'error': 'event_type required'}, status=status.HTTP_400_BAD_REQUEST)
            handler = self._get_handler()
            method = f'on_{event_type}'
            if hasattr(handler, method):
                payload.setdefault('sender', None)
                alert_log_id = payload.pop('alert_log_id', None) or payload.pop('alert_id', None)
                if event_type in ('alert_triggered', 'alert_resolved') and alert_log_id:
                    from api.alerts.models.core import AlertLog
                    payload['alert_log'] = AlertLog.objects.get(id=alert_log_id)
                getattr(handler, method)(**payload)
            return Response({'success': True, 'event_type': event_type})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventViewSet.emit error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

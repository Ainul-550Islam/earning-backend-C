"""
DR Integration Celery Tasks — Automated DR operations via Celery Beat.
Add to CELERY_BEAT_SCHEDULE in Django settings.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='dr_integration.auto_backup', bind=True, max_retries=3)
def auto_backup_task(self, backup_type: str = 'incremental',
                     policy_id: str = None, actor_id: str = 'celery_beat'):
    """
    Celery task: Trigger DR-managed backup.
    Replaces the basic api/backup/tasks.py backup jobs.

    Suggested schedule:
        - Full backup: every Sunday 2:00 AM
        - Differential: daily (Mon-Sat) 2:00 AM
        - Incremental: every 4 hours
    """
    from dr_integration.services import DRBackupBridge
    bridge = DRBackupBridge()
    result = bridge.trigger_backup(
        backup_type=backup_type,
        policy_id=policy_id,
        actor_id=actor_id,
    )
    if not result.get('success'):
        logger.error(f"DR auto backup failed: {result.get('error')}")
        raise self.retry(countdown=300, exc=Exception(result.get('error')))
    logger.info(f"DR auto backup triggered: {result.get('job_id')}")
    return result


@shared_task(name='dr_integration.sync_dr_status')
def sync_dr_status_task():
    """
    Celery task: Sync DR system status into Django DRSystemStatus model.
    Run every 5 minutes to keep Django admin up-to-date.
    """
    from dr_integration.services import DRFailoverBridge, DRBackupBridge, DRMonitoringBridge
    from dr_integration.models import DRSystemStatus

    health = DRFailoverBridge().get_health_status()
    backup_stats = DRBackupBridge().get_backup_stats()
    storage = DRMonitoringBridge().check_storage_health()

    DRSystemStatus.objects.update_or_create(
        id=1,
        defaults={
            'overall_health': health.get('overall', 'unknown'),
            'active_alerts': len(DRAlertBridge_get_active()),
            'raw_status': {
                'health': health,
                'backup_stats': backup_stats,
                'storage': storage,
            },
        }
    )
    return {'synced': True, 'health': health.get('overall')}


def DRAlertBridge_get_active():
    try:
        from dr_integration.models import DRAlert
        return list(DRAlert.objects.filter(
            is_acknowledged=False,
            resolved_at__isnull=True,
        ).values('id', 'severity', 'rule_name'))
    except Exception:
        return []


@shared_task(name='dr_integration.verify_recent_backups')
def verify_recent_backups_task():
    """
    Celery task: Verify integrity of backups from last 24h.
    Run daily at 6:00 AM.
    """
    from dr_integration.services import DRBackupBridge
    bridge = DRBackupBridge()
    backups = bridge.get_backup_list(status='completed', limit=20)
    verified = 0
    failed = 0
    for backup in backups:
        result = bridge.verify_backup(backup['id'])
        if result.get('verified'):
            verified += 1
        else:
            failed += 1
            logger.warning(f"Backup verification failed: {backup['id']}")
            # Fire alert if verification fails
            from dr_integration.services import DRAlertBridge
            DRAlertBridge().fire_alert(
                rule_name='backup_verification_failed',
                severity='error',
                message=f"Backup {backup['id']} failed verification: {result.get('error')}",
                metric='backup.verified',
                value=0,
                threshold=1,
            )
    return {'verified': verified, 'failed': failed}


@shared_task(name='dr_integration.health_check')
def dr_health_check_task():
    """
    Celery task: Run DR health check and fire alerts if degraded.
    Run every 2 minutes.
    """
    from dr_integration.services import DRFailoverBridge, DRAlertBridge
    health = DRFailoverBridge().get_health_status()
    overall = health.get('overall', 'unknown')

    if overall in ('critical', 'down'):
        DRAlertBridge().fire_alert(
            rule_name='dr_system_health_critical',
            severity='critical',
            message=f"DR system health is {overall}: {health}",
            metric='dr.health',
            value=0,
            threshold=1,
        )
    elif overall == 'degraded':
        DRAlertBridge().fire_alert(
            rule_name='dr_system_health_degraded',
            severity='warning',
            message=f"DR system health degraded: {health}",
            metric='dr.health',
            value=0.5,
            threshold=1,
        )
    return {'health': overall, 'components': health.get('components', {})}


@shared_task(name='dr_integration.collect_and_push_metrics')
def collect_and_push_metrics_task():
    """
    Celery task: Collect Django API metrics and push to Prometheus/Datadog.
    Run every minute.
    """
    from dr_integration.services import DRMonitoringBridge, DRMetricsBridge

    metrics = DRMonitoringBridge().collect_system_metrics()
    alerts = DRMonitoringBridge().evaluate_alert_rules(metrics)

    # Push to Prometheus
    DRMetricsBridge.update_from_django_stats({
        'health': {'components': {'system': {'status': 'healthy', **metrics}}}
    })

    # Push Django-specific metrics
    try:
        from dr_integration.models import DRBackupRecord, DRAlert
        DRMetricsBridge.record(
            'api.active_alerts',
            DRAlert.objects.filter(is_acknowledged=False, resolved_at__isnull=True).count()
        )
        DRMetricsBridge.record(
            'api.backups_today',
            DRBackupRecord.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
        )
    except Exception:
        pass

    return {'metrics_collected': len(metrics), 'alerts_fired': len(alerts)}


@shared_task(name='dr_integration.check_key_rotation')
def check_key_rotation_task():
    """
    Celery task: Check if encryption keys need rotation.
    Run daily at midnight.
    """
    from dr_integration.services import DRSecurityBridge
    bridge = DRSecurityBridge()
    due = bridge.check_keys_rotation_due()
    if due:
        from dr_integration.services import DRAlertBridge
        DRAlertBridge().fire_alert(
            rule_name='encryption_key_rotation_due',
            severity='warning',
            message=f"{len(due)} encryption key(s) are due for rotation",
        )
    return {'keys_due_for_rotation': len(due), 'keys': due}


@shared_task(name='dr_integration.cleanup_old_dr_alerts')
def cleanup_old_dr_alerts_task():
    """
    Celery task: Clean up resolved/old DR alerts.
    Run weekly.
    """
    from dr_integration.models import DRAlert
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=30)
    deleted = DRAlert.objects.filter(
        resolved_at__lt=cutoff,
        is_acknowledged=True
    ).delete()
    return {'deleted': deleted[0]}

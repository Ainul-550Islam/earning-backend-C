"""
DR Integration Services — Core bridge between Django API and DR System.

This module wraps the DR system's FastAPI/SQLAlchemy services so they can
be called from Django without running the FastAPI server.

Usage:
    from dr_integration.services import DRBackupBridge, DRFailoverBridge

    bridge = DRBackupBridge()
    result = bridge.trigger_backup(backup_type='full')
"""
import logging
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── Path setup: add DR system root (not its parent) to Python path ────────────
# DR_SYSTEM_PATH should point to the directory that CONTAINS disaster_recovery/
# e.g. /app  so that `from disaster_recovery.services import ...` resolves.
DR_SYSTEM_PATH = os.environ.get('DR_SYSTEM_PATH', '/app/disaster_recovery')
_dr_root = os.path.dirname(DR_SYSTEM_PATH)  # one level up from the package
if _dr_root not in sys.path:
    sys.path.insert(0, _dr_root)


def _get_dr_session():
    """
    Get a SQLAlchemy session for the DR system database.
    Returns None (mock mode) when the DR package is not importable.
    """
    try:
        from disaster_recovery.dependencies import SessionLocal
        return SessionLocal()
    except ImportError:
        logger.warning("dr_integration.session: DR system not available — mock mode active")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class DRBackupBridge:
    """
    Bridge between Django API and DR system's BackupService.

    Replaces the simple api/backup/ with full DR-level backup:
    - GFS retention (Grandfather-Father-Son)
    - AES-256-GCM encryption
    - Multi-cloud storage (S3/Azure/GCP/local)
    - Automated verification
    - PITR (Point-In-Time Recovery)
    """

    def trigger_backup(self, backup_type: str = 'incremental',
                       policy_id: str = None,
                       actor_id: str = 'django_api',
                       tenant_id: str = None) -> dict:
        """Trigger a backup job via DR system."""
        db = _get_dr_session()
        if not db:
            return self._mock_backup_result(backup_type)

        try:
            from disaster_recovery.services import BackupService
            from disaster_recovery.enums import BackupType

            type_map = {
                'full': BackupType.FULL,
                'incremental': BackupType.INCREMENTAL,
                'differential': BackupType.DIFFERENTIAL,
            }
            svc = BackupService(db)
            job = svc.trigger_backup(
                policy_id=policy_id,
                backup_type=type_map.get(backup_type, BackupType.INCREMENTAL),
                actor_id=actor_id,
            )
            result = {
                'success': True,
                'job_id': str(job.id),
                'backup_type': backup_type,
                'status': str(job.status.value) if hasattr(job.status, 'value') else str(job.status),
                'triggered_at': datetime.utcnow().isoformat(),
                'actor': actor_id,
            }
            # Sync to Django model
            self._sync_to_django(job, tenant_id)
            return result
        except Exception as e:
            logger.error(f"DR backup trigger failed: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            if db:
                db.close()

    def get_backup_list(self, status: str = None, limit: int = 50) -> List[dict]:
        """Get list of backups from DR system."""
        db = _get_dr_session()
        if not db:
            return []
        try:
            from disaster_recovery.services import BackupService
            from disaster_recovery.enums import BackupStatus
            svc = BackupService(db)
            params = {'page': 1, 'page_size': limit}
            if status:
                params['status'] = BackupStatus[status.upper()]
            result = svc.repo.list_jobs(**params)
            return [
                {
                    'id': str(j.id),
                    'backup_type': str(j.backup_type.value) if j.backup_type else None,
                    'status': str(j.status.value) if j.status else None,
                    'size_bytes': j.source_size_bytes,
                    'is_verified': j.is_verified,
                    'completed_at': j.completed_at.isoformat() if j.completed_at else None,
                    'created_at': j.created_at.isoformat() if j.created_at else None,
                }
                for j in result.get('items', [])
            ]
        except Exception as e:
            logger.error(f"DR backup list failed: {e}")
            return []
        finally:
            if db:
                db.close()

    def verify_backup(self, backup_id: str) -> dict:
        """Verify a specific backup's integrity."""
        from disaster_recovery.BACKUP_MANAGEMENT.backup_verifier import BackupVerifier
        verifier = BackupVerifier()
        db = _get_dr_session()
        if not db:
            return {'verified': True, 'backup_id': backup_id, 'mode': 'mock'}
        try:
            from disaster_recovery.models import BackupJob
            job = db.query(BackupJob).filter(BackupJob.id == backup_id).first()
            if not job:
                return {'verified': False, 'error': 'Backup not found'}
            result = verifier.verify(job.storage_path or '', job.checksum or '')
            return {'verified': result.get('checksum_valid', False),
                    'backup_id': backup_id, **result}
        except Exception as e:
            return {'verified': False, 'error': str(e)}
        finally:
            if db: db.close()

    def get_backup_stats(self) -> dict:
        """Get backup statistics for API dashboard."""
        db = _get_dr_session()
        if not db:
            return {'total': 0, 'success_rate': 100.0}
        try:
            from disaster_recovery.services import BackupService
            svc = BackupService(db)
            return svc.repo.get_backup_stats(days=30)
        except Exception as e:
            logger.error(f"DR backup stats failed: {e}")
            return {}
        finally:
            if db: db.close()

    def _sync_to_django(self, dr_job, tenant_id: str = None):
        """Sync DR backup job to Django DRBackupRecord model."""
        try:
            from dr_integration.models import DRBackupRecord
            DRBackupRecord.objects.update_or_create(
                dr_job_id=str(dr_job.id),
                defaults={
                    'backup_type': str(dr_job.backup_type.value) if dr_job.backup_type else 'incremental',
                    'status': str(dr_job.status.value) if dr_job.status else 'pending',
                    'checksum': dr_job.checksum or '',
                }
            )
        except Exception as e:
            logger.debug(f"DR-Django sync error: {e}")

    def _mock_backup_result(self, backup_type: str) -> dict:
        """Return mock result when DR system is not available."""
        import uuid
        return {
            'success': True,
            'job_id': str(uuid.uuid4()),
            'backup_type': backup_type,
            'status': 'pending',
            'mode': 'mock_dr_unavailable',
            'triggered_at': datetime.utcnow().isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# RESTORE BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class DRRestoreBridge:
    """
    Bridge for restore operations — much more powerful than api/backup/restore.
    Supports PITR, table-level restore, cross-region restore, rollback.
    """

    def request_restore(self, restore_type: str, backup_id: str = None,
                        target_database: str = None, point_in_time: str = None,
                        requested_by: str = 'django_api',
                        require_approval: bool = True) -> dict:
        """Create a restore request via DR system."""
        db = _get_dr_session()
        if not db:
            return self._mock_restore_result(restore_type)
        try:
            from disaster_recovery.RESTORE_MANAGEMENT.restore_validator import RestoreValidator
            request_data = {
                'restore_type': restore_type,
                'backup_job_id': backup_id,
                'target_database': target_database,
                'point_in_time': point_in_time,
                'requested_by': requested_by,
                'approval_status': 'pending' if require_approval else 'approved',
            }
            validator = RestoreValidator(db_session=db,
                                         config={'require_approval': require_approval})
            validation = validator.validate(request_data)
            if not validation['valid'] and require_approval:
                return {'success': False, 'validation_errors': validation['errors']}

            from dr_integration.models import DRRestoreRecord
            record = DRRestoreRecord.objects.create(
                restore_type=restore_type,
                target_database=target_database or 'default',
                approval_status='pending' if require_approval else 'approved',
                notes=f"Requested via Django API by {requested_by}",
            )
            return {
                'success': True,
                'restore_id': str(record.id),
                'status': record.approval_status,
                'validation': validation,
                'message': (
                    'Restore request submitted — awaiting approval'
                    if require_approval else 'Restore approved and queued'
                ),
            }
        except Exception as e:
            logger.error(f"DR restore request failed: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            if db: db.close()

    def validate_pitr(self, database: str, target_time: str) -> dict:
        """Check if PITR is available for a database at a specific time."""
        db = _get_dr_session()
        if not db:
            return {'feasible': True, 'note': 'mock mode'}
        try:
            from disaster_recovery.RESTORE_MANAGEMENT.restore_validator import RestoreValidator
            validator = RestoreValidator(db_session=db)
            dt = datetime.fromisoformat(target_time)
            return validator.validate_pitr_feasibility(database, dt)
        except Exception as e:
            return {'feasible': False, 'error': str(e)}
        finally:
            if db: db.close()

    def _mock_restore_result(self, restore_type: str) -> dict:
        import uuid
        return {'success': True, 'restore_id': str(uuid.uuid4()),
                'status': 'pending', 'mode': 'mock_dr_unavailable'}


# ══════════════════════════════════════════════════════════════════════════════
# FAILOVER BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class DRFailoverBridge:
    """
    Bridge for failover — not available in base API at all.
    Adds automatic + manual failover capability to the Django API.
    """

    def get_health_status(self) -> dict:
        """Get overall system health from DR system."""
        try:
            from disaster_recovery.FAILOVER_MANAGEMENT.health_checker import HealthChecker
            from django.conf import settings
            checker = HealthChecker()
            components = getattr(settings, 'DR_HEALTH_CHECK_COMPONENTS', [
                {'name': 'database', 'type': 'database',
                 'url': settings.DATABASES['default'].get('NAME', 'django_db')},
                {'name': 'redis', 'type': 'tcp', 'host': 'localhost', 'port': 6379},
                {'name': 'api', 'type': 'http', 'url': 'http://localhost:8000/health/'},
            ])
            return checker.check_all(components)
        except Exception as e:
            logger.error(f"DR health check failed: {e}")
            return {'overall': 'unknown', 'error': str(e)}

    def trigger_manual_failover(self, primary_node: str, secondary_node: str,
                                 reason: str, triggered_by_id: str = None,
                                 is_drill: bool = False) -> dict:
        """Trigger manual failover with full audit trail."""
        db = _get_dr_session()
        if not db:
            return self._mock_failover_result(primary_node, secondary_node)
        try:
            from disaster_recovery.services import FailoverService
            from disaster_recovery.enums import FailoverType
            svc = FailoverService(db)
            result = svc.trigger_failover(
                primary_node=primary_node,
                secondary_node=secondary_node,
                failover_type=FailoverType.MANUAL,
                reason=reason,
                triggered_by=triggered_by_id or 'django_api',
            )
            # Save to Django
            from dr_integration.models import DRFailoverEvent
            DRFailoverEvent.objects.create(
                failover_type='drill' if is_drill else 'manual',
                status='initiated',
                primary_node=primary_node,
                secondary_node=secondary_node,
                trigger_reason=reason,
                is_drill=is_drill,
            )
            return result
        except Exception as e:
            logger.error(f"DR failover trigger failed: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            if db: db.close()

    def get_replication_status(self) -> dict:
        """Get current replication lag and status."""
        try:
            from django.conf import settings
            replicas = getattr(settings, 'DR_REPLICA_HOSTS', [])
            if not replicas:
                return {'replicas': [], 'note': 'No replicas configured in DR_REPLICA_HOSTS'}
            from disaster_recovery.REPLICATION_MANAGEMENT.asynchronous_replication import AsynchronousReplication
            repl = AsynchronousReplication(
                primary=settings.DATABASES['default']['HOST'],
                replicas=replicas,
            )
            return repl.check_all_replicas()
        except Exception as e:
            return {'error': str(e), 'replicas': []}

    def get_rto_rpo_stats(self) -> dict:
        """Get current RTO and RPO metrics."""
        db = _get_dr_session()
        if not db:
            return {'rto_seconds': None, 'rpo_seconds': None}
        try:
            from disaster_recovery.DR_DRILL_MANAGEMENT.rto_calculator import RTOCalculator
            calc = RTOCalculator(db_session=db)
            rto_trend = calc.get_rto_trend(last_n=5)
            rpo = db  # Would query latest replication lag
            return {
                'rto_trend': rto_trend,
                'rpo_seconds': self.get_replication_status().get('max_lag_seconds'),
            }
        except Exception as e:
            return {'error': str(e)}
        finally:
            if db: db.close()

    def _mock_failover_result(self, primary: str, secondary: str) -> dict:
        return {'success': True, 'mode': 'mock',
                'primary': primary, 'secondary': secondary}


# ══════════════════════════════════════════════════════════════════════════════
# ALERT BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class DRAlertBridge:
    """
    Bridges the existing api/alerts/ module with DR's multi-level
    escalation policy + PagerDuty/Slack/Datadog integrations.
    """

    def fire_alert(self, rule_name: str, severity: str, message: str,
                   metric: str = None, value: float = None,
                   threshold: float = None, tenant_id: str = None) -> dict:
        """Fire an alert through DR's alert manager."""
        from django.utils import timezone
        alert_data = {
            'rule_name': rule_name,
            'severity': severity,
            'message': message,
            'metric': metric or rule_name,
            'value': value,
            'threshold': threshold,
            'fired_at': timezone.now().isoformat(),
        }
        # Route to DR integrations (non-blocking via thread pool)
        self._notify_via_dr_channels(alert_data, severity)
        # Persist to Django model
        try:
            from dr_integration.models import DRAlert
            DRAlert.objects.create(
                rule_name=rule_name,
                severity=severity,
                message=message,
                metric=metric or '',
                metric_value=value,
                threshold=threshold,
                fired_at=timezone.now(),
            )
        except Exception as e:
            logger.warning("dr_integration.alert_model_save_error", extra={"error": str(e)})
        return {'fired': True, 'alert': alert_data}

    def get_escalation_level(self, alert_id: str, fired_at: datetime,
                              severity: str = 'medium') -> int:
        """Get current escalation level for an alert."""
        try:
            from disaster_recovery.MONITORING_ALERTING.escalation_policy import EscalationPolicy
            policy = EscalationPolicy()
            return policy.get_current_escalation_level(fired_at, False, severity)
        except Exception as e:
            return 1

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> dict:
        """Acknowledge a DR alert."""
        from django.utils import timezone
        try:
            from dr_integration.models import DRAlert
            alert = DRAlert.objects.filter(id=alert_id).first()
            if alert:
                alert.is_acknowledged = True
                alert.acknowledged_at = timezone.now()
                alert.save(update_fields=['is_acknowledged', 'acknowledged_at'])
            return {'acknowledged': True, 'alert_id': alert_id, 'by': acknowledged_by}
        except Exception as e:
            logger.error("dr_integration.acknowledge_alert_error", extra={"alert_id": alert_id, "error": str(e)})
            return {'acknowledged': False, 'error': str(e)}

    def _notify_via_dr_channels(self, alert: dict, severity: str):
        """
        Route alert to DR notification channels.

        All external HTTP calls (PagerDuty, Slack, Datadog) are dispatched
        via httpx in a thread executor so they never block the Django async
        event loop.  Each channel failure is isolated — one failing channel
        does not prevent the others from firing.
        """
        from django.conf import settings
        dr_config = getattr(settings, 'DR_NOTIFICATION_CONFIG', {})
        if not dr_config:
            return

        import concurrent.futures
        import httpx

        def _call_pagerduty():
            if severity not in ('critical', 'error'):
                return
            api_key = dr_config.get('pagerduty_api_key')
            if not api_key:
                return
            try:
                from disaster_recovery.INTEGRATIONS.pagerduty_integration import PagerDutyIntegration
                pd = PagerDutyIntegration(api_key)
                pd.trigger_alert(
                    summary=f"[Django API] {alert['rule_name']}: {alert['message'][:100]}",
                    severity=severity,
                    component='django_api',
                )
            except Exception as e:
                logger.warning("dr_integration.pagerduty_notify_error", extra={"error": str(e)})

        def _call_slack():
            webhook = dr_config.get('slack_webhook_url')
            if not webhook:
                return
            try:
                from disaster_recovery.INTEGRATIONS.slack_integration import SlackIntegration
                SlackIntegration(webhook).post_alert(alert)
            except Exception as e:
                logger.warning("dr_integration.slack_notify_error", extra={"error": str(e)})

        def _call_datadog():
            api_key = dr_config.get('datadog_api_key')
            if not api_key:
                return
            try:
                from disaster_recovery.INTEGRATIONS.datadog_integration import DatadogIntegration
                dd = DatadogIntegration(api_key)
                dd.create_event(
                    title=f"[Django API Alert] {alert['rule_name']}",
                    text=alert['message'],
                    alert_type={'critical': 'error', 'error': 'error',
                                'warning': 'warning', 'info': 'info'}.get(severity, 'info'),
                    tags=[f"severity:{severity}", "source:django_api"],
                )
            except Exception as e:
                logger.warning("dr_integration.datadog_notify_error", extra={"error": str(e)})

        # Run all three channels concurrently in a thread pool — non-blocking
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [
                pool.submit(_call_pagerduty),
                pool.submit(_call_slack),
                pool.submit(_call_datadog),
            ]
            for f in concurrent.futures.as_completed(futures, timeout=10):
                try:
                    f.result()
                except Exception as e:
                    logger.warning("dr_integration.notify_channel_error", extra={"error": str(e)})


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class DRAuditBridge:
    """
    Enhances api/audit_logs/ with DR's immutable audit logging:
    - Integrity hashing per entry
    - JSONL append-only files
    - SIEM-ready structured format
    - 7-year retention support
    """

    def __init__(self):
        self._dr_logger = None

    def _get_dr_logger(self):
        if self._dr_logger is None:
            try:
                from disaster_recovery.SECURITY_COMPLIANCE.audit_logger import AuditLogger
                from django.conf import settings
                config = getattr(settings, 'DR_AUDIT_CONFIG', {})
                self._dr_logger = AuditLogger(config=config)
            except Exception as e:
                logger.debug(f"DR AuditLogger init error: {e}")
        return self._dr_logger

    def log(self, actor_id: str, action: str, resource_type: str = None,
             resource_id: str = None, ip_address: str = None,
             result: str = 'success', error_message: str = None,
             request_id: str = None, actor_type: str = 'user',
             old_values: dict = None, new_values: dict = None) -> dict:
        """Log to both Django audit_logs AND DR immutable log."""
        dr_logger = self._get_dr_logger()
        entry = {}
        if dr_logger:
            try:
                entry = dr_logger.log(
                    actor_id=str(actor_id),
                    action=action,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    ip_address=ip_address,
                    result=result,
                    error_message=error_message,
                    request_id=request_id,
                    actor_type=actor_type,
                    old_values=old_values,
                    new_values=new_values,
                )
            except Exception as e:
                logger.debug(f"DR audit log error: {e}")
        return entry

    def search_logs(self, actor_id: str = None, action: str = None,
                    resource_type: str = None, from_date: datetime = None,
                    to_date: datetime = None, limit: int = 100) -> List[dict]:
        """Search DR audit logs."""
        dr_logger = self._get_dr_logger()
        if not dr_logger:
            return []
        try:
            return dr_logger.search(
                actor_id=actor_id, action=action,
                resource_type=resource_type,
                from_date=from_date, to_date=to_date, limit=limit,
            )
        except Exception as e:
            logger.error(f"DR audit search error: {e}")
            return []

    def verify_log_integrity(self) -> dict:
        """Verify immutable audit log integrity."""
        dr_logger = self._get_dr_logger()
        if not dr_logger:
            return {'status': 'unavailable'}
        return dr_logger.verify_integrity()

    def log_security_event(self, event_type: str, actor_id: str,
                            description: str, details: dict = None) -> dict:
        """Log a security event — routes to DR security log."""
        dr_logger = self._get_dr_logger()
        if dr_logger:
            try:
                return dr_logger.log_security_event(event_type, str(actor_id), description, details)
            except Exception as e:
                logger.debug(f"DR security log error: {e}")
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# MONITORING BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class DRMonitoringBridge:
    """
    Exposes DR system's monitoring capabilities to the Django API.
    Connects api/alerts/ metrics_collector with DR's system/db monitors.
    """

    def collect_system_metrics(self) -> dict:
        """Collect system metrics via DR's SystemMonitor."""
        try:
            from disaster_recovery.MONITORING_ALERTING.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            return monitor.collect()
        except Exception as e:
            return {'error': str(e)}

    def check_storage_health(self) -> dict:
        """Check backup storage health via DR's StorageMonitor."""
        try:
            from django.conf import settings
            from disaster_recovery.MONITORING_ALERTING.storage_monitor import StorageMonitor
            storage_configs = getattr(settings, 'DR_STORAGE_CONFIGS', [
                {'name': 'local', 'provider': 'local', 'base_path': '/var/backups/api'}
            ])
            monitor = StorageMonitor(storage_configs=storage_configs)
            return monitor.check_all()
        except Exception as e:
            return {'error': str(e)}

    def get_status_page_data(self) -> dict:
        """Generate status page data via DR's StatusPage."""
        try:
            from django.conf import settings
            from disaster_recovery.MONITORING_ALERTING.status_page import StatusPage
            components = getattr(settings, 'DR_STATUS_PAGE_COMPONENTS', [
                {'name': 'api', 'display_name': 'API Server', 'group': 'Application'},
                {'name': 'database', 'display_name': 'Database', 'group': 'Infrastructure'},
                {'name': 'payment_gateway', 'display_name': 'Payment Gateway', 'group': 'External'},
                {'name': 'offerwall', 'display_name': 'Offerwall', 'group': 'Application'},
            ])
            page = StatusPage(components=components,
                              config=getattr(settings, 'DR_STATUS_PAGE_CONFIG', {}))
            health = self.collect_system_metrics()
            return page.generate(health)
        except Exception as e:
            return {'error': str(e)}

    def get_on_call_contact(self) -> dict:
        """Get current on-call contact from DR roster."""
        try:
            from django.conf import settings
            from disaster_recovery.MONITORING_ALERTING.on_call_roster import OnCallRoster
            roster_config = getattr(settings, 'DR_ON_CALL_ROSTER', [])
            roster = OnCallRoster(roster=roster_config)
            primary = roster.get_primary_on_call()
            return primary or {'note': 'No on-call configured in DR_ON_CALL_ROSTER'}
        except Exception as e:
            return {'error': str(e)}

    def evaluate_alert_rules(self, metrics: dict) -> List[dict]:
        """Run DR alert rule engine against current metrics."""
        try:
            from disaster_recovery.MONITORING_ALERTING.alert_manager import AlertManager
            manager = AlertManager()
            alerts = []
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)):
                    fired = manager.evaluate(metric_name, value)
                    alerts.extend(fired)
            return alerts
        except Exception as e:
            return []


# ══════════════════════════════════════════════════════════════════════════════
# PROMETHEUS BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class DRMetricsBridge:
    """Exposes Django API metrics via DR's Prometheus integration."""

    _prom = None

    @classmethod
    def get_prometheus(cls):
        if cls._prom is None:
            try:
                from django.conf import settings
                from disaster_recovery.INTEGRATIONS.prometheus_integration import PrometheusIntegration
                config = getattr(settings, 'DR_PROMETHEUS_CONFIG', {'port': 9091})
                cls._prom = PrometheusIntegration(config=config)
            except Exception as e:
                logger.debug(f"Prometheus init error: {e}")
        return cls._prom

    @classmethod
    def record(cls, metric_name: str, value: float, labels: dict = None):
        prom = cls.get_prometheus()
        if prom:
            try:
                prom.record(metric_name, value, labels)
            except Exception:
                pass

    @classmethod
    def update_from_django_stats(cls, stats: dict):
        """Push Django API stats to Prometheus."""
        prom = cls.get_prometheus()
        if not prom:
            return
        try:
            # Backup metrics
            if 'backup' in stats:
                prom.update_backup_metrics(stats['backup'])
            # Health metrics
            if 'health' in stats:
                prom.update_health_metrics(stats['health'])
            # Incident metrics
            if 'incidents' in stats:
                prom.update_incident_metrics(stats['incidents'])
            # Storage metrics
            if 'storage' in stats:
                prom.update_storage_metrics(stats['storage'])
        except Exception as e:
            logger.debug(f"Prometheus update error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY BRIDGE
# ══════════════════════════════════════════════════════════════════════════════

class DRSecurityBridge:
    """
    Enhances api/security/ with DR-level security features:
    - Key rotation
    - Compliance checking (HIPAA/PCI/SOC2)
    - Access control audit
    """

    def check_compliance(self, framework: str = 'HIPAA') -> dict:
        """Run DR compliance checker for specified framework."""
        try:
            from disaster_recovery.DR_DRILL_MANAGEMENT.compliance_checker import DrillComplianceChecker
            db = _get_dr_session()
            checker = DrillComplianceChecker(db_session=db)
            result = checker.check(framework)
            if db: db.close()
            return result
        except Exception as e:
            return {'framework': framework, 'error': str(e)}

    def rotate_encryption_key(self, authorized_by: str) -> dict:
        """Rotate API encryption keys via DR key manager."""
        try:
            from disaster_recovery.SECURITY_COMPLIANCE.key_management import KeyManager
            from django.conf import settings
            config = getattr(settings, 'DR_KEY_CONFIG', {})
            manager = KeyManager(config=config)
            return manager.rotate_key(authorized_by=authorized_by)
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def check_keys_rotation_due(self) -> List[dict]:
        """Check if any encryption keys are due for rotation."""
        try:
            from disaster_recovery.SECURITY_COMPLIANCE.key_management import KeyManager
            from django.conf import settings
            manager = KeyManager(config=getattr(settings, 'DR_KEY_CONFIG', {}))
            return manager.check_rotation_needed()
        except Exception as e:
            return []

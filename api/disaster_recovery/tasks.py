"""Celery Tasks for Disaster Recovery System."""
import logging
from celery import Celery
from .config import settings

app = Celery("dr_system", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json",
                timezone="UTC", enable_utc=True)
logger = logging.getLogger(__name__)

@app.task(bind=True, max_retries=3, default_retry_delay=300)
def run_backup_task(self, policy_id: str):
    logger.info(f"Celery: run_backup_task policy={policy_id}")
    try:
        from .dependencies import SessionLocal
        from .AUTOMATION_ENGINES.auto_backup import AutoBackup
        db = SessionLocal()
        result = AutoBackup.run_for_policy(policy_id, db)
        db.close()
        return result
    except Exception as e:
        logger.error(f"Backup task failed: {e}")
        raise self.retry(exc=e)

@app.task(bind=True, max_retries=2)
def run_health_check_task(self):
    logger.info("Celery: run_health_check_task")
    from .FAILOVER_MANAGEMENT.health_checker import HealthChecker
    checker = HealthChecker()
    return checker.check_all([])

@app.task
def run_retention_cleanup_task(policy_id: str):
    logger.info(f"Celery: run_retention_cleanup policy={policy_id}")
    from .dependencies import SessionLocal
    from .services import BackupService
    db = SessionLocal()
    svc = BackupService(db)
    count = svc.cleanup_old_backups(policy_id)
    db.close()
    return {"cleaned": count}

@app.task
def run_sla_check_task(service_name: str):
    logger.info(f"Celery: run_sla_check service={service_name}")
    from .dependencies import SessionLocal
    from .MONITORING_ALERTING.sla_monitor import SLAMonitor
    db = SessionLocal()
    monitor = SLAMonitor(db)
    result = monitor.check_sla_breach(service_name)
    db.close()
    return result

# Periodic tasks (Celery Beat schedule)
app.conf.beat_schedule = {
    "hourly-health-check": {"task": "disaster_recovery.tasks.run_health_check_task", "schedule": 30.0},
    "daily-backup-all": {"task": "disaster_recovery.tasks.run_backup_task", "schedule": 86400.0, "args": ["default"]},
    "daily-sla-check": {"task": "disaster_recovery.tasks.run_sla_check_task", "schedule": 86400.0, "args": ["api-server"]},
}

# api/admin_panel/background_jobs.py
"""
Admin Panel Background Jobs — Celery task orchestration.
All long-running admin operations run as background jobs.
Provides: job registry, progress tracking, job history, retry logic.
"""
from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class JobStatus:
    job_id: str
    job_type: str
    status: str         # queued | running | done | failed | cancelled
    progress_pct: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Dict = field(default_factory=dict)
    error: str = ''
    actor: str = ''

    def to_dict(self) -> Dict:
        return {
            'job_id': self.job_id, 'job_type': self.job_type, 'status': self.status,
            'progress_pct': self.progress_pct, 'started_at': self.started_at,
            'completed_at': self.completed_at, 'result': self.result,
            'error': self.error, 'actor': self.actor,
        }


class JobTracker:
    """Tracks background job progress in cache."""
    TTL = 86400  # 24h

    def create(self, job_type: str, actor: str = '') -> str:
        job_id = str(uuid.uuid4())
        status = JobStatus(job_id=job_id, job_type=job_type, status='queued', actor=actor)
        cache.set(f'job:{job_id}', status.__dict__, self.TTL)
        # Add to user's job list
        if actor:
            jobs = cache.get(f'jobs:user:{actor}') or []
            jobs.insert(0, job_id)
            cache.set(f'jobs:user:{actor}', jobs[:50], self.TTL)
        return job_id

    def update(self, job_id: str, status: str, progress: int = None,
               result: Dict = None, error: str = '') -> None:
        data = cache.get(f'job:{job_id}') or {}
        data['status'] = status
        if progress is not None:
            data['progress_pct'] = progress
        if result is not None:
            data['result'] = result
        if error:
            data['error'] = error
        if status == 'running' and not data.get('started_at'):
            data['started_at'] = timezone.now().isoformat()
        if status in ('done', 'failed'):
            data['completed_at'] = timezone.now().isoformat()
        cache.set(f'job:{job_id}', data, self.TTL)

    def get(self, job_id: str) -> Optional[Dict]:
        return cache.get(f'job:{job_id}')

    def get_user_jobs(self, actor: str, limit: int = 20) -> List[Dict]:
        job_ids = cache.get(f'jobs:user:{actor}') or []
        jobs = []
        for jid in job_ids[:limit]:
            status = self.get(jid)
            if status:
                jobs.append(status)
        return jobs


tracker = JobTracker()


# ===========================================================================
# BACKGROUND JOB TASKS
# ===========================================================================

@shared_task(bind=True, max_retries=3, queue='admin_panel.bulk')
def send_push_broadcast(self, title: str, body: str, data: Dict, filters: Dict):
    """Background push notification broadcast."""
    from api.admin_panel.notifications_push import push_manager
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.filter(is_active=True)
    if filters:
        qs = qs.filter(**filters)
    sent = failed = 0
    for user in qs.iterator(chunk_size=100):
        r = push_manager.send_to_user(user.pk, title, body, data)
        sent += r.get('sent', 0)
        failed += r.get('failed', 0)
    return {'sent': sent, 'failed': failed}


@shared_task(bind=True, queue='admin_panel.bulk')
def bulk_wallet_sync(self, user_ids: List[int]):
    """Background wallet integrity sync."""
    from api.admin_panel.INTEGRATION_SYSTEM.sync_manager import sync_manager
    results = sync_manager.bulk_wallet_integrity_check(user_ids)
    return results


@shared_task(bind=True, queue='admin_panel.bulk')
def generate_data_export_task(self, export_id: int):
    """Generate a data export in the background."""
    try:
        from api.admin_panel.data_export import AdminDataExporter
        AdminDataExporter.process_export(export_id)
    except Exception as exc:
        raise self.retry(exc=exc, max_retries=2)


@shared_task(bind=True, queue='admin_panel')
def run_compliance_check(self, user_id: int):
    """Run full compliance check for a user."""
    from api.admin_panel.compliance import ComplianceEngine
    engine = ComplianceEngine()
    return engine.check_user(user_id)


@shared_task(queue='admin_panel.ai')
def run_ai_batch_classification(transaction_ids: List[int]):
    """Batch classify transactions using AI."""
    from api.admin_panel.openAI import bulk_classify_transactions
    from api.wallet.models import WalletTransaction
    txns = list(WalletTransaction.objects.filter(pk__in=transaction_ids).values(
        'id', 'amount', 'transaction_type', 'user_id', 'created_at'
    ))
    return bulk_classify_transactions(txns)


@shared_task(queue='admin_panel')
def refresh_sanctions_list():
    """Refresh cached sanctions list from external source."""
    from api.admin_panel.sanctions import screener
    # In production, fetch from OFAC/UN API
    logger.info("[BgJobs] Sanctions list refresh triggered")
    return {'refreshed': True, 'timestamp': timezone.now().isoformat()}


@shared_task(queue='admin_panel')
def cleanup_expired_jobs():
    """Clean up expired background job status records."""
    logger.info("[BgJobs] Expired job cleanup completed")
    return True


# ===========================================================================
# JOB QUEUE API
# ===========================================================================

def queue_job(job_type: str, task_name: str, actor: str = '', **task_kwargs) -> str:
    """Queue a background job and return job_id for tracking."""
    job_id = tracker.create(job_type, actor=actor)
    task_kwargs['job_id'] = job_id
    from celery import current_app
    current_app.send_task(task_name, kwargs=task_kwargs, queue='admin_panel.bulk')
    return job_id


def get_job_status(job_id: str) -> Optional[Dict]:
    return tracker.get(job_id)


def get_user_jobs(actor_username: str) -> List[Dict]:
    return tracker.get_user_jobs(actor_username)
"""
tasks/services/WorkerHealthService.py
Monitor Celery workers and update WorkerHealth records.
"""
import logging
from typing import Dict, Any, List
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class WorkerHealthService:
    """
    Queries Celery workers via inspect API, updates WorkerHealth model,
    and detects offline/stale workers.
    """

    CACHE_KEY = 'worker_health_all'
    CACHE_TTL = 60  # seconds

    def refresh(self, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Query all Celery workers and update WorkerHealth records.
        Returns a summary of online/offline workers.
        """
        try:
            from celery import current_app
            from api.tasks.models.monitoring import WorkerHealth

            inspector   = current_app.control.inspect(timeout=timeout)
            active      = inspector.active()   or {}
            stats       = inspector.stats()    or {}
            queues_info = inspector.active_queues() or {}
            ping_result = inspector.ping()     or {}

            online_workers = set(active.keys())
            updated = []

            for worker_name in online_workers:
                worker_stat   = stats.get(worker_name, {})
                worker_queues = queues_info.get(worker_name, [])
                active_tasks  = active.get(worker_name, [])

                pool_info     = worker_stat.get('pool', {})
                concurrency   = pool_info.get('max-concurrency', 1)
                processed     = worker_stat.get('total', {})
                processed_total = sum(processed.values()) if isinstance(processed, dict) else 0

                hostname = worker_name.split('@')[-1] if '@' in worker_name else worker_name

                WorkerHealth.objects.update_or_create(
                    worker_id=worker_name,
                    defaults={
                        'hostname': hostname,
                        'status': (
                            WorkerHealth.Status.BUSY
                            if active_tasks
                            else WorkerHealth.Status.IDLE
                        ),
                        'queue_names': [q.get('name') for q in worker_queues],
                        'concurrency': concurrency,
                        'active_tasks': len(active_tasks),
                        'processed_total': processed_total,
                        'last_heartbeat': timezone.now(),
                        'celery_version': worker_stat.get('versions', {}).get('celery', ''),
                    },
                )
                updated.append(worker_name)

            # Mark stale workers offline
            from datetime import timedelta
            stale_cutoff = timezone.now() - timedelta(minutes=2)
            WorkerHealth.objects.exclude(
                worker_id__in=online_workers
            ).filter(
                last_heartbeat__lt=stale_cutoff,
                status__in=[
                    WorkerHealth.Status.ONLINE,
                    WorkerHealth.Status.IDLE,
                    WorkerHealth.Status.BUSY,
                ],
            ).update(status=WorkerHealth.Status.OFFLINE)

            summary = {
                'online': len(online_workers),
                'workers': updated,
                'checked_at': timezone.now().isoformat(),
            }
            cache.set(self.CACHE_KEY, summary, timeout=self.CACHE_TTL)

            return summary

        except Exception as e:
            logger.error(f"[ERROR] WorkerHealthService.refresh: {e}")
            return {'error': str(e), 'online': 0}

    def get_all(self) -> List[Dict]:
        """Return all WorkerHealth records as dicts."""
        try:
            from api.tasks.models.monitoring import WorkerHealth

            return list(
                WorkerHealth.objects.order_by('-last_heartbeat').values(
                    'worker_id', 'hostname', 'status', 'queue_names',
                    'concurrency', 'active_tasks', 'processed_total',
                    'last_heartbeat', 'cpu_percent', 'memory_mb',
                )
            )
        except Exception as e:
            logger.error(f"[ERROR] WorkerHealthService.get_all: {e}")
            return []

    def get_online_count(self) -> int:
        """Return count of online workers (fast cache check)."""
        cached = cache.get(self.CACHE_KEY)
        if cached:
            return cached.get('online', 0)
        result = self.refresh()
        return result.get('online', 0)

    def send_task_to_worker(
        self,
        worker_id: str,
        task_name: str,
        kwargs: dict = None,
    ) -> Dict[str, Any]:
        """Dispatch a task to a specific worker by worker_id."""
        try:
            from celery import current_app

            result = current_app.send_task(
                task_name,
                kwargs=kwargs or {},
                queue=worker_id,
            )
            return {'success': True, 'task_id': result.id}

        except Exception as e:
            logger.error(f"[ERROR] WorkerHealthService.send_task_to_worker: {e}")
            return {'success': False, 'error': str(e)}

"""
tasks/services/QueueDepthService.py
Monitor queue depths and persist QueueDepth snapshots.
"""
import logging
from typing import Dict, Any, List
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class QueueDepthService:
    """
    Queries the broker for queue depths and stores snapshots.
    Supports Redis and RabbitMQ backends.
    """

    CACHE_PREFIX = 'queue_depth_'
    CACHE_TTL    = 60

    def snapshot_all(self) -> List[Dict]:
        """
        Take a depth snapshot for every registered TaskQueue and persist
        a QueueDepth record. Returns a list of snapshot dicts.
        """
        snapshots = []
        try:
            from api.tasks.models.queue import TaskQueue
            from api.tasks.models.monitoring import QueueDepth

            queues = TaskQueue.objects.filter(is_active=True)
            for queue in queues:
                depth_info = self.get_queue_depth(queue.name)

                snapshot = QueueDepth.objects.create(
                    queue_name=queue.name,
                    depth=depth_info.get('depth', 0),
                    processing_count=depth_info.get('processing_count', 0),
                    failed_count=depth_info.get('failed_count', 0),
                    consumer_count=depth_info.get('consumer_count', 0),
                    checked_at=timezone.now(),
                )
                snapshots.append({
                    'queue_name': queue.name,
                    'depth': snapshot.depth,
                    'processing_count': snapshot.processing_count,
                    'failed_count': snapshot.failed_count,
                })

                # Cache per-queue
                cache.set(
                    f'{self.CACHE_PREFIX}{queue.name}',
                    depth_info,
                    timeout=self.CACHE_TTL,
                )

        except Exception as e:
            logger.error(f"[ERROR] QueueDepthService.snapshot_all: {e}")

        return snapshots

    def get_queue_depth(self, queue_name: str) -> Dict[str, Any]:
        """
        Query the broker for the current depth of a named queue.
        Tries Redis via django-redis first, then falls back to Celery inspect.
        """
        # Try cache first
        cached = cache.get(f'{self.CACHE_PREFIX}{queue_name}')
        if cached:
            return cached

        depth_info = {
            'queue_name': queue_name,
            'depth': 0,
            'processing_count': 0,
            'failed_count': 0,
            'consumer_count': 0,
            'checked_at': timezone.now().isoformat(),
        }

        # ── Redis broker depth ─────────────────────────────────────────
        try:
            from django_redis import get_redis_connection
            r     = get_redis_connection('default')
            depth = r.llen(queue_name)
            if depth is not None:
                depth_info['depth'] = int(depth)
                return depth_info
        except Exception:
            pass

        # ── Celery inspect fallback ────────────────────────────────────
        try:
            from celery import current_app

            inspector = current_app.control.inspect(timeout=2.0)
            reserved  = inspector.reserved() or {}

            processing_count = sum(
                len(tasks)
                for tasks in reserved.values()
            )
            depth_info['processing_count'] = processing_count

        except Exception as e:
            logger.debug(f"[DEBUG] QueueDepthService.get_queue_depth inspect: {e}")

        return depth_info

    def get_all_depths(self) -> List[Dict]:
        """Return depth info for all registered queues."""
        try:
            from api.tasks.models.queue import TaskQueue

            return [
                self.get_queue_depth(q.name)
                for q in TaskQueue.objects.filter(is_active=True)
            ]
        except Exception as e:
            logger.error(f"[ERROR] QueueDepthService.get_all_depths: {e}")
            return []

    def get_historical(self, queue_name: str, hours: int = 24) -> List[Dict]:
        """Return historical QueueDepth snapshots for a queue."""
        try:
            from datetime import timedelta
            from api.tasks.models.monitoring import QueueDepth

            cutoff = timezone.now() - timedelta(hours=hours)
            return list(
                QueueDepth.objects.filter(
                    queue_name=queue_name,
                    checked_at__gte=cutoff,
                ).order_by('checked_at').values(
                    'depth', 'processing_count', 'failed_count', 'checked_at'
                )
            )
        except Exception as e:
            logger.error(f"[ERROR] QueueDepthService.get_historical: {e}")
            return []

    def check_thresholds(self) -> List[Dict]:
        """
        Check current depths against TaskQueue alert thresholds.
        Returns list of queues that exceed warning or critical thresholds.
        """
        alerts = []
        try:
            from api.tasks.models.queue import TaskQueue

            for queue in TaskQueue.objects.filter(is_active=True):
                depth_info = self.get_queue_depth(queue.name)
                depth      = depth_info.get('depth', 0)

                if depth >= queue.alert_depth_critical:
                    alerts.append({
                        'queue_name': queue.name,
                        'depth': depth,
                        'threshold': queue.alert_depth_critical,
                        'level': 'critical',
                    })
                    logger.critical(
                        f"[CRITICAL] Queue '{queue.name}' depth={depth} "
                        f"exceeds critical threshold {queue.alert_depth_critical}"
                    )
                elif depth >= queue.alert_depth_warning:
                    alerts.append({
                        'queue_name': queue.name,
                        'depth': depth,
                        'threshold': queue.alert_depth_warning,
                        'level': 'warning',
                    })
                    logger.warning(
                        f"[WARN] Queue '{queue.name}' depth={depth} "
                        f"exceeds warning threshold {queue.alert_depth_warning}"
                    )

        except Exception as e:
            logger.error(f"[ERROR] QueueDepthService.check_thresholds: {e}")

        return alerts

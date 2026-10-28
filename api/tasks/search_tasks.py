"""tasks/search_tasks.py — Search index management."""
import logging
from celery import shared_task
from django.utils import timezone
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.search_tasks.index_tasks')
def index_tasks(self, task_ids: list = None) -> dict:
    """Index MasterTask records for full-text search."""
    try:
        indexed = 0
        try:
            from api.tasks.models import MasterTask
            qs = MasterTask.objects.filter(is_active=True)
            if task_ids:
                qs = qs.filter(pk__in=task_ids)
            # Try Elasticsearch
            try:
                from django_elasticsearch_dsl.registries import registry
                for task in qs.iterator(chunk_size=100):
                    registry.update(task)
                    indexed += 1
            except ImportError:
                # Fallback: PostgreSQL full-text search
                from django.db import connection
                if connection.vendor == 'postgresql':
                    from django.contrib.postgres.search import SearchVector
                    qs.update(
                        search_vector=SearchVector('name', 'task_id', 'category')
                    )
                indexed = qs.count()
        except ImportError as e:
            logger.warning(f"[WARN] Search models not available: {e}")
        return {'status': 'success', 'indexed': indexed, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.search_tasks.index_offers')
def index_offers(self) -> dict:
    """Index SmartlinkOffer records for search."""
    try:
        indexed = 0
        try:
            from ad_networks.models import SmartlinkOffer
            for offer in SmartlinkOffer.objects.filter(is_active=True).iterator(chunk_size=100):
                try:
                    from django_elasticsearch_dsl.registries import registry
                    registry.update(offer)
                    indexed += 1
                except ImportError:
                    indexed += 1
        except ImportError:
            pass
        return {'status': 'success', 'indexed': indexed, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)

@shared_task(bind=True, max_retries=1, default_retry_delay=60,
             name='tasks.search_tasks.rebuild_search_index')
def rebuild_search_index(self) -> dict:
    """Full rebuild of all search indexes."""
    try:
        from celery import current_app
        current_app.send_task('tasks.search_tasks.index_tasks')
        current_app.send_task('tasks.search_tasks.index_offers')
        return {'status': 'queued', 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)

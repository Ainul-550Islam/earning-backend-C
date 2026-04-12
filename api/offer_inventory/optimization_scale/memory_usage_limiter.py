# api/offer_inventory/optimization_scale/memory_usage_limiter.py
"""Memory Usage Limiter — Prevent memory exhaustion from large operations."""
import logging

logger = logging.getLogger(__name__)

MAX_QUERY_RESULTS       = 10000
MAX_EXPORT_ROWS         = 100000
MAX_BULK_IDS            = 5000
MAX_NOTIFICATION_BATCH  = 10000


class MemoryUsageLimiter:
    """Safety guards against memory-intensive operations."""

    @staticmethod
    def limit_queryset(qs, max_results: int = MAX_QUERY_RESULTS):
        """Apply a safety cap to a queryset."""
        return qs[:max_results]

    @staticmethod
    def check_bulk_operation(item_count: int, operation: str) -> dict:
        """Safety check before bulk operations."""
        limits = {
            'ids'          : MAX_BULK_IDS,
            'export'       : MAX_EXPORT_ROWS,
            'notification' : MAX_NOTIFICATION_BATCH,
            'query'        : MAX_QUERY_RESULTS,
        }
        limit = limits.get(operation, 10000)
        if item_count > limit:
            return {
                'allowed': False,
                'reason' : f'{operation} limit is {limit:,}, requested {item_count:,}',
                'limit'  : limit,
            }
        return {'allowed': True, 'limit': limit}

    @staticmethod
    def get_process_memory() -> dict:
        """Get current process memory usage (requires psutil)."""
        try:
            import psutil, os
            process = psutil.Process(os.getpid())
            rss_mb  = process.memory_info().rss / 1024 / 1024
            return {
                'rss_mb'    : round(rss_mb, 1),
                'percent'   : round(process.memory_percent(), 1),
                'is_high'   : rss_mb > 512,
                'threshold' : 512,
            }
        except ImportError:
            return {'rss_mb': 0, 'percent': 0, 'is_high': False, 'note': 'psutil not installed'}

    @staticmethod
    def paginate_large_queryset(qs, batch_size: int = 1000):
        """
        Memory-safe iteration using keyset pagination.
        Avoids loading all records into memory.
        """
        last_id = None
        while True:
            if last_id is None:
                batch = list(qs.order_by('id')[:batch_size])
            else:
                batch = list(qs.filter(id__gt=last_id).order_by('id')[:batch_size])
            if not batch:
                break
            yield from batch
            last_id = batch[-1].id
            if len(batch) < batch_size:
                break

    @staticmethod
    def stream_large_export(qs, serializer_fn, batch_size: int = 500):
        """
        Stream large exports in batches to avoid memory spikes.
        serializer_fn: callable that converts a model instance to dict.
        """
        paginator = MemoryUsageLimiter.paginate_large_queryset(qs, batch_size)
        for obj in paginator:
            yield serializer_fn(obj)

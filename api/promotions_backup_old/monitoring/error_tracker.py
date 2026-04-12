# api/promotions/monitoring/error_tracker.py
# Error Tracker — Application errors, exceptions, performance issues
import logging, traceback
from django.core.cache import cache
logger = logging.getLogger('monitoring.errors')

class ErrorTracker:
    """Error tracking + aggregation. Sentry-lite।"""
    STREAM_KEY  = 'monitor:errors:stream'
    MAX_ERRORS  = 1000

    def capture(self, exc: Exception, context: dict = None) -> str:
        import time, uuid, hashlib
        tb      = traceback.format_exc()
        err_id  = uuid.uuid4().hex[:8]
        sig     = hashlib.md5(f'{type(exc).__name__}:{str(exc)[:100]}'.encode()).hexdigest()[:12]

        entry = {
            'id': err_id, 'type': type(exc).__name__, 'message': str(exc)[:500],
            'traceback': tb[-2000:], 'context': context or {},
            'signature': sig, 'timestamp': time.time(),
        }
        stream = cache.get(self.STREAM_KEY) or []
        stream.append(entry)
        cache.set(self.STREAM_KEY, stream[-self.MAX_ERRORS:], timeout=86400)

        # Alert on new error types
        seen_key = f'monitor:err:seen:{sig}'
        if not cache.get(seen_key):
            cache.set(seen_key, True, timeout=3600)
            logger.error(f'New error type: {type(exc).__name__}: {str(exc)[:200]}')

        return err_id

    def get_recent(self, limit: int = 50, error_type: str = None) -> list:
        stream = cache.get(self.STREAM_KEY) or []
        if error_type:
            stream = [e for e in stream if e['type'] == error_type]
        return stream[-limit:]

    def get_summary(self) -> dict:
        stream = cache.get(self.STREAM_KEY) or []
        from collections import Counter
        counts = Counter(e['type'] for e in stream)
        return {'total': len(stream), 'by_type': dict(counts.most_common(10))}

error_tracker = ErrorTracker()

def track_error(exc: Exception, **ctx):
    return error_tracker.capture(exc, ctx)

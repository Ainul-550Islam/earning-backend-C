# api/cms/graceful_shutdown.py
"""
Graceful shutdown handling for CMS.
Handles SIGTERM/SIGINT signals to finish in-flight requests before stopping.
"""
import logging
import signal
import threading
from django.conf import settings

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """
    Handles graceful shutdown on SIGTERM/SIGINT.
    Waits for in-flight requests and background tasks to complete.
    """
    _shutdown_event = threading.Event()
    _request_count = 0
    _lock = threading.Lock()

    @classmethod
    def is_shutting_down(cls) -> bool:
        return cls._shutdown_event.is_set()

    @classmethod
    def mark_request_start(cls):
        with cls._lock:
            cls._request_count += 1

    @classmethod
    def mark_request_end(cls):
        with cls._lock:
            cls._request_count = max(0, cls._request_count - 1)

    @classmethod
    def setup_signal_handlers(cls):
        """Register SIGTERM and SIGINT handlers."""
        def handler(signum, frame):
            sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
            logger.info(f"[Shutdown] Received {sig_name} — initiating graceful shutdown")
            cls._shutdown_event.set()
            # Drain in-flight requests
            import time
            timeout = getattr(settings, 'GRACEFUL_SHUTDOWN_TIMEOUT', 30)
            start = time.time()
            while cls._request_count > 0:
                if time.time() - start > timeout:
                    logger.warning(f"[Shutdown] Timeout after {timeout}s — forcing shutdown")
                    break
                logger.info(f"[Shutdown] Waiting for {cls._request_count} in-flight requests...")
                time.sleep(1)
            logger.info("[Shutdown] Clean shutdown complete")

        try:
            signal.signal(signal.SIGTERM, handler)
            signal.signal(signal.SIGINT, handler)
            logger.debug("[Shutdown] Signal handlers registered")
        except (ValueError, OSError):
            # Not in main thread — skip
            pass


class ShutdownMiddleware:
    """
    Django middleware that rejects new requests during shutdown
    and tracks in-flight request count.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        GracefulShutdown.setup_signal_handlers()

    def __call__(self, request):
        if GracefulShutdown.is_shutting_down():
            from django.http import HttpResponse
            return HttpResponse(
                '{"error": "service_shutting_down"}',
                status=503,
                content_type='application/json',
                headers={'Retry-After': '30'}
            )
        GracefulShutdown.mark_request_start()
        try:
            return self.get_response(request)
        finally:
            GracefulShutdown.mark_request_end()

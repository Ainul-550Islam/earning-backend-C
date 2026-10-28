"""
Per-app settings for Real-time Dashboard Backend.

Reads from Django settings with sensible defaults so the app is usable
out-of-the-box and can be tuned without modifying source code.

Usage throughout the app:
    from .app_settings import app_settings

    timeout = app_settings.WEBSOCKET_TIMEOUT
    cache_ttl = app_settings.CACHE_TIMEOUT

Add to your project's settings.py to override any default:

    REALTIME_DASHBOARD = {
        'WEBSOCKET_TIMEOUT': 1800,          # 30 minutes
        'CACHE_TIMEOUT': 600,               # 10 minutes
        'MAX_CONNECTIONS_PER_USER': 5,
        'METRIC_BROADCAST_BATCH_SIZE': 100,
        'STALE_CONNECTION_CLEANUP_INTERVAL': 900,   # seconds
        'DEFAULT_PAGE_SIZE': 20,
        'MAX_PAGE_SIZE': 100,
        'THROTTLE_METRIC_UPDATE': '120/minute',
        'THROTTLE_DASHBOARD_RENDER': '30/minute',
        'THROTTLE_WEBSOCKET_CONNECT': '10/minute',
        'ENABLE_CACHING': True,
    }
"""
from django.conf import settings


class _AppSettings:
    """
    Lazy proxy over `settings.REALTIME_DASHBOARD` (a dict) that falls back
    to module-level defaults for every missing key.

    Attributes are read at access time, not at import time, so the object
    is safe to construct at module level without triggering
    django.core.exceptions.ImproperlyConfigured before Django is set up.
    """

    _PREFIX = 'REALTIME_DASHBOARD'

    _DEFAULTS = {
        # ── WebSocket ─────────────────────────────────────────────────────────
        # Seconds of silence before a connection is considered stale.
        # The cleanup_stale_connections Celery task uses this value.
        'WEBSOCKET_TIMEOUT': 3600,          # 1 hour

        # How often consumers expect a client ping (seconds).
        # Clients that miss this interval should be considered gone.
        'PING_INTERVAL': 30,

        # How many seconds to wait before attempting a client reconnect.
        'RECONNECT_INTERVAL': 5,

        # Maximum concurrent WebSocket connections per user.
        # Enforced by WebSocketManagerService (not yet implemented at the
        # DB constraint level — this is a service-layer soft cap).
        'MAX_CONNECTIONS_PER_USER': 10,

        # ── Celery tasks ──────────────────────────────────────────────────────
        # Interval (seconds) for the cleanup_stale_connections beat task.
        'STALE_CONNECTION_CLEANUP_INTERVAL': 900,   # 15 minutes

        # Interval (seconds) for the broadcast_active_metrics beat task.
        'METRIC_BROADCAST_INTERVAL': 30,

        # How many active metric IDs to include in a single broadcast batch.
        # Tune down if channel-layer message size is a concern.
        'METRIC_BROADCAST_BATCH_SIZE': 200,

        # ── Caching ───────────────────────────────────────────────────────────
        # Master toggle. Set False to disable all cache.get/set calls
        # (useful for debugging or environments without a cache backend).
        'ENABLE_CACHING': True,

        # Default TTL (seconds) for cached objects.
        'CACHE_TIMEOUT': 300,           # 5 minutes

        # Per-model cache TTLs (seconds).
        'WIDGET_CACHE_TIMEOUT': 300,
        'METRIC_CACHE_TIMEOUT': 60,     # Metrics change frequently
        'DASHBOARD_CACHE_TIMEOUT': 300,
        'LAYOUT_CACHE_TIMEOUT': 600,    # Layouts rarely change

        # Cache key prefixes (must end with ':').
        'WIDGET_CACHE_PREFIX': 'rtd:widget:',
        'METRIC_CACHE_PREFIX': 'rtd:metric:',
        'DASHBOARD_CACHE_PREFIX': 'rtd:dashboard:',
        'LAYOUT_CACHE_PREFIX': 'rtd:layout:',

        # ── Pagination ────────────────────────────────────────────────────────
        'DEFAULT_PAGE_SIZE': 20,
        'MAX_PAGE_SIZE': 100,

        # ── Throttling (named scopes for DEFAULT_THROTTLE_RATES) ─────────────
        'THROTTLE_METRIC_UPDATE': '120/minute',
        'THROTTLE_DASHBOARD_RENDER': '30/minute',
        'THROTTLE_WEBSOCKET_CONNECT': '10/minute',
        'THROTTLE_HEALTH_CHECK': '120/minute',
        'THROTTLE_BURST_USER': '20/minute',
    }

    def __getattr__(self, name: str):
        if name.startswith('_'):
            raise AttributeError(name)
        if name not in self._DEFAULTS:
            raise AttributeError(
                f"'app_settings' has no attribute '{name}'. "
                f"Valid keys: {sorted(self._DEFAULTS)}"
            )
        user_config = getattr(settings, self._PREFIX, {})
        return user_config.get(name, self._DEFAULTS[name])

    def as_dict(self) -> dict:
        """Return all resolved settings as a plain dict (useful for debugging)."""
        user_config = getattr(settings, self._PREFIX, {})
        return {key: user_config.get(key, default) for key, default in self._DEFAULTS.items()}


app_settings = _AppSettings()

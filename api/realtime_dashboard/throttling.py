"""
Custom throttle classes for Real-time Dashboard Backend.

RETRY-AFTER HEADERS (automatic via DRF):
    When any throttle rejects a request, DRF raises Throttled(wait=N) and
    the custom_exception_handler converts it to HTTP 429 with:
        Retry-After: <seconds>
    No extra code required here — DRF's exception_handler already injects
    the header from exc.wait. Verified via TestThrottleRetryAfterHeader.

Add to settings.py:

    REST_FRAMEWORK = {
        'DEFAULT_THROTTLE_CLASSES': [
            'rest_framework.throttling.AnonRateThrottle',
            'rest_framework.throttling.UserRateThrottle',
        ],
        'DEFAULT_THROTTLE_RATES': {
            'anon':                 '60/hour',
            'user':                 '1000/hour',
            # Named scopes used by the custom classes below:
            'metric_update':        '120/minute',   # POST /api/metrics/<id>/
            'dashboard_render':     '30/minute',    # GET /api/dashboards/<id>/render/
            'websocket_connect':    '10/minute',    # WS connect handshakes
            'health_check':         '120/minute',   # GET /api/health/
            'burst_user':           '20/minute',    # Layout write operations
        },
    }

Per-viewset override example:

    class RealTimeMetricViewSet(viewsets.ModelViewSet):
        throttle_classes = [MetricUpdateThrottle]

Named scopes map to 'DEFAULT_THROTTLE_RATES' keys. If a key is absent,
the throttle is DISABLED for that scope (tests set DEFAULT_THROTTLE_RATES
to all high limits via tests/settings.py so throttle tests are isolated).
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class MetricUpdateThrottle(UserRateThrottle):
    """
    Throttle for metric update endpoints (POST /api/metrics/<id>/activate,
    PATCH /api/metrics/<id>/, aggregate, etc.).

    Each metric save triggers a WebSocket broadcast to every subscriber.
    An unbounded write rate fans out into a channel-layer DDoS.
    120/min (2/sec) is generous for real-time data while preventing abuse.

    Retry-After header: added automatically by DRF's Throttled exception.
    """
    scope = 'metric_update'


class DashboardRenderThrottle(UserRateThrottle):
    """
    Throttle for GET /api/dashboards/<id>/render/.

    Rendering assembles widgets + metrics in a single synchronous DB
    transaction. High call rates starve the connection pool.
    30/min covers legitimate polling at 2-second intervals.

    Retry-After header: added automatically by DRF's Throttled exception.
    """
    scope = 'dashboard_render'


class WebSocketConnectThrottle(AnonRateThrottle):
    """
    Throttle for WebSocket connection handshakes.

    Applied at the consumer level (base_consumer.py track_connect())
    rather than at a DRF viewset, because the WS handshake is an HTTP
    Upgrade request handled by Channels, not DRF's APIView dispatch.

    The cache-counter implementation in TrackedConsumerMixin closes
    connections with code 4029 (HTTP 429 equivalent) when exceeded.
    """
    scope = 'websocket_connect'


class HealthCheckThrottle(AnonRateThrottle):
    """
    Throttle for GET /api/health/.

    Load balancers probe this frequently; 120/min per IP handles any
    reasonable probe interval while blocking runaway scrapers.
    """
    scope = 'health_check'


class BurstUserThrottle(UserRateThrottle):
    """
    Tight burst throttle for write operations on shared resources.

    Applied to DashboardLayoutViewSet POST/PUT/DELETE via get_throttles().
    Layout changes invalidate cached renders for ALL users — a 50-mutation
    burst would cascade into 50 × N cache invalidations.

    Rate: 20/minute per authenticated user (add to DEFAULT_THROTTLE_RATES).
    """
    scope = 'burst_user'

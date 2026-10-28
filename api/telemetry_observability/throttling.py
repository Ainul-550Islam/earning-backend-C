"""
API rate-limiting throttle classes for Telemetry Observability.

Wired in settings/base.py → REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'].
DRY: all rate logic in one place — never hardcode in views.

Hierarchy (highest → lowest rate):
  ServiceAccountThrottle > TelemetryUserThrottle > TelemetryAnonThrottle

Ingest-specific throttles (higher limits for write-heavy endpoints):
  MetricIngestThrottle  — POST /metrics/ and /metrics/batch/
  LogIngestThrottle     — POST /logs/   and /logs/batch/
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


# ── Default throttles (applied to all endpoints) ──────────────────────────────

class TelemetryAnonThrottle(AnonRateThrottle):
    """
    Unauthenticated requests: conservative limit.
    Rate set by THROTTLE_ANON env var (default: 100/hour).
    """
    scope = 'anon'


class TelemetryUserThrottle(UserRateThrottle):
    """
    Authenticated users: standard limit.
    Rate set by THROTTLE_USER env var (default: 1000/hour).
    """
    scope = 'user'


class ServiceAccountThrottle(UserRateThrottle):
    """
    Service accounts (metric agents, log shippers): high limit.
    Rate set by THROTTLE_SERVICE env var (default: 10000/hour).
    Apply to specific viewsets with: throttle_classes = [ServiceAccountThrottle]
    """
    scope = 'service_account'


# ── Ingest-specific throttles ─────────────────────────────────────────────────

class MetricIngestThrottle(UserRateThrottle):
    """
    High-frequency metric ingestion limit.
    Rate set by THROTTLE_METRIC_INGEST env var (default: 5000/minute).
    Apply on MetricViewSet.create and batch_create actions.
    """
    scope = 'metric_ingest'


class LogIngestThrottle(UserRateThrottle):
    """
    High-frequency log ingestion limit.
    Rate set by THROTTLE_LOG_INGEST env var (default: 5000/minute).
    Apply on LogViewSet.create and batch_create actions.
    """
    scope = 'log_ingest'


# ── Read-only throttle ────────────────────────────────────────────────────────

class ReadOnlyThrottle(UserRateThrottle):
    """
    Higher read limit for dashboard / analytics consumers.
    Rate: 2000/hour (hardcoded — dashboards are read-heavy but bounded).
    """
    scope = 'user'
    rate  = '2000/hour'

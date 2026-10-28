"""
payout_queue/throttles.py  ← NEW FILE

Why this exists
---------------
viewsets.py originally had zero throttle_classes. A burst attack on
POST /batches/{id}/process/ would fire unbounded Celery tasks, one per
request. This file defines three throttle tiers:

  PayoutBurstThrottle      — short window, for spike protection
  PayoutSustainedThrottle  — longer window, for sustained abuse
  ProcessBatchThrottle     — tighter limit specifically on process/retry
                             endpoints that spawn expensive Celery tasks

Usage in viewsets
-----------------
    from .throttles import PayoutBurstThrottle, PayoutSustainedThrottle, ProcessBatchThrottle

    class PayoutBatchViewSet(viewsets.ModelViewSet):
        throttle_classes = [PayoutBurstThrottle, PayoutSustainedThrottle]

    # Override per-action for process/process-async/retry:
    @action(...)
    def process(self, request, ...):
        self.throttle_classes = [ProcessBatchThrottle]
        self.check_throttles(request)
        ...

Default rates are conservative. Tune via PAYOUT_THROTTLE_RATES in settings:

    PAYOUT_THROTTLE_RATES = {
        "burst":   "60/min",
        "sustained": "1000/hour",
        "process": "10/min",
    }

Superusers bypass all throttles (see has_bypass()).
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

def _get_rate(key: str, default: str) -> str:
    """Read from PAYOUT_THROTTLE_RATES setting or fall back to default."""
    rates: dict = getattr(settings, "PAYOUT_THROTTLE_RATES", {})
    return rates.get(key, default)

class _PayoutBaseThrottle(SimpleRateThrottle):
    """
    Base class for all payout throttles.

    Adds:
      - Superuser bypass: superusers are never throttled.
      - cache_format override: uses 'payout_{scope}_{ident}' keys so
        payout throttles don't collide with the rest of the application.
    """

    cache_format = "payout_throttle_%(scope)s_%(ident)s"

    # Subclasses must set this
    _settings_key: str = ""
    _default_rate: str = "60/min"

    def get_rate(self) -> str:  # type: ignore[override]
        return _get_rate(self._settings_key, self._default_rate)

    def allow_request(self, request, view) -> bool:
        if self._is_superuser(request):
            return True
        return super().allow_request(request, view)

    @staticmethod
    def _is_superuser(request) -> bool:
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_superuser", False))

    def get_cache_key(self, request, view) -> Optional[str]:
        """
        Use user PK for authenticated requests; fall back to IP for anonymous.
        Anonymous requests on payout endpoints should be rare (all require auth),
        but we handle them gracefully rather than raising.
        """
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            ident = str(user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}

class PayoutBurstThrottle(_PayoutBaseThrottle):
    """
    60 requests / minute per authenticated user.

    Protects against rapid automated calls. Applied on all payout_queue
    viewsets as the first throttle in the chain.

    Override via settings:
        PAYOUT_THROTTLE_RATES = {"burst": "120/min"}   # more lenient
    """

    scope = "payout_burst"
    _settings_key = "burst"
    _default_rate = "60/min"

class PayoutSustainedThrottle(_PayoutBaseThrottle):
    """
    1 000 requests / hour per authenticated user.

    Catches sustained crawlers or runaway automation that bypasses the
    burst window by spreading requests over time.

    Override via settings:
        PAYOUT_THROTTLE_RATES = {"sustained": "2000/hour"}
    """

    scope = "payout_sustained"
    _settings_key = "sustained"
    _default_rate = "1000/hour"

class ProcessBatchThrottle(_PayoutBaseThrottle):
    """
    10 requests / minute per user.

    Applied specifically to expensive Celery-task-spawning endpoints:
      POST /batches/{id}/process/
      POST /batches/{id}/process-async/
      POST /items/{id}/retry/
      POST /items/retry-due/

    Each of these spawns at least one Celery task. Without this throttle,
    a single staff user could queue hundreds of tasks in seconds.

    Override via settings:
        PAYOUT_THROTTLE_RATES = {"process": "30/min"}  # higher-traffic ops
    """

    scope = "payout_process"
    _settings_key = "process"
    _default_rate = "10/min"

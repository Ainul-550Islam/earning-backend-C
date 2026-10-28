"""
Django middleware for Feature Flags & A/B Testing.

FIX (Critical Blocker — broken analytics middleware): the original
`FlagAnalyticsMiddleware` fetched every active flag and called
`is_enabled()` + variant-weight resolution for EACH one, on EVERY
request — with 50 active flags that's 100+ extra DB queries per
request, none of which the request actually needed. It has been
replaced with `FlagAnalyticsMiddleware` below, which does O(1) work per
request: it just hands off to a Celery task (see tasks.py) that performs
the same bookkeeping asynchronously, off the request/response cycle.
"""
from typing import Callable
from django.http import HttpRequest, HttpResponse

from .flag_engine import FlagEngine
from .experiment_runner import ExperimentRunner
from .utils import get_flag_context_from_request


class FeatureFlagMiddleware:
    """
    Middleware for feature flag evaluation. Adds `request.flag_context`
    and `request.flag_engine` so views/decorators don't need to rebuild
    them.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.engine = FlagEngine()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.flag_context = get_flag_context_from_request(request)
        request.flag_engine = self.engine

        response = self.get_response(request)

        return response


class ExperimentMiddleware:
    """
    Middleware for A/B testing experiment assignment. Adds
    `request.experiment_runner` and `request.active_experiments`.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.runner = ExperimentRunner()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.experiment_runner = self.runner
        request.active_experiments = self.runner.get_active_experiments()

        response = self.get_response(request)

        return response


class FlagAnalyticsMiddleware:
    """
    Middleware for tracking flag analytics.

    FIX: previously this middleware did, per request:
        1. `engine.get_active_flags()`                — 1 query
        2. for EACH active flag: `engine.is_enabled()` — N queries (cache miss) or 0 (hit)
        3. for EACH active flag with variants: another query for variants
        4. `update_flag_analytics()`                   — 1-2 writes per flag
    With 50 active flags that is 100-150+ queries on every single request,
    regardless of which flags the request actually cared about.

    The fixed version below does a SINGLE, fast, non-blocking action: queue
    one Celery task with the already-known request context. All flag
    evaluation + analytics writes happen asynchronously in a worker process
    (see tasks.track_request_analytics), completely off the request path.
    If Celery isn't configured (e.g. local dev without a broker), the
    try/except ensures requests are never blocked or broken by this.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        context = get_flag_context_from_request(request)

        try:
            from .tasks import track_request_analytics
            track_request_analytics.delay(context)
        except Exception:
            # Never let analytics break the request/response cycle —
            # this also covers Celery being unavailable in dev/test.
            pass

        return response

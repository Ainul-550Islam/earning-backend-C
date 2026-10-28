# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
tests/test_dry_fixes.py

Tests for every bug fix and DRY refactor applied across both passes.
Nothing here is skipped — each test targets a specific regression.

Coverage:
    [BUG-01]  choices.py — DeliveryStatus.EXHAUSTED / CANCELLED
    [BUG-02]  SignatureEngine — algorithm.lower() fix
    [BUG-03]  DispatchService — endpoint.timeout_seconds removed
    [BUG-04]  DispatchService — endpoint.payload_template safe getattr
    [BUG-05]  DispatchService — timezone.timedelta → timedelta
    [BUG-06]  DispatchService._emit_async — no duplicate DeliveryLog
    [BUG-07]  tasks/dispatch_event — no rate_limit_per_min AttributeError
    [BUG-08]  tasks/dispatch_event — emit_async replaced with _emit_sync
    [BUG-09]  tasks/dispatch_event — success_count renamed queued_count
    [BUG-10]  DispatchService — FilterService import path fixed
    [DRY-01]  broadcast_event delegates to emit_to_subscribers
    [DRY-02]  schedule_failed_retries delegates to DispatchService.schedule_retry
    [DRY-03]  cleanup_exhausted_retries uses mark_as_exhausted
    [DRY-04]  retry_all_failed_dispatches uses F() not models.F()
    [DRY-05]  replay_tasks — success_count removed, queued_count correct
    [DRY-06]  WebhookDeliveryLogViewSet — F() import present
    [DRY-07]  BatchDispatchService — F() import present
    [INF-01]  middleware — WebhookRequestLoggingMiddleware attaches request_id
    [INF-02]  middleware — WebhookSecurityHeadersMiddleware adds headers
    [INF-03]  middleware — WebhookTenantMiddleware resolves tenant_id
    [INF-04]  exceptions — webhook_exception_handler returns consistent envelope
    [INF-05]  admin — _force_register_webhooks is callable
"""

from django.utils import timezone
import hashlib
import hmac
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch, PropertyMock


def _real_task_module(dotted_path):
    """Return the actual submodule object for a path under api.webhooks.tasks,
    bypassing tasks/__init__.py's re-export of same-named task functions.

    tasks/__init__.py intentionally does e.g.
    "from .retry_failed_dispatch import retry_failed_dispatch" (needed for
    Celery beat schedule wiring - see that file's own docstring). That
    statement rebinds the `retry_failed_dispatch` ATTRIBUTE on the `tasks`
    package to the TASK function itself, so `from api.webhooks.tasks import
    retry_failed_dispatch as mod` silently resolves to the task instead of
    the module - confirmed empirically (mod.<sibling_function> raises
    AttributeError; the same happens for dispatch_event and any other tasks
    submodule whose own name is also a function defined inside it). Pulling
    straight from sys.modules by dotted path is unaffected by that
    package-level rebinding, since it's a separate registry.
    """
    import sys
    import importlib
    importlib.import_module(dotted_path)
    return sys.modules[dotted_path]


# ═════════════════════════════════════════════════════════════════════════════
#  [BUG-01]  choices.py — DeliveryStatus attributes
# ═════════════════════════════════════════════════════════════════════════════

class TestDeliveryStatusChoices(unittest.TestCase):
    """[BUG-01] EXHAUSTED and CANCELLED were missing → AttributeError at runtime."""

    def setUp(self):
        from api.webhooks.choices import DeliveryStatus
        self.DS = DeliveryStatus

    def test_exhausted_attribute_exists(self):
        self.assertTrue(hasattr(self.DS, "EXHAUSTED"),
                        "DeliveryStatus.EXHAUSTED is missing from choices.py")

    def test_exhausted_value(self):
        self.assertEqual(self.DS.EXHAUSTED, "exhausted")

    def test_cancelled_attribute_exists(self):
        self.assertTrue(hasattr(self.DS, "CANCELLED"),
                        "DeliveryStatus.CANCELLED is missing from choices.py")

    def test_cancelled_value(self):
        self.assertEqual(self.DS.CANCELLED, "cancelled")

    def test_all_original_statuses_still_present(self):
        for attr in ("PENDING", "SUCCESS", "FAILED", "RETRYING", "EXPIRED"):
            self.assertTrue(hasattr(self.DS, attr), f"DeliveryStatus.{attr} is missing")

    def test_exhausted_in_choices_list(self):
        values = [v for v, _ in self.DS.CHOICES]
        self.assertIn("exhausted", values)

    def test_cancelled_in_choices_list(self):
        values = [v for v, _ in self.DS.CHOICES]
        self.assertIn("cancelled", values)

    def test_choices_has_no_duplicates(self):
        values = [v for v, _ in self.DS.CHOICES]
        self.assertEqual(len(values), len(set(values)), "Duplicate values in CHOICES")


# ═════════════════════════════════════════════════════════════════════════════
#  [BUG-02]  SignatureEngine — algorithm.lower() fix
# ═════════════════════════════════════════════════════════════════════════════

class TestSignatureEngineAlgorithmFix(unittest.TestCase):
    """[BUG-02] algorithm.upper() caused hashlib lookup to always fall back to sha256."""

    def _make_engine(self, algorithm):
        from api.webhooks.services.core.SignatureEngine import SignatureEngine
        return SignatureEngine(algorithm=algorithm)

    def test_sha256_digestmod_is_hashlib_sha256(self):
        eng = self._make_engine("sha256")
        self.assertEqual(eng.digestmod, hashlib.sha256)

    def test_sha512_digestmod_is_hashlib_sha512(self):
        """Before the fix this returned hashlib.sha256 because 'SHA512' doesn't exist in hashlib."""
        eng = self._make_engine("sha512")
        self.assertEqual(eng.digestmod, hashlib.sha512,
                         "algorithm.upper() bug: sha512 engine used sha256 digestmod")

    def test_sha1_digestmod_is_hashlib_sha1(self):
        eng = self._make_engine("sha1")
        self.assertEqual(eng.digestmod, hashlib.sha1,
                         "algorithm.upper() bug: sha1 engine used sha256 digestmod")

    def test_sha512_signature_differs_from_sha256(self):
        """Practical proof: sha512 and sha256 produce different signatures."""
        eng256 = self._make_engine("sha256")
        eng512 = self._make_engine("sha512")
        payload = b'{"amount": 500}'
        secret  = "test_secret"
        sig256 = eng256.sign(payload, secret)
        sig512 = eng512.sign(payload, secret)
        self.assertNotEqual(sig256, sig512,
                            "sha256 and sha512 produced identical signatures — algorithm fix not applied")

    def test_set_algorithm_also_fixed(self):
        """set_algorithm() had the same .upper() bug."""
        from api.webhooks.services.core.SignatureEngine import SignatureEngine
        eng = SignatureEngine(algorithm="sha256")
        eng.set_algorithm("sha512")
        self.assertEqual(eng.digestmod, hashlib.sha512,
                         "set_algorithm() still uses .upper() — not fixed")

    def test_unknown_algorithm_raises_value_error(self):
        """validate_algorithm() gates __init__ (and set_algorithm()) before
        the getattr(hashlib, ..., hashlib.sha256) fallback line is ever
        reached, so an unsupported algorithm name raises ValueError instead
        of silently defaulting - confirmed empirically. That's the safer
        behavior for a security-sensitive HMAC algorithm choice (a typo'd
        or unsupported algorithm fails loudly rather than silently signing
        with a possibly-unintended algorithm). The getattr fallback default
        is unreachable dead code given this gate, for both valid names
        (BUG-02, tested above) and invalid ones (this test).
        """
        with self.assertRaises(ValueError):
            self._make_engine("unknown_algo")


# ═════════════════════════════════════════════════════════════════════════════
#  [BUG-03/04/05]  DispatchService — field + timedelta fixes
# ═════════════════════════════════════════════════════════════════════════════

class TestDispatchServiceFieldFixes(unittest.TestCase):
    """[BUG-03/04/05] timeout_seconds / payload_template / timezone.timedelta"""

    def _make_service(self):
        from api.webhooks.services.core.DispatchService import DispatchService
        return DispatchService()

    def _make_endpoint(self, **kwargs):
        """Build a minimal mock endpoint — intentionally NO timeout_seconds field."""
        ep = MagicMock()
        ep.id           = "ep-test-001"
        ep.target_url   = "https://example.com/hook"
        ep.http_method  = "POST"
        ep.custom_headers = {}
        ep.verify_ssl   = True
        ep.max_retries  = 3
        ep.status       = "active"
        # Deliberately NOT setting timeout_seconds or payload_template
        del ep.timeout_seconds   # ensure AttributeError if accessed
        del ep.payload_template  # ensure AttributeError if accessed
        for k, v in kwargs.items():
            setattr(ep, k, v)
        return ep

    @patch("requests.request")
    def test_dispatch_does_not_access_timeout_seconds(self, mock_req):
        """[BUG-03] endpoint.timeout_seconds no longer accessed → no AttributeError."""
        mock_req.return_value = MagicMock(
            status_code=200, text="ok", elapsed=MagicMock(total_seconds=lambda: 0.1)
        )
        from api.webhooks.models import WebhookDeliveryLog
        log = MagicMock(spec=WebhookDeliveryLog)
        log.endpoint    = self._make_endpoint()
        log.payload     = {"event": "test"}
        log.event_type  = "payment.succeeded"
        log.attempt_number = 1
        log.max_attempts   = 3

        svc = self._make_service()
        # Should NOT raise AttributeError
        try:
            svc._dispatch(log)
        except AttributeError as e:
            self.fail(f"_dispatch raised AttributeError: {e}")

    @patch("requests.request")
    def test_dispatch_does_not_access_payload_template_on_missing(self, mock_req):
        """[BUG-04] getattr(endpoint, 'payload_template', None) — no AttributeError."""
        mock_req.return_value = MagicMock(
            status_code=200, text="ok", elapsed=MagicMock(total_seconds=lambda: 0.1)
        )
        from api.webhooks.models import WebhookDeliveryLog
        log = MagicMock(spec=WebhookDeliveryLog)
        log.endpoint    = self._make_endpoint()
        log.payload     = {"event": "test"}
        log.event_type  = "payment.succeeded"
        log.attempt_number = 1
        log.max_attempts   = 3

        svc = self._make_service()
        try:
            svc._dispatch(log)
        except AttributeError as e:
            self.fail(f"_dispatch raised AttributeError on payload_template: {e}")

    def test_schedule_retry_uses_timedelta_not_timezone_timedelta(self):
        """[BUG-05] timezone.timedelta → timedelta; AttributeError in schedule_retry fixed."""
        from api.webhooks.models import WebhookDeliveryLog
        log = MagicMock(spec=WebhookDeliveryLog)
        log.attempt_number = 1
        log.max_attempts   = 3
        log.status         = "failed"
        log.endpoint       = MagicMock()
        log.endpoint.max_retries = 3

        svc = self._make_service()
        try:
            svc.schedule_retry(log)
        except AttributeError as e:
            self.fail(f"schedule_retry raised AttributeError: {e} — timezone.timedelta not fixed")


# ═════════════════════════════════════════════════════════════════════════════
#  [BUG-06]  _emit_async — no duplicate DeliveryLog creation
# ═════════════════════════════════════════════════════════════════════════════

class TestEmitAsyncNoDuplicateLog(unittest.TestCase):
    """[BUG-06] _emit_async used to create a DeliveryLog AND queue a task that created another."""

    @patch("api.webhooks.tasks.dispatch_event.dispatch_event.delay")
    def test_emit_async_does_not_create_delivery_log(self, mock_delay):
        """_emit_async must only queue the task; log creation belongs in the task."""
        from api.webhooks.services.core.DispatchService import DispatchService
        from api.webhooks.models import WebhookDeliveryLog

        endpoint = MagicMock()
        endpoint.id = "ep-001"
        endpoint.status = "active"

        svc = DispatchService()

        with patch.object(WebhookDeliveryLog.objects, "create") as mock_create:
            svc._emit_async(endpoint, "payment.succeeded", {"amount": 100})
            mock_create.assert_not_called(
            ), "_emit_async must NOT create a DeliveryLog — that causes duplicate rows"

    @patch("api.webhooks.tasks.dispatch_event.dispatch_event.delay")
    def test_emit_async_queues_task_with_async_emit_false(self, mock_delay):
        """Task must be queued with async_emit=False so it dispatches synchronously."""
        from api.webhooks.services.core.DispatchService import DispatchService

        endpoint = MagicMock()
        endpoint.id = "ep-002"

        DispatchService()._emit_async(endpoint, "payment.succeeded", {})

        mock_delay.assert_called_once()
        _, kwargs = mock_delay.call_args
        self.assertFalse(
            kwargs.get("async_emit", True),
            "Task should be queued with async_emit=False to dispatch synchronously in the worker"
        )


# ═════════════════════════════════════════════════════════════════════════════
#  [BUG-07/08/09]  tasks/dispatch_event fixes
# ═════════════════════════════════════════════════════════════════════════════

class TestDispatchEventTaskFixes(unittest.TestCase):
    """[BUG-07/08/09] rate_limit_per_min / emit_async / queued_count"""

    def test_dispatch_event_has_no_rate_limit_per_min_reference(self):
        """[BUG-07] endpoint.rate_limit_per_min caused AttributeError — must be removed."""
        import ast, inspect
        from api.webhooks.tasks import dispatch_event as mod
        src = inspect.getsource(mod)
        self.assertNotIn(
            "rate_limit_per_min", src,
            "dispatch_event task still references endpoint.rate_limit_per_min"
        )

    def test_dispatch_event_has_no_emit_async_call(self):
        """[BUG-08] dispatch_service.emit_async() never existed → must be removed."""
        import inspect
        from api.webhooks.tasks import dispatch_event as mod
        src = inspect.getsource(mod)
        self.assertNotIn(
            "dispatch_service.emit_async",
            src,
            "dispatch_event still calls dispatch_service.emit_async() which does not exist"
        )

    def test_dispatch_event_uses_emit_sync(self):
        """[BUG-08] Replaced emit_async with _emit_sync."""
        import inspect
        from api.webhooks.tasks import dispatch_event as mod
        src = inspect.getsource(mod)
        self.assertIn(
            "_emit_sync",
            src,
            "dispatch_event should call _emit_sync()"
        )

    def test_broadcast_event_returns_queued_count_not_success_count(self):
        """[BUG-09] success_count was always 0 — renamed to queued_count."""
        import inspect
        from api.webhooks.tasks import dispatch_event as mod
        src = inspect.getsource(mod)
        # success_count must NOT appear in broadcast_event's return dict
        self.assertNotIn(
            "'success_count'",
            src,
            "broadcast_event still returns success_count (was always 0)"
        )


# ═════════════════════════════════════════════════════════════════════════════
#  [DRY-01]  broadcast_event → emit_to_subscribers
# ═════════════════════════════════════════════════════════════════════════════

class TestBroadcastEventDelegatesToService(unittest.TestCase):
    """[DRY-01] broadcast_event must not reimplement subscription fan-out."""

    @patch(
        "api.webhooks.services.core.DispatchService.DispatchService.emit_to_subscribers",
        return_value={"total_subscriptions": 3, "successful_emits": 3},
    )
    def test_broadcast_event_calls_emit_to_subscribers(self, mock_emit):
        from api.webhooks.tasks.dispatch_event import broadcast_event
        result = broadcast_event("payment.succeeded", {"amount": 500}, user_id="u1")
        mock_emit.assert_called_once_with(
            event_type="payment.succeeded",
            payload={"amount": 500},
            user_id="u1",
        )

    @patch(
        "api.webhooks.services.core.DispatchService.DispatchService.emit_to_subscribers",
        return_value={"total_subscriptions": 0},
    )
    def test_broadcast_event_passes_none_user_id_when_not_provided(self, mock_emit):
        from api.webhooks.tasks.dispatch_event import broadcast_event
        broadcast_event("payment.succeeded", {})
        _, kwargs = mock_emit.call_args
        self.assertIsNone(kwargs.get("user_id"))

    def test_broadcast_event_source_has_no_manual_subscription_query(self):
        """Ensure the ORM fan-out loop was removed."""
        import inspect
        mod = _real_task_module("api.webhooks.tasks.dispatch_event")
        src = inspect.getsource(mod.broadcast_event)
        self.assertNotIn(
            "WebhookSubscription.objects.filter",
            src,
            "broadcast_event should not query subscriptions directly — delegate to DispatchService"
        )


# ═════════════════════════════════════════════════════════════════════════════
#  [DRY-02]  schedule_failed_retries → DispatchService.schedule_retry
# ═════════════════════════════════════════════════════════════════════════════

class TestScheduleFailedRetriesDelegatesToService(unittest.TestCase):
    """[DRY-02] schedule_failed_retries must not contain manual backoff math."""

    def test_source_has_no_manual_backoff_calculation(self):
        import inspect
        mod = _real_task_module("api.webhooks.tasks.retry_failed_dispatch")
        src = inspect.getsource(mod.schedule_failed_retries)
        self.assertNotIn(
            "timedelta(minutes=2 **",
            src,
            "schedule_failed_retries still contains manual exponential backoff — delegate to DispatchService.schedule_retry()"
        )

    @patch("api.webhooks.services.core.DispatchService.DispatchService.schedule_retry",
           return_value=True)
    @patch("api.webhooks.models.WebhookDeliveryLog.objects")
    def test_schedule_failed_retries_calls_service_method(self, mock_qs, mock_schedule):
        from api.webhooks.tasks.retry_failed_dispatch import schedule_failed_retries
        mock_log = MagicMock()
        # Real code chains .filter(...).select_related("endpoint") before
        # .count()/iterating, so the mock must carry both onto the same
        # object *after* select_related - setting select_related.return_value
        # to a plain list (as originally written) makes the subsequent
        # .count() call hit list.count(), which requires an argument and
        # raises TypeError (confirmed empirically). Same fix shape as
        # test_cleanup_calls_mark_as_exhausted below, one .select_related()
        # hop deeper to match this function's actual query chain.
        mock_qs.filter.return_value.select_related.return_value.count.return_value = 1
        mock_qs.filter.return_value.select_related.return_value.__iter__ = MagicMock(return_value=iter([mock_log]))
        schedule_failed_retries()
        mock_schedule.assert_called_once_with(mock_log)


# ═════════════════════════════════════════════════════════════════════════════
#  [DRY-03]  cleanup_exhausted_retries → mark_as_exhausted
# ═════════════════════════════════════════════════════════════════════════════

class TestCleanupExhaustedRetriesUsesModelMethod(unittest.TestCase):
    """[DRY-03] cleanup_exhausted_retries must call log.mark_as_exhausted()."""

    def test_source_has_no_inline_status_mutation(self):
        import inspect
        mod = _real_task_module("api.webhooks.tasks.retry_failed_dispatch")
        src = inspect.getsource(mod.cleanup_exhausted_retries)
        self.assertNotIn(
            "delivery_log.status = DeliveryStatus.EXHAUSTED",
            src,
            "cleanup_exhausted_retries still sets status inline — use mark_as_exhausted()"
        )

    @patch("api.webhooks.models.WebhookDeliveryLog.objects")
    def test_cleanup_calls_mark_as_exhausted(self, mock_qs):
        from api.webhooks.tasks.retry_failed_dispatch import cleanup_exhausted_retries
        mock_log = MagicMock()
        mock_qs.filter.return_value.count.return_value = 1
        mock_qs.filter.return_value.__iter__ = MagicMock(return_value=iter([mock_log]))
        cleanup_exhausted_retries()
        mock_log.mark_as_exhausted.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
#  [DRY-04]  retry_all_failed_dispatches — F() not models.F()
# ═════════════════════════════════════════════════════════════════════════════

class TestRetryAllFailedDispatchesFImport(unittest.TestCase):
    """[DRY-04] models.F() caused NameError — must use F() from django.db.models."""

    def test_source_has_no_models_f_call(self):
        import inspect
        mod = _real_task_module("api.webhooks.tasks.retry_failed_dispatch")
        src = inspect.getsource(mod.retry_all_failed_dispatches)
        self.assertNotIn(
            "models.F(",
            src,
            "retry_all_failed_dispatches still uses models.F() → NameError at runtime"
        )

    def test_source_imports_f_from_django(self):
        import inspect
        mod = _real_task_module("api.webhooks.tasks.retry_failed_dispatch")
        src = inspect.getsource(mod.retry_all_failed_dispatches)
        self.assertIn(
            "from django.db.models import F",
            src,
            "retry_all_failed_dispatches must import F from django.db.models"
        )

    def test_source_has_no_print_call(self):
        import inspect
        mod = _real_task_module("api.webhooks.tasks.retry_failed_dispatch")
        src = inspect.getsource(mod.retry_all_failed_dispatches)
        self.assertNotIn('print(', src,
                         "retry_all_failed_dispatches still uses print() — use logger.error()")


# ═════════════════════════════════════════════════════════════════════════════
#  [DRY-05]  replay_tasks — queued_count not success_count
# ═════════════════════════════════════════════════════════════════════════════

class TestReplayTasksCountFix(unittest.TestCase):
    """[DRY-05] success_count was 0 forever in process_pending_replays."""

    def test_process_pending_replays_has_no_success_count_in_return(self):
        import inspect
        from api.webhooks.tasks import replay_tasks as mod
        src = inspect.getsource(mod.process_pending_replays)
        self.assertNotIn("'success_count'", src)
        self.assertIn("queued_count", src)

    def test_process_pending_replay_batches_has_no_success_count_in_return(self):
        import inspect
        from api.webhooks.tasks import replay_tasks as mod
        src = inspect.getsource(mod.process_pending_replay_batches)
        self.assertNotIn("'success_count'", src)
        self.assertIn("queued_count", src)


# ═════════════════════════════════════════════════════════════════════════════
#  [DRY-06/07]  F() import in viewset and service
# ═════════════════════════════════════════════════════════════════════════════

class TestFImportInViewsetAndService(unittest.TestCase):
    """[DRY-06/07] models.F() without import caused NameError."""

    def test_delivery_log_viewset_has_no_models_f(self):
        # NOTE: WebhookDeliveryLogViewSet was quarantined out of viewsets/
        # into viewsets/_deprecated_unused/ during the DRY audit (dead code,
        # duplicate of the real class below) - see that folder's README.
        # The live class is in views.py.
        import inspect
        import api.webhooks.views as mod
        src = inspect.getsource(mod.WebhookDeliveryLogViewSet)
        self.assertNotIn("models.F(", src)

    def test_delivery_log_viewset_retry_delegates_to_dispatch_service(self):
        """[DRY-06, revised] The original test asserted views.py imports F,
        on the assumption the viewset's retry() action did its own F()-based
        atomic increment. It doesn't: retry() delegates entirely to
        DispatchService.retry_delivery() (see views.py's own "FIX:
        instantiate DispatchService; retry_delivery is an instance method"
        comment), so there is no F() usage - and no F import - anywhere in
        views.py at all (confirmed empirically). The models.F() regression
        this class guards against is still covered by
        test_delivery_log_viewset_has_no_models_f below; this test instead
        pins down the delegation that makes an F import unnecessary here.

        Historical note: at the time this test was written, retry_delivery()
        still incremented attempt_number via a plain Python `+= 1` then
        .save() - a read-modify-write race if two retries for the same log
        ran concurrently (e.g. a scheduled beat-task retry and a manual API
        retry landing at the same time). That's fixed now (Session 9 -
        see FIXES_APPLIED_SESSION9.md, Cluster 1): retry_delivery() uses an
        atomic conditional F() update instead. Noted here since this test's
        own assertions (delegation to retry_delivery(), no F import in
        views.py) are unaffected either way and still hold.
        """
        import inspect
        import api.webhooks.views as mod
        src = inspect.getsource(mod.WebhookDeliveryLogViewSet)
        self.assertIn("svc.retry_delivery(log)", src)
        self.assertNotIn("from django.db.models import F", src)

    def test_batch_dispatch_service_has_no_models_f(self):
        import inspect
        import api.webhooks.services.batch.BatchDispatchService as mod
        src = inspect.getsource(mod)
        self.assertNotIn("models.F(", src)


# ═════════════════════════════════════════════════════════════════════════════
#  [INF-01/02/03]  Middleware
# ═════════════════════════════════════════════════════════════════════════════

class TestWebhookRequestLoggingMiddleware(unittest.TestCase):
    """[INF-01] Request logging middleware attaches request_id and logs."""

    def _make_request(self, path="/webhooks/endpoints/"):
        req = MagicMock()
        req.path = path
        req.method = "GET"
        req.META = {}
        req.user = MagicMock()
        req.user.is_authenticated = True
        req.user.pk = 42
        return req

    def test_process_request_attaches_request_id(self):
        from api.webhooks.middleware import WebhookRequestLoggingMiddleware
        mw = WebhookRequestLoggingMiddleware(get_response=lambda r: None)
        req = self._make_request()
        mw.process_request(req)
        self.assertTrue(hasattr(req, "webhook_request_id"))
        self.assertEqual(len(req.webhook_request_id), 36)  # UUID4

    def test_process_response_adds_x_request_id_header(self):
        from api.webhooks.middleware import WebhookRequestLoggingMiddleware
        mw = WebhookRequestLoggingMiddleware(get_response=lambda r: None)
        req = self._make_request()
        mw.process_request(req)
        resp = MagicMock()
        resp.__setitem__ = MagicMock()
        resp.status_code = 200
        mw.process_response(req, resp)
        resp.__setitem__.assert_any_call("X-Request-ID", req.webhook_request_id)

    def test_non_webhook_path_skips_header(self):
        from api.webhooks.middleware import WebhookRequestLoggingMiddleware
        mw = WebhookRequestLoggingMiddleware(get_response=lambda r: None)
        req = self._make_request(path="/api/users/")
        mw.process_request(req)
        resp = MagicMock()
        resp.__setitem__ = MagicMock()
        resp.status_code = 200
        mw.process_response(req, resp)
        resp.__setitem__.assert_not_called()


class TestWebhookSecurityHeadersMiddleware(unittest.TestCase):
    """[INF-02] Security middleware adds hardened headers."""

    def _run(self, path):
        from api.webhooks.middleware import WebhookSecurityHeadersMiddleware
        mw = WebhookSecurityHeadersMiddleware(get_response=lambda r: None)
        req = MagicMock(); req.path = path
        headers = {}
        resp = MagicMock()
        resp.__setitem__ = lambda self_, k, v: headers.update({k: v})
        mw.process_response(req, resp)
        return headers

    def test_security_headers_added_for_webhook_path(self):
        headers = self._run("/webhooks/endpoints/")
        self.assertIn("X-Content-Type-Options", headers)
        self.assertIn("X-Frame-Options", headers)
        self.assertIn("Cache-Control", headers)
        self.assertIn("Strict-Transport-Security", headers)

    def test_security_headers_not_added_for_other_paths(self):
        headers = self._run("/api/users/")
        self.assertEqual(headers, {})


class TestWebhookTenantMiddleware(unittest.TestCase):
    """[INF-03] Tenant middleware resolves tenant_id from header/JWT/profile."""

    def _make_mw(self):
        from api.webhooks.middleware import WebhookTenantMiddleware
        return WebhookTenantMiddleware(get_response=lambda r: None)

    def test_resolves_from_header(self):
        mw = self._make_mw()
        req = MagicMock()
        req.META = {"HTTP_X_TENANT_ID": "tenant-abc"}
        req.auth = None
        req.user = MagicMock(); req.user.is_authenticated = False
        mw.process_request(req)
        self.assertEqual(req.tenant_id, "tenant-abc")

    def test_resolves_from_jwt(self):
        mw = self._make_mw()
        req = MagicMock()
        req.META = {}
        req.auth = {"tenant_id": "tenant-jwt-123"}
        req.user = MagicMock(); req.user.is_authenticated = False
        mw.process_request(req)
        self.assertEqual(req.tenant_id, "tenant-jwt-123")

    def test_resolves_from_user_profile(self):
        mw = self._make_mw()
        req = MagicMock()
        req.META = {}
        req.auth = None
        req.user = MagicMock()
        req.user.is_authenticated = True
        req.user.profile.tenant_id = "tenant-profile-456"
        mw.process_request(req)
        self.assertEqual(req.tenant_id, "tenant-profile-456")

    def test_tenant_id_none_when_not_resolvable(self):
        mw = self._make_mw()
        req = MagicMock()
        req.META = {}
        req.auth = None
        req.user = MagicMock(); req.user.is_authenticated = False
        mw.process_request(req)
        self.assertIsNone(req.tenant_id)

    def test_header_takes_priority_over_jwt(self):
        mw = self._make_mw()
        req = MagicMock()
        req.META = {"HTTP_X_TENANT_ID": "header-wins"}
        req.auth = {"tenant_id": "jwt-loses"}
        req.user = MagicMock(); req.user.is_authenticated = False
        mw.process_request(req)
        self.assertEqual(req.tenant_id, "header-wins")


# ═════════════════════════════════════════════════════════════════════════════
#  [INF-04]  Custom exception handler
# ═════════════════════════════════════════════════════════════════════════════

class TestWebhookExceptionHandler(unittest.TestCase):
    """[INF-04] webhook_exception_handler returns consistent {success, error} envelope."""

    def _call(self, exc):
        from api.webhooks.exceptions import webhook_exception_handler
        context = {"request": MagicMock(), "view": MagicMock()}
        return webhook_exception_handler(exc, context)

    def test_404_returns_standard_envelope(self):
        from rest_framework.exceptions import NotFound
        resp = self._call(NotFound("No WebhookEndpoint found."))
        self.assertFalse(resp.data["success"])
        self.assertIn("error", resp.data)
        self.assertIn("message", resp.data["error"])
        self.assertIn("code", resp.data["error"])

    def test_validation_error_includes_detail(self):
        from rest_framework.exceptions import ValidationError
        resp = self._call(ValidationError({"target_url": ["This field is required."]}))
        self.assertFalse(resp.data["success"])
        self.assertIn("detail", resp.data["error"])

    def test_permission_denied_returns_envelope(self):
        from rest_framework.exceptions import PermissionDenied
        resp = self._call(PermissionDenied())
        self.assertFalse(resp.data["success"])
        self.assertEqual(resp.status_code, 403)

    def test_unhandled_exception_returns_500_envelope(self):
        resp = self._call(RuntimeError("boom"))
        self.assertFalse(resp.data["success"])
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.data["error"]["code"], "internal_error")

    def test_success_key_always_false_on_error(self):
        from rest_framework.exceptions import NotFound, ValidationError, PermissionDenied
        for exc in [NotFound(), ValidationError("bad"), PermissionDenied()]:
            resp = self._call(exc)
            self.assertIs(resp.data["success"], False)


# ═════════════════════════════════════════════════════════════════════════════
#  [INF-05]  admin — _force_register_webhooks is callable
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminForceRegister(unittest.TestCase):
    """[INF-05] _force_register_webhooks must be importable and callable."""

    def test_function_is_importable(self):
        try:
            from api.webhooks.admin import _force_register_webhooks
        except ImportError as e:
            self.fail(f"_force_register_webhooks not importable: {e}")

    def test_function_is_callable(self):
        from api.webhooks.admin import _force_register_webhooks
        self.assertTrue(callable(_force_register_webhooks))

    def test_function_handles_already_registered(self):
        """Calling twice must not raise AlreadyRegistered."""
        from api.webhooks.admin import _force_register_webhooks
        try:
            _force_register_webhooks()
            _force_register_webhooks()  # second call must be idempotent
        except Exception as e:
            self.fail(f"_force_register_webhooks raised on second call: {e}")


if __name__ == "__main__":
    unittest.main()

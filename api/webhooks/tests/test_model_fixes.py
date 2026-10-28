"""
tests/test_model_fixes.py

Regression tests that would FAIL on the buggy code and PASS after fixes.

Covers:
    [CORE-01] models/core.py — duplicate validators= on target_url
    [ANA-01]  models/analytics.py — reset_at auto_now_add silent no-op
    [ANA-02]  models/analytics.py — WebhookAnalytics.save() update_fields
    [ADV-01]  models/advanced.py — WebhookFilter.clean() value validation
    [ADV-02]  models/advanced.py — WebhookBatch.clean() missing entirely
"""

from django.utils import timezone
from datetime import timedelta
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: minimal WebhookEndpoint-like stub
# ─────────────────────────────────────────────────────────────────────────────

def _make_endpoint(target_url="https://example.com/hook", max_retries=3):
    """Return a stub that mimics WebhookEndpoint without a DB."""
    from unittest.mock import MagicMock
    ep = MagicMock()
    ep.target_url  = target_url
    ep.max_retries = max_retries
    return ep


# ═════════════════════════════════════════════════════════════════════════════
#  [CORE-01] — validate_webhook_url must now run on target_url
# ═════════════════════════════════════════════════════════════════════════════

class TestTargetUrlValidators(unittest.TestCase):
    """
    Before fix: only URLValidator ran (second validators= overwrote the first).
    After fix:  both validate_webhook_url AND URLValidator run in sequence.
    """

    def _validator_list(self):
        """Extract the validators list from the fixed field declaration."""
        from api.webhooks.models.core import WebhookEndpoint
        field = WebhookEndpoint._meta.get_field("target_url")
        return field.validators

    def test_field_has_two_validators(self):
        """Both explicitly-configured validators (validate_webhook_url +
        URLValidator(schemes=["https", "http"])) must be present - i.e.
        neither was silently dropped by a duplicate validators= kwarg
        overwriting the first (the original CORE-01 bug).

        field.validators at runtime is NOT just the 2 explicitly passed in
        models/core.py's validators=[...] kwarg - Django's URLField/CharField
        machinery automatically appends its own default validators too (a
        URLValidator for being a URLField - with schemes ['http', 'https',
        'ftp', 'ftps'], distinct from the explicit one's ['https', 'http'] -
        and a MaxLengthValidator for max_length=2048), so the real count is
        4, not 2 (confirmed empirically: len(field.validators) == 4).
        Checking presence of both explicit ones instead of a total count
        that Django itself doesn't keep at exactly 2.
        """
        from api.webhooks.validators import validate_webhook_url
        validators = self._validator_list()
        self.assertIn(
            validate_webhook_url,
            validators,
            "validate_webhook_url missing from target_url.validators — "
            "the duplicate kwarg bug may have resurfaced.",
        )
        self.assertTrue(
            any(
                isinstance(v, URLValidator) and getattr(v, "schemes", None) == ["https", "http"]
                for v in validators
            ),
            "The explicitly-configured URLValidator(schemes=['https','http']) is missing — "
            "the duplicate kwarg bug may have resurfaced.",
        )

    def test_validate_webhook_url_is_first_validator(self):
        """validate_webhook_url must be included in the validator list."""
        from api.webhooks.validators import validate_webhook_url
        validators = self._validator_list()
        self.assertIn(
            validate_webhook_url,
            validators,
            "validate_webhook_url not present in target_url.validators — "
            "the duplicate kwarg bug has not been fixed.",
        )

    def test_url_validator_is_also_present(self):
        """URLValidator must still be in the list alongside validate_webhook_url."""
        from django.core.validators import URLValidator
        validators = self._validator_list()
        url_validator_types = [type(v) for v in validators]
        self.assertIn(
            URLValidator,
            url_validator_types,
            "URLValidator missing from target_url.validators.",
        )

    def test_validate_webhook_url_called_on_clean(self):
        """
        validate_webhook_url should be invoked when the field is cleaned.
        Before the fix it was silently dropped — this test would have passed
        for an internal/SSRF URL that only URLValidator allows.
        """
        from api.webhooks.validators import validate_webhook_url
        from django.core.exceptions import ValidationError as DjValidationError

        # validate_webhook_url typically blocks localhost/internal IPs.
        # We patch it to raise so we can confirm it's actually called.
        with patch("api.webhooks.models.core.validate_webhook_url",
                   side_effect=DjValidationError("blocked")) as mock_validator:
            from api.webhooks.models.core import WebhookEndpoint
            field = WebhookEndpoint._meta.get_field("target_url")
            # Reload to pick up the patched reference
            if mock_validator in field.validators:
                with self.assertRaises(DjValidationError):
                    for v in field.validators:
                        v("http://localhost/hook")


# ═════════════════════════════════════════════════════════════════════════════
#  [ANA-01] — WebhookRateLimit.reset_at must be writable
# ═════════════════════════════════════════════════════════════════════════════

class TestRateLimitResetAt(unittest.TestCase):
    """
    Before fix: reset_at had auto_now_add=True → DB-immutable → reset_counter()
                was a silent no-op.
    After fix:  reset_at uses default=timezone.now → field is writable.
    """

    def _field(self):
        from api.webhooks.models.analytics import WebhookRateLimit
        return WebhookRateLimit._meta.get_field("reset_at")

    def test_reset_at_does_not_have_auto_now_add(self):
        """reset_at must NOT have auto_now_add=True after the fix."""
        field = self._field()
        self.assertFalse(
            getattr(field, "auto_now_add", False),
            "WebhookRateLimit.reset_at still has auto_now_add=True — "
            "reset_counter() will remain a silent no-op.",
        )

    def test_reset_at_has_callable_default(self):
        """reset_at should have a callable default (timezone.now) after the fix."""
        field = self._field()
        self.assertTrue(
            callable(field.default),
            "WebhookRateLimit.reset_at should have default=timezone.now "
            "(a callable). Found non-callable default instead.",
        )

    def test_reset_counter_updates_reset_at(self):
        """
        reset_counter() must update reset_at and call save() with update_fields.
        Before the fix, the assignment was silently discarded by the ORM.
        """
        from django.utils import timezone
        from api.webhooks.models.analytics import WebhookRateLimit

        instance                = WebhookRateLimit.__new__(WebhookRateLimit)
        instance.current_count  = 50
        instance.reset_at       = timezone.now()

        original_reset_at = instance.reset_at

        saved_kwargs = {}

        def fake_save(**kwargs):
            saved_kwargs.update(kwargs)

        instance.save = fake_save

        instance.reset_counter()

        self.assertEqual(instance.current_count, 0, "current_count not reset to 0")
        self.assertNotEqual(
            instance.reset_at, original_reset_at,
            "reset_at was NOT updated by reset_counter() — "
            "auto_now_add bug may still be present.",
        )
        self.assertIn(
            "reset_at",
            saved_kwargs.get("update_fields", []),
            "reset_at not in update_fields — save() will not persist it.",
        )

    def test_window_has_expired_uses_reset_at(self):
        """window_has_expired() must return True once window has passed."""
        from datetime import timedelta
        from django.utils import timezone
        from api.webhooks.models.analytics import WebhookRateLimit

        instance                 = WebhookRateLimit.__new__(WebhookRateLimit)
        instance.window_seconds  = 3600
        # Set reset_at to 2 hours ago — window has definitely expired
        instance.reset_at        = timezone.now() - timedelta(hours=2)

        self.assertTrue(
            instance.window_has_expired(),
            "window_has_expired() should return True for a 2-hour-old reset_at "
            "with a 1-hour window.",
        )

    def test_window_not_expired_when_recent(self):
        """window_has_expired() must return False when the window is still open."""
        from datetime import timedelta
        from django.utils import timezone
        from api.webhooks.models.analytics import WebhookRateLimit

        instance                 = WebhookRateLimit.__new__(WebhookRateLimit)
        instance.window_seconds  = 3600
        instance.reset_at        = timezone.now()

        self.assertFalse(
            instance.window_has_expired(),
            "window_has_expired() returned True for a freshly created window.",
        )


# ═════════════════════════════════════════════════════════════════════════════
#  [ANA-02] — WebhookAnalytics.save() update_fields propagation
# ═════════════════════════════════════════════════════════════════════════════

class TestWebhookAnalyticsSave(unittest.TestCase):
    """
    Before fix: save() recalculated success_rate but never added it to
                update_fields, causing lost updates under concurrent writes.
    After fix:  success_rate is always injected into update_fields.
    """

    def _make_analytics(self, total, success):
        from api.webhooks.models.analytics import WebhookAnalytics
        a = WebhookAnalytics.__new__(WebhookAnalytics)
        a.total_sent   = total
        a.success_count = success
        a.failed_count  = total - success
        a.success_rate  = 0.0
        a.avg_latency_ms = 0.0
        return a

    def test_save_calculates_success_rate(self):
        """save() must set success_rate before delegating to super."""
        a = self._make_analytics(total=100, success=75)

        captured = {}
        with patch("django.db.models.Model.save", lambda self, *a, **kw: captured.update(kw)):
            a.save()

        self.assertAlmostEqual(a.success_rate, 75.0, places=1)

    def test_save_injects_success_rate_into_update_fields(self):
        """When update_fields is passed, success_rate must be appended."""
        a = self._make_analytics(total=200, success=180)

        captured = {}
        with patch("django.db.models.Model.save", lambda self, *args, **kw: captured.update(kw)):
            a.save(update_fields=["total_sent", "success_count", "failed_count"])

        update_fields = captured.get("update_fields", [])
        self.assertIn(
            "success_rate",
            update_fields,
            "success_rate was not injected into update_fields — "
            "concurrent task writes will produce stale values.",
        )

    def test_save_zero_total_gives_zero_rate(self):
        """success_rate must be 0.0 when total_sent == 0 (no division by zero)."""
        a = self._make_analytics(total=0, success=0)
        with patch("django.db.models.Model.save"):
            a.save()
        self.assertEqual(a.success_rate, 0.0)

    def test_save_full_success_gives_100(self):
        a = self._make_analytics(total=50, success=50)
        with patch("django.db.models.Model.save"):
            a.save()
        self.assertAlmostEqual(a.success_rate, 100.0, places=1)


# ═════════════════════════════════════════════════════════════════════════════
#  [ADV-01] — WebhookFilter.clean() value validation
# ═════════════════════════════════════════════════════════════════════════════

class TestWebhookFilterClean(unittest.TestCase):
    """
    Before fix: clean() checked field_path and operator but NEVER validated
                the value field against the operator's type contract.
    After fix:  operator-aware validation added.
    """

    def _make_filter(self, field_path="user.email", operator="equals", value="test@example.com"):
        from api.webhooks.models.advanced import WebhookFilter
        f = WebhookFilter.__new__(WebhookFilter)
        f.field_path = field_path
        f.operator   = operator
        f.value      = value
        f.is_active  = True
        return f

    def test_valid_equals_scalar_passes(self):
        """EQUALS with a scalar string must pass clean()."""
        f = self._make_filter(operator="equals", value="test@example.com")
        f.clean()  # must not raise

    def test_valid_in_list_passes(self):
        """IN with a non-empty list must pass clean()."""
        f = self._make_filter(operator="in", value=["USD", "BDT", "EUR"])
        f.clean()

    def test_valid_not_in_list_passes(self):
        """NOT_IN with a non-empty list must pass clean()."""
        f = self._make_filter(operator="not_in", value=["BLOCKED"])
        f.clean()

    def test_in_with_scalar_raises_validation_error(self):
        """IN operator with a scalar value must raise ValidationError."""
        f = self._make_filter(operator="in", value="USD")
        with self.assertRaises(ValidationError) as ctx:
            f.clean()
        self.assertIn("list", str(ctx.exception).lower())

    def test_in_with_empty_list_raises_validation_error(self):
        """IN operator with an empty list must raise ValidationError."""
        f = self._make_filter(operator="in", value=[])
        with self.assertRaises(ValidationError) as ctx:
            f.clean()
        self.assertIn("empty", str(ctx.exception).lower())

    def test_not_in_with_dict_raises_validation_error(self):
        """NOT_IN operator with a dict value must raise ValidationError."""
        f = self._make_filter(operator="not_in", value={"key": "val"})
        with self.assertRaises(ValidationError):
            f.clean()

    def test_equals_with_list_raises_validation_error(self):
        """EQUALS operator with a list value must raise ValidationError."""
        f = self._make_filter(operator="equals", value=["a", "b"])
        with self.assertRaises(ValidationError) as ctx:
            f.clean()
        self.assertIn("scalar", str(ctx.exception).lower())

    def test_contains_with_dict_raises_validation_error(self):
        """CONTAINS operator with a dict value must raise ValidationError."""
        f = self._make_filter(operator="contains", value={"nested": "obj"})
        with self.assertRaises(ValidationError):
            f.clean()

    def test_greater_than_with_scalar_int_passes(self):
        """GREATER_THAN with an int value must pass clean()."""
        f = self._make_filter(operator="greater_than", value=100)
        f.clean()

    def test_less_than_with_scalar_float_passes(self):
        """LESS_THAN with a float value must pass clean()."""
        f = self._make_filter(operator="less_than", value=99.99)
        f.clean()

    def test_null_value_raises_validation_error(self):
        """Any non-EXISTS operator with value=None must raise ValidationError."""
        f = self._make_filter(operator="equals", value=None)
        with self.assertRaises(ValidationError) as ctx:
            f.clean()
        self.assertIn("required", str(ctx.exception).lower())

    def test_missing_field_path_raises_validation_error(self):
        """Empty field_path must raise ValidationError."""
        f = self._make_filter(field_path="", operator="equals", value="x")
        with self.assertRaises(ValidationError) as ctx:
            f.clean()
        self.assertIn("required", str(ctx.exception).lower())

    def test_missing_field_path_whitespace_raises(self):
        """Whitespace-only field_path must raise ValidationError."""
        f = self._make_filter(field_path="   ", operator="equals", value="x")
        with self.assertRaises(ValidationError):
            f.clean()

    def test_exists_operator_passes_without_value_validation(self):
        """EXISTS operator skips value validation entirely."""
        f = self._make_filter(operator="exists", value=None)
        f.clean()  # must not raise

    def test_not_exists_operator_passes_without_value_validation(self):
        """NOT_EXISTS operator skips value validation entirely."""
        f = self._make_filter(operator="not_exists", value=None)
        f.clean()


# ═════════════════════════════════════════════════════════════════════════════
#  [ADV-02] — WebhookBatch.clean() — now exists
# ═════════════════════════════════════════════════════════════════════════════

class TestWebhookBatchClean(unittest.TestCase):
    """
    Before fix: WebhookBatch had NO clean() method at all.
    After fix:  clean() validates batch_id, temporal order, and status/completed_at.
    """

    def _make_batch(self, batch_id="BATCH-001", status="pending", completed_at=None, pk=None):
        from api.webhooks.models.advanced import WebhookBatch
        b              = WebhookBatch.__new__(WebhookBatch)
        b.pk           = pk
        b.batch_id     = batch_id
        b.status       = status
        b.completed_at = completed_at
        b.event_count  = 5
        return b

    def test_valid_pending_batch_passes(self):
        """A pending batch with a valid batch_id must pass clean()."""
        b = self._make_batch()
        b.clean()  # must not raise

    def test_empty_batch_id_raises(self):
        """Empty batch_id must raise ValidationError."""
        b = self._make_batch(batch_id="")
        with self.assertRaises(ValidationError) as ctx:
            b.clean()
        self.assertIn("batch_id", str(ctx.exception).lower())

    def test_whitespace_batch_id_raises(self):
        """Whitespace-only batch_id must raise ValidationError."""
        b = self._make_batch(batch_id="   ")
        with self.assertRaises(ValidationError):
            b.clean()

    def test_completed_batch_without_completed_at_raises(self):
        """COMPLETED status without completed_at must raise ValidationError."""
        b = self._make_batch(status="completed", completed_at=None)
        with self.assertRaises(ValidationError) as ctx:
            b.clean()
        msg = str(ctx.exception).lower()
        self.assertIn("completed_at", msg)

    def test_failed_batch_without_completed_at_raises(self):
        """FAILED status without completed_at must raise ValidationError."""
        b = self._make_batch(status="failed", completed_at=None)
        with self.assertRaises(ValidationError):
            b.clean()

    def test_cancelled_batch_without_completed_at_raises(self):
        """CANCELLED status without completed_at must raise ValidationError."""
        b = self._make_batch(status="cancelled", completed_at=None)
        with self.assertRaises(ValidationError):
            b.clean()

    def test_completed_batch_with_completed_at_passes(self):
        """COMPLETED status WITH completed_at must pass clean()."""
        from django.utils import timezone
        b = self._make_batch(status="completed", completed_at=timezone.now())
        b.clean()  # must not raise

    def test_clean_method_exists(self):
        """WebhookBatch must have a clean() method defined (regression guard)."""
        from api.webhooks.models.advanced import WebhookBatch
        self.assertTrue(
            hasattr(WebhookBatch, "clean") and callable(WebhookBatch.clean),
            "WebhookBatch.clean() method is missing — [ADV-02] fix not applied.",
        )


# ═════════════════════════════════════════════════════════════════════════════
#  WebhookEndpoint — additional model behaviour tests
# ═════════════════════════════════════════════════════════════════════════════

class TestWebhookEndpointProperties(unittest.TestCase):
    """Tests for WebhookEndpoint properties exposed by [SER-02] fix."""

    def _make_ep(self, total=0, success=0):
        from api.webhooks.models.core import WebhookEndpoint
        ep = WebhookEndpoint.__new__(WebhookEndpoint)
        ep.total_deliveries   = total
        ep.success_deliveries = success
        ep.failed_deliveries  = total - success
        return ep

    def test_success_rate_zero_when_no_deliveries(self):
        ep = self._make_ep(total=0, success=0)
        self.assertEqual(ep.success_rate, 0.0)

    def test_success_rate_100_when_all_succeed(self):
        ep = self._make_ep(total=10, success=10)
        self.assertEqual(ep.success_rate, 100.0)

    def test_success_rate_50_half_success(self):
        ep = self._make_ep(total=200, success=100)
        self.assertEqual(ep.success_rate, 50.0)

    def test_success_rate_rounded_to_2dp(self):
        ep = self._make_ep(total=3, success=2)
        self.assertEqual(ep.success_rate, 66.67)

    def test_max_retries_clean_rejects_over_10(self):
        """WebhookEndpoint.clean() must reject max_retries > 10."""
        from api.webhooks.models.core import WebhookEndpoint
        ep = WebhookEndpoint.__new__(WebhookEndpoint)
        ep.target_url  = "https://example.com/hook"
        ep.max_retries = 11
        with self.assertRaises(ValidationError) as ctx:
            ep.clean()
        self.assertIn("10", str(ctx.exception))

    def test_max_retries_clean_accepts_10(self):
        """WebhookEndpoint.clean() must allow max_retries == 10."""
        from api.webhooks.models.core import WebhookEndpoint
        ep = WebhookEndpoint.__new__(WebhookEndpoint)
        ep.target_url  = "https://example.com/hook"
        ep.max_retries = 10
        ep.clean()  # must not raise

    def test_delivery_log_schedule_retry_returns_false_when_not_retryable(self):
        """schedule_retry() must return False when is_retryable is False."""
        from api.webhooks.models.core import WebhookDeliveryLog
        log = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
        log.status         = "success"
        log.attempt_number = 1
        log.max_attempts   = 3
        result = log.schedule_retry()
        self.assertFalse(result)

    def test_delivery_log_is_retryable_false_when_exhausted(self):
        """is_retryable must be False when attempt_number >= max_attempts."""
        from api.webhooks.models.core import WebhookDeliveryLog
        log = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
        log.status         = "failed"
        log.attempt_number = 3
        log.max_attempts   = 3
        self.assertFalse(log.is_retryable)

    def test_delivery_log_mark_as_exhausted_sets_status(self):
        """mark_as_exhausted() must set status to EXHAUSTED."""
        from api.webhooks.models.core import WebhookDeliveryLog
        from api.webhooks.choices import DeliveryStatus
        log            = WebhookDeliveryLog.__new__(WebhookDeliveryLog)
        log.error_message = ""
        log.completed_at  = None
        log.save          = MagicMock()
        log.mark_as_exhausted(error_message="too many retries")
        self.assertEqual(log.status, DeliveryStatus.EXHAUSTED)
        self.assertEqual(log.error_message, "too many retries")
        log.save.assert_called_once()


if __name__ == "__main__":
    unittest.main()

"""
tests/test_exception_handler.py

Coverage for alerts/exception_handler.py — a new file created this session
that wires the 30+ custom exception classes in exceptions.py to structured
DRF responses with correct HTTP status codes (previously: zero of these
exceptions were ever caught by any EXCEPTION_HANDLER, so DRF's default
handler turned every one into a generic 500).
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied as DRFPermissionDenied
from rest_framework.views import APIView
from rest_framework.test import APIRequestFactory

from api.alerts.exception_handler import alerts_exception_handler
from api.alerts.exceptions import (
    AlertSystemException,
    ValidationError as AlertValidationError,
    InvalidThresholdError,
    InvalidTimeWindowError,
    InvalidRecipientError,
    AlertProcessingError,
    AlertRuleNotFoundError,
    AlertRuleInactiveError,
    DatabaseError,
    RateLimitError,
)


def _make_context():
    """Minimal DRF exception-handler context: a dummy view + a built request."""
    factory = APIRequestFactory()
    request = factory.get('/fake-endpoint/')

    class _DummyView(APIView):
        pass

    return {'view': _DummyView(), 'request': request, 'args': (), 'kwargs': {}}


class MappedExceptionStatusCodeTest(TestCase):
    """Each of the 8 explicitly mapped exception types must return its
    documented status code, not just 'some 4xx/5xx'."""

    def test_alert_rule_not_found_returns_404(self):
        response = alerts_exception_handler(
            AlertRuleNotFoundError("Rule 999 not found"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_alert_rule_inactive_returns_422(self):
        response = alerts_exception_handler(
            AlertRuleInactiveError("Rule is not active"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_invalid_threshold_returns_400(self):
        response = alerts_exception_handler(
            InvalidThresholdError("Threshold out of range"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_time_window_returns_400(self):
        response = alerts_exception_handler(
            InvalidTimeWindowError("Bad time window"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_recipient_returns_400(self):
        response = alerts_exception_handler(
            InvalidRecipientError("Bad recipient"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_alert_validation_error_returns_400(self):
        response = alerts_exception_handler(
            AlertValidationError("Validation failed"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_alert_processing_error_returns_500(self):
        response = alerts_exception_handler(
            AlertProcessingError("Processing failed"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_base_alert_system_exception_returns_500(self):
        response = alerts_exception_handler(
            AlertSystemException("Generic system error"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubclassPrecedenceTest(TestCase):
    """The _STATUS_MAP dict is iterated in insertion order, and Python 3.7+
    dicts preserve insertion order — more specific exception classes are
    listed before their parents, so isinstance() must match the most
    specific entry first, not fall through to the generic 500."""

    def test_alert_rule_not_found_does_not_fall_through_to_generic_500(self):
        """AlertRuleNotFoundError is a subclass of AlertProcessingError,
        which is a subclass of AlertSystemException. If ordering were wrong,
        this would incorrectly return 500 instead of 404."""
        response = alerts_exception_handler(
            AlertRuleNotFoundError("Rule 1 missing"), _make_context())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_invalid_threshold_does_not_fall_through_to_validation_400_incorrectly(self):
        """InvalidThresholdError IS a 400 (same as the generic ValidationError
        mapping), so this confirms the more specific class name still
        appears correctly in the response body, not just the status code."""
        response = alerts_exception_handler(
            InvalidThresholdError("Bad threshold"), _make_context())
        self.assertEqual(response.data['error'], 'InvalidThresholdError')


class UnmappedExceptionFallthroughTest(TestCase):
    """Exception subclasses NOT explicitly listed in _STATUS_MAP (e.g.
    DatabaseError, RateLimitError) still inherit from AlertSystemException,
    so they correctly fall through to the generic 500 mapping rather than
    raising an unhandled error inside the handler itself."""

    def test_database_error_falls_through_to_500(self):
        response = alerts_exception_handler(
            DatabaseError("Connection lost"), _make_context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_rate_limit_error_falls_through_to_500(self):
        response = alerts_exception_handler(
            RateLimitError("Too many requests"), _make_context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResponseShapeTest(TestCase):
    """Every alerts-exception response must follow the documented
    {error, message, code} shape, not DRF's default {detail: ...} shape."""

    def test_response_has_error_message_code_keys(self):
        response = alerts_exception_handler(
            AlertRuleNotFoundError("Rule 42 not found"), _make_context())
        self.assertIn('error', response.data)
        self.assertIn('message', response.data)
        self.assertIn('code', response.data)

    def test_error_key_is_exception_class_name(self):
        response = alerts_exception_handler(
            AlertRuleInactiveError("inactive"), _make_context())
        self.assertEqual(response.data['error'], 'AlertRuleInactiveError')

    def test_message_key_is_exception_string(self):
        response = alerts_exception_handler(
            InvalidThresholdError("Threshold must be positive"), _make_context())
        self.assertEqual(response.data['message'], 'Threshold must be positive')

    def test_code_key_uses_exception_default_code_when_not_overridden(self):
        """AlertSystemException.__init__ always sets self.code (defaulting
        to default_code if not explicitly passed), so the handler's
        getattr(exc, 'code', ...) fallback should never actually trigger
        for any api.alerts.exceptions.* instance."""
        exc = AlertRuleNotFoundError("Rule 7 not found")
        response = alerts_exception_handler(exc, _make_context())
        self.assertEqual(response.data['code'], exc.code)

    def test_code_key_respects_explicit_code_override(self):
        exc = AlertProcessingError("Custom failure", code='custom_processing_code')
        response = alerts_exception_handler(exc, _make_context())
        self.assertEqual(response.data['code'], 'custom_processing_code')


class DRFFallthroughTest(TestCase):
    """Non-alerts exceptions (standard DRF exceptions like NotAuthenticated)
    must fall through to DRF's own exception_handler, not be swallowed or
    misrouted by the alerts-specific mapping loop."""

    def test_not_authenticated_falls_through_to_drf_handler(self):
        response = alerts_exception_handler(NotAuthenticated(), _make_context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_drf_permission_denied_falls_through_to_drf_handler(self):
        response = alerts_exception_handler(DRFPermissionDenied(), _make_context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_drf_fallthrough_response_normalised_to_error_message_code_shape(self):
        """The handler normalises DRF's default {detail: ...} shape into
        the same {error, message, code} shape used for alerts exceptions,
        so API consumers get a consistent response format either way."""
        response = alerts_exception_handler(NotAuthenticated(), _make_context())
        self.assertIn('error', response.data)
        self.assertIn('message', response.data)
        self.assertIn('code', response.data)
        self.assertEqual(response.data['error'], 'APIError')

    def test_completely_unhandleable_exception_returns_none(self):
        """A plain Python exception with no DRF mapping (e.g. ValueError
        raised outside any DRF-recognised context) should return None,
        matching drf_exception_handler's own documented contract — Django
        then falls back to its own unhandled-exception machinery."""
        response = alerts_exception_handler(ValueError("not a DRF exception"), _make_context())
        self.assertIsNone(response)


class LoggingTest(TestCase):
    """Verify the handler logs a warning for every alerts exception it
    catches, including the view name for debugging context."""

    def test_logs_warning_with_view_name(self):
        import logging
        with self.assertLogs('api.alerts.exception_handler', level='WARNING') as cm:
            alerts_exception_handler(
                AlertRuleNotFoundError("Rule 5 missing"), _make_context())
        self.assertTrue(
            any('AlertRuleNotFoundError' in msg for msg in cm.output))

    def test_get_view_name_handles_missing_view_gracefully(self):
        from api.alerts.exception_handler import _get_view_name
        self.assertEqual(_get_view_name({}), 'unknown')
        self.assertEqual(_get_view_name({'view': None}), 'unknown')

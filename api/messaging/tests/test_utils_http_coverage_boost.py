"""
test_utils_http_coverage_boost.py
====================================
Real-execution coverage for messaging/utils/http.py.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework import status

from api.messaging.utils.http import (
    MessagingAPIView,
    _bad_request,
    _err,
    _error_response,
    _forbidden,
    _no_content,
    _not_found,
    make_safe_receiver,
    safe_receiver_error_handler,
)


class _ExcWithStatus(Exception):
    http_status = 422


class _PlainExc(Exception):
    pass


# ---------------------------------------------------------------------------
# _err / _error_response
# ---------------------------------------------------------------------------

class TestErr:
    def test_explicit_status_wins(self):
        resp = _err(_ExcWithStatus("bad"), http_status=418)
        assert resp.status_code == 418
        assert resp.data == {"detail": "bad"}

    def test_uses_exception_http_status_when_omitted(self):
        resp = _err(_ExcWithStatus("nope"))
        assert resp.status_code == 422

    def test_defaults_to_400_when_no_http_status_anywhere(self):
        resp = _err(_PlainExc("plain"))
        assert resp.status_code == 400
        assert resp.data == {"detail": "plain"}

    def test_messaging_error_uses_to_dict_shape(self):
        """
        Regression test (Part 6 audit): views.py used to define its own
        local _err() that shadowed this imported, "centralized" one
        (despite importing it right above the shadowing definition), and
        that local copy included an extra "error_type" key this one
        didn't - meaning error responses from views.py looked different
        from every other view/viewset in the same API. This now uses
        MessagingError.to_dict() (exceptions.py), which was always the
        richer, clearly-intended shape for the whole exception hierarchy.
        """
        from api.messaging.exceptions import ChatNotFoundError
        resp = _err(ChatNotFoundError("no such chat"))
        assert resp.status_code == 404
        assert resp.data == {
            "error_type": "ChatNotFoundError",
            "code": "chat_not_found",
            "detail": "no such chat",
        }

    def test_plain_exception_unaffected_by_to_dict_change(self):
        """A plain Exception has no to_dict() - must keep the simple
        {"detail": ...} shape exactly as before."""
        resp = _err(_PlainExc("just a plain error"))
        assert resp.data == {"detail": "just a plain error"}
        assert "error_type" not in resp.data


class TestErrorResponse:
    def test_explicit_status_wins(self):
        resp = _error_response(_ExcWithStatus("bad"), http_status=status.HTTP_403_FORBIDDEN)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_uses_exception_http_status_when_omitted(self):
        resp = _error_response(_ExcWithStatus("nope"))
        assert resp.status_code == 422

    def test_defaults_to_400_when_no_http_status_anywhere(self):
        resp = _error_response(_PlainExc("plain"))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_delegates_to_err_for_messaging_error_shape(self):
        """Regression test (Part 6 audit): _error_response used to
        duplicate its own stale {"detail": ...}-only copy of _err()'s
        logic rather than delegating to it, so it never picked up the
        to_dict() enrichment above."""
        from api.messaging.exceptions import ChatAccessDeniedError
        resp = _error_response(ChatAccessDeniedError("nope"))
        assert resp.data == {
            "error_type": "ChatAccessDeniedError",
            "code": "chat_access_denied",
            "detail": "nope",
        }


# ---------------------------------------------------------------------------
# shortcut helpers
# ---------------------------------------------------------------------------

class TestShortcutHelpers:
    def test_not_found_default(self):
        resp = _not_found()
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.data == {"detail": "Not found."}

    def test_not_found_custom_detail(self):
        resp = _not_found("chat not found")
        assert resp.data == {"detail": "chat not found"}

    def test_forbidden_default(self):
        resp = _forbidden()
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.data == {"detail": "Access denied."}

    def test_forbidden_custom_detail(self):
        resp = _forbidden("nope")
        assert resp.data == {"detail": "nope"}

    def test_bad_request(self):
        resp = _bad_request("missing field")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data == {"detail": "missing field"}

    def test_no_content(self):
        resp = _no_content()
        assert resp.status_code == status.HTTP_204_NO_CONTENT


# ---------------------------------------------------------------------------
# MessagingAPIView
# ---------------------------------------------------------------------------

class TestMessagingApiView:
    view = MessagingAPIView()

    def test_err_delegates(self):
        resp = self.view._err(_PlainExc("x"), 401)
        assert resp.status_code == 401
        assert resp.data == {"detail": "x"}

    def test_error_response_delegates(self):
        resp = self.view._error_response(_PlainExc("y"), 402)
        assert resp.status_code == 402

    def test_not_found_delegates(self):
        resp = self.view._not_found("missing")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.data == {"detail": "missing"}

    def test_forbidden_delegates(self):
        resp = self.view._forbidden("no")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_bad_request_delegates(self):
        resp = self.view._bad_request("bad field")
        assert resp.data == {"detail": "bad field"}

    def test_no_content_delegates(self):
        resp = self.view._no_content()
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_is_a_real_apiview_subclass(self):
        from rest_framework.views import APIView
        assert isinstance(self.view, APIView)


# ---------------------------------------------------------------------------
# safe_receiver_error_handler
# ---------------------------------------------------------------------------

class TestSafeReceiverErrorHandler:
    def test_logs_with_context(self):
        with patch("messaging.utils.http.logger.error") as mock_error:
            safe_receiver_error_handler(
                "chat_message_sent", ValueError("boom"), message_id=42, chat_id="c1"
            )
        mock_error.assert_called_once()
        args = mock_error.call_args[0]
        assert args[0] == "Signal receiver error in '%s'%s: %s"
        assert args[1] == "chat_message_sent"
        assert "message_id=42" in args[2]
        assert "chat_id='c1'" in args[2]
        assert mock_error.call_args.kwargs["exc_info"] is True

    def test_logs_without_context(self):
        with patch("messaging.utils.http.logger.error") as mock_error:
            safe_receiver_error_handler("some_signal", RuntimeError("x"))
        args = mock_error.call_args[0]
        assert args[2] == ""  # no parenthesized context suffix


# ---------------------------------------------------------------------------
# make_safe_receiver
# ---------------------------------------------------------------------------

class TestMakeSafeReceiver:
    def test_successful_call_passes_through_return_value(self):
        @make_safe_receiver("my_signal")
        def handler(x, y=1):
            return x + y

        assert handler(2, y=3) == 5

    def test_exception_is_caught_and_logged_not_raised(self):
        @make_safe_receiver("my_signal")
        def handler(**kwargs):
            raise ValueError("receiver blew up")

        with patch("messaging.utils.http.safe_receiver_error_handler") as mock_handler:
            result = handler(sender=None, chat_id="c1")

        assert result is None  # swallowed, not propagated
        mock_handler.assert_called_once()
        call_args = mock_handler.call_args[0]
        assert call_args[0] == "my_signal"
        assert isinstance(call_args[1], ValueError)

    def test_preserves_function_name_via_functools_wraps(self):
        @make_safe_receiver("my_signal")
        def my_original_handler(**kwargs):
            pass

        assert my_original_handler.__name__ == "my_original_handler"

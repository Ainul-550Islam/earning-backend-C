# fraud_detection/utils/response.py
"""
Single source-of-truth for HTTP response helpers.

Previously `_ok()` and `_err()` were EACH defined in 7 separate files
(views_tasks, views_detectors, views_notification_service,
views_signals_monitor, views_repositories, views_factories,
security/security_views).  That is 14 duplicate definitions.

Now there is exactly ONE definition in the entire codebase.

Usage
-----
Module-level (outside a class):
    from api.fraud_detection.utils.response import ok, err
    return ok(data)
    return err("message", 400)

Inside a FraudBaseView subclass (preferred):
    return self.ok(data)
    return self.err("message", 400)
"""
from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.response import Response


def ok(data: Any, code: int = status.HTTP_200_OK) -> Response:
    """Return a DRF Response with HTTP 200 (or custom code)."""
    return Response(data, status=code)


def err(msg: Any, code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    """Return a DRF Response with ``{"error": msg}`` and HTTP 400 (or custom code)."""
    return Response({"error": msg}, status=code)

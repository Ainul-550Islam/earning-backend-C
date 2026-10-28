# fraud_detection/utils/base_views.py
"""
Base API view classes for the fraud_detection app.

Eliminates the following duplications
--------------------------------------
1. ``throttle_classes = [FraudEndpointRateThrottle, BurstProtectionThrottle]``
   was repeated in **every single view class** across 7 files (150+ occurrences).
   Now declared ONCE in FraudBaseView.

2. ``permission_classes = [IsAuthenticated]``
   was repeated in every read-only view class.
   Now declared ONCE in FraudBaseView.

3. ``permission_classes = [IsAuthenticated, IsAdminUser]``
   was repeated in every admin-only view class.
   Now declared ONCE in FraudAdminView.

4. ``def _ok(data, code=200)`` and ``def _err(msg, code=400)``
   were each defined 7 times (once per view module).
   Now exposed as ``self.ok()`` and ``self.err()`` via FraudBaseView.

5. Inline admin check:
   ``if not request.user.is_staff: return _err("Admin access required.", 403)``
   was duplicated ~25 times across views that need mixed auth.
   Now replaced by ``if e := self.require_admin(request): return e``.

6. ``_paginate(qs, request)`` helper was duplicated in every file.
   Now exposed as ``self.paginate(qs, request)`` via FraudBaseView.

7. ``try/except DoesNotExist`` pattern for model lookups was duplicated
   in 5 DetailAPIView classes.
   Now replaced by ``self.get_or_none(Model, pk=pk)``.

8. Standard 500 error handler:
   ``except Exception as exc: logger.exception(...); return self.err(str(exc), 500)``
   — the logger.exception line still differs per-view intentionally
   (includes the view name for traceability), but the response is uniform.

Classes
-------
FraudBaseView   — IsAuthenticated + both throttle classes + ok/err/paginate helpers
FraudAdminView  — IsAdminUser (extends FraudBaseView)
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Type

from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
)
from .pagination import paginate_qs
from .helpers    import get_or_none

logger = logging.getLogger(__name__)


class FraudBaseView(APIView):
    """
    Base class for ALL fraud_detection API views.

    Provides
    --------
    - throttle_classes (both throttles, declared once)
    - permission_classes (IsAuthenticated, declared once)
    - self.ok(data, code)      — success response
    - self.err(msg, code)      — error response
    - self.paginate(qs)        — pagination metadata from request query-params
    - self.require_admin()     — returns 403 response if not staff, else None
    - self.get_or_none(Model)  — safe model fetch (no DoesNotExist propagation)
    """

    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def ok(self, data: Any, code: int = status.HTTP_200_OK) -> Response:
        """Return a successful DRF Response."""
        return Response(data, status=code)

    def err(self, msg: Any, code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """Return an error DRF Response with ``{"error": msg}``."""
        return Response({"error": msg}, status=code)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def paginate(self, qs: Any) -> dict:
        """
        Return pagination metadata for *qs* using the current request's
        query-params (?page=, ?page_size=).

        Usage::

            meta = self.paginate(qs)
            s, e = meta.pop("slice")
            return self.ok({**meta, "results": serializer(qs[s:e], many=True).data})
        """
        return paginate_qs(qs, self.request)

    # ------------------------------------------------------------------
    # Admin gating
    # ------------------------------------------------------------------

    def require_admin(self, request=None) -> Optional[Response]:
        """
        Return a 403 Response if the requesting user is not staff.
        Return ``None`` if the user IS staff (caller should proceed).

        Usage::

            if e := self.require_admin(): return e
            # user is admin — continue
        """
        req = request or self.request
        if not req.user.is_staff:
            return self.err("Admin access required.", status.HTTP_403_FORBIDDEN)
        return None

    # ------------------------------------------------------------------
    # Safe model fetch
    # ------------------------------------------------------------------

    def get_or_none(self, model_class: Type, **kwargs) -> Optional[Any]:
        """
        Return the first matching model instance, or ``None`` if not found.

        Replaces five separate ``try/except DoesNotExist`` blocks.

        Usage::

            rule = self.get_or_none(FraudRule, pk=pk)
            if rule is None:
                return self.err("FraudRule not found.", 404)
        """
        return get_or_none(model_class, **kwargs)


class FraudAdminView(FraudBaseView):
    """
    Base class for views that are admin-only at the class level.

    Use ``FraudBaseView`` when a single view mixes public GET + admin POST/DELETE.
    Use ``FraudAdminView`` when ALL methods require admin.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

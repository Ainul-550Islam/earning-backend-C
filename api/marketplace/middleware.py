"""
marketplace/middleware.py — Marketplace Middleware
"""

import logging
import time

from django.http import JsonResponse

logger = logging.getLogger(__name__)


class MarketplaceLoggingMiddleware:
    """
    Logs every marketplace API request with timing info.
    Attach to MIDDLEWARE in settings for marketplace routes only.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/marketplace/"):
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        elapsed = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "[marketplace] %s %s → %s  (%.2fms)  tenant=%s  user=%s",
            request.method,
            request.path,
            response.status_code,
            elapsed,
            getattr(getattr(request, "tenant", None), "slug", "—"),
            getattr(request.user, "username", "anon"),
        )
        return response


class SellerStatusMiddleware:
    """
    Block suspended/banned sellers from write operations in the marketplace.
    """

    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith("/api/marketplace/")
            and request.method not in self.SAFE_METHODS
            and request.user.is_authenticated
            and not request.user.is_staff
        ):
            tenant = getattr(request, "tenant", None)
            if tenant:
                from .models import SellerProfile
                seller = SellerProfile.objects.filter(
                    user=request.user, tenant=tenant
                ).first()
                if seller and seller.status in ("suspended", "banned"):
                    return JsonResponse(
                        {"detail": f"Your seller account is {seller.status}."},
                        status=403,
                    )

        return self.get_response(request)

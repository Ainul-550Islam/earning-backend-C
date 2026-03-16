"""
decorators.py – Postback security decorators.

These can be applied to custom views that extend the postback pipeline
(e.g., admin-triggered test postbacks or partner portal endpoints).
"""
import functools
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def require_postback_signature(view_func):
    """
    Decorator that verifies the postback HMAC signature on a view.
    Expects the view to have `network_key` as a URL kwarg.

    Usage:
        @require_postback_signature
        def my_view(request, network_key):
            ...
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .constants import SIGNATURE_HEADER, TIMESTAMP_HEADER, NONCE_HEADER
        from .models import NetworkPostbackConfig
        from .utils.signature_validator import validate_full_request
        from .exceptions import (
            InvalidSignatureException,
            SignatureExpiredException,
            NonceReusedException,
            NetworkNotFoundException,
        )

        network_key = kwargs.get("network_key", "")
        signature = request.META.get(
            "HTTP_" + SIGNATURE_HEADER.upper().replace("-", "_"), ""
        )
        timestamp_str = request.META.get(
            "HTTP_" + TIMESTAMP_HEADER.upper().replace("-", "_"), ""
        )
        nonce = request.META.get(
            "HTTP_" + NONCE_HEADER.upper().replace("-", "_"), ""
        )

        try:
            network = NetworkPostbackConfig.objects.get_by_key_or_raise(network_key)
            if network.signature_algorithm != "none":
                validate_full_request(
                    provided_signature=signature,
                    timestamp_str=timestamp_str,
                    nonce=nonce,
                    secret=network.secret_key,
                    network_id=str(network.pk),
                    algorithm=network.signature_algorithm,
                    method=request.method,
                    path=request.path,
                    query_params=dict(request.GET),
                    body=request.body,
                )
        except (
            InvalidSignatureException,
            SignatureExpiredException,
            NonceReusedException,
            NetworkNotFoundException,
        ) as exc:
            logger.warning(
                "require_postback_signature failed for network_key=%r: %s",
                network_key, exc.detail,
            )
            return JsonResponse({"detail": str(exc.detail)}, status=exc.status_code)
        except Exception as exc:
            logger.exception("require_postback_signature unexpected error: %s", exc)
            return JsonResponse({"detail": "Signature verification error."}, status=500)

        return view_func(request, *args, **kwargs)

    return wrapper


def log_postback_attempt(view_func):
    """
    Lightweight decorator that logs every postback request
    (IP, network, method) before the view runs.
    Useful for audit trails on test endpoints.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .utils.ip_checker import get_client_ip
        ip = get_client_ip(request, trust_forwarded=False)
        network_key = kwargs.get("network_key", "unknown")
        logger.info(
            "[postback_attempt] method=%s network=%s ip=%s path=%s",
            request.method, network_key, ip, request.path,
        )
        return view_func(request, *args, **kwargs)
    return wrapper


def postback_rate_limit(view_func):
    """
    Per-network rate limiting using Django cache.
    Counts requests per (network_key, source_ip) per minute.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        import time
        from django.core.cache import cache
        from .utils.ip_checker import get_client_ip

        network_key = kwargs.get("network_key", "unknown")
        ip = get_client_ip(request, trust_forwarded=False)
        minute_bucket = int(time.time()) // 60
        cache_key = f"postback:rate:{network_key}:{ip}:{minute_bucket}"

        count = cache.get(cache_key, 0)
        if count >= 1000:
            return JsonResponse(
                {"detail": "Rate limit exceeded."},
                status=429,
            )
        cache.set(cache_key, count + 1, timeout=60)
        return view_func(request, *args, **kwargs)
    return wrapper

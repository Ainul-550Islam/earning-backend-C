"""
Middleware — FastAPI middleware for request logging, security headers, rate limiting, CORS, and tracing.
"""
import logging, time, uuid
from datetime import datetime
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs all API requests with timing, user context, and unique request ID."""

    SKIP_PATHS = {"/health", "/metrics", "/favicon.ico", "/docs", "/openapi.json"}

    def __init__(self, app: ASGIApp, log_body: bool = False):
        super().__init__(app)
        self.log_body = log_body

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        request.state.started_at = time.monotonic()
        user_id = self._extract_user_id(request)
        logger.info(f"[{request_id}] {request.method} {request.url.path} user={user_id or 'anonymous'} ip={request.client.host if request.client else 'unknown'}")
        try:
            response = await call_next(request)
            duration_ms = (time.monotonic() - request.state.started_at) * 1000
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            log_fn = logger.warning if response.status_code >= 400 else logger.info
            log_fn(f"[{request_id}] {response.status_code} {request.method} {request.url.path} ({duration_ms:.2f}ms)")
            return response
        except Exception as exc:
            duration_ms = (time.monotonic() - request.state.started_at) * 1000
            logger.error(f"[{request_id}] ERROR {request.method} {request.url.path} ({duration_ms:.2f}ms): {exc}")
            raise

    def _extract_user_id(self, request: Request) -> Optional[str]:
        auth = request.headers.get("Authorization","")
        if auth.startswith("Bearer "):
            try:
                import base64, json as j
                token = auth.split(".")[1]
                padding = 4 - len(token) % 4
                payload = base64.b64decode(token + "="*padding)
                claims = j.loads(payload)
                return claims.get("sub") or claims.get("user_id")
            except Exception: pass
        return None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers (HSTS, XSS protection, content type, etc.) to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory rate limiting: 100 requests/minute per IP."""

    def __init__(self, app: ASGIApp, requests_per_minute: int = 100):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._counters: dict = {}
        self._windows: dict = {}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health","/metrics"}:
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        if now - self._windows.get(client_ip, now) >= 60:
            self._counters[client_ip] = 0
            self._windows[client_ip] = now
        count = self._counters.get(client_ip, 0) + 1
        self._counters[client_ip] = count
        if count > self.rpm:
            logger.warning(f"Rate limit exceeded: {client_ip}")
            return Response(content='{"detail":"Rate limit exceeded"}', status_code=429,
                             headers={"Content-Type":"application/json","Retry-After":"60",
                                      "X-RateLimit-Limit":str(self.rpm),"X-RateLimit-Remaining":"0"})
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(max(self.rpm-count,0))
        return response


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Propagates X-Correlation-ID for distributed tracing."""

    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response


class PerformanceMonitorMiddleware(BaseHTTPMiddleware):
    """Logs requests taking > 2 seconds as slow requests."""

    SLOW_THRESHOLD_MS = 2000

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        if duration_ms >= self.SLOW_THRESHOLD_MS:
            logger.warning(f"SLOW REQUEST: {request.method} {request.url.path} {duration_ms:.0f}ms")
        return response


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """Returns 503 when DR_MAINTENANCE_MODE=1 environment variable is set."""

    ALLOWED_IN_MAINTENANCE = {"/health","/metrics","/api/v1/status"}

    def __init__(self, app: ASGIApp, maintenance_mode: bool = False):
        super().__init__(app)
        self.maintenance_mode = maintenance_mode

    async def dispatch(self, request: Request, call_next):
        import os
        if (self.maintenance_mode or os.environ.get("DR_MAINTENANCE_MODE","0") == "1") and request.url.path not in self.ALLOWED_IN_MAINTENANCE:
            return Response(content='{"detail":"Service temporarily unavailable — maintenance in progress","retry_after":300}',
                             status_code=503, headers={"Content-Type":"application/json",
                                                        "Retry-After":"300","X-Maintenance-Mode":"true"})
        return await call_next(request)


def configure_middleware(app) -> None:
    """Configure all middleware on a FastAPI app in the correct order."""
    from .config import settings
    app.add_middleware(PerformanceMonitorMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=getattr(settings,"rate_limit_per_minute",100))
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware, log_body=getattr(settings,"log_request_body",False))
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware,
                        allow_origins=getattr(settings,"cors_origins",["http://localhost:3000"]),
                        allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    logger.info("All middleware configured")

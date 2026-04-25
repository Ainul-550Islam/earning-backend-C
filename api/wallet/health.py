# api/wallet/health.py
"""
Health check endpoints for monitoring (Prometheus, Grafana, AWS ALB, etc.)

Endpoints:
  GET /api/wallet/health/           — basic health
  GET /api/wallet/health/detailed/  — detailed subsystem check
  GET /api/wallet/health/metrics/   — Prometheus metrics

Used by:
  - Load balancers (ALB, nginx) — liveness check
  - Monitoring (Datadog, Grafana) — metrics
  - CI/CD pipelines — deployment validation
"""
import time
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger("wallet.health")


@never_cache
@require_http_methods(["GET"])
def health_check(request):
    """
    GET /api/wallet/health/
    Returns 200 OK if wallet app is healthy, 503 if not.
    Used by load balancers for routing decisions.
    """
    try:
        from .models.core import Wallet
        wallet_count = Wallet.objects.count()

        return JsonResponse({
            "status":    "healthy",
            "service":   "wallet",
            "timestamp": timezone.now().isoformat(),
            "wallet_count": wallet_count,
        }, status=200)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JsonResponse({
            "status": "unhealthy",
            "error":  str(e),
        }, status=503)


@never_cache
@require_http_methods(["GET"])
def health_detailed(request):
    """
    GET /api/wallet/health/detailed/
    Detailed check of all subsystems.
    """
    checks = {}
    overall = "healthy"

    # Database
    try:
        start = time.monotonic()
        from .models.core import Wallet
        Wallet.objects.filter(pk=0).exists()
        checks["database"] = {"status": "ok", "latency_ms": round((time.monotonic()-start)*1000, 2)}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Cache (Redis)
    try:
        from django.core.cache import cache
        start = time.monotonic()
        cache.set("wallet_health_ping", "pong", 10)
        assert cache.get("wallet_health_ping") == "pong"
        checks["cache"] = {"status": "ok", "latency_ms": round((time.monotonic()-start)*1000, 2)}
    except Exception as e:
        checks["cache"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Celery
    try:
        from celery import current_app
        inspect = current_app.control.inspect(timeout=1.0)
        active = inspect.active()
        checks["celery"] = {"status": "ok" if active else "degraded",
                            "workers": len(active) if active else 0}
    except Exception as e:
        checks["celery"] = {"status": "error", "error": str(e)}

    # Pending withdrawals check
    try:
        from .models.withdrawal import WithdrawalRequest
        pending = WithdrawalRequest.objects.filter(status="pending").count()
        stuck = WithdrawalRequest.objects.filter(
            status="pending",
            created_at__lt=timezone.now() - __import__("datetime").timedelta(hours=24)
        ).count()
        checks["withdrawals"] = {"pending": pending, "stuck_24h": stuck,
                                  "status": "warning" if stuck > 0 else "ok"}
    except Exception as e:
        checks["withdrawals"] = {"status": "error", "error": str(e)}

    status_code = 200 if overall == "healthy" else 503
    return JsonResponse({
        "status":    overall,
        "service":   "wallet",
        "timestamp": timezone.now().isoformat(),
        "checks":    checks,
    }, status=status_code)


@never_cache
@require_http_methods(["GET"])
def health_metrics(request):
    """
    GET /api/wallet/health/metrics/
    Prometheus-compatible text format metrics.
    """
    lines = []
    try:
        from .models.core import Wallet, WalletTransaction
        from .models.withdrawal import WithdrawalRequest
        from django.db.models import Sum, Count

        wallets_total   = Wallet.objects.count()
        locked_wallets  = Wallet.objects.filter(is_locked=True).count()
        pending_wd      = WithdrawalRequest.objects.filter(status="pending").count()
        total_balance   = Wallet.objects.aggregate(t=Sum("current_balance"))["t"] or Decimal("0")

        lines += [
            "# HELP wallet_total_wallets Total number of wallets",
            "# TYPE wallet_total_wallets gauge",
            f"wallet_total_wallets {wallets_total}",
            "",
            "# HELP wallet_locked_wallets Number of locked wallets",
            "# TYPE wallet_locked_wallets gauge",
            f"wallet_locked_wallets {locked_wallets}",
            "",
            "# HELP wallet_pending_withdrawals Pending withdrawal count",
            "# TYPE wallet_pending_withdrawals gauge",
            f"wallet_pending_withdrawals {pending_wd}",
            "",
            "# HELP wallet_total_balance_bdt Total balance across all wallets (BDT)",
            "# TYPE wallet_total_balance_bdt gauge",
            f"wallet_total_balance_bdt {float(total_balance)}",
        ]
    except Exception as e:
        lines.append(f"# ERROR: {e}")

    from django.http import HttpResponse
    return HttpResponse("\n".join(lines), content_type="text/plain; version=0.0.4")

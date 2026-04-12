#!/usr/bin/env python
"""scripts/health_check.py — Full PostbackEngine health check."""
import os, sys, django, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

def check_redis():
    try:
        from django.core.cache import cache
        cache.set("pe:health:test", "ok", timeout=5)
        return cache.get("pe:health:test") == "ok"
    except Exception as e:
        return False, str(e)

def check_db():
    try:
        from api.postback_engine.models import AdNetworkConfig
        AdNetworkConfig.objects.count()
        return True
    except Exception as e:
        return False

def check_celery():
    try:
        from celery.app.control import Control
        from config.celery import app
        inspector = app.control.inspect(timeout=3)
        active = inspector.active()
        return active is not None
    except Exception:
        return False

def main():
    checks = {
        "database":        check_db(),
        "redis_cache":     check_redis(),
        "celery_workers":  check_celery(),
    }

    # Network stats
    from api.postback_engine.models import AdNetworkConfig, PostbackRawLog
    from api.postback_engine.enums import PostbackStatus
    checks["active_networks"] = AdNetworkConfig.objects.filter(is_active=True).count()
    checks["pending_postbacks"] = PostbackRawLog.objects.filter(status=PostbackStatus.RECEIVED).count()
    checks["failed_postbacks"] = PostbackRawLog.objects.filter(status=PostbackStatus.FAILED).count()

    # Queue depth
    try:
        from api.postback_engine.queue_management.queue_manager import queue_manager
        checks["queue_depth"] = queue_manager.get_stats()
    except Exception:
        checks["queue_depth"] = "unknown"

    all_ok = all(v is not False for v in [checks["database"], checks["redis_cache"]])
    checks["status"] = "healthy" if all_ok else "degraded"

    print(json.dumps(checks, indent=2, default=str))
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()

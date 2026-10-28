# fraud_detection/utils/helpers.py
"""
Shared helper functions used across multiple view modules.

Eliminates these previously duplicated patterns
-----------------------------------------------
1. ``lazy_repo(class_name)``
   Replaces 6 identical try/except ImportError blocks:
       _rule_repo(), _case_repo(), _alert_repo(),
       _risk_profile_repo(), _ip_rep_repo(), _suspicious_ip_repo()

2. ``lazy_detector(class_name)``
   Replaces the repeated ``_load(class_name)`` function that appeared in
   views_detectors.py and had the same body as lazy_repo but for detectors.

3. ``lazy_service(module_path, class_name)``
   Used by views_notification_service.py instead of its inline ``_svc()``.

4. ``cache_append(key, entry, max_entries, ttl)``
   Replaces three separate cache-log helpers:
       TaskHistoryAPIView.record()  (views_tasks.py)
       _record_activity()           (views_signals_monitor.py)
       _log_attack()                (security/security_views.py)

5. ``get_or_none(Model, **kwargs)``
   Replaces five identical try/except DoesNotExist patterns:
       _get_rule(), _get_case(), _get_alert(), _get_profile(), _get_ip()

6. ``record_stat(slug, success)``
   Replaces ``_record_run()`` in views_detectors.py.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Lazy repository accessor
# ---------------------------------------------------------------------------

def lazy_repo(class_name: str) -> Optional[Any]:
    """
    Try to instantiate a repository class from
    ``api.fraud_detection.repositories``.

    Returns the repository instance or ``None`` on ImportError / AttributeError.
    The caller should check the result and fall back to direct ORM.

    Example
    -------
    repo = lazy_repo("FraudRuleRepository")
    if repo and hasattr(repo, "get_all"):
        return repo.get_all(...)
    # fall back to ORM
    """
    try:
        from api.fraud_detection import repositories
        cls = getattr(repositories, class_name)
        return cls()
    except (ImportError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# 2. Lazy detector accessor
# ---------------------------------------------------------------------------

def lazy_detector(class_name: str) -> Optional[Any]:
    """
    Try to instantiate a detector class from
    ``api.fraud_detection.detectors.<ClassName>``.

    Returns the detector instance or ``None`` if the module is absent.
    All detector view methods check for ``None`` and return 503.

    Example
    -------
    det = lazy_detector("VPNProxyDetector")
    if det is None:
        return self.err("Detector unavailable.", 503)
    result = det.detect(data)
    """
    try:
        mod = __import__(
            f"api.fraud_detection.detectors.{class_name}",
            fromlist=[class_name],
        )
        cls = getattr(mod, class_name)
        return cls()
    except (ImportError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# 3. Lazy service accessor
# ---------------------------------------------------------------------------

def lazy_service(module_path: str, class_name: str) -> Optional[Any]:
    """
    Try to instantiate a service class from an arbitrary module path.

    Example
    -------
    svc = lazy_service(
        "api.fraud_detection.services.FraudNotificationService",
        "FraudNotificationService",
    )
    """
    try:
        mod = __import__(module_path, fromlist=[class_name])
        cls = getattr(mod, class_name)
        return cls()
    except (ImportError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# 4. Cache-backed append log
# ---------------------------------------------------------------------------

def cache_append(
    key: str,
    entry: Dict,
    max_entries: int = 1000,
    ttl: int = 86_400,
) -> None:
    """
    Prepend *entry* to a list stored at cache *key*, trimming to *max_entries*.

    Replaces three separate implementations:
    - TaskHistoryAPIView.record()   in views_tasks.py
    - _record_activity()            in views_signals_monitor.py
    - _log_attack()                 in security/security_views.py

    All had the same cache.get → insert(0) → cache.set pattern.

    Example
    -------
    cache_append(
        "fraud_task_history",
        {"task_name": "run_fraud_scan", "status": "PENDING",
         "triggered_at": timezone.now().isoformat()},
        max_entries=500,
        ttl=86_400,
    )
    """
    from django.core.cache import cache
    log = cache.get(key, [])
    log.insert(0, entry)
    cache.set(key, log[:max_entries], timeout=ttl)


# ---------------------------------------------------------------------------
# 5. ORM object-or-None helper
# ---------------------------------------------------------------------------

def get_or_none(model_class: Type, **kwargs) -> Optional[Any]:
    """
    Return the first matching model instance or ``None``.

    Replaces five identical ``try / except DoesNotExist`` patterns:
    - _get_rule(pk)    in FraudRuleRepoDetailAPIView
    - _get_case(pk)    in FraudCaseRepoDetailAPIView
    - _get_alert(pk)   in FraudAlertRepoDetailAPIView
    - _get_profile(pk) in FraudRiskProfileRepoDetailAPIView
    - _get_ip(pk)      in IPReputationRepoDetailAPIView

    Example
    -------
    rule = get_or_none(FraudRule, pk=pk)
    if rule is None:
        return self.err("FraudRule not found.", 404)
    """
    try:
        return model_class.objects.get(**kwargs)
    except model_class.DoesNotExist:
        return None


# ---------------------------------------------------------------------------
# 6. Detector run-counter
# ---------------------------------------------------------------------------

def record_stat(slug: str, success: bool, user: Any = None) -> None:
    """
    Increment a per-detector run counter stored in cache.

    Replaces ``_record_run()`` from views_detectors.py.

    Example
    -------
    record_stat("referral-fraud", success=True, user=request.user)
    """
    from django.core.cache import cache
    key  = f"detector_stats:{slug}"
    stat = cache.get(key) or {"runs": 0, "errors": 0, "last_run": None}
    stat["runs" if success else "errors"] += 1
    stat["last_run"] = timezone.now().isoformat()
    if user:
        stat["last_user"] = str(user)
    cache.set(key, stat, timeout=86_400)

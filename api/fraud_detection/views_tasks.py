# =============================================================================
# fraud_detection/views_tasks.py  (DRY-refactored)
# =============================================================================
"""
HTTP API for every Celery task defined in tasks.py.

DRY improvements
-----------------
• Extends FraudBaseView/FraudAdminView — eliminates 31 duplicate
  throttle_classes, 30 permission_classes, 2 _ok/_err definitions.
• _TriggerBase mixin carries all trigger boilerplate; each concrete
  trigger view is ≤6 lines.
• _record() is one module-level function (was TaskHistoryAPIView.record
  class-method + inline code combined).
• cache_append() from utils replaces inline cache.get/insert/set.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from django.utils import timezone
from rest_framework import status
from api.fraud_detection.utils import FraudBaseView, FraudAdminView, cache_append

logger = logging.getLogger(__name__)
_HISTORY_KEY = "fraud_task_history"


# ---------------------------------------------------------------------------
# Module-level helpers (each defined exactly once)
# ---------------------------------------------------------------------------

def _try_celery_app():
    try:
        from celery import current_app
        return current_app
    except ImportError:
        return None


def _enqueue(task_fn_name: str, *args, **kwargs) -> Dict:
    try:
        from api.fraud_detection import tasks as task_module
        fn     = getattr(task_module, task_fn_name)
        result = fn.delay(*args, **kwargs)
        return {"queued": True, "task_id": result.id,
                "task_name": task_fn_name, "status": "PENDING"}
    except ImportError:
        return {"queued": False, "error": "Celery not configured",
                "task_name": task_fn_name}
    except AttributeError:
        return {"queued": False,
                "error": f"Task '{task_fn_name}' not found",
                "task_name": task_fn_name}
    except Exception as exc:
        logger.exception("_enqueue(%s): %s", task_fn_name, exc)
        return {"queued": False, "error": str(exc), "task_name": task_fn_name}


def _task_result(task_id: str) -> Dict:
    try:
        from celery.result import AsyncResult
        r    = AsyncResult(task_id)
        data: Dict = {"task_id": task_id, "status": r.status}
        if r.ready():
            if r.successful():
                data["result"] = (r.result if isinstance(r.result, dict)
                                  else str(r.result))
            elif r.failed():
                data["error"] = str(r.result)
        return data
    except ImportError:
        return {"task_id": task_id, "status": "UNKNOWN",
                "error": "Celery not available"}
    except Exception as exc:
        return {"task_id": task_id, "status": "ERROR", "error": str(exc)}


def _record(task_name: str, task_id: str, status_: str,
            triggered_by: Optional[str] = None,
            params: Optional[Dict] = None) -> None:
    meta = TASK_REGISTRY.get(task_name, {})
    cache_append(
        _HISTORY_KEY,
        {"task_name": task_name, "task_id": task_id, "status": status_,
         "group": meta.get("group", "unknown"), "triggered_by": triggered_by,
         "params": params or {},
         "triggered_at": timezone.now().isoformat()},
        max_entries=500, ttl=86_400,
    )


# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------

TASK_REGISTRY: Dict[str, Dict] = {
    "run_fraud_scan": {
        "slug": "run-fraud-scan", "group": "detection",
        "description": "Comprehensive fraud scan on recent activity.",
        "params": {}, "schedule": "every 15 minutes",
    },
    "auto_ban_high_risk": {
        "slug": "auto-ban-high-risk", "group": "detection",
        "description": "Review critical risk profiles and take ban/restrict actions.",
        "params": {}, "schedule": "every 30 minutes",
    },
    "calculate_user_risk_scores": {
        "slug": "calculate-risk-scores", "group": "detection",
        "description": "Calculate/update risk scores for all or specific users.",
        "params": {"user_ids": "list[int] optional"}, "schedule": "every hour",
    },
    "update_device_trust_scores": {
        "slug": "update-device-trust", "group": "detection",
        "description": "Recalculate trust scores for all device fingerprints.",
        "params": {}, "schedule": "every 6 hours",
    },
    "train_fraud_patterns": {
        "slug": "train-fraud-patterns", "group": "detection",
        "description": "Train ML fraud patterns using last 30 days of data.",
        "params": {}, "schedule": "daily at 02:00",
    },
    "analyze_fraud_patterns": {
        "slug": "analyze-fraud-patterns", "group": "detection",
        "description": "Analyze last 24 hours for new anomaly patterns.",
        "params": {}, "schedule": "every 2 hours",
    },
    "graph_network_scan": {
        "slug": "graph-network-scan", "group": "detection",
        "description": "Deep graph-based fraud network scan.",
        "params": {}, "schedule": "daily at 03:00",
    },
    "velocity_engine_cleanup": {
        "slug": "velocity-cleanup", "group": "detection",
        "description": "Purge stale velocity counters and windows.",
        "params": {}, "schedule": "every hour",
    },
    "ml_drift_check": {
        "slug": "ml-drift-check", "group": "detection",
        "description": "Check for ML model drift; alert if accuracy drops.",
        "params": {}, "schedule": "every 4 hours",
    },
    "retrain_fraud_patterns": {
        "slug": "retrain-fraud-patterns", "group": "detection",
        "description": "Full ML model retrain using accumulated labelled data.",
        "params": {}, "schedule": "weekly Sunday 01:00",
    },
    "recalculate_stale_risk_profiles": {
        "slug": "recalculate-stale-profiles", "group": "detection",
        "description": "Recalculate risk scores for profiles not updated in 24 h.",
        "params": {}, "schedule": "every 6 hours",
    },
    "send_pending_notifications": {
        "slug": "send-pending-notifications", "group": "notifications",
        "description": "Flush pending notification queue to all channels.",
        "params": {}, "schedule": "every 5 minutes",
    },
    "retry_failed_notifications": {
        "slug": "retry-notifications", "group": "notifications",
        "description": "Retry failed notifications.",
        "params": {}, "schedule": "every 30 minutes",
    },
    "deliver_fraud_notification": {
        "slug": "deliver-notification", "group": "notifications",
        "description": "Deliver a specific notification by notification_id.",
        "params": {"notification_id": "int — required"}, "schedule": "on demand",
    },
    "warm_fraud_cache": {
        "slug": "warm-cache", "group": "maintenance",
        "description": "Pre-populate Redis with high-risk profiles + active rules.",
        "params": {}, "schedule": "every 2 hours",
    },
    "cleanup_fraud_cache": {
        "slug": "cleanup-cache", "group": "maintenance",
        "description": "Evict stale cache entries for fraud data.",
        "params": {}, "schedule": "daily at 01:00",
    },
    "generate_fraud_report": {
        "slug": "generate-report", "group": "maintenance",
        "description": "Generate daily/weekly/monthly fraud report.",
        "params": {"report_type": "str daily|weekly|monthly",
                   "date_range": "str YYYY-MM-DD optional"},
        "schedule": "daily at 06:00",
    },
    "archive_old_fraud_data": {
        "slug": "archive-data", "group": "maintenance",
        "description": "Archive fraud records older than days_to_keep (default 90).",
        "params": {"days_to_keep": "int — default 90"},
        "schedule": "weekly Sunday 04:00",
    },
    "cleanup_orphaned_records": {
        "slug": "cleanup-orphaned", "group": "maintenance",
        "description": "Delete orphaned device fingerprints, stale IP records.",
        "params": {}, "schedule": "daily at 05:00",
    },
    "ip_reputation_cleanup": {
        "slug": "ip-reputation-cleanup", "group": "maintenance",
        "description": "Remove expired/stale IP reputation records.",
        "params": {}, "schedule": "daily at 02:30",
    },
    "whitelist_cleanup_expired": {
        "slug": "whitelist-cleanup", "group": "maintenance",
        "description": "Remove expired whitelist entries.",
        "params": {}, "schedule": "every 6 hours",
    },
    "check_and_unban_users": {
        "slug": "check-unban-users", "group": "maintenance",
        "description": "Lift bans for users whose suspension has ended.",
        "params": {}, "schedule": "every 15 minutes",
    },
    "audit_log_cleanup": {
        "slug": "audit-log-cleanup", "group": "maintenance",
        "description": "Delete audit log entries beyond retention period.",
        "params": {}, "schedule": "weekly Monday 03:00",
    },
}

SLUG_TO_TASK = {meta["slug"]: name for name, meta in TASK_REGISTRY.items()}


# =============================================================================
# Monitoring views  (IsAuthenticated via FraudBaseView)
# =============================================================================

class TaskListAPIView(FraudBaseView):
    """GET /fraud/tasks/"""
    def get(self, request):
        group = request.query_params.get("group")
        tasks = [
            {"task_name": name, "slug": meta["slug"], "group": meta["group"],
             "description": meta["description"], "params": meta["params"],
             "schedule": meta["schedule"],
             "trigger_url": f"/fraud/tasks/{meta['slug']}/trigger/"}
            for name, meta in TASK_REGISTRY.items()
            if not group or meta["group"] == group
        ]
        return self.ok({
            "total":  len(tasks),
            "groups": sorted({m["group"] for m in TASK_REGISTRY.values()}),
            "tasks":  tasks,
        })


class TaskStatusAPIView(FraudBaseView):
    """GET /fraud/tasks/status/<task_id>/"""
    def get(self, request, task_id: str):
        return self.ok(_task_result(task_id))


class TaskRevokeAPIView(FraudAdminView):
    """POST /fraud/tasks/revoke/<task_id>/"""
    def post(self, request, task_id: str):
        terminate = bool(request.data.get("terminate", False))
        app = _try_celery_app()
        try:
            if app:
                app.control.revoke(task_id, terminate=terminate)
                return self.ok({"revoked": True, "task_id": task_id,
                                 "terminate": terminate})
            return self.err("Celery not available.")
        except Exception as exc:
            logger.exception("TaskRevokeAPIView task_id=%s: %s", task_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskActiveAPIView(FraudBaseView):
    """GET /fraud/tasks/active/"""
    def get(self, request):
        app = _try_celery_app()
        try:
            if not app:
                return self.ok({"active": [], "note": "Celery not available"})
            active = app.control.inspect(timeout=3).active() or {}
            tasks  = [
                {"worker": w, "task_id": t.get("id"),
                 "task_name": t.get("name"), "args": t.get("args"),
                 "kwargs": t.get("kwargs"), "started": t.get("time_start")}
                for w, tlist in active.items() for t in (tlist or [])
            ]
            return self.ok({"active_count": len(tasks), "tasks": tasks})
        except Exception as exc:
            logger.exception("TaskActiveAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskScheduledAPIView(FraudBaseView):
    """GET /fraud/tasks/scheduled/"""
    def get(self, request):
        app = _try_celery_app()
        cfg = [{"task": n, "schedule": m["schedule"]}
               for n, m in TASK_REGISTRY.items()]
        try:
            if not app:
                return self.ok({"scheduled": [], "config_schedule": cfg,
                                 "note": "Celery not available"})
            sched = app.control.inspect(timeout=3).scheduled() or {}
            tasks = [
                {"worker": w,
                 "task_id": t.get("request", {}).get("id"),
                 "task_name": t.get("request", {}).get("name"),
                 "eta": t.get("eta")}
                for w, tlist in sched.items() for t in (tlist or [])
            ]
            return self.ok({"scheduled_count": len(tasks), "scheduled": tasks,
                             "config_schedule": cfg})
        except Exception as exc:
            logger.exception("TaskScheduledAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskHistoryAPIView(FraudBaseView):
    """GET /fraud/tasks/history/"""
    def get(self, request):
        from django.core.cache import cache
        try:
            limit = min(200, int(request.query_params.get("limit", 50)))
        except (TypeError, ValueError):
            limit = 50
        group = request.query_params.get("group")
        log   = cache.get(_HISTORY_KEY, [])
        if group:
            log = [h for h in log if h.get("group") == group]
        return self.ok({"total": len(log), "limit": limit,
                         "history": log[:limit]})

    @staticmethod
    def record(task_name, task_id, status_, triggered_by=None, params=None):
        _record(task_name, task_id, status_, triggered_by, params)


class TaskStatsAPIView(FraudBaseView):
    """GET /fraud/tasks/stats/"""
    def get(self, request):
        from django.core.cache import cache
        history   = cache.get(_HISTORY_KEY, [])
        by_status: Dict[str, int] = {}
        by_group:  Dict[str, int] = {}
        for h in history:
            s = h.get("status", "?"); g = h.get("group", "?")
            by_status[s] = by_status.get(s, 0) + 1
            by_group[g]  = by_group.get(g, 0) + 1
        return self.ok({"total_runs": len(history),
                         "registered_tasks": len(TASK_REGISTRY),
                         "by_status": by_status, "by_group": by_group})


# =============================================================================
# Shared trigger mixin  (DRY: all 22 trigger views share this)
# =============================================================================

class _TriggerBase(FraudAdminView):
    _task_fn:      str  = ""
    _long_running: bool = False

    def _get_args(self, request) -> tuple:
        return ()

    def _params(self, request) -> Dict:
        return {}

    def post(self, request):
        args   = self._get_args(request)
        result = _enqueue(self._task_fn, *args)
        if result.get("queued"):
            _record(self._task_fn, result["task_id"], "PENDING",
                    triggered_by=str(request.user), params=self._params(request))
        if self._long_running and result.get("queued"):
            result["warning"] = ("Long-running task. "
                                  "Poll /fraud/tasks/status/<task_id>/ for progress.")
        code = (status.HTTP_202_ACCEPTED if result.get("queued")
                else status.HTTP_200_OK)
        return self.ok(result, code)


# =============================================================================
# Group A — Risk & Detection (11 trigger views)
# =============================================================================

class TaskRunFraudScanAPIView(_TriggerBase):
    _task_fn = "run_fraud_scan"

class TaskAutoBanHighRiskAPIView(_TriggerBase):
    _task_fn = "auto_ban_high_risk"

class TaskCalculateRiskScoresAPIView(_TriggerBase):
    _task_fn = "calculate_user_risk_scores"
    def _get_args(self, r): return (r.data.get("user_ids") or None,)
    def _params(self, r):   return {"user_ids": r.data.get("user_ids") or "all"}
    def post(self, request):
        uid = request.data.get("user_ids")
        if uid is not None and not isinstance(uid, list):
            return self.err("user_ids must be a list of integers.")
        return super().post(request)

class TaskUpdateDeviceTrustAPIView(_TriggerBase):
    _task_fn = "update_device_trust_scores"

class TaskTrainFraudPatternsAPIView(_TriggerBase):
    _task_fn = "train_fraud_patterns"
    _long_running = True

class TaskAnalyzeFraudPatternsAPIView(_TriggerBase):
    _task_fn = "analyze_fraud_patterns"

class TaskGraphNetworkScanAPIView(_TriggerBase):
    _task_fn = "graph_network_scan"

class TaskVelocityCleanupAPIView(_TriggerBase):
    _task_fn = "velocity_engine_cleanup"

class TaskMLDriftCheckAPIView(_TriggerBase):
    _task_fn = "ml_drift_check"

class TaskRetrainFraudPatternsAPIView(_TriggerBase):
    _task_fn = "retrain_fraud_patterns"
    _long_running = True

class TaskRecalculateStaleProfilesAPIView(_TriggerBase):
    _task_fn = "recalculate_stale_risk_profiles"


# =============================================================================
# Group B — Notification triggers (3 views)
# =============================================================================

class TaskSendPendingNotificationsAPIView(_TriggerBase):
    _task_fn = "send_pending_notifications"

class TaskRetryNotificationsAPIView(_TriggerBase):
    _task_fn = "retry_failed_notifications"

class TaskDeliverNotificationAPIView(_TriggerBase):
    _task_fn = "deliver_fraud_notification"
    def _get_args(self, r): return (int(r.data["notification_id"]),)
    def _params(self, r):   return {"notification_id": r.data.get("notification_id")}
    def post(self, request):
        nid = request.data.get("notification_id")
        if not nid:
            return self.err("notification_id is required.")
        try:
            int(nid)
        except (TypeError, ValueError):
            return self.err("notification_id must be an integer.")
        return super().post(request)


# =============================================================================
# Group C — Maintenance triggers (9 views)
# =============================================================================

class TaskWarmCacheAPIView(_TriggerBase):
    _task_fn = "warm_fraud_cache"

class TaskCleanupCacheAPIView(_TriggerBase):
    _task_fn = "cleanup_fraud_cache"

class TaskGenerateReportAPIView(_TriggerBase):
    _task_fn = "generate_fraud_report"
    def _get_args(self, r):
        return (r.data.get("report_type", "daily"), r.data.get("date_range"))
    def _params(self, r):
        return {"report_type": r.data.get("report_type", "daily"),
                "date_range": r.data.get("date_range")}
    def post(self, request):
        if request.data.get("report_type", "daily") not in {"daily","weekly","monthly"}:
            return self.err("report_type must be 'daily', 'weekly', or 'monthly'.")
        return super().post(request)

class TaskArchiveDataAPIView(_TriggerBase):
    _task_fn = "archive_old_fraud_data"
    def _get_args(self, r):
        try:    return (max(30, int(r.data.get("days_to_keep", 90))),)
        except: return (90,)
    def _params(self, r):
        try:    return {"days_to_keep": max(30, int(r.data.get("days_to_keep", 90)))}
        except: return {"days_to_keep": 90}
    def post(self, request):
        resp = super().post(request)
        if hasattr(resp, "data") and resp.data.get("queued"):
            resp.data["warning"] = "Destructive — data older than cutoff will be archived."
        return resp

class TaskCleanupOrphanedAPIView(_TriggerBase):
    _task_fn = "cleanup_orphaned_records"

class TaskIPReputationCleanupAPIView(_TriggerBase):
    _task_fn = "ip_reputation_cleanup"

class TaskWhitelistCleanupAPIView(_TriggerBase):
    _task_fn = "whitelist_cleanup_expired"

class TaskCheckUnbanUsersAPIView(_TriggerBase):
    _task_fn = "check_and_unban_users"

class TaskAuditLogCleanupAPIView(_TriggerBase):
    _task_fn = "audit_log_cleanup"


# ── ALIASES: names expected by urls.py ───────────────────────────────────────
class TriggerFraudScanAPIView(_TriggerBase):
    task_name = "fraud.run_fraud_scan"
    task_func_path = "api.fraud_detection.tasks.run_fraud_scan"

class TriggerBatchRiskAPIView(_TriggerBase):
    task_name = "fraud.batch_risk_assessment"
    task_func_path = "api.fraud_detection.tasks.batch_risk_assessment"

    def post(self, request):
        user_ids = request.data.get("user_ids", [])
        if not user_ids:
            from rest_framework.response import Response
            from rest_framework import status
            return Response({"error": "user_ids required"}, status=status.HTTP_400_BAD_REQUEST)
        from api.fraud_detection.tasks import batch_risk_assessment
        job = batch_risk_assessment.delay(user_ids)
        from rest_framework.response import Response
        return Response({"task_id": job.id, "user_count": len(user_ids)})

class CapitalTaskSubmitAPIView(_TriggerBase):
    """Submit a capital-level task by name."""
    task_name = "capital"
    task_func_path = ""

    def post(self, request):
        from rest_framework.response import Response
        from rest_framework import status
        from api.fraud_detection.tasks import get_capital_task_manager
        task_type = request.data.get("task_type")
        payload   = request.data.get("payload", {})
        mgr = get_capital_task_manager()
        dispatch = {
            "critical_fraud_analysis":    lambda: mgr.submit_critical_fraud_analysis(
                payload.get("user_id"), payload.get("context")),
            "regulatory_check":           lambda: mgr.submit_regulatory_check(
                payload.get("compliance_type", "aml"), payload.get("period_days", 30)),
            "financial_loss_monitor":     lambda: mgr.submit_financial_loss_monitor(
                payload.get("threshold", 10000.0)),
            "terrorist_screening":        lambda: mgr.submit_terrorist_screening(payload),
        }
        if task_type not in dispatch:
            return Response({"error": f"Unknown task_type: {task_type}"}, status=status.HTTP_400_BAD_REQUEST)
        job = dispatch[task_type]()
        return Response({"task_id": job.id, "task_type": task_type})

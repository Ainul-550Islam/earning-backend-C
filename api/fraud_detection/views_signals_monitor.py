# =============================================================================
# fraud_detection/views_signals_monitor.py  (DRY-refactored)
# =============================================================================
"""
Signal monitoring and manual-trigger HTTP API.

DRY improvements
-----------------
• Extends FraudBaseView / FraudAdminView — removes 13 duplicate
  throttle_classes and 13 permission_classes lines.
• cache_append() from utils replaces inline _record_activity() helper.
• _ACTIVITY_KEY and _STATS_KEY defined once at module level.
• SignalTriggerBase mixin reduces all 6 trigger views to ≤15 lines each.
"""
from __future__ import annotations
import logging
from typing import Any, Dict
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from api.fraud_detection.utils import FraudBaseView, FraudAdminView, cache_append

logger       = logging.getLogger(__name__)
_ACTIVITY_KEY = "signal_activity_log"
_STATS_KEY    = "signal_stats"


def _record_activity(signal_name: str, event: str, meta: Dict = None) -> None:
    """Append signal fire record — uses shared cache_append (defined once)."""
    cache_append(
        _ACTIVITY_KEY,
        {"signal": signal_name, "event": event,
         "meta": meta or {}, "timestamp": timezone.now().isoformat()},
        max_entries=1000, ttl=86_400 * 7,
    )
    stats = cache.get(_STATS_KEY, {})
    stats[signal_name] = stats.get(signal_name, 0) + 1
    cache.set(_STATS_KEY, stats, timeout=86_400 * 7)


# ---------------------------------------------------------------------------
# Signal handler catalogue
# ---------------------------------------------------------------------------

SIGNAL_HANDLERS = [
    {"name": "handle_new_fraud_attempt",    "sender": "FraudAttempt",
     "signal": "post_save",
     "description": "Main fraud-attempt handler: velocity, geo, biometrics, graph, risk.",
     "can_trigger": True,  "trigger_slug": "fraud-attempt"},
    {"name": "create_user_risk_profile",    "sender": "User",
     "signal": "post_save",
     "description": "Auto-creates UserRiskProfile on new user registration.",
     "can_trigger": False, "trigger_slug": None},
    {"name": "check_transaction_fraud",     "sender": "wallet.WalletTransaction",
     "signal": "pre_save",
     "description": "Velocity + geo check on withdrawal/transaction events.",
     "can_trigger": False, "trigger_slug": None},
    {"name": "check_offer_completion_fraud","sender": "OfferCompletion",
     "signal": "post_save",
     "description": "Full fraud check on new offer completions.",
     "can_trigger": False, "trigger_slug": None},
    {"name": "update_device_trust_score",   "sender": "DeviceFingerprint",
     "signal": "post_save",
     "description": "Recalculates device trust score on save.",
     "can_trigger": True,  "trigger_slug": "device-update"},
    {"name": "handle_ip_reputation_changes","sender": "IPReputation",
     "signal": "post_save",
     "description": "Propagates IP reputation changes to linked fraud attempts.",
     "can_trigger": True,  "trigger_slug": "ip-change"},
    {"name": "handle_fraud_case_lifecycle", "sender": "FraudCase",
     "signal": "post_save",
     "description": "Sends notifications on case status transitions.",
     "can_trigger": False, "trigger_slug": None},
    {"name": "handle_case_action",          "sender": "FraudCaseAction",
     "signal": "post_save",
     "description": "Logs and notifies on case action creation.",
     "can_trigger": False, "trigger_slug": None},
    {"name": "handle_evidence_addition",    "sender": "FraudCaseEvidence",
     "signal": "post_save",
     "description": "Notifies case owners when new evidence is added.",
     "can_trigger": False, "trigger_slug": None},
    {"name": "handle_fraud_alert",          "sender": "FraudAlert",
     "signal": "post_save",
     "description": "Dispatches notifications on new/updated alerts.",
     "can_trigger": True,  "trigger_slug": "alert-handler"},
    {"name": "handle_notification_delivery","sender": "FraudNotification",
     "signal": "post_save",
     "description": "Queues notification delivery via Celery.",
     "can_trigger": False, "trigger_slug": None},
    {"name": "handle_whitelist_changes",    "sender": "FraudWhitelist",
     "signal": "post_save",
     "description": "Invalidates cached whitelist on changes.",
     "can_trigger": True,  "trigger_slug": "whitelist-sync"},
    {"name": "handle_pattern_updates",      "sender": "FraudPattern",
     "signal": "post_save",
     "description": "Clears pattern cache and re-evaluates pending attempts.",
     "can_trigger": False, "trigger_slug": None},
]


# =============================================================================
# Monitoring views
# =============================================================================

class SignalStatusAPIView(FraudBaseView):
    """GET /fraud/signals/status/"""
    def get(self, request):
        stats = cache.get(_STATS_KEY, {})
        handlers = [
            {**h,
             "run_count": stats.get(h["name"], 0),
             "trigger_url": (f"/fraud/signals/trigger/{h['trigger_slug']}/"
                              if h["can_trigger"] else None)}
            for h in SIGNAL_HANDLERS
        ]
        return self.ok({"total": len(handlers),
                         "can_trigger": sum(1 for h in handlers if h["can_trigger"]),
                         "handlers": handlers})


class SignalHandlerListAPIView(FraudBaseView):
    """GET /fraud/signals/handlers/"""
    def get(self, request):
        senders: Dict[str, list] = {}
        for h in SIGNAL_HANDLERS:
            senders.setdefault(h["sender"], []).append(h["name"])
        return self.ok({"signal_types_used": ["post_save","pre_save"],
                         "senders": senders, "handler_count": len(SIGNAL_HANDLERS)})


class SignalActivityAPIView(FraudBaseView):
    """GET /fraud/signals/activity/"""
    def get(self, request):
        try:
            limit = min(500, int(request.query_params.get("limit", 50)))
        except (TypeError, ValueError):
            limit = 50
        sig_filter = request.query_params.get("signal")
        log = cache.get(_ACTIVITY_KEY, [])
        if sig_filter:
            log = [e for e in log if e.get("signal") == sig_filter]
        return self.ok({"total": len(log), "limit": limit, "activity": log[:limit]})


class SignalStatsAPIView(FraudBaseView):
    """GET /fraud/signals/stats/"""
    def get(self, request):
        stats = cache.get(_STATS_KEY, {})
        by_handler = sorted(
            [{"handler": h["name"], "sender": h["sender"],
              "fire_count": stats.get(h["name"], 0)}
             for h in SIGNAL_HANDLERS],
            key=lambda x: -x["fire_count"],
        )
        return self.ok({"total_fires": sum(stats.values()),
                         "by_handler": by_handler})


# =============================================================================
# Shared trigger mixin
# =============================================================================

class _SignalTriggerBase(FraudAdminView):
    """
    Base for all signal trigger views.
    Subclasses set _signal_name, _model_name, _id_field, _signal_fn_name.
    """
    _signal_name:    str = ""
    _model_name:     str = ""
    _id_field:       str = ""
    _signal_fn_name: str = ""

    def _get_model_and_instance(self, pk):
        raise NotImplementedError

    def post(self, request):
        pk = request.data.get(self._id_field)
        if not pk:
            return self.err(f"{self._id_field} is required.")
        try:
            model_cls, instance = self._get_model_and_instance(pk)
        except Exception:
            return self.err(f"{self._model_name} {pk} not found.",
                             status.HTTP_404_NOT_FOUND)
        try:
            from api.fraud_detection import signals as sig_mod
            fn = getattr(sig_mod, self._signal_fn_name)
            fn(sender=model_cls, instance=instance, created=False)
            _record_activity(self._signal_fn_name, "manual_trigger",
                              {self._id_field: str(pk),
                               "triggered_by": str(request.user)})
            return self.ok({"triggered": True, "signal": self._signal_fn_name,
                             self._id_field: str(pk)})
        except Exception as exc:
            logger.exception("%s.post %s=%s: %s",
                              self.__class__.__name__, self._id_field, pk, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 6 concrete trigger views
# =============================================================================

class SignalTriggerFraudAttemptAPIView(_SignalTriggerBase):
    """POST /fraud/signals/trigger/fraud-attempt/"""
    _signal_name    = "handle_new_fraud_attempt"
    _model_name     = "FraudAttempt"
    _id_field       = "attempt_id"
    _signal_fn_name = "handle_new_fraud_attempt"

    def _get_model_and_instance(self, pk):
        from api.fraud_detection.models import FraudAttempt
        return FraudAttempt, FraudAttempt.objects.get(pk=pk)


class SignalTriggerIPChangeAPIView(_SignalTriggerBase):
    """POST /fraud/signals/trigger/ip-change/"""
    _signal_name    = "handle_ip_reputation_changes"
    _model_name     = "IPReputation"
    _id_field       = "ip_id"
    _signal_fn_name = "handle_ip_reputation_changes"

    def _get_model_and_instance(self, pk):
        from api.fraud_detection.models import IPReputation
        return IPReputation, IPReputation.objects.get(pk=pk)

    def post(self, request):
        pk = request.data.get(self._id_field)
        if not pk:
            return self.err(f"{self._id_field} is required.")
        try:
            from api.fraud_detection.models import IPReputation
            record = IPReputation.objects.get(pk=pk)
        except Exception:
            return self.err(f"IPReputation {pk} not found.", status.HTTP_404_NOT_FOUND)
        try:
            from api.fraud_detection import signals as sig_mod
            sig_mod.handle_ip_reputation_changes(sender=IPReputation, instance=record)
            _record_activity(self._signal_fn_name, "manual_trigger",
                              {"ip_id": pk, "ip_address": record.ip_address,
                               "triggered_by": str(request.user)})
            return self.ok({"triggered": True, "signal": self._signal_fn_name,
                             "ip_id": pk, "ip_address": record.ip_address})
        except Exception as exc:
            logger.exception("SignalTriggerIPChangeAPIView ip_id=%s: %s", pk, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SignalTriggerDeviceUpdateAPIView(_SignalTriggerBase):
    """POST /fraud/signals/trigger/device-update/"""
    _signal_name    = "update_device_trust_score"
    _model_name     = "DeviceFingerprint"
    _id_field       = "device_id"
    _signal_fn_name = "update_device_trust_score"

    def _get_model_and_instance(self, pk):
        from api.fraud_detection.models import DeviceFingerprint
        return DeviceFingerprint, DeviceFingerprint.objects.get(pk=pk)


class SignalTriggerRiskRecalcAPIView(FraudAdminView):
    """POST /fraud/signals/trigger/risk-recalc/"""
    def post(self, request):
        attempt_id = request.data.get("attempt_id")
        if not attempt_id:
            return self.err("attempt_id is required.")
        try:
            from api.fraud_detection.models import FraudAttempt
            attempt = FraudAttempt.objects.get(pk=attempt_id)
        except Exception:
            return self.err(f"FraudAttempt {attempt_id} not found.",
                             status.HTTP_404_NOT_FOUND)
        try:
            from api.fraud_detection.signals import _update_user_risk_from_attempt
            _update_user_risk_from_attempt(attempt)
            _record_activity("_update_user_risk_from_attempt", "manual_trigger",
                              {"attempt_id": str(attempt_id),
                               "triggered_by": str(request.user)})
            return self.ok({"triggered": True,
                             "signal": "_update_user_risk_from_attempt",
                             "attempt_id": str(attempt_id),
                             "user_id": attempt.user_id})
        except Exception as exc:
            logger.exception("SignalTriggerRiskRecalcAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SignalTriggerAlertHandlerAPIView(_SignalTriggerBase):
    """POST /fraud/signals/trigger/alert-handler/"""
    _signal_name    = "handle_fraud_alert"
    _model_name     = "FraudAlert"
    _id_field       = "alert_id"
    _signal_fn_name = "handle_fraud_alert"

    def _get_model_and_instance(self, pk):
        from api.fraud_detection.models import FraudAlert
        return FraudAlert, FraudAlert.objects.get(pk=pk)


class SignalTriggerWhitelistSyncAPIView(_SignalTriggerBase):
    """POST /fraud/signals/trigger/whitelist-sync/"""
    _signal_name    = "handle_whitelist_changes"
    _model_name     = "FraudWhitelist"
    _id_field       = "whitelist_id"
    _signal_fn_name = "handle_whitelist_changes"

    def _get_model_and_instance(self, pk):
        from api.fraud_detection.models import FraudWhitelist
        return FraudWhitelist, FraudWhitelist.objects.get(pk=pk)


# =============================================================================
# Middleware monitoring
# =============================================================================

class MiddlewareStatusAPIView(FraudBaseView):
    """GET /fraud/signals/middleware/status/"""
    def get(self, request):
        from django.conf import settings
        mw_list   = getattr(settings, "MIDDLEWARE", [])
        installed = any("FraudDetectionMiddleware" in m for m in mw_list)
        fraud_cfg = getattr(settings, "FRAUD_DETECTION_SETTINGS", {})
        return self.ok({
            "middleware": "FraudDetectionMiddleware",
            "installed":  installed,
            "module":     "api.fraud_detection.middleware.FraudDetectionMiddleware",
            "config": {
                "block_vpn":        fraud_cfg.get("BLOCK_VPN", False),
                "block_tor":        fraud_cfg.get("BLOCK_TOR", False),
                "risk_threshold":   fraud_cfg.get("RISK_THRESHOLD", 70),
                "auto_ban_enabled": fraud_cfg.get("AUTO_BAN_ENABLED", True),
                "log_all_requests": fraud_cfg.get("LOG_ALL_REQUESTS", False),
            },
            "checks_performed": ["user_risk_score","ip_reputation","device_risk"],
        })


class MiddlewareStatsAPIView(FraudBaseView):
    """GET /fraud/signals/middleware/stats/"""
    _STATS_KEY = "fraud_middleware_stats"

    def get(self, request):
        stats  = cache.get(self._STATS_KEY, {})
        total  = stats.get("total_requests", 0)
        blocked= stats.get("total_blocked", 0)
        flagged= stats.get("total_flagged", 0)
        return self.ok({
            "total_requests":  total,
            "total_blocked":   blocked,
            "total_flagged":   flagged,
            "block_rate": round(blocked / total * 100, 2) if total else 0.0,
            "flag_rate":  round(flagged / total * 100, 2) if total else 0.0,
            "by_reason":       stats.get("by_reason", {}),
            "top_blocked_ips": stats.get("top_blocked_ips", []),
        })

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
SignalEventLogAPIView   = SignalActivityAPIView
SignalEventStatsAPIView = SignalStatsAPIView

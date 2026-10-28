# =============================================================================
# api/auto_mod/adapters.py
# =============================================================================
"""
auto_mod ↔ other system adapters.

"এক কাজের জন্য একটাই মালিক" — adapters are the ONLY place where
auto_mod talks to external systems. No other auto_mod file may import
from api.users, api.tasks, api.fraud_detection, etc.

Adapter Pattern:
  Each adapter is a thin, stateless class that translates between
  auto_mod domain objects and the external system's interface.
  All adapters raise AutoModAdapterError on failure (never crash the pipeline).

Supported systems (from INSTALLED_APPS):
  ┌─────────────────────────┬──────────────────────────────────────────────┐
  │ Adapter                 │ External System                              │
  ├─────────────────────────┼──────────────────────────────────────────────┤
  │ UserAdapter             │ api.users — user profile & reputation        │
  │ TaskAdapter             │ api.tasks — task proof submission             │
  │ FraudAdapter            │ api.fraud_detection — fraud signals          │
  │ NotificationAdapter     │ api.notifications — moderator/user alerts    │
  │ AnalyticsAdapter        │ api.analytics — moderation event tracking    │
  │ WalletAdapter           │ api.wallet — reward/penalty transactions      │
  │ AuditLogAdapter         │ api.audit_logs — compliance audit trail      │
  │ TenantAdapter           │ api.tenants — multi-tenant context           │
  │ RateLimitAdapter        │ api.rate_limit — submission rate limiting    │
  │ WebhookAdapter          │ api.webhooks — outbound webhook dispatch     │
  │ KYCAdapter              │ api.kyc — identity verification status       │
  │ SecurityAdapter         │ api.security — threat intelligence           │
  │ AIEngineAdapter         │ api.ai_engine — ML inference calls           │
  │ PostbackAdapter         │ api.postback / api.postback_engine           │
  │ GamificationAdapter     │ api.gamification — points/badges on decision │
  │ SubscriptionAdapter     │ api.subscription — feature gating            │
  │ ProxyIntelligenceAdapter│ api.proxy_intelligence — IP/VPN detection    │
  │ CacheAdapter            │ api.cache — shared cache layer               │
  └─────────────────────────┴──────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("auto_mod.adapters")


class AutoModAdapterError(Exception):
    """Raised when an adapter call fails. Never propagates beyond the adapter."""


def _safe_import(module_path: str, attr: str = None):
    """Import a module or attribute, returning None if unavailable."""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, attr) if attr else mod
    except (ImportError, AttributeError):
        return None


# =============================================================================
# UserAdapter
# =============================================================================
class UserAdapter:
    """
    Talks to api.users.
    Used by: ModerationService (get submitter risk profile),
             AppealService (validate appellant identity)
    """

    @staticmethod
    def get_user_risk_profile(user_id: str | int) -> dict:
        """
        Returns {user_id, trust_score, is_verified, submission_count,
                 rejection_rate, is_flagged, country}.
        Falls back to safe defaults if api.users unavailable.
        """
        try:
            UserProfile = _safe_import("api.users.models", "UserProfile")
            if UserProfile:
                profile = UserProfile.objects.filter(user_id=user_id).first()
                if profile:
                    return {
                        "user_id":         str(user_id),
                        "trust_score":     getattr(profile, "trust_score", 0.7),
                        "is_verified":     getattr(profile, "is_verified", False),
                        "submission_count": getattr(profile, "submission_count", 0),
                        "rejection_rate":   getattr(profile, "rejection_rate", 0.0),
                        "is_flagged":       getattr(profile, "is_flagged", False),
                        "country":          getattr(profile, "country", None),
                    }
        except Exception as exc:
            logger.warning("UserAdapter.get_user_risk_profile failed: %s", exc)
        return {
            "user_id": str(user_id), "trust_score": 0.7,
            "is_verified": False, "submission_count": 0,
            "rejection_rate": 0.0, "is_flagged": False, "country": None,
        }

    @staticmethod
    def update_user_reputation(user_id: str | int, delta: float, reason: str = "") -> bool:
        """Adjust user reputation score. Returns True on success."""
        try:
            update_fn = _safe_import("api.users.services", "update_user_reputation")
            if update_fn:
                update_fn(user_id=user_id, delta=delta, reason=reason)
                return True
        except Exception as exc:
            logger.warning("UserAdapter.update_user_reputation failed: %s", exc)
        return False

    @staticmethod
    def flag_user(user_id: str | int, reason: str, flagged_by_system: str = "auto_mod") -> bool:
        """Flag a user for suspicious behaviour."""
        try:
            flag_fn = _safe_import("api.users.services", "flag_user")
            if flag_fn:
                flag_fn(user_id=user_id, reason=reason, source=flagged_by_system)
                return True
        except Exception as exc:
            logger.warning("UserAdapter.flag_user failed: %s", exc)
        return False


# =============================================================================
# TaskAdapter
# =============================================================================
class TaskAdapter:
    """
    Talks to api.tasks.
    Used by: ModerationService (fetch task proof context),
             BotService (update task status after decision)
    """

    @staticmethod
    def get_task_proof(task_id: str) -> dict | None:
        """Fetch task proof metadata for a given task_id."""
        try:
            TaskProof = _safe_import("api.tasks.models", "TaskProof")
            if TaskProof:
                proof = TaskProof.objects.filter(pk=task_id).first()
                if proof:
                    return {
                        "task_id":     str(proof.pk),
                        "task_type":   getattr(proof, "task_type", ""),
                        "file_urls":   getattr(proof, "file_urls", []),
                        "text":        getattr(proof, "text_content", ""),
                        "submitted_at": str(getattr(proof, "created_at", "")),
                        "user_id":     str(getattr(proof, "user_id", "")),
                    }
        except Exception as exc:
            logger.warning("TaskAdapter.get_task_proof failed: %s", exc)
        return None

    @staticmethod
    def update_task_status(task_id: str, status: str, reason: str = "") -> bool:
        """
        Inform api.tasks of the moderation decision.
        status: 'approved' | 'rejected' | 'under_review' | 'escalated'
        """
        try:
            update_fn = _safe_import("api.tasks.services", "update_task_moderation_status")
            if update_fn:
                update_fn(task_id=task_id, status=status, reason=reason)
                return True
        except Exception as exc:
            logger.warning("TaskAdapter.update_task_status failed: %s", exc)
        return False

    @staticmethod
    def get_pending_task_proofs(limit: int = 100, submission_type: str = "") -> list[dict]:
        """Fetch pending task proofs that need moderation."""
        try:
            TaskProof = _safe_import("api.tasks.models", "TaskProof")
            if TaskProof:
                qs = TaskProof.objects.filter(moderation_status="pending")
                if submission_type:
                    qs = qs.filter(task_type=submission_type)
                return [
                    {
                        "task_id":   str(p.pk),
                        "task_type": getattr(p, "task_type", ""),
                        "user_id":   str(getattr(p, "user_id", "")),
                        "file_urls": getattr(p, "file_urls", []),
                    }
                    for p in qs[:limit]
                ]
        except Exception as exc:
            logger.warning("TaskAdapter.get_pending_task_proofs failed: %s", exc)
        return []


# =============================================================================
# FraudAdapter
# =============================================================================
class FraudAdapter:
    """
    Talks to api.fraud_detection.
    Used by: ModerationService (enrich submissions with fraud signals),
             BotService (flag suspicious bursts)
    """

    @staticmethod
    def get_fraud_signals(user_id: str | int, ip: str = "") -> dict:
        """
        Returns {risk_score, signals: [], is_flagged, vpn_detected, proxy_detected}.
        """
        try:
            get_signals = _safe_import("api.fraud_detection.services", "get_fraud_signals")
            if get_signals:
                return get_signals(user_id=user_id, ip=ip)
        except Exception as exc:
            logger.warning("FraudAdapter.get_fraud_signals failed: %s", exc)
        # Also check our own internal fraud_detection module
        try:
            from .fraud_detection import FraudRiskAggregator
            return FraudRiskAggregator.assess(user_id=user_id, ip=ip)
        except Exception:
            pass
        return {"risk_score": 0.0, "signals": [], "is_flagged": False,
                "vpn_detected": False, "proxy_detected": False}

    @staticmethod
    def report_fraud_event(user_id: str | int, event_type: str, metadata: dict) -> bool:
        """Report a confirmed fraud event back to api.fraud_detection."""
        try:
            report_fn = _safe_import("api.fraud_detection.services", "report_fraud_event")
            if report_fn:
                report_fn(user_id=user_id, event_type=event_type,
                          source="auto_mod", metadata=metadata)
                return True
        except Exception as exc:
            logger.warning("FraudAdapter.report_fraud_event failed: %s", exc)
        return False


# =============================================================================
# NotificationAdapter
# =============================================================================
class NotificationAdapter:
    """
    Talks to api.notifications.
    Used by: AppealService, ModerationQueueService, BotService
    """

    @staticmethod
    def notify_user(user_id: str | int, notification_type: str,
                    context: dict | None = None) -> bool:
        """Send an in-app or push notification to a user."""
        try:
            send_fn = _safe_import("api.notifications.services", "send_notification")
            if send_fn:
                send_fn(user_id=user_id, notification_type=notification_type,
                        context=context or {}, source="auto_mod")
                return True
        except Exception as exc:
            logger.warning("NotificationAdapter.notify_user failed: %s", exc)
        return False

    @staticmethod
    def notify_moderator(moderator_id: str | int, event: str, context: dict) -> bool:
        """Alert a moderator of a queue assignment or escalation."""
        try:
            send_fn = _safe_import("api.notifications.services", "send_staff_notification")
            if send_fn:
                send_fn(user_id=moderator_id, event=event,
                        context=context, source="auto_mod")
                return True
        except Exception as exc:
            logger.warning("NotificationAdapter.notify_moderator failed: %s", exc)
        return False

    @staticmethod
    def notify_submission_decision(submission, decision: str) -> bool:
        """Notify the submitter of an approve/reject decision."""
        user_id = getattr(submission, "user_id", None) or getattr(
            getattr(submission, "user", None), "pk", None
        )
        if not user_id:
            return False
        return NotificationAdapter.notify_user(
            user_id=user_id,
            notification_type=f"moderation.{decision}",
            context={
                "submission_id": str(submission.pk),
                "content_id":    submission.content_id,
                "decision":      decision,
            },
        )


# =============================================================================
# AnalyticsAdapter
# =============================================================================
class AnalyticsAdapter:
    """
    Talks to api.analytics.
    Used by: ModerationService, AppealService (track moderation events)
    """

    @staticmethod
    def track_event(event_name: str, properties: dict,
                    user_id: str | int | None = None) -> bool:
        try:
            track_fn = _safe_import("api.analytics.services", "track_event")
            if track_fn:
                track_fn(event=event_name, properties=properties,
                         user_id=user_id, source="auto_mod")
                return True
        except Exception as exc:
            logger.warning("AnalyticsAdapter.track_event failed: %s", exc)
        return False

    @staticmethod
    def track_moderation_decision(submission, decision: str, confidence: float) -> bool:
        return AnalyticsAdapter.track_event(
            "auto_mod.decision",
            {
                "submission_id":   str(submission.pk),
                "submission_type": submission.submission_type,
                "decision":        decision,
                "confidence":      confidence,
                "is_automated":    True,
            },
            user_id=getattr(getattr(submission, "user", None), "pk", None),
        )

    @staticmethod
    def track_appeal_outcome(appeal, outcome: str) -> bool:
        return AnalyticsAdapter.track_event(
            "auto_mod.appeal_outcome",
            {"appeal_id": str(appeal.pk), "outcome": outcome},
            user_id=getattr(getattr(appeal, "user", None), "pk", None),
        )


# =============================================================================
# WalletAdapter
# =============================================================================
class WalletAdapter:
    """
    Talks to api.wallet.
    Used by: ModerationService (reward approved submissions, penalise fraud)
    """

    @staticmethod
    def credit_reward(user_id: str | int, amount: float,
                      reason: str, reference_id: str = "") -> bool:
        try:
            credit_fn = _safe_import("api.wallet.services", "credit_wallet")
            if credit_fn:
                credit_fn(user_id=user_id, amount=amount,
                          reason=reason, reference_id=reference_id,
                          source="auto_mod")
                return True
        except Exception as exc:
            logger.warning("WalletAdapter.credit_reward failed: %s", exc)
        return False

    @staticmethod
    def deduct_penalty(user_id: str | int, amount: float,
                       reason: str, reference_id: str = "") -> bool:
        try:
            deduct_fn = _safe_import("api.wallet.services", "deduct_wallet")
            if deduct_fn:
                deduct_fn(user_id=user_id, amount=amount,
                          reason=reason, reference_id=reference_id,
                          source="auto_mod")
                return True
        except Exception as exc:
            logger.warning("WalletAdapter.deduct_penalty failed: %s", exc)
        return False


# =============================================================================
# AuditLogAdapter
# =============================================================================
class AuditLogAdapter:
    """
    Talks to api.audit_logs.
    Used by: Every service (all decisions must be audited)
    """

    @staticmethod
    def log(action: str, actor_id: str | int | None, target_id: str,
            target_type: str, changes: dict | None = None,
            ip: str = "", metadata: dict | None = None) -> bool:
        try:
            log_fn = _safe_import("api.audit_logs.services", "create_audit_log")
            if log_fn:
                log_fn(
                    action=action, actor_id=actor_id,
                    target_id=target_id, target_type=target_type,
                    changes=changes or {}, ip=ip,
                    metadata=metadata or {}, source="auto_mod",
                )
                return True
        except Exception as exc:
            logger.warning("AuditLogAdapter.log failed: %s", exc)
        # Fallback: use our own compliance ModerationLog
        try:
            from .models import ModerationLog
            from django.utils import timezone
            ModerationLog.objects.create(
                action=action[:50],
                content_type=target_type[:50],
                content_id=target_id[:200],
                reason=str(changes or ""),
                created_at=timezone.now(),
            )
            return True
        except Exception:
            pass
        return False


# =============================================================================
# TenantAdapter
# =============================================================================
class TenantAdapter:
    """
    Talks to api.tenants.
    Used by: All services (multi-tenant context resolution)
    """

    @staticmethod
    def get_current_tenant():
        """Get the current tenant from request context."""
        try:
            get_fn = _safe_import("api.tenants.middleware", "get_current_tenant")
            if get_fn:
                return get_fn()
        except Exception as exc:
            logger.debug("TenantAdapter.get_current_tenant failed: %s", exc)
        return None

    @staticmethod
    def get_tenant_moderation_config(tenant_id: str) -> dict:
        """
        Get tenant-specific moderation settings.
        Returns {auto_approve_threshold, require_human_review,
                 allowed_submission_types, max_appeals_per_user}.
        """
        try:
            Tenant = _safe_import("api.tenants.models", "Tenant")
            if Tenant:
                tenant = Tenant.objects.filter(pk=tenant_id).first()
                if tenant:
                    config = getattr(tenant, "moderation_config", {}) or {}
                    return {
                        "auto_approve_threshold":  config.get("auto_approve_threshold", 0.85),
                        "require_human_review":    config.get("require_human_review", False),
                        "allowed_submission_types": config.get("allowed_submission_types", []),
                        "max_appeals_per_user":    config.get("max_appeals_per_user", 3),
                    }
        except Exception as exc:
            logger.warning("TenantAdapter.get_tenant_moderation_config failed: %s", exc)
        return {
            "auto_approve_threshold":  0.85,
            "require_human_review":    False,
            "allowed_submission_types": [],
            "max_appeals_per_user":    3,
        }


# =============================================================================
# RateLimitAdapter
# =============================================================================
class RateLimitAdapter:
    """
    Talks to api.rate_limit.
    Used by: middleware (block burst submissions)
    """

    @staticmethod
    def check_submission_limit(user_id: str | int,
                               submission_type: str = "default") -> dict:
        """
        Returns {allowed: bool, remaining: int, retry_after: int|None}.
        Falls back to internal SubmissionRateLimiter.
        """
        try:
            check_fn = _safe_import("api.rate_limit.services", "check_rate_limit")
            if check_fn:
                return check_fn(user_id=user_id, scope=f"auto_mod:{submission_type}")
        except Exception as exc:
            logger.warning("RateLimitAdapter.check_submission_limit failed: %s", exc)
        # Fallback: internal rate limiter
        try:
            from .fraud_detection import SubmissionRateLimiter
            return SubmissionRateLimiter.check_and_record(
                user_id=user_id, submission_type=submission_type
            )
        except Exception:
            return {"allowed": True, "remaining": 50, "retry_after": None}


# =============================================================================
# WebhookAdapter
# =============================================================================
class WebhookAdapter:
    """
    Talks to api.webhooks.
    Used by: ModerationService (notify advertisers/publishers of decisions)
    """

    @staticmethod
    def send_moderation_event(event_type: str, payload: dict) -> bool:
        try:
            dispatch_fn = _safe_import("api.webhooks.services", "dispatch_webhook")
            if dispatch_fn:
                dispatch_fn(event_type=f"auto_mod.{event_type}",
                            payload=payload, source="auto_mod")
                return True
        except Exception as exc:
            logger.warning("WebhookAdapter.send_moderation_event failed: %s", exc)
        # Fallback: internal webhook dispatcher
        try:
            from .webhooks import dispatcher
            dispatcher.dispatch(f"auto_mod.{event_type}", payload)
            return True
        except Exception:
            return False

    @staticmethod
    def notify_submission_approved(submission) -> bool:
        return WebhookAdapter.send_moderation_event("submission.approved", {
            "submission_id":   str(submission.pk),
            "content_id":      submission.content_id,
            "submission_type": submission.submission_type,
        })

    @staticmethod
    def notify_submission_rejected(submission, reason: str = "") -> bool:
        return WebhookAdapter.send_moderation_event("submission.rejected", {
            "submission_id":   str(submission.pk),
            "content_id":      submission.content_id,
            "submission_type": submission.submission_type,
            "reason":          reason,
        })


# =============================================================================
# KYCAdapter
# =============================================================================
class KYCAdapter:
    """
    Talks to api.kyc.
    Used by: AppealService (high-value appeals require KYC verification)
    """

    @staticmethod
    def get_kyc_status(user_id: str | int) -> dict:
        """Returns {verified: bool, level: str, documents_submitted: bool}."""
        try:
            get_fn = _safe_import("api.kyc.services", "get_kyc_status")
            if get_fn:
                return get_fn(user_id=user_id)
        except Exception as exc:
            logger.warning("KYCAdapter.get_kyc_status failed: %s", exc)
        return {"verified": False, "level": "none", "documents_submitted": False}

    @staticmethod
    def require_kyc_for_appeal(appeal) -> bool:
        """Return True if this appeal requires KYC verification."""
        user_id = getattr(getattr(appeal, "user", None), "pk", None)
        if not user_id:
            return False
        kyc = KYCAdapter.get_kyc_status(user_id)
        return not kyc.get("verified", False)


# =============================================================================
# SecurityAdapter
# =============================================================================
class SecurityAdapter:
    """
    Talks to api.security.
    Used by: middleware (block threats before they reach moderation pipeline)
    """

    @staticmethod
    def check_ip_threat(ip: str) -> dict:
        """Returns {is_threat: bool, threat_type: str, risk_score: float}."""
        try:
            check_fn = _safe_import("api.security.services", "check_ip_threat")
            if check_fn:
                return check_fn(ip=ip)
        except Exception as exc:
            logger.warning("SecurityAdapter.check_ip_threat failed: %s", exc)
        # Fallback: internal IP reputation
        try:
            from .fraud_detection import IPReputationService
            result = IPReputationService.score_ip(ip)
            return {
                "is_threat":   result["risk_score"] >= 0.7,
                "threat_type": "proxy" if result["is_proxy"] else
                               "tor"   if result["is_tor"]   else "none",
                "risk_score":  result["risk_score"],
            }
        except Exception:
            return {"is_threat": False, "threat_type": "none", "risk_score": 0.0}

    @staticmethod
    def log_security_event(event_type: str, ip: str,
                           user_id: str | int | None, metadata: dict) -> bool:
        try:
            log_fn = _safe_import("api.security.services", "log_security_event")
            if log_fn:
                log_fn(event_type=event_type, ip=ip, user_id=user_id,
                       metadata=metadata, source="auto_mod")
                return True
        except Exception as exc:
            logger.warning("SecurityAdapter.log_security_event failed: %s", exc)
        return False


# =============================================================================
# AIEngineAdapter
# =============================================================================
class AIEngineAdapter:
    """
    Talks to api.ai_engine.
    Used by: ScannerService (offload heavy inference to centralised AI engine)
    """

    @staticmethod
    def classify_image(image_url: str,
                       model_type: str = "image") -> dict:
        """Returns {confidence, labels, is_flagged, model_version}."""
        try:
            classify_fn = _safe_import("api.ai_engine.services", "classify_image")
            if classify_fn:
                return classify_fn(image_url=image_url, model_type=model_type)
        except Exception as exc:
            logger.warning("AIEngineAdapter.classify_image failed: %s", exc)
        return {"confidence": 0.0, "labels": [], "is_flagged": False, "model_version": "fallback"}

    @staticmethod
    def classify_text(text: str, model_type: str = "text") -> dict:
        """Returns {confidence, labels, is_flagged, model_version}."""
        try:
            classify_fn = _safe_import("api.ai_engine.services", "classify_text")
            if classify_fn:
                return classify_fn(text=text, model_type=model_type)
        except Exception as exc:
            logger.warning("AIEngineAdapter.classify_text failed: %s", exc)
        return {"confidence": 0.0, "labels": [], "is_flagged": False, "model_version": "fallback"}

    @staticmethod
    def run_ocr(image_url: str) -> dict:
        """Returns {extracted_text, confidence, language}."""
        try:
            ocr_fn = _safe_import("api.ai_engine.services", "run_ocr")
            if ocr_fn:
                return ocr_fn(image_url=image_url)
        except Exception as exc:
            logger.warning("AIEngineAdapter.run_ocr failed: %s", exc)
        return {"extracted_text": "", "confidence": 0.0, "language": "unknown"}


# =============================================================================
# PostbackAdapter
# =============================================================================
class PostbackAdapter:
    """
    Talks to api.postback / api.postback_engine.
    Used by: ModerationService (fire postback on approved task proof)
    """

    @staticmethod
    def fire_postback(submission, decision: str) -> bool:
        """Fire advertiser postback on final moderation decision."""
        if decision not in ("approved", "auto_approved", "human_approved"):
            return False
        try:
            fire_fn = _safe_import("api.postback_engine.services", "fire_postback") or \
                      _safe_import("api.postback.services", "fire_postback")
            if fire_fn:
                fire_fn(
                    content_id=submission.content_id,
                    submission_type=submission.submission_type,
                    source="auto_mod",
                )
                return True
        except Exception as exc:
            logger.warning("PostbackAdapter.fire_postback failed: %s", exc)
        return False


# =============================================================================
# GamificationAdapter
# =============================================================================
class GamificationAdapter:
    """
    Talks to api.gamification.
    Used by: ModerationService (award points for approved submissions)
    """

    @staticmethod
    def award_points(user_id: str | int, points: int,
                     action: str, reference_id: str = "") -> bool:
        try:
            award_fn = _safe_import("api.gamification.services", "award_points")
            if award_fn:
                award_fn(user_id=user_id, points=points,
                         action=action, reference_id=reference_id,
                         source="auto_mod")
                return True
        except Exception as exc:
            logger.warning("GamificationAdapter.award_points failed: %s", exc)
        return False

    @staticmethod
    def on_submission_approved(submission) -> bool:
        user_id = getattr(getattr(submission, "user", None), "pk", None)
        if not user_id:
            return False
        return GamificationAdapter.award_points(
            user_id=user_id, points=10,
            action="task_proof_approved",
            reference_id=str(submission.pk),
        )


# =============================================================================
# ProxyIntelligenceAdapter
# =============================================================================
class ProxyIntelligenceAdapter:
    """
    Talks to api.proxy_intelligence.
    Used by: FraudAdapter, SecurityAdapter (enrich IP risk scoring)
    """

    @staticmethod
    def check_ip(ip: str) -> dict:
        """Returns {is_proxy, is_vpn, is_tor, country, risk_score}."""
        try:
            check_fn = _safe_import("api.proxy_intelligence.services", "check_ip")
            if check_fn:
                return check_fn(ip=ip)
        except Exception as exc:
            logger.warning("ProxyIntelligenceAdapter.check_ip failed: %s", exc)
        # Fallback to internal
        try:
            from .fraud_detection import IPReputationService
            r = IPReputationService.score_ip(ip)
            return {"is_proxy": r["is_proxy"], "is_vpn": r["is_vpn"],
                    "is_tor": r["is_tor"], "country": r["country"],
                    "risk_score": r["risk_score"]}
        except Exception:
            return {"is_proxy": False, "is_vpn": False, "is_tor": False,
                    "country": None, "risk_score": 0.0}


# =============================================================================
# CacheAdapter
# =============================================================================
class CacheAdapter:
    """
    Talks to api.cache (shared cache layer).
    Used by: All services that need distributed caching.
    Falls back to Django's default cache if api.cache unavailable.
    """

    @staticmethod
    def get(key: str, default=None):
        try:
            cache_get = _safe_import("api.cache.services", "cache_get")
            if cache_get:
                return cache_get(f"auto_mod:{key}", default)
        except Exception:
            pass
        from django.core.cache import cache
        return cache.get(f"auto_mod:{key}", default)

    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> bool:
        try:
            cache_set = _safe_import("api.cache.services", "cache_set")
            if cache_set:
                return cache_set(f"auto_mod:{key}", value, timeout)
        except Exception:
            pass
        from django.core.cache import cache
        cache.set(f"auto_mod:{key}", value, timeout)
        return True

    @staticmethod
    def delete(key: str) -> bool:
        from django.core.cache import cache
        cache.delete(f"auto_mod:{key}")
        return True


# =============================================================================
# SubscriptionAdapter
# =============================================================================
class SubscriptionAdapter:
    """
    Talks to api.subscription.
    Used by: ViewSets (feature-gate advanced moderation features by plan)
    """

    @staticmethod
    def has_feature(tenant_id: str, feature: str) -> bool:
        """Check if a tenant's subscription includes a specific feature."""
        try:
            check_fn = _safe_import("api.subscription.services", "has_feature")
            if check_fn:
                return check_fn(tenant_id=tenant_id, feature=feature)
        except Exception as exc:
            logger.warning("SubscriptionAdapter.has_feature failed: %s", exc)
        return True  # default: allow all if subscription service unavailable

    FEATURE_ML_MODELS     = "auto_mod.ml_models"
    FEATURE_APPEALS       = "auto_mod.appeals"
    FEATURE_BULK_MODERATE = "auto_mod.bulk_moderate"
    FEATURE_COMPLIANCE    = "auto_mod.compliance"


# =============================================================================
# Registry — single import point for all adapters
# =============================================================================

# =============================================================================
# ADDITIONAL ADAPTERS — 28 more systems
# =============================================================================

class AdminPanelAdapter:
    """api.admin_panel — push stats, create alerts, log admin actions."""
    @staticmethod
    def push_moderation_stats(stats: dict) -> bool:
        try:
            fn = _safe_import("api.admin_panel.services", "push_stats")
            if fn: fn(module="auto_mod", stats=stats); return True
        except Exception as e: logger.warning("AdminPanelAdapter: %s", e)
        return False

    @staticmethod
    def create_admin_alert(title: str, message: str, severity: str = "info") -> bool:
        try:
            fn = _safe_import("api.admin_panel.services", "create_alert")
            if fn: fn(source="auto_mod", title=title, message=message, severity=severity); return True
        except Exception as e: logger.warning("AdminPanelAdapter: %s", e)
        return False

    @staticmethod
    def log_admin_action(admin_user_id: str, action: str, target: str, metadata: dict) -> bool:
        try:
            fn = _safe_import("api.admin_panel.services", "log_admin_action")
            if fn: fn(user_id=admin_user_id, action=action, target=target, metadata=metadata, source="auto_mod"); return True
        except Exception as e: logger.warning("AdminPanelAdapter: %s", e)
        return False


class PaymentGatewayAdapter:
    """api.payment_gateways — verify transactions, hold/release/cancel payouts."""
    @staticmethod
    def verify_transaction(transaction_id: str) -> dict:
        try:
            fn = _safe_import("api.payment_gateways.services", "verify_transaction")
            if fn: return fn(transaction_id=transaction_id)
        except Exception as e: logger.warning("PaymentGatewayAdapter: %s", e)
        return {"verified": False, "status": "unknown"}

    @staticmethod
    def hold_payout(user_id: str, amount: float, reason: str) -> dict:
        try:
            fn = _safe_import("api.payment_gateways.services", "hold_payout")
            if fn: return fn(user_id=user_id, amount=amount, reason=reason, source="auto_mod")
        except Exception as e: logger.warning("PaymentGatewayAdapter: %s", e)
        return {"held": False}

    @staticmethod
    def release_payout(user_id: str, hold_id: str) -> bool:
        try:
            fn = _safe_import("api.payment_gateways.services", "release_payout")
            if fn: fn(hold_id=hold_id, released_by="auto_mod"); return True
        except Exception as e: logger.warning("PaymentGatewayAdapter: %s", e)
        return False

    @staticmethod
    def cancel_payout(user_id: str, hold_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.payment_gateways.services", "cancel_payout")
            if fn: fn(hold_id=hold_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("PaymentGatewayAdapter: %s", e)
        return False


class AdNetworkAdapter:
    """api.ad_networks — traffic quality, fraud signals."""
    @staticmethod
    def get_traffic_quality(network_id: str, publisher_id: str) -> dict:
        try:
            fn = _safe_import("api.ad_networks.services", "get_traffic_quality")
            if fn: return fn(network_id=network_id, publisher_id=publisher_id)
        except Exception as e: logger.warning("AdNetworkAdapter: %s", e)
        return {"quality_score": 0.7, "fraud_rate": 0.0}

    @staticmethod
    def report_invalid_traffic(network_id: str, publisher_id: str, details: dict) -> bool:
        try:
            fn = _safe_import("api.ad_networks.services", "report_invalid_traffic")
            if fn: fn(network_id=network_id, publisher_id=publisher_id, details=details, source="auto_mod"); return True
        except Exception as e: logger.warning("AdNetworkAdapter: %s", e)
        return False

    @staticmethod
    def get_network_fraud_signals(network_id: str) -> list:
        try:
            fn = _safe_import("api.ad_networks.services", "get_fraud_signals")
            if fn: return fn(network_id=network_id)
        except Exception as e: logger.warning("AdNetworkAdapter: %s", e)
        return []


class OfferwallAdapter:
    """api.offerwall — offer lookup, completion, rejection, config."""
    @staticmethod
    def get_offer(offer_id: str) -> dict | None:
        try:
            M = _safe_import("api.offerwall.models", "Offer")
            if M:
                o = M.objects.filter(pk=offer_id).first()
                if o: return {"offer_id": str(o.pk), "name": getattr(o,"name",""),
                              "payout": getattr(o,"payout",0.0), "is_active": getattr(o,"is_active",True),
                              "allowed_countries": getattr(o,"allowed_countries",[])}
        except Exception as e: logger.warning("OfferwallAdapter: %s", e)
        return None

    @staticmethod
    def mark_offer_completed(offer_id: str, user_id: str, submission_id: str) -> bool:
        try:
            fn = _safe_import("api.offerwall.services", "mark_completed")
            if fn: fn(offer_id=offer_id, user_id=user_id, submission_id=submission_id, source="auto_mod"); return True
        except Exception as e: logger.warning("OfferwallAdapter: %s", e)
        return False

    @staticmethod
    def reject_offer_completion(offer_id: str, user_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.offerwall.services", "reject_completion")
            if fn: fn(offer_id=offer_id, user_id=user_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("OfferwallAdapter: %s", e)
        return False

    @staticmethod
    def get_offer_moderation_config(offer_id: str) -> dict:
        try:
            fn = _safe_import("api.offerwall.services", "get_moderation_config")
            if fn: return fn(offer_id=offer_id)
        except Exception as e: logger.warning("OfferwallAdapter: %s", e)
        return {"auto_approve_threshold": 0.85, "require_screenshot": True}


class ReferralAdapter:
    """api.referral — referral info, fraud detection, self-referral check."""
    @staticmethod
    def get_referral_info(user_id: str) -> dict:
        try:
            fn = _safe_import("api.referral.services", "get_referral_info")
            if fn: return fn(user_id=user_id)
        except Exception as e: logger.warning("ReferralAdapter: %s", e)
        return {"referred_by": None, "referral_chain_depth": 0, "is_self_referral": False}

    @staticmethod
    def flag_referral_fraud(user_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.referral.services", "flag_fraud")
            if fn: fn(user_id=user_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("ReferralAdapter: %s", e)
        return False

    @staticmethod
    def is_self_referral(referrer_id: str, referee_id: str) -> bool:
        try:
            fn = _safe_import("api.referral.services", "is_self_referral")
            if fn: return fn(referrer_id=referrer_id, referee_id=referee_id)
        except Exception as e: logger.warning("ReferralAdapter: %s", e)
        return False


class EngagementAdapter:
    """api.engagement — engagement score, genuine-user check, event recording."""
    @staticmethod
    def get_engagement_score(user_id: str) -> dict:
        try:
            fn = _safe_import("api.engagement.services", "get_engagement_score")
            if fn: return fn(user_id=user_id)
        except Exception as e: logger.warning("EngagementAdapter: %s", e)
        return {"score": 50.0, "tier": "normal", "session_count": 0}

    @staticmethod
    def is_genuine_user(user_id: str) -> bool:
        try:
            fn = _safe_import("api.engagement.services", "is_genuine_user")
            if fn: return fn(user_id=user_id)
        except Exception as e: logger.warning("EngagementAdapter: %s", e)
        return True

    @staticmethod
    def record_moderation_interaction(user_id: str, event: str) -> bool:
        try:
            fn = _safe_import("api.engagement.services", "record_event")
            if fn: fn(user_id=user_id, event=f"auto_mod.{event}"); return True
        except Exception as e: logger.warning("EngagementAdapter: %s", e)
        return False


class CMSAdapter:
    """api.cms — moderation policy, rejection text, appeal instructions."""
    @staticmethod
    def get_moderation_policy(policy_slug: str, locale: str = "en") -> dict | None:
        try:
            fn = _safe_import("api.cms.services", "get_content")
            if fn: return fn(slug=policy_slug, locale=locale)
        except Exception as e: logger.warning("CMSAdapter: %s", e)
        return None

    @staticmethod
    def get_rejection_reason_text(reason_code: str, locale: str = "en") -> str:
        try:
            fn = _safe_import("api.cms.services", "get_rejection_reason")
            if fn: return fn(code=reason_code, locale=locale)
        except Exception as e: logger.warning("CMSAdapter: %s", e)
        return reason_code

    @staticmethod
    def get_appeal_instructions(locale: str = "en") -> str:
        try:
            fn = _safe_import("api.cms.services", "get_content")
            if fn:
                c = fn(slug="appeal_instructions", locale=locale)
                return (c or {}).get("body", "")
        except Exception as e: logger.warning("CMSAdapter: %s", e)
        return ""


class SupportAdapter:
    """api.support — create/escalate/close support tickets."""
    @staticmethod
    def create_ticket(user_id: str, subject: str, body: str,
                      priority: str = "normal", reference_id: str = "") -> dict:
        try:
            fn = _safe_import("api.support.services", "create_ticket")
            if fn: return fn(user_id=user_id, subject=subject, body=body,
                             priority=priority, reference_id=reference_id, source="auto_mod")
        except Exception as e: logger.warning("SupportAdapter: %s", e)
        return {"ticket_id": None, "created": False}

    @staticmethod
    def escalate_ticket(ticket_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.support.services", "escalate_ticket")
            if fn: fn(ticket_id=ticket_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("SupportAdapter: %s", e)
        return False

    @staticmethod
    def close_ticket(ticket_id: str, resolution: str) -> bool:
        try:
            fn = _safe_import("api.support.services", "close_ticket")
            if fn: fn(ticket_id=ticket_id, resolution=resolution, source="auto_mod"); return True
        except Exception as e: logger.warning("SupportAdapter: %s", e)
        return False


class AlertsAdapter:
    """api.alerts — Slack/email/PagerDuty alerts for SLA breaches, fraud spikes, bot failures."""
    @staticmethod
    def send_alert(title: str, message: str, severity: str = "warning",
                   channel: str = "slack", metadata: dict | None = None) -> bool:
        try:
            fn = _safe_import("api.alerts.services", "send_alert")
            if fn: fn(title=title, message=message, severity=severity,
                      channel=channel, source="auto_mod", metadata=metadata or {}); return True
        except Exception as e: logger.warning("AlertsAdapter: %s", e)
        return False

    @staticmethod
    def alert_sla_breach(entity_type: str, entity_id: str, minutes_overdue: float) -> bool:
        return AlertsAdapter.send_alert(
            f"SLA Breach: {entity_type}",
            f"{entity_type} {entity_id} is {minutes_overdue:.0f}min overdue",
            severity="critical",
            metadata={"entity_type": entity_type, "entity_id": entity_id}
        )

    @staticmethod
    def alert_fraud_spike(publisher_id: str, fraud_rate: float) -> bool:
        return AlertsAdapter.send_alert(
            "Fraud Spike Detected",
            f"Publisher {publisher_id} fraud rate: {fraud_rate:.1%}",
            severity="critical",
            metadata={"publisher_id": publisher_id, "fraud_rate": fraud_rate}
        )

    @staticmethod
    def alert_bot_failure(bot_id: str, bot_name: str, error: str) -> bool:
        return AlertsAdapter.send_alert(
            f"Bot Failed: {bot_name}", error[:500], severity="error",
            metadata={"bot_id": bot_id}
        )


class DjoyaltyAdapter:
    """api.djoyalty — loyalty points award/deduct, tier lookup."""
    @staticmethod
    def award_points(user_id: str, points: int, action: str, reference_id: str = "") -> bool:
        try:
            fn = _safe_import("api.djoyalty.services", "award_points")
            if fn: fn(user_id=user_id, points=points, action=action, reference_id=reference_id, source="auto_mod"); return True
        except Exception as e: logger.warning("DjoyaltyAdapter: %s", e)
        return False

    @staticmethod
    def deduct_points(user_id: str, points: int, reason: str) -> bool:
        try:
            fn = _safe_import("api.djoyalty.services", "deduct_points")
            if fn: fn(user_id=user_id, points=points, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("DjoyaltyAdapter: %s", e)
        return False

    @staticmethod
    def get_loyalty_tier(user_id: str) -> str:
        try:
            fn = _safe_import("api.djoyalty.services", "get_tier")
            if fn: return fn(user_id=user_id)
        except Exception as e: logger.warning("DjoyaltyAdapter: %s", e)
        return "standard"


class LocalizationAdapter:
    """api.localization — translate keys, get user locale, format messages."""
    @staticmethod
    def translate(key: str, locale: str = "en", context: dict | None = None) -> str:
        try:
            fn = _safe_import("api.localization.services", "translate")
            if fn: return fn(key=key, locale=locale, context=context or {})
        except Exception as e: logger.warning("LocalizationAdapter: %s", e)
        return key

    @staticmethod
    def get_user_locale(user_id: str) -> str:
        try:
            fn = _safe_import("api.localization.services", "get_user_locale")
            if fn: return fn(user_id=user_id)
        except Exception as e: logger.warning("LocalizationAdapter: %s", e)
        return "en"

    @staticmethod
    def format_moderation_message(message_key: str, user_id: str, context: dict | None = None) -> str:
        locale = LocalizationAdapter.get_user_locale(user_id)
        return LocalizationAdapter.translate(message_key, locale=locale, context=context)


class BackupAdapter:
    """api.backup — archive records, backup ML model files."""
    @staticmethod
    def archive_moderation_records(older_than_days: int = 365) -> dict:
        try:
            fn = _safe_import("api.backup.services", "archive_records")
            if fn: return fn(module="auto_mod", older_than_days=older_than_days)
        except Exception as e: logger.warning("BackupAdapter: %s", e)
        return {"archived": 0}

    @staticmethod
    def backup_model_version(model_version_id: str, file_path: str) -> dict:
        try:
            fn = _safe_import("api.backup.services", "backup_file")
            if fn: return fn(reference_id=model_version_id, file_path=file_path, source="auto_mod.ml_model")
        except Exception as e: logger.warning("BackupAdapter: %s", e)
        return {"backed_up": False, "backup_path": None}

    @staticmethod
    def get_backup_status(reference_id: str) -> dict:
        try:
            fn = _safe_import("api.backup.services", "get_backup_status")
            if fn: return fn(reference_id=reference_id)
        except Exception as e: logger.warning("BackupAdapter: %s", e)
        return {"exists": False, "last_backup_at": None}


class PromotionsAdapter:
    """api.promotions — active promotions, bonus multipliers, promo conversions."""
    @staticmethod
    def get_active_promotions(user_id: str, submission_type: str = "") -> list:
        try:
            fn = _safe_import("api.promotions.services", "get_active_promotions")
            if fn: return fn(user_id=user_id, context={"submission_type": submission_type})
        except Exception as e: logger.warning("PromotionsAdapter: %s", e)
        return []

    @staticmethod
    def apply_bonus_multiplier(user_id: str, base_reward: float, submission_type: str) -> float:
        promos = PromotionsAdapter.get_active_promotions(user_id, submission_type=submission_type)
        multiplier = max((p.get("reward_multiplier", 1.0) for p in promos), default=1.0)
        return round(base_reward * multiplier, 4)

    @staticmethod
    def record_promo_conversion(user_id: str, promo_id: str, submission_id: str) -> bool:
        try:
            fn = _safe_import("api.promotions.services", "record_conversion")
            if fn: fn(promo_id=promo_id, user_id=user_id, reference_id=submission_id, source="auto_mod"); return True
        except Exception as e: logger.warning("PromotionsAdapter: %s", e)
        return False


class VersionControlAdapter:
    """api.version_control — feature flags, versioned config."""
    @staticmethod
    def get_feature_flag(flag_name: str, default: bool = False) -> bool:
        try:
            fn = _safe_import("api.version_control.services", "get_flag")
            if fn: return fn(f"auto_mod.{flag_name}", default=default)
        except Exception as e: logger.warning("VersionControlAdapter: %s", e)
        return default

    @staticmethod
    def get_config_version(config_key: str) -> dict:
        try:
            fn = _safe_import("api.version_control.services", "get_config")
            if fn: return fn(key=f"auto_mod.{config_key}")
        except Exception as e: logger.warning("VersionControlAdapter: %s", e)
        return {"version": "1.0", "config": {}}

    @staticmethod
    def is_feature_enabled(feature: str) -> bool:
        return VersionControlAdapter.get_feature_flag(feature, default=True)


class BehaviorAnalyticsAdapter:
    """api.behavior_analytics — behavior profiles, submission velocity, event recording."""
    @staticmethod
    def get_behavior_profile(user_id: str) -> dict:
        try:
            fn = _safe_import("api.behavior_analytics.services", "get_behavior_profile")
            if fn: return fn(user_id=user_id)
        except Exception as e: logger.warning("BehaviorAnalyticsAdapter: %s", e)
        return {"risk_score": 0.0, "is_bot": False, "anomaly_signals": []}

    @staticmethod
    def record_submission_event(user_id: str, event_type: str, metadata: dict) -> bool:
        try:
            fn = _safe_import("api.behavior_analytics.services", "record_event")
            if fn: fn(user_id=user_id, event_type=f"auto_mod.{event_type}", metadata=metadata); return True
        except Exception as e: logger.warning("BehaviorAnalyticsAdapter: %s", e)
        return False

    @staticmethod
    def get_submission_velocity(user_id: str, window_hours: int = 24) -> dict:
        try:
            fn = _safe_import("api.behavior_analytics.services", "get_submission_velocity")
            if fn: return fn(user_id=user_id, window_hours=window_hours)
        except Exception as e: logger.warning("BehaviorAnalyticsAdapter: %s", e)
        return {"count": 0, "per_hour": 0.0, "is_burst": False}


class InventoryAdapter:
    """api.inventory — offer availability, capacity, cap management."""
    @staticmethod
    def is_offer_active(offer_id: str) -> bool:
        try:
            fn = _safe_import("api.inventory.services", "is_offer_active")
            if fn: return fn(offer_id=offer_id)
        except Exception as e: logger.warning("InventoryAdapter: %s", e)
        return True

    @staticmethod
    def get_offer_capacity(offer_id: str) -> dict:
        try:
            fn = _safe_import("api.inventory.services", "get_offer_capacity")
            if fn: return fn(offer_id=offer_id)
        except Exception as e: logger.warning("InventoryAdapter: %s", e)
        return {"daily_remaining": 9999, "total_remaining": 9999, "is_capped": False}

    @staticmethod
    def decrement_offer_cap(offer_id: str, count: int = 1) -> bool:
        try:
            fn = _safe_import("api.inventory.services", "decrement_cap")
            if fn: fn(offer_id=offer_id, count=count, source="auto_mod"); return True
        except Exception as e: logger.warning("InventoryAdapter: %s", e)
        return False


class MessagingAdapter:
    """api.messaging — in-app messages for appeal updates, rejection notices."""
    @staticmethod
    def send_message(to_user_id: str, subject: str, body: str,
                     from_system: str = "auto_mod", metadata: dict | None = None) -> bool:
        try:
            fn = _safe_import("api.messaging.services", "send_message")
            if fn: fn(to_user_id=to_user_id, subject=subject, body=body,
                      from_system=from_system, metadata=metadata or {}); return True
        except Exception as e: logger.warning("MessagingAdapter: %s", e)
        return False

    @staticmethod
    def send_appeal_update(appeal, message: str) -> bool:
        uid = getattr(getattr(appeal, "user", None), "pk", None)
        if not uid: return False
        return MessagingAdapter.send_message(str(uid), "Appeal Status Update", message,
                                             metadata={"appeal_id": str(appeal.pk)})

    @staticmethod
    def send_rejection_message(submission, reason: str, locale: str = "en") -> bool:
        uid = getattr(getattr(submission, "user", None), "pk", None)
        if not uid: return False
        return MessagingAdapter.send_message(str(uid), "Submission Rejected", reason,
                                             metadata={"submission_id": str(submission.pk)})


class PayoutQueueAdapter:
    """api.payout_queue — queue, cancel, status of payouts."""
    @staticmethod
    def queue_payout(user_id: str, amount: float, reference_id: str,
                     payout_type: str = "task_reward") -> dict:
        try:
            fn = _safe_import("api.payout_queue.services", "queue_payout")
            if fn: return fn(user_id=user_id, amount=amount, reference_id=reference_id,
                             payout_type=payout_type, source="auto_mod")
        except Exception as e: logger.warning("PayoutQueueAdapter: %s", e)
        return {"queued": False, "payout_id": None}

    @staticmethod
    def cancel_payout(payout_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.payout_queue.services", "cancel_payout")
            if fn: fn(payout_id=payout_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("PayoutQueueAdapter: %s", e)
        return False

    @staticmethod
    def get_payout_status(payout_id: str) -> dict:
        try:
            fn = _safe_import("api.payout_queue.services", "get_payout_status")
            if fn: return fn(payout_id=payout_id)
        except Exception as e: logger.warning("PayoutQueueAdapter: %s", e)
        return {"status": "unknown", "paid_at": None}


class MarketplaceAdapter:
    """api.marketplace — listing lookup, fraud reports, listing pause."""
    @staticmethod
    def get_listing(listing_id: str) -> dict | None:
        try:
            M = _safe_import("api.marketplace.models", "Listing")
            if M:
                obj = M.objects.filter(pk=listing_id).first()
                if obj: return {"listing_id": str(obj.pk),
                                "is_active": getattr(obj,"is_active",True),
                                "payout": getattr(obj,"payout",0.0)}
        except Exception as e: logger.warning("MarketplaceAdapter: %s", e)
        return None

    @staticmethod
    def report_listing_fraud(listing_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.marketplace.services", "report_fraud")
            if fn: fn(listing_id=listing_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("MarketplaceAdapter: %s", e)
        return False

    @staticmethod
    def pause_listing(listing_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.marketplace.services", "pause_listing")
            if fn: fn(listing_id=listing_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("MarketplaceAdapter: %s", e)
        return False


class MonetizationToolsAdapter:
    """api.monetization_tools — publisher monetisation status, suspend/restore."""
    @staticmethod
    def get_publisher_monetization_status(publisher_id: str) -> dict:
        try:
            fn = _safe_import("api.monetization_tools.services", "get_monetization_status")
            if fn: return fn(publisher_id=publisher_id)
        except Exception as e: logger.warning("MonetizationToolsAdapter: %s", e)
        return {"is_eligible": True, "tier": "standard"}

    @staticmethod
    def suspend_monetization(publisher_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.monetization_tools.services", "suspend_monetization")
            if fn: fn(publisher_id=publisher_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("MonetizationToolsAdapter: %s", e)
        return False

    @staticmethod
    def restore_monetization(publisher_id: str) -> bool:
        try:
            fn = _safe_import("api.monetization_tools.services", "restore_monetization")
            if fn: fn(publisher_id=publisher_id, source="auto_mod"); return True
        except Exception as e: logger.warning("MonetizationToolsAdapter: %s", e)
        return False


class PublisherToolsAdapter:
    """api.publisher_tools — stats push, dashboard data, flag publisher."""
    @staticmethod
    def update_publisher_stats(publisher_id: str, stats: dict) -> bool:
        try:
            fn = _safe_import("api.publisher_tools.services", "update_stats")
            if fn: fn(publisher_id=publisher_id, stats=stats, source="auto_mod"); return True
        except Exception as e: logger.warning("PublisherToolsAdapter: %s", e)
        return False

    @staticmethod
    def get_publisher_dashboard_data(publisher_id: str) -> dict:
        try:
            fn = _safe_import("api.publisher_tools.services", "get_dashboard_data")
            if fn: return fn(publisher_id=publisher_id)
        except Exception as e: logger.warning("PublisherToolsAdapter: %s", e)
        return {}

    @staticmethod
    def flag_publisher_in_dashboard(publisher_id: str, flag_type: str, message: str) -> bool:
        try:
            fn = _safe_import("api.publisher_tools.services", "flag_publisher")
            if fn: fn(publisher_id=publisher_id, flag_type=flag_type, message=message, source="auto_mod"); return True
        except Exception as e: logger.warning("PublisherToolsAdapter: %s", e)
        return False


class AdvertiserPortalAdapter:
    """api.advertiser_portal — moderation settings, notifications, fraud reports."""
    @staticmethod
    def get_advertiser_moderation_settings(advertiser_id: str) -> dict:
        try:
            fn = _safe_import("api.advertiser_portal.services", "get_moderation_settings")
            if fn: return fn(advertiser_id=advertiser_id)
        except Exception as e: logger.warning("AdvertiserPortalAdapter: %s", e)
        return {"auto_approve_threshold": 0.85, "webhook_url": None}

    @staticmethod
    def notify_advertiser(advertiser_id: str, event_type: str, data: dict) -> bool:
        try:
            fn = _safe_import("api.advertiser_portal.services", "send_notification")
            if fn: fn(advertiser_id=advertiser_id, event=event_type, data=data, source="auto_mod"); return True
        except Exception as e: logger.warning("AdvertiserPortalAdapter: %s", e)
        return False

    @staticmethod
    def report_fraud_to_advertiser(advertiser_id: str, fraud_summary: dict) -> bool:
        try:
            fn = _safe_import("api.advertiser_portal.services", "report_fraud")
            if fn: fn(advertiser_id=advertiser_id, summary=fraud_summary, source="auto_mod"); return True
        except Exception as e: logger.warning("AdvertiserPortalAdapter: %s", e)
        return False


class OfferInventoryAdapter:
    """api.offer_inventory — inventory lookup, capping, conversion recording."""
    @staticmethod
    def get_offer_inventory(offer_id: str) -> dict:
        try:
            fn = _safe_import("api.offer_inventory.services", "get_inventory")
            if fn: return fn(offer_id=offer_id)
        except Exception as e: logger.warning("OfferInventoryAdapter: %s", e)
        return {"daily_cap": None, "total_cap": None, "used_today": 0, "is_paused": False}

    @staticmethod
    def is_offer_capped(offer_id: str) -> bool:
        inv = OfferInventoryAdapter.get_offer_inventory(offer_id)
        if inv.get("is_paused"): return True
        if inv.get("daily_cap") and inv.get("used_today", 0) >= inv["daily_cap"]: return True
        return False

    @staticmethod
    def record_approved_conversion(offer_id: str) -> bool:
        try:
            fn = _safe_import("api.offer_inventory.services", "record_conversion")
            if fn: fn(offer_id=offer_id, source="auto_mod"); return True
        except Exception as e: logger.warning("OfferInventoryAdapter: %s", e)
        return False


class SmartlinkAdapter:
    """api.smartlink — validate links, flag abuse, get stats."""
    @staticmethod
    def validate_smartlink(link_id: str, user_id: str, ip: str = "") -> dict:
        try:
            fn = _safe_import("api.smartlink.services", "validate_link")
            if fn: return fn(link_id=link_id, user_id=user_id, ip=ip)
        except Exception as e: logger.warning("SmartlinkAdapter: %s", e)
        return {"valid": True, "is_flagged": False}

    @staticmethod
    def flag_smartlink_abuse(link_id: str, reason: str) -> bool:
        try:
            fn = _safe_import("api.smartlink.services", "flag_abuse")
            if fn: fn(link_id=link_id, reason=reason, source="auto_mod"); return True
        except Exception as e: logger.warning("SmartlinkAdapter: %s", e)
        return False

    @staticmethod
    def get_smartlink_stats(link_id: str) -> dict:
        try:
            fn = _safe_import("api.smartlink.services", "get_link_stats")
            if fn: return fn(link_id=link_id)
        except Exception as e: logger.warning("SmartlinkAdapter: %s", e)
        return {"clicks": 0, "conversions": 0, "fraud_rate": 0.0}


class DisasterRecoveryAdapter:
    """api.disaster_recovery + api.dr_integration — checkpoint/restore, health check."""
    @staticmethod
    def checkpoint(entity_type: str, entity_id: str, state: dict) -> bool:
        for mod in ("api.disaster_recovery.services", "api.dr_integration.services"):
            try:
                fn = _safe_import(mod, "checkpoint")
                if fn: fn(module="auto_mod", entity_type=entity_type, entity_id=entity_id, state=state); return True
            except Exception as e: logger.warning("DisasterRecoveryAdapter: %s", e)
        return False

    @staticmethod
    def restore(entity_type: str, entity_id: str) -> dict | None:
        try:
            fn = _safe_import("api.disaster_recovery.services", "restore")
            if fn: return fn(module="auto_mod", entity_type=entity_type, entity_id=entity_id)
        except Exception as e: logger.warning("DisasterRecoveryAdapter: %s", e)
        return None

    @staticmethod
    def health_check() -> dict:
        try:
            fn = _safe_import("api.disaster_recovery.services", "health_check")
            if fn: return fn()
        except Exception as e: logger.warning("DisasterRecoveryAdapter: %s", e)
        return {"healthy": True, "primary": True, "failover_ready": False}


class OfferRoutingAdapter:
    """api.offer_routing — routing config, route conversions, stats."""
    @staticmethod
    def get_routing_config(offer_id: str, publisher_id: str = "") -> dict:
        try:
            fn = _safe_import("api.offer_routing.services", "get_routing_config")
            if fn: return fn(offer_id=offer_id, publisher_id=publisher_id)
        except Exception as e: logger.warning("OfferRoutingAdapter: %s", e)
        return {"postback_url": None, "redirect_url": None, "tracking_params": {}}

    @staticmethod
    def route_approved_conversion(offer_id: str, publisher_id: str, submission_id: str) -> bool:
        try:
            fn = _safe_import("api.offer_routing.services", "route_conversion")
            if fn: fn(offer_id=offer_id, publisher_id=publisher_id, submission_id=submission_id, source="auto_mod"); return True
        except Exception as e: logger.warning("OfferRoutingAdapter: %s", e)
        return False

    @staticmethod
    def get_offer_routing_stats(offer_id: str) -> dict:
        try:
            fn = _safe_import("api.offer_routing.services", "get_routing_stats")
            if fn: return fn(offer_id=offer_id)
        except Exception as e: logger.warning("OfferRoutingAdapter: %s", e)
        return {"total_routed": 0, "success_rate": 0.0}


class TestsAdapter:
    """
    api.tests — project-level test utilities and shared fixtures.
    Used by: auto_mod test suite (register shared factories, seed test data,
             mock external services in CI/CD environments).

    Note: This adapter is a NO-OP in production (all methods return
    safe defaults). It only activates when api.tests is importable
    AND settings.TESTING is True.
    """

    @staticmethod
    def _is_test_env() -> bool:
        """Return True only in test/CI environment."""
        try:
            from django.conf import settings
            return getattr(settings, "TESTING", False) or getattr(settings, "TEST", False)
        except Exception:
            return False

    @staticmethod
    def get_test_user(role: str = "publisher") -> Any | None:
        """
        Return a pre-created test user for a given role.
        Roles: 'publisher', 'advertiser', 'moderator', 'admin'.
        Returns None in production.
        """
        if not TestsAdapter._is_test_env():
            return None
        try:
            get_fn = _safe_import("api.tests.factories", "get_test_user")
            if get_fn:
                return get_fn(role=role)
        except Exception as exc:
            logger.debug("TestsAdapter.get_test_user: %s", exc)
        return None

    @staticmethod
    def create_test_submission(submission_type: str = "task_proof",
                               status: str = "pending") -> Any | None:
        """Create a minimal SuspiciousSubmission for testing. No-op in production."""
        if not TestsAdapter._is_test_env():
            return None
        try:
            factory = _safe_import("api.tests.factories", "SuspiciousSubmissionFactory")
            if factory:
                return factory(submission_type=submission_type, status=status)
        except Exception as exc:
            logger.debug("TestsAdapter.create_test_submission: %s", exc)
        return None

    @staticmethod
    def mock_external_services() -> bool:
        """
        Patch all external service calls with safe mocks for CI.
        Call this in setUpClass() of integration tests.
        Returns True if mocks were applied.
        """
        if not TestsAdapter._is_test_env():
            return False
        try:
            mock_fn = _safe_import("api.tests.utils", "mock_auto_mod_services")
            if mock_fn:
                mock_fn()
                return True
        except Exception as exc:
            logger.debug("TestsAdapter.mock_external_services: %s", exc)
        return False

    @staticmethod
    def seed_test_data(scenario: str = "default") -> dict:
        """
        Seed the database with test data for a given scenario.
        Scenarios: 'default', 'high_fraud', 'appeal_workflow', 'ml_models'.
        Returns a dict of created object IDs. No-op in production.
        """
        if not TestsAdapter._is_test_env():
            return {}
        try:
            seed_fn = _safe_import("api.tests.seeds", f"seed_{scenario}")
            if seed_fn:
                return seed_fn(module="auto_mod")
        except Exception as exc:
            logger.debug("TestsAdapter.seed_test_data: %s", exc)
        return {}

    @staticmethod
    def reset_test_data() -> bool:
        """Tear down test data created by seed_test_data(). No-op in production."""
        if not TestsAdapter._is_test_env():
            return False
        try:
            reset_fn = _safe_import("api.tests.utils", "reset_auto_mod_data")
            if reset_fn:
                reset_fn()
                return True
        except Exception as exc:
            logger.debug("TestsAdapter.reset_test_data: %s", exc)
        return False

    @staticmethod
    def get_mock_fraud_signals(risk_level: str = "low") -> dict:
        """Return canned fraud signal data for a given risk level in tests."""
        profiles = {
            "low":      {"risk_score": 0.1, "is_flagged": False, "signals": []},
            "medium":   {"risk_score": 0.5, "is_flagged": False,
                         "signals": ["high_velocity"]},
            "high":     {"risk_score": 0.85, "is_flagged": True,
                         "signals": ["bot_ua", "proxy_ip", "high_velocity"]},
            "critical": {"risk_score": 0.99, "is_flagged": True,
                         "signals": ["blacklisted", "click_stuffing", "bot_ua"]},
        }
        return profiles.get(risk_level, profiles["low"])

    @staticmethod
    def assert_moderation_pipeline_healthy() -> dict:
        """
        Run a lightweight smoke-test of the auto_mod pipeline.
        Used in CI health-check jobs.
        Returns {passed, checks, errors}.
        """
        checks  = []
        errors  = []

        # 1. Models importable
        try:
            from .models import (SuspiciousSubmission, ProofScanner,
                                  ModerationQueue, ModerationAppeal, TaskBot)
            checks.append("models_importable")
        except Exception as e:
            errors.append(f"models: {e}")

        # 2. Services importable
        try:
            from .services import (ModerationService, BotService,
                                    AppealService, MLModelService)
            checks.append("services_importable")
        except Exception as e:
            errors.append(f"services: {e}")

        # 3. Choices complete
        try:
            from .choices import (BotStatus, TaskType, ScanStatus,
                                   AppealOutcome, AppealStatus)
            checks.append("choices_complete")
        except Exception as e:
            errors.append(f"choices: {e}")

        # 4. Adapters importable
        try:
            from .adapters import AdapterRegistry
            assert len([a for a in dir(AdapterRegistry) if not a.startswith('_')]) >= 44
            checks.append("adapters_complete")
        except Exception as e:
            errors.append(f"adapters: {e}")

        return {
            "passed": len(errors) == 0,
            "checks": checks,
            "errors": errors,
        }

class AdapterRegistry:
    """
    Central registry — সব adapter এখানে।
    Usage:
        from api.auto_mod.adapters import AdapterRegistry as adapters
        adapters.offerwall.mark_offer_completed(offer_id, user_id, submission_id)
        adapters.payout_queue.queue_payout(user_id, amount, reference_id)
    """
    # Original 18
    user               = UserAdapter
    task               = TaskAdapter
    fraud              = FraudAdapter
    notification       = NotificationAdapter
    analytics          = AnalyticsAdapter
    wallet             = WalletAdapter
    audit              = AuditLogAdapter
    tenant             = TenantAdapter
    rate_limit         = RateLimitAdapter
    webhook            = WebhookAdapter
    kyc                = KYCAdapter
    security           = SecurityAdapter
    ai_engine          = AIEngineAdapter
    postback           = PostbackAdapter
    gamification       = GamificationAdapter
    proxy_intelligence = ProxyIntelligenceAdapter
    cache              = CacheAdapter
    subscription       = SubscriptionAdapter

    # New 28
    admin_panel        = AdminPanelAdapter
    payment_gateways   = PaymentGatewayAdapter
    ad_networks        = AdNetworkAdapter
    offerwall          = OfferwallAdapter
    referral           = ReferralAdapter
    engagement         = EngagementAdapter
    cms                = CMSAdapter
    support            = SupportAdapter
    alerts             = AlertsAdapter
    djoyalty           = DjoyaltyAdapter
    localization       = LocalizationAdapter
    backup             = BackupAdapter
    promotions         = PromotionsAdapter
    version_control    = VersionControlAdapter
    behavior_analytics = BehaviorAnalyticsAdapter
    inventory          = InventoryAdapter
    messaging          = MessagingAdapter
    payout_queue       = PayoutQueueAdapter
    marketplace        = MarketplaceAdapter
    monetization_tools = MonetizationToolsAdapter
    publisher_tools    = PublisherToolsAdapter
    advertiser_portal  = AdvertiserPortalAdapter
    offer_inventory    = OfferInventoryAdapter
    smartlink          = SmartlinkAdapter
    disaster_recovery  = DisasterRecoveryAdapter
    offer_routing      = OfferRoutingAdapter
    tests              = TestsAdapter

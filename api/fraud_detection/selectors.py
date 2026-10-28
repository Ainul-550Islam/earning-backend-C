# =============================================================================
# fraud_detection/selectors.py
#
# Selector functions — thin, reusable QuerySet builders consumed by ViewSets,
# services, and serializers.  No business logic here; only filtering / ordering.
# Follows the pattern: selector(filters) → QuerySet  (never evaluated here).
# =============================================================================
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

User = get_user_model()


# ---------------------------------------------------------------------------
# FraudRule selector
# ---------------------------------------------------------------------------

def fraud_rule_selector(
    *,
    is_active: bool | None  = None,
    rule_type: str | None   = None,
    severity: str | None    = None,
    search: str | None      = None,
    ordering: str           = '-severity',
) -> QuerySet:
    from api.fraud_detection.models import FraudRule
    qs = FraudRule.objects.all()
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if rule_type:
        qs = qs.filter(rule_type=rule_type)
    if severity:
        qs = qs.filter(severity=severity)
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
    return qs.order_by(ordering)


def fraud_rule_detail_selector(*, pk: int) -> Any:
    from api.fraud_detection.models import FraudRule
    return FraudRule.objects.get(pk=pk)


# ---------------------------------------------------------------------------
# FraudAttempt selector
# ---------------------------------------------------------------------------

def fraud_attempt_selector(
    *,
    user_id: int | None     = None,
    status: str | None      = None,
    attempt_type: str | None = None,
    is_resolved: bool | None = None,
    min_score: int | None   = None,
    date_from: Any          = None,
    date_to: Any            = None,
    ordering: str           = '-created_at',
) -> QuerySet:
    from api.fraud_detection.models import FraudAttempt
    qs = FraudAttempt.objects.select_related('user', 'resolved_by')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if status:
        qs = qs.filter(status=status)
    if attempt_type:
        qs = qs.filter(attempt_type=attempt_type)
    if is_resolved is not None:
        qs = qs.filter(is_resolved=is_resolved)
    if min_score is not None:
        qs = qs.filter(fraud_score__gte=min_score)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)
    return qs.order_by(ordering)


# ---------------------------------------------------------------------------
# FraudAlert selector
# ---------------------------------------------------------------------------

def fraud_alert_selector(
    *,
    user_id: int | None     = None,
    is_resolved: bool | None = None,
    priority: str | None    = None,
    alert_type: str | None  = None,
    date_from: Any          = None,
    date_to: Any            = None,
    ordering: str           = '-created_at',
) -> QuerySet:
    from api.fraud_detection.models import FraudAlert
    qs = FraudAlert.objects.select_related('user', 'fraud_attempt', 'resolved_by')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if is_resolved is not None:
        qs = qs.filter(is_resolved=is_resolved)
    if priority:
        qs = qs.filter(priority=priority)
    if alert_type:
        qs = qs.filter(alert_type=alert_type)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)
    return qs.order_by(ordering)


def fraud_alert_detail_selector(*, pk: int) -> Any:
    from api.fraud_detection.models import FraudAlert
    return FraudAlert.objects.select_related('user', 'fraud_attempt', 'resolved_by').get(pk=pk)


# ---------------------------------------------------------------------------
# FraudCase selector
# ---------------------------------------------------------------------------

def fraud_case_selector(
    *,
    user_id: int | None     = None,
    status: str | None      = None,
    priority: str | None    = None,
    assigned_to_id: int | None = None,
    is_high_priority: bool | None = None,
    ordering: str           = '-opened_at',
) -> QuerySet:
    from api.fraud_detection.models import FraudCase
    qs = FraudCase.objects.select_related('user', 'assigned_to', 'resolved_by')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if assigned_to_id is not None:
        qs = qs.filter(assigned_to_id=assigned_to_id)
    if is_high_priority is not None:
        qs = qs.filter(is_high_priority=is_high_priority)
    return qs.order_by(ordering)


def fraud_case_detail_selector(*, pk: int) -> Any:
    from api.fraud_detection.models import FraudCase
    return FraudCase.objects.select_related('user', 'assigned_to', 'resolved_by').get(pk=pk)


# ---------------------------------------------------------------------------
# UserRiskProfile selector
# ---------------------------------------------------------------------------

def user_risk_profile_selector(
    *,
    is_flagged: bool | None     = None,
    is_restricted: bool | None  = None,
    monitoring_level: str | None = None,
    min_score: int | None       = None,
    max_score: int | None       = None,
    ordering: str               = '-overall_risk_score',
) -> QuerySet:
    from api.fraud_detection.models import UserRiskProfile
    qs = UserRiskProfile.objects.select_related('user')
    if is_flagged is not None:
        qs = qs.filter(is_flagged=is_flagged)
    if is_restricted is not None:
        qs = qs.filter(is_restricted=is_restricted)
    if monitoring_level:
        qs = qs.filter(monitoring_level=monitoring_level)
    if min_score is not None:
        qs = qs.filter(overall_risk_score__gte=min_score)
    if max_score is not None:
        qs = qs.filter(overall_risk_score__lte=max_score)
    return qs.order_by(ordering)


# ---------------------------------------------------------------------------
# DeviceFingerprint selector
# ---------------------------------------------------------------------------

def device_fingerprint_selector(
    *,
    user_id: int | None     = None,
    is_vpn: bool | None     = None,
    is_proxy: bool | None   = None,
    is_bot: bool | None     = None,
    min_trust: int | None   = None,
    max_trust: int | None   = None,
    ordering: str           = '-last_seen',
) -> QuerySet:
    from api.fraud_detection.models import DeviceFingerprint
    qs = DeviceFingerprint.objects.select_related('user')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if is_vpn is not None:
        qs = qs.filter(is_vpn=is_vpn)
    if is_proxy is not None:
        qs = qs.filter(is_proxy=is_proxy)
    if is_bot is not None:
        qs = qs.filter(is_bot=is_bot)
    if min_trust is not None:
        qs = qs.filter(trust_score__gte=min_trust)
    if max_trust is not None:
        qs = qs.filter(trust_score__lte=max_trust)
    return qs.order_by(ordering)


# ---------------------------------------------------------------------------
# IPReputation selector
# ---------------------------------------------------------------------------

def ip_reputation_selector(
    *,
    is_blacklisted: bool | None = None,
    country: str | None         = None,
    min_fraud_score: int | None = None,
    ordering: str               = '-fraud_score',
) -> QuerySet:
    from api.fraud_detection.models import IPReputation
    qs = IPReputation.objects.all()
    if is_blacklisted is not None:
        qs = qs.filter(is_blacklisted=is_blacklisted)
    if country:
        qs = qs.filter(country=country)
    if min_fraud_score is not None:
        qs = qs.filter(fraud_score__gte=min_fraud_score)
    return qs.order_by(ordering)


# ---------------------------------------------------------------------------
# FraudWhitelist selector
# ---------------------------------------------------------------------------

def fraud_whitelist_selector(
    *,
    entity_type: str | None = None,
    is_active: bool | None  = None,
    search: str | None      = None,
    ordering: str           = '-created_at',
) -> QuerySet:
    from api.fraud_detection.models import FraudWhitelist
    qs = FraudWhitelist.objects.select_related('whitelisted_by')
    if entity_type:
        qs = qs.filter(entity_type=entity_type)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if search:
        qs = qs.filter(entity_value__icontains=search)
    return qs.order_by(ordering)


# ---------------------------------------------------------------------------
# OfferCompletion selector
# ---------------------------------------------------------------------------

def offer_completion_selector(
    *,
    user_id: int | None     = None,
    offer_id: int | None    = None,
    status: str | None      = None,
    is_fraud: bool | None   = None,
    date_from: Any          = None,
    date_to: Any            = None,
    ordering: str           = '-tracked_at',
) -> QuerySet:
    from api.fraud_detection.models import OfferCompletion
    qs = OfferCompletion.objects.select_related('user', 'offer', 'reviewed_by')
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    if offer_id is not None:
        qs = qs.filter(offer_id=offer_id)
    if status:
        qs = qs.filter(status=status)
    if is_fraud is not None:
        qs = qs.filter(is_fraud=is_fraud)
    if date_from:
        qs = qs.filter(tracked_at__gte=date_from)
    if date_to:
        qs = qs.filter(tracked_at__lte=date_to)
    return qs.order_by(ordering)


# ---------------------------------------------------------------------------
# Object-style selectors (risk profile / suspicious IP)
#
# Every other selector in this file is a plain function, but
# fraud_risk_profile_selector and fraud_suspicious_ip_selector are used
# across analytics.py, monitoring.py, throttling.py, interactors.py and
# use_cases.py as objects — .list(), .get_high_risk_users(),
# .get_profile_by_user(user_id), .get_suspicious_ip(ip_address). These two
# small classes give callers that surface without touching any of them.
# ---------------------------------------------------------------------------

class _FraudRiskProfileSelector:
    def list(self, *, filters: dict | None = None, limit: int | None = None):
        from api.fraud_detection.models import UserRiskProfile
        qs = UserRiskProfile.objects.select_related('user')
        if filters:
            qs = qs.filter(**filters)
        qs = qs.order_by('-overall_risk_score')
        return qs if limit is None else qs[:limit]

    def get_high_risk_users(self):
        # Mirrors user_risk_profile_selector(is_flagged=True) above.
        # Swap for a score threshold or monitoring_level filter if that's
        # what "high risk" is meant to mean here instead.
        return user_risk_profile_selector(is_flagged=True)

    def get_profile_by_user(self, user_id: int):
        from api.fraud_detection.models import UserRiskProfile
        return (
            UserRiskProfile.objects
            .select_related('user')
            .filter(user_id=user_id)
            .first()
        )


class _FraudSuspiciousIPSelector:
    def get_suspicious_ip(self, ip_address: str):
        from api.fraud_detection.models import IPReputation
        # Returns the reputation record for this IP if one exists at all.
        # Add .filter(is_blacklisted=True) too if "suspicious" should mean
        # pre-filtered rather than "has any record."
        return IPReputation.objects.filter(ip_address=ip_address).first()


fraud_risk_profile_selector = _FraudRiskProfileSelector()
fraud_suspicious_ip_selector = _FraudSuspiciousIPSelector()


# ---------------------------------------------------------------------------
# Object-style selector: device fingerprint
# ---------------------------------------------------------------------------

class _FraudDeviceFingerprintSelector:
    def list(self, *, filters: dict | None = None, limit: int | None = None):
        from api.fraud_detection.models import DeviceFingerprint
        qs = DeviceFingerprint.objects.select_related('user')
        if filters:
            qs = qs.filter(**filters)
        qs = qs.order_by('-last_seen')
        return qs if limit is None else qs[:limit]


fraud_device_fingerprint_selector = _FraudDeviceFingerprintSelector()

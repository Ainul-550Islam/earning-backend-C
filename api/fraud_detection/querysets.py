# =============================================================================
# fraud_detection/querysets.py
#
# Named QuerySet classes wired to models via models_managers_patch.py.
# Also importable directly for type hints in service layers.
# =============================================================================
from __future__ import annotations

from django.db import models
from django.utils import timezone


class FraudDetectionQuerySet(models.QuerySet):
    """QuerySet for FraudAttempt."""

    def unresolved(self):
        return self.filter(is_resolved=False)

    def pending(self):
        return self.filter(status='pending')

    def confirmed(self):
        return self.filter(status='confirmed')

    def high_risk(self, threshold: int = 70):
        return self.filter(fraud_score__gte=threshold)

    def for_user(self, user):
        return self.filter(user=user)

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)

    def by_type(self, attempt_type: str):
        return self.filter(attempt_type=attempt_type)

    def with_user(self):
        return self.select_related('user', 'resolved_by')

    def ordered_by_risk(self):
        return self.order_by('-fraud_score', '-created_at')


class FraudCaseQuerySet(models.QuerySet):
    """QuerySet for FraudCase."""

    def open(self):
        return self.filter(status__in=['open', 'investigating'])

    def closed(self):
        return self.filter(status__in=['resolved', 'closed', 'dismissed'])

    def high_priority(self):
        return self.filter(priority__in=['high', 'critical'])

    def unassigned(self):
        return self.filter(assigned_to__isnull=True, status='open')

    def assigned_to_user(self, user):
        return self.filter(assigned_to=user)

    def for_user(self, user):
        return self.filter(user=user)

    def escalated(self):
        return self.filter(status='escalated')

    def stale(self, hours: int = 72):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(
            status__in=['open', 'investigating'],
            opened_at__lte=cutoff,
        )

    def with_related(self):
        return self.select_related('user', 'assigned_to', 'resolved_by')


class FraudAlertQuerySet(models.QuerySet):
    """QuerySet for FraudAlert."""

    def unresolved(self):
        return self.filter(is_resolved=False)

    def critical(self):
        return self.filter(priority='critical', is_resolved=False)

    def for_user(self, user):
        return self.filter(user=user)

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)

    def by_priority(self, priority: str):
        return self.filter(priority=priority)

    def by_type(self, alert_type: str):
        return self.filter(alert_type=alert_type)

    def with_related(self):
        return self.select_related('user', 'fraud_attempt', 'resolved_by')


class FraudRuleQuerySet(models.QuerySet):
    """QuerySet for FraudRule."""

    def active(self):
        return self.filter(is_active=True)

    def by_severity(self, severity: str):
        return self.filter(severity=severity)

    def real_time(self):
        return self.filter(is_active=True, run_frequency='real_time')

    def high_impact(self):
        return self.filter(is_active=True, severity__in=['high', 'critical'])

    def never_triggered(self):
        return self.filter(trigger_count=0)

    def most_triggered(self, limit: int = 10):
        return self.order_by('-trigger_count')[:limit]


class UserRiskProfileQuerySet(models.QuerySet):
    """QuerySet for UserRiskProfile."""

    def flagged(self):
        return self.filter(is_flagged=True)

    def restricted(self):
        return self.filter(is_restricted=True)

    def high_risk(self, threshold: int = 70):
        return self.filter(overall_risk_score__gte=threshold)

    def low_risk(self, threshold: int = 30):
        return self.filter(overall_risk_score__lt=threshold)

    def critical(self):
        return self.filter(overall_risk_score__gte=81)

    def monitoring_required(self):
        return self.filter(monitoring_level__in=['elevated', 'high', 'critical'])

    def due_for_assessment(self):
        return self.filter(
            models.Q(next_assessment_due__lte=timezone.now()) |
            models.Q(next_assessment_due__isnull=True)
        )

    def with_user(self):
        return self.select_related('user')


class DeviceFingerprintQuerySet(models.QuerySet):
    """QuerySet for DeviceFingerprint."""

    def suspicious(self):
        return self.filter(
            models.Q(is_vpn=True)   |
            models.Q(is_proxy=True) |
            models.Q(is_tor=True)   |
            models.Q(is_bot=True)
        )

    def low_trust(self, threshold: int = 40):
        return self.filter(trust_score__lte=threshold)

    def for_user(self, user):
        return self.filter(user=user)

    def recent(self, days: int = 30):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(last_seen__gte=cutoff)

    def by_ip(self, ip: str):
        return self.filter(ip_address=ip)

    def mobile(self):
        return self.filter(is_mobile=True)

    def bots(self):
        return self.filter(is_bot=True)


class IPReputationQuerySet(models.QuerySet):
    """QuerySet for IPReputation."""

    def blacklisted(self):
        return self.filter(is_blacklisted=True)

    def high_risk(self, threshold: int = 70):
        return self.filter(fraud_score__gte=threshold)

    def by_country(self, country: str):
        return self.filter(country=country)

    def with_threats(self):
        # Returns IPs that have at least one threat type entry
        return self.exclude(threat_types=[])

    def recently_checked(self, hours: int = 24):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(last_threat_check__gte=cutoff)


class FraudWhitelistQuerySet(models.QuerySet):
    """QuerySet for FraudWhitelist."""

    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def expired(self):
        return self.filter(
            expires_at__isnull=False,
            expires_at__lt=timezone.now(),
        )

    def by_entity_type(self, entity_type: str):
        return self.filter(entity_type=entity_type)

    def search(self, q: str):
        return self.filter(entity_value__icontains=q)

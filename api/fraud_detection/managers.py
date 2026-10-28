# =============================================================================
# fraud_detection/managers.py
#
# Custom Manager and QuerySet classes for all Fraud Detection models.
# Applied to models at runtime via models_managers_patch.py (Mode A).
# =============================================================================
from __future__ import annotations

from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# FraudRule
# ---------------------------------------------------------------------------

class FraudRuleQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def by_severity(self, severity: str):
        return self.filter(severity=severity)

    def real_time(self):
        return self.filter(is_active=True, run_frequency='real_time')

    def high_impact(self):
        return self.filter(is_active=True, severity__in=['high', 'critical'])


class FraudRuleManager(models.Manager):
    def get_queryset(self):
        return FraudRuleQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def real_time(self):
        return self.get_queryset().real_time()


# ---------------------------------------------------------------------------
# FraudAttempt
# ---------------------------------------------------------------------------

class FraudAttemptQuerySet(models.QuerySet):
    def unresolved(self):
        return self.filter(is_resolved=False)

    def high_risk(self, threshold: int = 70):
        return self.filter(fraud_score__gte=threshold)

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)

    def for_user(self, user):
        return self.filter(user=user)

    def pending(self):
        return self.filter(status='pending')

    def confirmed(self):
        return self.filter(status='confirmed')


class FraudCaseManager(models.Manager):
    """Manager for FraudCase (reused naming convention)."""
    def get_queryset(self):
        return models.QuerySet(self.model, using=self._db)

    def open(self):
        return self.get_queryset().filter(status__in=['open', 'investigating'])

    def high_priority(self):
        return self.get_queryset().filter(priority__in=['high', 'critical'])

    def unassigned(self):
        return self.get_queryset().filter(assigned_to__isnull=True, status='open')

    def stale(self, hours: int = 72):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.get_queryset().filter(
            status__in=['open', 'investigating'],
            opened_at__lte=cutoff,
        )


# ---------------------------------------------------------------------------
# FraudAlert
# ---------------------------------------------------------------------------

class FraudAlertQuerySet(models.QuerySet):
    def unresolved(self):
        return self.filter(is_resolved=False)

    def critical(self):
        return self.filter(priority='critical', is_resolved=False)

    def for_user(self, user):
        return self.filter(user=user)

    def recent(self, hours: int = 24):
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)


class FraudAlertManager(models.Manager):
    def get_queryset(self):
        return FraudAlertQuerySet(self.model, using=self._db)

    def unresolved(self):
        return self.get_queryset().unresolved()

    def critical(self):
        return self.get_queryset().critical()


# ---------------------------------------------------------------------------
# UserRiskProfile
# ---------------------------------------------------------------------------

class FraudRiskProfileQuerySet(models.QuerySet):
    def flagged(self):
        return self.filter(is_flagged=True)

    def restricted(self):
        return self.filter(is_restricted=True)

    def high_risk(self, threshold: int = 70):
        return self.filter(overall_risk_score__gte=threshold)

    def monitoring_required(self):
        return self.filter(monitoring_level__in=['elevated', 'high', 'critical'])


class FraudRiskProfileManager(models.Manager):
    def get_queryset(self):
        return FraudRiskProfileQuerySet(self.model, using=self._db)

    def high_risk(self, threshold: int = 70):
        return self.get_queryset().high_risk(threshold)

    def flagged(self):
        return self.get_queryset().flagged()


# ---------------------------------------------------------------------------
# DeviceFingerprint
# ---------------------------------------------------------------------------

class DeviceFingerprintQuerySet(models.QuerySet):
    def suspicious(self):
        return self.filter(
            models.Q(is_vpn=True) | models.Q(is_proxy=True) | models.Q(is_tor=True) | models.Q(is_bot=True)
        )

    def low_trust(self, threshold: int = 40):
        return self.filter(trust_score__lte=threshold)

    def for_user(self, user):
        return self.filter(user=user)

    def recent(self, days: int = 30):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(last_seen__gte=cutoff)


class DeviceFingerprintManager(models.Manager):
    def get_queryset(self):
        return DeviceFingerprintQuerySet(self.model, using=self._db)

    def suspicious(self):
        return self.get_queryset().suspicious()


# ---------------------------------------------------------------------------
# IPReputation
# ---------------------------------------------------------------------------

class FraudSuspiciousIPQuerySet(models.QuerySet):
    def blacklisted(self):
        return self.filter(is_blacklisted=True)

    def high_risk(self, threshold: int = 70):
        return self.filter(fraud_score__gte=threshold)

    def by_country(self, country: str):
        return self.filter(country=country)


class FraudSuspiciousIPManager(models.Manager):
    def get_queryset(self):
        return FraudSuspiciousIPQuerySet(self.model, using=self._db)

    def blacklisted(self):
        return self.get_queryset().blacklisted()

    def high_risk(self, threshold: int = 70):
        return self.get_queryset().high_risk(threshold)


# ---------------------------------------------------------------------------
# BaseIntegrityManager — for FraudWhitelist, FraudCaseEvidence, FraudCaseAction
# ---------------------------------------------------------------------------

class BaseIntegrityQuerySet(models.QuerySet):
    def with_valid_hash(self):
        """Return only records that have an integrity hash set."""
        return self.exclude(integrity_hash='')

    def active(self):
        """Works for FraudWhitelist (has is_active). No-op for others."""
        if hasattr(self.model, 'is_active'):
            return self.filter(is_active=True)
        return self


class BaseIntegrityManager(models.Manager):
    def get_queryset(self):
        return BaseIntegrityQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

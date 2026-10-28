# api/referral/managers.py
# Custom QuerySet and Model Managers for referral module
# ============================================================

from django.db import models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


# ── Referral Manager ──────────────────────────────────────────────────────────

class ReferralQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_suspicious=False)

    def suspicious(self):
        return self.filter(is_suspicious=True)

    def by_referrer(self, user):
        return self.filter(referrer=user)

    def with_commissions(self):
        return self.prefetch_related('referralearning_set')

    def level1_only(self):
        return self.filter(level=1)

    def recent(self, days=30):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class ReferralManager(models.Manager):
    def get_queryset(self):
        return ReferralQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_user(self, user):
        return self.get_queryset().by_referrer(user)

    def count_for_user(self, user) -> int:
        return self.get_queryset().filter(referrer=user).count()

    def get_chain(self, user):
        """Get all referral levels for a user (L1+L2+L3)."""
        try:
            from api.referral.models import ReferralChain
            return ReferralChain.objects.filter(beneficiary=user).select_related('earner')
        except Exception:
            return self.none()


# ── ReferralEarning Manager ───────────────────────────────────────────────────

class ReferralEarningQuerySet(models.QuerySet):
    def released(self):
        return self.filter(status='released')

    def held(self):
        return self.filter(status='held')

    def by_level(self, level: int):
        return self.filter(level=level)

    def by_source(self, source_type: str):
        return self.filter(source_type=source_type)

    def total_amount(self) -> Decimal:
        result = self.aggregate(t=models.Sum('amount'))['t']
        return result or Decimal('0')

    def this_month(self):
        now = timezone.now()
        return self.filter(
            created_at__year=now.year,
            created_at__month=now.month,
        )


class ReferralEarningManager(models.Manager):
    def get_queryset(self):
        return ReferralEarningQuerySet(self.model, using=self._db)

    def for_referrer(self, user):
        return self.get_queryset().filter(referrer=user)

    def total_for_user(self, user) -> Decimal:
        return self.for_referrer(user).released().total_amount()

    def this_month_for_user(self, user) -> Decimal:
        return self.for_referrer(user).released().this_month().total_amount()


# ── CommissionLog Manager ─────────────────────────────────────────────────────

class CommissionLogQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status='pending')

    def held(self):
        return self.filter(status='held')

    def released(self):
        return self.filter(status='released')

    def overdue_holds(self):
        """Held commissions past their release date."""
        try:
            return self.filter(
                status='held',
                hold__release_at__lt=timezone.now(),
                hold__is_released=False,
            )
        except Exception:
            return self.none()

    def for_user(self, user):
        return self.filter(user=user)

    def sum_amount(self) -> Decimal:
        result = self.aggregate(t=models.Sum('amount'))['t']
        return result or Decimal('0')


class CommissionLogManager(models.Manager):
    def get_queryset(self):
        return CommissionLogQuerySet(self.model, using=self._db)

    def pending_for_user(self, user):
        return self.get_queryset().for_user(user).pending()

    def overdue_holds(self):
        return self.get_queryset().overdue_holds()


# ── SuspiciousReferral Manager ────────────────────────────────────────────────

class SuspiciousReferralQuerySet(models.QuerySet):
    def pending_review(self):
        return self.filter(status='pending')

    def high_risk(self, threshold: int = 50):
        return self.filter(fraud_score__gte=threshold)

    def confirmed_fraud(self):
        return self.filter(status='fraud')

    def cleared(self):
        return self.filter(status='cleared')


class SuspiciousReferralManager(models.Manager):
    def get_queryset(self):
        return SuspiciousReferralQuerySet(self.model, using=self._db)

    def high_risk(self):
        return self.get_queryset().high_risk()

    def pending_review(self):
        return self.get_queryset().pending_review()


# ── ReferralCode Manager ──────────────────────────────────────────────────────

class ReferralCodeQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def primary(self):
        return self.filter(is_primary=True, is_active=True)

    def not_expired(self):
        return self.filter(
            models.Q(expires_at__isnull=True) |
            models.Q(expires_at__gt=timezone.now())
        )

    def by_code(self, code: str):
        return self.filter(
            models.Q(code=code) | models.Q(custom_code=code)
        ).first()


class ReferralCodeManager(models.Manager):
    def get_queryset(self):
        return ReferralCodeQuerySet(self.model, using=self._db)

    def get_primary_for_user(self, user):
        return self.get_queryset().filter(
            user=user, is_primary=True, is_active=True
        ).first()

    def validate(self, code: str):
        """Returns code obj if valid, None if invalid/expired."""
        return self.get_queryset().active().not_expired().by_code(code)


# ── ReferralCampaign Manager ──────────────────────────────────────────────────

class ReferralCampaignQuerySet(models.QuerySet):
    def active_now(self):
        now = timezone.now()
        return self.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        )

    def within_budget(self):
        return self.filter(
            models.Q(max_budget__isnull=True) |
            models.Q(current_spend__lt=models.F('max_budget'))
        )

    def featured(self):
        return self.filter(is_featured=True)


class ReferralCampaignManager(models.Manager):
    def get_queryset(self):
        return ReferralCampaignQuerySet(self.model, using=self._db)

    def get_active(self):
        """Get the single active campaign (or None)."""
        return self.get_queryset().active_now().within_budget().first()
# api/referral/querysets.py
# All custom QuerySets for referral models
# Imported by managers.py — can also be used directly for .as_manager()
# ============================================================

from django.db import models
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class ReferralQuerySet(models.QuerySet):

    def active(self):
        """Non-suspicious referrals."""
        return self.filter(is_suspicious=False)

    def suspicious(self):
        return self.filter(is_suspicious=True)

    def by_referrer(self, user):
        return self.filter(referrer=user)

    def by_referred_user(self, user):
        return self.filter(referred_user=user)

    def with_commissions(self):
        from django.db.models import Sum
        return self.annotate(
            commission_sum=Sum('referral_referralearning_referred_user__amount')
        )

    def recent(self, days: int = 30):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def this_month(self):
        n = timezone.now()
        return self.filter(created_at__year=n.year, created_at__month=n.month)

    def level1_only(self):
        return self.filter(level=1)

    def with_related(self):
        return self.select_related('referrer', 'referred_user', 'tenant')

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)


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

    def by_code(self, value: str):
        """Lookup by code OR custom_code."""
        return self.filter(
            models.Q(code__iexact=value) | models.Q(custom_code__iexact=value)
        ).first()

    def with_stats(self):
        """Annotate with click/conversion counts."""
        from django.db.models import Sum, Count
        return self.annotate(
            total_clicks=models.F('clicks'),
            total_conversions=models.F('conversions'),
        )

    def top_converting(self, limit: int = 10):
        return self.active().not_expired().order_by('-conversions')[:limit]


class ReferralEarningQuerySet(models.QuerySet):

    def released(self):
        return self.filter(status='released')

    def held(self):
        return self.filter(status='held')

    def pending(self):
        return self.filter(status='pending')

    def clawed_back(self):
        return self.filter(status='clawed_back')

    def by_level(self, level: int):
        return self.filter(level=level)

    def by_source(self, source_type: str):
        return self.filter(source_type=source_type)

    def for_referrer(self, user):
        return self.filter(referrer=user)

    def for_referred(self, user):
        return self.filter(referred_user=user)

    def this_month(self):
        n = timezone.now()
        return self.filter(created_at__year=n.year, created_at__month=n.month)

    def last_n_days(self, n: int):
        return self.filter(created_at__gte=timezone.now() - timedelta(days=n))

    def total_amount(self) -> Decimal:
        result = self.aggregate(t=models.Sum('amount'))['t']
        return result or Decimal('0')

    def with_related(self):
        return self.select_related('referrer', 'referred_user', 'referral', 'tenant')


class CommissionLogQuerySet(models.QuerySet):

    def pending(self):
        return self.filter(status='pending')

    def held(self):
        return self.filter(status='held')

    def released(self):
        return self.filter(status='released')

    def cancelled(self):
        return self.filter(status='cancelled')

    def clawed_back(self):
        return self.filter(status='clawed_back')

    def by_level(self, level: int):
        return self.filter(level=level)

    def for_user(self, user):
        return self.filter(user=user)

    def for_referred_user(self, user):
        return self.filter(referred_user=user)

    def overdue_holds(self):
        return self.filter(
            status='held',
            hold__release_at__lt=timezone.now(),
            hold__is_released=False,
        )

    def sum_amount(self) -> Decimal:
        return self.aggregate(t=models.Sum('amount'))['t'] or Decimal('0')

    def with_related(self):
        return self.select_related('user', 'referred_user', 'campaign', 'tenant')

    def this_month(self):
        n = timezone.now()
        return self.filter(created_at__year=n.year, created_at__month=n.month)

    def last_n_days(self, n: int):
        return self.filter(created_at__gte=timezone.now() - timedelta(days=n))


class SuspiciousReferralQuerySet(models.QuerySet):

    def pending_review(self):
        return self.filter(status='pending')

    def reviewing(self):
        return self.filter(status='reviewing')

    def confirmed_fraud(self):
        return self.filter(status='fraud')

    def cleared(self):
        return self.filter(status='cleared')

    def high_risk(self, threshold: int = 50):
        return self.filter(fraud_score__gte=threshold)

    def critical_risk(self, threshold: int = 80):
        return self.filter(fraud_score__gte=threshold)

    def low_risk(self, max_score: int = 30):
        return self.filter(fraud_score__lt=max_score)

    def unreviewed(self):
        return self.filter(reviewed_at__isnull=True)

    def with_related(self):
        return self.select_related(
            'referral', 'referral__referrer', 'referral__referred_user',
            'reviewed_by', 'tenant'
        )


class ReferralCampaignQuerySet(models.QuerySet):

    def active_now(self):
        now = timezone.now()
        return self.filter(is_active=True, start_date__lte=now, end_date__gte=now)

    def within_budget(self):
        return self.filter(
            models.Q(max_budget__isnull=True) |
            models.Q(current_spend__lt=models.F('max_budget'))
        )

    def has_capacity(self):
        return self.filter(
            models.Q(max_referrals__isnull=True) |
            models.Q(current_referrals__lt=models.F('max_referrals'))
        )

    def featured(self):
        return self.filter(is_featured=True, is_active=True)

    def upcoming(self):
        return self.filter(start_date__gt=timezone.now(), is_active=True)

    def ended(self):
        return self.filter(end_date__lt=timezone.now())

    def get_best_active(self):
        """Get the best active campaign — highest multiplier."""
        return (
            self.active_now()
                .within_budget()
                .has_capacity()
                .order_by('-bonus_multiplier')
                .first()
        )


class ReferralFraudRuleQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def by_type(self, rule_type: str):
        return self.filter(rule_type=rule_type)

    def block_rules(self):
        return self.filter(action='block', is_active=True)

    def flag_rules(self):
        return self.filter(action='flag', is_active=True)

    def ordered_by_priority(self):
        return self.filter(is_active=True).order_by('-priority')


class CommissionHoldQuerySet(models.QuerySet):

    def unreleased(self):
        return self.filter(is_released=False)

    def overdue(self):
        return self.filter(
            is_released=False,
            release_at__lt=timezone.now(),
        )

    def due_soon(self, hours: int = 24):
        deadline = timezone.now() + timedelta(hours=hours)
        return self.filter(
            is_released=False,
            release_at__lte=deadline,
            release_at__gte=timezone.now(),
        )


class CommissionClawbackQuerySet(models.QuerySet):

    def pending(self):
        return self.filter(status='pending')

    def approved(self):
        return self.filter(status='approved')

    def processing(self):
        return self.filter(status='processing')

    def completed(self):
        return self.filter(status='completed')

    def sum_amount(self) -> Decimal:
        return self.aggregate(t=models.Sum('clawback_amount'))['t'] or Decimal('0')


class ReferralLTVQuerySet(models.QuerySet):

    def high_value(self):
        return self.filter(value_category='high_value')

    def churned(self):
        return self.filter(churn_risk='churned')

    def at_risk(self):
        return self.filter(churn_risk__in=['medium', 'high'])

    def for_referrer(self, user):
        return self.filter(referred_by=user)

    def top_by_ltv(self, limit: int = 10):
        return self.order_by('-lifetime_value')[:limit]


class ReferralInsightQuerySet(models.QuerySet):

    def last_30_days(self):
        cutoff = timezone.now().date() - timedelta(days=30)
        return self.filter(date__gte=cutoff)

    def last_7_days(self):
        cutoff = timezone.now().date() - timedelta(days=7)
        return self.filter(date__gte=cutoff)

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)


class TopReferrerQuerySet(models.QuerySet):

    def for_period(self, period: str):
        return self.filter(period=period)

    def today(self):
        return self.filter(date=timezone.now().date(), period='daily')

    def this_week(self):
        return self.filter(period='weekly').order_by('-date').first_by_date()

    def top_n(self, n: int = 10):
        return self.order_by('rank')[:n]

    def improved(self):
        """Users who moved up in rank."""
        return self.filter(rank_change__gt=0)

    def declined(self):
        return self.filter(rank_change__lt=0)
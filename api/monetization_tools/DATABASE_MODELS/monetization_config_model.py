"""
DATABASE_MODELS/monetization_config_model.py
=============================================
QuerySet + Manager for MonetizationConfig, RevenueGoal,
PublisherAccount, FlashSale, Coupon, CouponUsage,
ReferralProgram, ReferralLink, ReferralCommission.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import date, timedelta

from django.db import models
from django.db.models import Count, DecimalField, F, Q, Sum
from django.utils import timezone


# ── MonetizationConfig ──────────────────────────────────────────────────────

class MonetizationConfigManager(models.Manager):

    def for_tenant(self, tenant) -> 'MonetizationConfig':
        """Get or create config for tenant. Always returns an instance."""
        obj, _ = self.get_or_create(tenant=tenant)
        return obj

    def get_feature_flags(self, tenant) -> dict:
        cfg = self.for_tenant(tenant)
        return {
            'offerwall':     cfg.offerwall_enabled,
            'subscription':  cfg.subscription_enabled,
            'spin_wheel':    cfg.spin_wheel_enabled,
            'scratch_card':  cfg.scratch_card_enabled,
            'referral':      cfg.referral_enabled,
            'ab_testing':    cfg.ab_testing_enabled,
            'flash_sale':    cfg.flash_sale_enabled,
            'coupon':        cfg.coupon_enabled,
            'daily_streak':  cfg.daily_streak_enabled,
        }

    def is_enabled(self, tenant, feature: str) -> bool:
        flags = self.get_feature_flags(tenant)
        return flags.get(feature, False)


# ── RevenueGoal ─────────────────────────────────────────────────────────────

class RevenueGoalQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_period(self, period: str):
        return self.filter(period=period)

    def current(self):
        today = timezone.now().date()
        return self.active().filter(period_start__lte=today, period_end__gte=today)

    def achieved(self):
        return self.filter(current_value__gte=F('target_value'))

    def missed(self):
        today = timezone.now().date()
        return self.filter(period_end__lt=today, current_value__lt=F('target_value'))

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)


class RevenueGoalManager(models.Manager):
    def get_queryset(self):
        return RevenueGoalQuerySet(self.model, using=self._db)

    def current(self, tenant=None):
        qs = self.get_queryset().current()
        if tenant:
            qs = qs.for_tenant(tenant)
        return qs

    def achieved(self, tenant=None):
        qs = self.get_queryset().achieved()
        if tenant:
            qs = qs.for_tenant(tenant)
        return qs

    def update_progress(self, goal_id, new_value: Decimal):
        return self.filter(id=goal_id).update(current_value=new_value)


# ── PublisherAccount ────────────────────────────────────────────────────────

class PublisherAccountQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status='active')

    def pending(self):
        return self.filter(status='pending')

    def advertisers(self):
        return self.filter(account_type='advertiser')

    def publishers(self):
        return self.filter(account_type='publisher')

    def verified(self):
        return self.filter(is_verified=True)

    def unverified(self):
        return self.filter(is_verified=False)

    def over_credit_limit(self):
        return self.filter(current_balance_usd__gte=F('credit_limit_usd'), credit_limit_usd__gt=0)

    def by_country(self, country: str):
        return self.filter(country=country.upper())

    def top_by_spend(self, limit: int = 20):
        return self.advertisers().active().order_by('-total_spend_usd')[:limit]

    def top_by_revenue(self, limit: int = 20):
        return self.publishers().active().order_by('-total_revenue_usd')[:limit]


class PublisherAccountManager(models.Manager):
    def get_queryset(self):
        return PublisherAccountQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def pending_approval(self):
        return self.get_queryset().pending().order_by('created_at')

    def top_advertisers(self, limit: int = 20):
        return self.get_queryset().top_by_spend(limit)


# ── FlashSale ───────────────────────────────────────────────────────────────

class FlashSaleQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def live_now(self):
        now = timezone.now()
        return self.active().filter(starts_at__lte=now, ends_at__gte=now)

    def upcoming(self):
        now = timezone.now()
        return self.active().filter(starts_at__gt=now)

    def ended(self):
        return self.filter(ends_at__lt=timezone.now())

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def by_type(self, sale_type: str):
        return self.filter(sale_type=sale_type)


class FlashSaleManager(models.Manager):
    def get_queryset(self):
        return FlashSaleQuerySet(self.model, using=self._db)

    def live_now(self, tenant=None):
        qs = self.get_queryset().live_now()
        if tenant:
            qs = qs.for_tenant(tenant)
        return qs.prefetch_related('target_segments')

    def upcoming(self, tenant=None):
        qs = self.get_queryset().upcoming()
        if tenant:
            qs = qs.for_tenant(tenant)
        return qs.order_by('starts_at')

    def get_active_multiplier(self, tenant, offer_type: str = None) -> Decimal:
        """Return the highest active multiplier for offer_type."""
        qs = self.live_now(tenant).filter(sale_type__in=['offer_boost', 'double_points'])
        if offer_type:
            qs = qs.filter(
                Q(target_offer_types=[]) | Q(target_offer_types__contains=[offer_type])
            )
        result = qs.order_by('-multiplier').values_list('multiplier', flat=True).first()
        return result or Decimal('1.00')


# ── Coupon ──────────────────────────────────────────────────────────────────

class CouponQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        return self.filter(is_active=True).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=now)
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gt=now)
        )

    def not_exhausted(self):
        return self.filter(Q(max_uses=0) | Q(current_uses__lt=F('max_uses')))

    def valid(self):
        return self.active().not_exhausted()

    def by_code(self, code: str):
        return self.filter(code__iexact=code).first()

    def by_type(self, coupon_type: str):
        return self.filter(coupon_type=coupon_type)

    def expiring_within(self, hours: int = 48):
        now = timezone.now()
        cutoff = now + timedelta(hours=hours)
        return self.active().filter(valid_until__lte=cutoff, valid_until__gt=now)


class CouponManager(models.Manager):
    def get_queryset(self):
        return CouponQuerySet(self.model, using=self._db)

    def validate(self, code: str, user=None) -> tuple:
        """
        Returns (coupon, error_message).
        coupon=None means invalid.
        """
        coupon = self.get_queryset().by_code(code)
        if not coupon:
            return None, "Coupon not found."
        if not coupon.is_valid:
            return None, "Coupon is expired or exhausted."
        if user and coupon.first_time_only:
            from ..models import CouponUsage
            if CouponUsage.objects.filter(coupon=coupon, user=user).exists():
                return None, "This coupon is for first-time use only."
        if user and coupon.single_use:
            from ..models import CouponUsage
            count = CouponUsage.objects.filter(coupon=coupon, user=user).count()
            if count >= coupon.max_uses_per_user:
                return None, "You have already used this coupon."
        return coupon, None

    def redeem(self, coupon, user, reference_id: str = '') -> 'CouponUsage':
        """Mark coupon as used and increment counter atomically."""
        from ..models import CouponUsage
        from django.db.models import F
        usage = CouponUsage.objects.create(
            coupon=coupon,
            user=user,
            tenant=coupon.tenant,
            coins_granted=coupon.coin_amount,
            reference_id=reference_id,
        )
        self.filter(pk=coupon.pk).update(current_uses=F('current_uses') + 1)
        return usage


# ── Referral ────────────────────────────────────────────────────────────────

class ReferralCommissionQuerySet(models.QuerySet):
    def for_referrer(self, user):
        return self.filter(referrer=user)

    def unpaid(self):
        return self.filter(is_paid=False)

    def paid(self):
        return self.filter(is_paid=True)

    def by_level(self, level: int):
        return self.filter(level=level)

    def total_unpaid(self, user=None):
        qs = self.unpaid()
        if user:
            qs = qs.for_referrer(user)
        return qs.aggregate(total=Sum('commission_coins'))['total'] or Decimal('0.00')

    def commission_breakdown(self, user):
        return (
            self.for_referrer(user)
                .values('level', 'commission_type')
                .annotate(count=Count('id'), total=Sum('commission_coins'))
                .order_by('level')
        )


class ReferralCommissionManager(models.Manager):
    def get_queryset(self):
        return ReferralCommissionQuerySet(self.model, using=self._db)

    def pending_for_user(self, user) -> Decimal:
        return self.get_queryset().for_referrer(user).total_unpaid(user)

    def pay_all_for_user(self, user) -> int:
        """Mark all unpaid commissions as paid. Returns count."""
        now = timezone.now()
        return self.get_queryset().for_referrer(user).unpaid().update(
            is_paid=True, paid_at=now
        )

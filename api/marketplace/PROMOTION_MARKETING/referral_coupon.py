"""
PROMOTION_MARKETING/referral_coupon.py — Referral Program
===========================================================
- Each user gets a unique referral code
- Referee gets 5% off first order (max 100 BDT)
- Referrer earns 50 BDT wallet credit after referee's first purchase
- Tracks referral chain, prevents self-referral & fraud
"""
from __future__ import annotations
import logging
from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from api.marketplace.utils import generate_coupon_code

logger = logging.getLogger(__name__)

REFEREE_DISCOUNT_PERCENT = Decimal("5")
REFEREE_MAX_DISCOUNT_BDT = Decimal("100")
REFERRER_CREDIT_BDT      = Decimal("50")


class ReferralProgram(models.Model):
    tenant       = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                      related_name="referral_programs_tenant")
    referrer     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name="referrals_made")
    referee      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name="referred_by_referral", null=True, blank=True)
    referral_code= models.CharField(max_length=20, unique=True)
    is_used      = models.BooleanField(default=False)
    used_at      = models.DateTimeField(null=True, blank=True)
    order_id     = models.IntegerField(null=True, blank=True)
    referrer_credited = models.BooleanField(default=False)
    referee_discount_given = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_referral_program"
        indexes   = [models.Index(fields=["referral_code"])]

    def __str__(self):
        return f"Referral {self.referral_code} by {self.referrer.username}"


class ReferralService:

    @classmethod
    def get_or_create_code(cls, user, tenant) -> str:
        ref = ReferralProgram.objects.filter(referrer=user, tenant=tenant, referee__isnull=True).first()
        if ref:
            return ref.referral_code
        code = f"REF{user.pk}{generate_coupon_code(4)}"
        ReferralProgram.objects.create(tenant=tenant, referrer=user, referral_code=code)
        return code

    @classmethod
    def apply_referral_code(cls, referee_user, tenant, code: str) -> dict:
        if referee_user.date_joined and (timezone.now() - referee_user.date_joined).days > 3:
            return {"valid": False, "reason": "Referral codes only valid within 3 days of registration"}
        try:
            ref = ReferralProgram.objects.get(referral_code=code, tenant=tenant, referee__isnull=True)
        except ReferralProgram.DoesNotExist:
            return {"valid": False, "reason": "Invalid referral code"}
        if ref.referrer == referee_user:
            return {"valid": False, "reason": "Cannot use your own referral code"}
        ref.referee = referee_user
        ref.save(update_fields=["referee"])
        discount_pct = int(REFEREE_DISCOUNT_PERCENT)
        return {
            "valid": True,
            "discount_percent": discount_pct,
            "max_discount_bdt": str(REFEREE_MAX_DISCOUNT_BDT),
            "message": f"Welcome! You get {discount_pct}% off your first order (max {REFEREE_MAX_DISCOUNT_BDT} BDT)"
        }

    @classmethod
    @transaction.atomic
    def on_first_purchase(cls, referee_user, tenant, order_id: int, order_amount: Decimal):
        ref = ReferralProgram.objects.filter(
            referee=referee_user, tenant=tenant, is_used=False
        ).select_for_update().first()
        if not ref:
            return
        ref.is_used = True
        ref.used_at = timezone.now()
        ref.order_id = order_id
        ref.referee_discount_given = True
        ref.referrer_credited = True
        ref.save()
        # Credit referrer with wallet balance
        try:
            from api.marketplace.PROMOTION_MARKETING.loyalty_reward import LoyaltyService
            LoyaltyService.award_bonus(
                ref.referrer, tenant,
                points=int(REFERRER_CREDIT_BDT * 10),
                reason=f"Referral bonus: {referee_user.username} made first purchase",
                tx_type="referral",
            )
        except Exception as e:
            logger.error("[Referral] Credit failed: %s", e)
        logger.info("[Referral] Code %s: referee=%s, referrer credited", ref.referral_code, referee_user.username)

    @classmethod
    def calculate_referee_discount(cls, order_amount: Decimal) -> Decimal:
        disc = order_amount * REFEREE_DISCOUNT_PERCENT / 100
        return min(disc, REFEREE_MAX_DISCOUNT_BDT).quantize(Decimal("0.01"))

    @classmethod
    def stats(cls, user, tenant) -> dict:
        qs = ReferralProgram.objects.filter(referrer=user, tenant=tenant, referee__isnull=False)
        return {
            "total_referrals":    qs.count(),
            "successful":         qs.filter(is_used=True).count(),
            "pending":            qs.filter(is_used=False).count(),
            "total_credits_earned": str(qs.filter(referrer_credited=True).count() * REFERRER_CREDIT_BDT),
        }

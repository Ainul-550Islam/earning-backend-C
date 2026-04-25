# api/wallet/services/cpalead/CPALeadService.py
"""
CPAlead-style affiliate system service.
Handles: offer conversion, smart link routing, content lock, offer wall.
Integrates with GeoRate, PublisherLevel, PointsLedger, PerformanceBonus.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("wallet.service.cpalead")


class CPALeadService:

    # ── GEO rate lookup ──────────────────────────────────────────
    TIER1_COUNTRIES = {"US","GB","CA","AU","NZ"}
    TIER2_COUNTRIES = {"DE","FR","NL","JP","SG","KR","AE","SE","NO","DK","FI","CH"}

    @staticmethod
    def get_geo_rate(country_code: str) -> Decimal:
        """Return earning multiplier for a country (CPAlead Tier system)."""
        try:
            from ...models_cpalead_extra import GeoRate
            geo = GeoRate.objects.filter(country_code=country_code.upper(), is_active=True).first()
            if geo:
                return geo.rate_multiplier
        except Exception:
            pass
        code = country_code.upper()
        if code in CPALeadService.TIER1_COUNTRIES: return Decimal("2.50")
        if code in CPALeadService.TIER2_COUNTRIES: return Decimal("1.50")
        if code == "BD":                           return Decimal("1.00")
        return Decimal("0.80")

    @staticmethod
    def get_tier_multiplier(user) -> Decimal:
        """Return earning multiplier for user tier."""
        from ...constants import TIER_EARN_BONUS
        tier = getattr(user, "tier", "FREE")
        return TIER_EARN_BONUS.get(tier, Decimal("1.00"))

    @staticmethod
    def get_performance_bonus(user, wallet, base_amount: Decimal) -> Decimal:
        """Return any active performance bonus amount."""
        bonus = Decimal("0")
        try:
            from ...models_cpalead_extra import PerformanceBonus
            for pb in PerformanceBonus.objects.filter(user=user, wallet=wallet, status="active"):
                if not pb.is_active_now(): continue
                b = (base_amount * pb.bonus_percent / 100).quantize(Decimal("0.00000001"))
                if pb.max_bonus:
                    b = min(b, pb.max_bonus - pb.total_paid)
                bonus += max(b, Decimal("0"))
                pb.total_paid += bonus
                pb.save(update_fields=["total_paid"])
        except Exception as e:
            logger.debug(f"Performance bonus skip: {e}")
        return bonus

    @staticmethod
    @transaction.atomic
    def record_conversion(
        offer_id: int, user, wallet,
        click_id: str = "", ip_address: str = "",
        country_code: str = "", device_type: str = "",
    ) -> dict:
        """
        Record a CPA/CPI/CPC conversion and credit earnings.
        Full pipeline: cap check → GEO rate → tier mult → perf bonus → credit.
        """
        from ...models_cpalead_extra import EarningOffer, OfferConversion
        from ..core.WalletService import WalletService
        from ...choices import TransactionType

        offer = EarningOffer.objects.select_for_update().get(id=offer_id, is_active=True)

        # Cap check
        if offer.is_capped():
            raise ValueError(f"Offer '{offer.title}' daily/total cap reached")

        # Publisher level check
        try:
            from ...models_cpalead_extra import PublisherLevel
            pl = PublisherLevel.objects.get(wallet=wallet)
            if pl.level < offer.min_publisher_level:
                raise ValueError(f"Publisher Level {offer.min_publisher_level}+ required")
        except PublisherLevel.DoesNotExist:
            pass

        # Compute final payout
        base = offer.payout_bdt or offer.payout
        geo_mult  = CPALeadService.get_geo_rate(country_code)
        tier_mult = CPALeadService.get_tier_multiplier(user)
        payout    = (base * geo_mult * tier_mult).quantize(Decimal("0.00000001"))
        perf_bonus = CPALeadService.get_performance_bonus(user, wallet, payout)
        total_payout = payout + perf_bonus

        txn = WalletService.credit(
            wallet=wallet,
            amount=total_payout,
            txn_type=offer.offer_type,
            description=f"{offer.get_offer_type_display()}: {offer.title}",
            reference_id=str(offer.offer_id),
            reference_type=offer.offer_type,
            metadata={"offer_id":offer.id,"click_id":click_id,"country":country_code,
                      "geo_mult":str(geo_mult),"tier_mult":str(tier_mult),"perf_bonus":str(perf_bonus)},
            ip_address=ip_address,
            country_code=country_code,
        )

        conversion = OfferConversion.objects.create(
            offer=offer, user=user, wallet=wallet, transaction=txn,
            status="approved", payout=total_payout,
            click_id=click_id, ip_address=ip_address,
            country_code=country_code, device_type=device_type,
            approved_at=timezone.now(),
        )

        offer.conversions_today  += 1
        offer.total_conversions  += 1
        offer.save(update_fields=["conversions_today","total_conversions","updated_at"])

        # Award points
        try:
            from ...models_cpalead_extra import PointsLedger
            pl, _ = PointsLedger.objects.get_or_create(user=user, wallet=wallet)
            pl.award(total_payout)
        except Exception:
            pass

        logger.info(f"CPA conversion: offer={offer.title} user={user.id} payout={total_payout}")
        return {
            "conversion_id":  conversion.id,
            "payout":         float(total_payout),
            "geo_multiplier": float(geo_mult),
            "tier_multiplier":float(tier_mult),
            "performance_bonus":float(perf_bonus),
            "txn_id":         str(txn.txn_id),
        }

    @staticmethod
    def add_referral(referrer_wallet, base_amount: Decimal, level: int, referred_user_id) -> dict:
        """
        Pay CPAlead 3-level referral commission (6-month validity check).
        L1=10%, L2=5%, L3=2%
        """
        from ...constants import REFERRAL_RATES
        from ..core.WalletService import WalletService

        rate = REFERRAL_RATES.get(level, Decimal("0"))
        if not rate: return {"skipped": True}

        # Check 6-month validity
        try:
            from ...models_cpalead_extra import ReferralProgram
            from django.contrib.auth import get_user_model
            referred = get_user_model().objects.get(id=referred_user_id)
            ref = ReferralProgram.objects.filter(
                referrer=referrer_wallet.user, referred=referred,
                level=level, is_active=True,
            ).first()
            if ref and not ref.is_valid():
                logger.info(f"Referral expired: L{level} {referrer_wallet.user.username}←{referred.username}")
                return {"skipped": True, "reason": "expired"}
        except Exception:
            pass

        commission = (Decimal(str(base_amount)) * rate).quantize(Decimal("0.00000001"))
        if commission <= 0:
            return {"skipped": True}

        txn = WalletService.credit(
            wallet=referrer_wallet,
            amount=commission,
            txn_type="referral",
            description=f"Referral L{level} ({int(rate*100)}%) from user {referred_user_id}",
            reference_id=str(referred_user_id),
            reference_type="referral",
        )

        # Update referral program total
        try:
            ref.total_earned += commission
            ref.save(update_fields=["total_earned"])
        except Exception:
            pass

        return {"txn_id": str(txn.txn_id), "commission": float(commission), "level": level}

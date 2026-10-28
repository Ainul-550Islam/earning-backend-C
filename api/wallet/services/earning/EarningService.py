# api/wallet/services/earning/EarningService.py
"""
Record earnings from all sources: tasks, offers, CPA/CPI/CPC, referrals,
surveys, daily rewards, streaks, bonuses.

Every earning:
  1. Checks EarningCap (daily cap enforcement)
  2. Applies GEO rate multiplier (country_code)
  3. Applies tier bonus multiplier (user tier)
  4. Applies performance bonus (CPAlead up to 20%)
  5. Credits WalletService.credit()
  6. Creates EarningRecord
  7. [NEW] Creates OfferConversion when source_type is CPA/CPI/CPC/OFFER_WALL
  8. Updates EarningStreak
  9. Awards points (CPAlead 1000pts/$1)
"""
import logging
from decimal import Decimal
from datetime import date

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ...models import Wallet, EarningSource, EarningRecord, EarningStreak
from ...choices import EarningSourceType, TransactionType
from ...exceptions import InvalidAmountError
from ...constants import REFERRAL_RATES
from api.wallet.models.core import WalletTransaction

logger = logging.getLogger("wallet.service.earning")

# Source types that produce an OfferConversion record
OFFER_CONVERSION_TYPES = {
    EarningSourceType.CPA,
    EarningSourceType.CPI,
    EarningSourceType.CPC,
    EarningSourceType.OFFER_WALL,
}


class EarningService:

    @staticmethod
    @transaction.atomic
    def add_earning(
        wallet: Wallet,
        amount: Decimal,
        source_type: str = EarningSourceType.TASK,
        source_id: str = "",
        source: EarningSource = None,
        description: str = "",
        country_code: str = "",
        ip_address: str = None,
        device_type: str = "",
        metadata: dict = None,
        idempotency_key: str = "",
        check_cap: bool = True,
        # ── OfferConversion extras (only used when source_type is offer-based) ──
        click_id: str = "",
        sub_id: str = "",
        user_agent: str = "",
        conversion_status: str = "approved",
    ) -> dict:
        """
        Record an earning for a user. Full pipeline including cap check,
        multipliers, streak update, points award.

        When source_type is CPA / CPI / CPC / OFFER_WALL and `source` resolves
        to an EarningOffer, an OfferConversion record is created automatically
        so the conversion audit trail is always complete.

        Returns dict with txn, record, conversion (or None), streak_result.
        """
        from ..core.WalletService import WalletService
        from .EarningCapService import EarningCapService

        amount = Decimal(str(amount))
        if amount <= 0:
            raise InvalidAmountError(f"Earning amount must be positive, got {amount}")

        # ── Cap check ─────────────────────────────────────────────────
        if check_cap:
            allowed, remaining = EarningCapService.check(wallet, amount, source_type, source)
            if not allowed:
                raise InvalidAmountError(
                    f"Daily earning cap reached for source_type={source_type}. "
                    f"Remaining: {remaining}"
                )

        # ── Determine TXN type ────────────────────────────────────────
        TYPE_MAP = {
            EarningSourceType.CPA:          TransactionType.CPA,
            EarningSourceType.CPI:          TransactionType.CPI,
            EarningSourceType.CPC:          TransactionType.CPC,
            EarningSourceType.SURVEY:       TransactionType.SURVEY,
            EarningSourceType.OFFER_WALL:   TransactionType.OFFER_WALL,
            EarningSourceType.REFERRAL:     TransactionType.REFERRAL,
            EarningSourceType.BONUS:        TransactionType.BONUS,
            EarningSourceType.DAILY_REWARD: TransactionType.REWARD,
            EarningSourceType.STREAK:       TransactionType.BONUS,
            EarningSourceType.CONTEST:      TransactionType.CONTEST_PRIZE,
            EarningSourceType.CASHBACK:     TransactionType.CASHBACK,
        }
        txn_type = TYPE_MAP.get(source_type, TransactionType.EARNING)

        # ── Credit wallet (handles GEO + tier + bonus) ────────────────
        original_amount = amount
        txn = WalletService.credit(
            wallet=wallet,
            amount=amount,
            txn_type=txn_type,
            description=description or f"Earning: {source_type}",
            reference_id=str(source_id),
            reference_type=source_type,
            metadata={**(metadata or {}), "source_type": source_type, "source_id": str(source_id)},
            idempotency_key=idempotency_key,
            ip_address=ip_address,
            country_code=country_code,
        )

        # ── EarningRecord ─────────────────────────────────────────────
        credited = txn.amount  # may differ from original due to multipliers
        record = EarningRecord(
            wallet=wallet,
            source=source,
            transaction=txn,
            source_type=source_type,
            source_ref_id=str(source_id),
            amount=credited,
            original_amount=original_amount,
            country_code=country_code,
            device_type=device_type,
            ip_address=ip_address,
            metadata=metadata or {},
        )
        record.save()

        # ── OfferConversion (CPA / CPI / CPC / OFFER_WALL) ───────────
        conversion = None
        if source_type in OFFER_CONVERSION_TYPES:
            conversion = EarningService._create_offer_conversion(
                wallet=wallet,
                txn=txn,
                source=source,
                source_id=source_id,
                credited=credited,
                country_code=country_code,
                ip_address=ip_address,
                device_type=device_type,
                click_id=click_id,
                sub_id=sub_id,
                user_agent=user_agent,
                conversion_status=conversion_status,
            )

        # ── Streak update ─────────────────────────────────────────────
        streak_result = EarningService._update_streak(wallet, txn, record)

        logger.info(f"Earning: wallet={wallet.id} type={source_type} "
                    f"original={original_amount} credited={credited}"
                    + (f" conversion={conversion.id}" if conversion else ""))

        return {
            "txn":          txn,
            "record":       record,
            "conversion":   conversion,
            "streak":       streak_result,
            "credited":     str(credited),
            "original":     str(original_amount),
        }

    # ─────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _create_offer_conversion(
        wallet: Wallet,
        txn,
        source,          # EarningSource | None
        source_id: str,
        credited: Decimal,
        country_code: str,
        ip_address,
        device_type: str,
        click_id: str,
        sub_id: str,
        user_agent: str,
        conversion_status: str,
    ):
        """
        Create an OfferConversion row tied to the transaction.

        Strategy (in priority order):
          1. source is already an EarningOffer  → use directly
          2. source is an EarningSource with external_id  → look up EarningOffer
          3. source_id looks like an EarningOffer PK (numeric)  → look up by PK
          4. No offer found  → still create the conversion with offer=None
             so the payout is auditable even without a linked offer record.
        """
        try:
            from ...models_cpalead_extra import OfferConversion, EarningOffer

            # Resolve EarningOffer
            earning_offer = None
            if source is not None:
                # source might *be* an EarningOffer (duck-typed)
                if isinstance(source, EarningOffer):
                    earning_offer = source
                elif hasattr(source, "external_id") and source.external_id:
                    earning_offer = EarningOffer.objects.filter(
                        offer_id=source.external_id
                    ).first()

            if earning_offer is None and source_id:
                # Try numeric PK lookup
                try:
                    earning_offer = EarningOffer.objects.get(pk=int(source_id))
                except (ValueError, EarningOffer.DoesNotExist):
                    pass

            if earning_offer is None:
                logger.debug(
                    f"EarningService._create_offer_conversion: no EarningOffer found "
                    f"for source_id={source_id!r}; skipping OfferConversion creation."
                )
                return None

            conversion = OfferConversion.objects.create(
                offer=earning_offer,
                user=wallet.user,
                wallet=wallet,
                transaction=txn,
                status=conversion_status,
                payout=credited,
                click_id=click_id or "",
                sub_id=sub_id or "",
                ip_address=ip_address,
                user_agent=user_agent or "",
                country_code=country_code or "",
                device_type=device_type or "",
                approved_at=timezone.now() if conversion_status == "approved" else None,
            )

            # Keep offer aggregate counters up-to-date
            if conversion_status == "approved":
                EarningOffer.objects.filter(pk=earning_offer.pk).update(
                    conversions_today=earning_offer.__class__.objects.filter(
                        pk=earning_offer.pk
                    ).values_list("conversions_today", flat=True)[0] + 1,
                    total_conversions=earning_offer.__class__.objects.filter(
                        pk=earning_offer.pk
                    ).values_list("total_conversions", flat=True)[0] + 1,
                )

            return conversion

        except Exception as exc:
            # Never let conversion bookkeeping break the actual earning credit.
            logger.warning(
                f"EarningService._create_offer_conversion failed "
                f"(source_id={source_id!r}): {exc}",
                exc_info=True,
            )
            return None

    # ─────────────────────────────────────────────────────────────────
    # Public API — unchanged below this line
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def add_referral(
        referrer_wallet: Wallet,
        base_earning: Decimal,
        level: int,
        referred_user_id,
        idempotency_key: str = "",
    ) -> "WalletTransaction | None":
        """
        Pay referral commission to referrer.
        Level 1 = 10%, Level 2 = 5%, Level 3 = 2% (6-month window).
        """
        rate = REFERRAL_RATES.get(level, Decimal("0"))
        if rate == 0:
            return None

        # CPAlead: check 6-month validity
        try:
            from ...models_cpalead_extra import ReferralProgram
            from django.contrib.auth import get_user_model
            referred = get_user_model().objects.get(id=referred_user_id)
            ref = ReferralProgram.objects.filter(
                referrer=referrer_wallet.user, referred=referred, is_active=True
            ).first()
            if ref and not ref.is_valid():
                logger.info(f"Referral expired: {referrer_wallet.user.username} ← {referred.username}")
                return None
        except Exception:
            pass

        commission = (Decimal(str(base_earning)) * rate).quantize(Decimal("0.00000001"))
        if commission <= 0:
            return None

        result = EarningService.add_earning(
            wallet=referrer_wallet,
            amount=commission,
            source_type=EarningSourceType.REFERRAL,
            source_id=str(referred_user_id),
            description=f"Referral L{level} commission ({int(rate*100)}%) on {base_earning}",
            idempotency_key=idempotency_key,
        )

        # Update referral program total
        try:
            ref.total_earned += commission
            ref.save(update_fields=["total_earned"])
        except Exception:
            pass

        return result["txn"]

    @staticmethod
    def get_breakdown(wallet: Wallet, days: int = 30) -> dict:
        """Return earnings breakdown by source type for last N days."""
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        records = EarningRecord.objects.filter(wallet=wallet, earned_at__gte=since)

        by_type = {}
        total   = Decimal("0")
        for record in records:
            st = record.source_type
            by_type.setdefault(st, {"count": 0, "total": Decimal("0")})
            by_type[st]["count"] += 1
            by_type[st]["total"] += record.amount
            total += record.amount

        # Daily chart for last 30 days
        daily_chart = {}
        for i in range(days):
            d = (timezone.now() - timedelta(days=i)).date()
            day_total = records.filter(earned_at__date=d).aggregate(t=Sum("amount"))["t"] or Decimal("0")
            daily_chart[str(d)] = float(day_total)

        return {
            "total":       float(total),
            "days":        days,
            "by_type":     {k: {"count": v["count"], "total": float(v["total"])} for k, v in by_type.items()},
            "daily_chart": daily_chart,
        }

    @staticmethod
    def _update_streak(wallet: Wallet, txn, record) -> dict:
        """Update earning streak and award streak bonuses."""
        try:
            streak, _ = EarningStreak.objects.get_or_create(wallet=wallet)
            result = streak.update_streak(record.earned_at.date())

            if result.get("bonus") and result["bonus"] > 0:
                from ..core.WalletService import WalletService
                WalletService.credit(
                    wallet=wallet,
                    amount=result["bonus"],
                    txn_type=TransactionType.BONUS,
                    description=f"Streak {result['milestone']}-day milestone bonus",
                    metadata={"milestone": result["milestone"], "streak": result["streak"]},
                )
                logger.info(f"Streak bonus: wallet={wallet.id} "
                            f"days={result['milestone']} bonus={result['bonus']}")

            return result
        except Exception as e:
            logger.debug(f"Streak update skip: {e}")
            return {}

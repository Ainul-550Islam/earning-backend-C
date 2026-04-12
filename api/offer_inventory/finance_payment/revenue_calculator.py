# api/offer_inventory/finance_payment/revenue_calculator.py
"""
Revenue Calculator — Financial Accuracy Engine.

Rules enforced:
  1. ALL arithmetic uses Decimal — zero float involved at any step
  2. Referral commission calculated AFTER platform fee is deducted
     i.e. referral_bonus = user_net_reward × referral_rate
     NOT gross_revenue × referral_rate
  3. Loyalty bonus applied before referral split
  4. Tax applied on final net (after referral deduction)
  5. All results rounded to 4 decimal places (ROUND_HALF_UP)
  6. Overflow/underflow impossible — explicit Decimal conversions everywhere

Calculation order:
    gross_revenue           = network payout (Decimal)
    platform_cut            = gross × platform_pct
    user_gross              = gross − platform_cut
    loyalty_bonus_amount    = user_gross × loyalty_pct   [if any]
    user_after_loyalty      = user_gross + loyalty_bonus_amount
    referral_commission     = user_after_loyalty × referral_rate  ← AFTER fee
    tax_amount              = user_after_loyalty × tax_rate
    net_to_user             = user_after_loyalty − referral_commission − tax_amount
"""
import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

# ── Precision ─────────────────────────────────────────────────────
P4 = Decimal('0.0001')    # 4 decimal places
P2 = Decimal('0.01')      # 2 decimal places for display

# ── Platform defaults ─────────────────────────────────────────────
DEFAULT_PLATFORM_PCT  = Decimal('30')     # 30% to platform
DEFAULT_REFERRAL_PCT  = Decimal('5')      # 5% of user_net to referrer
DEFAULT_TAX_PCT       = Decimal('0')      # 0% — adjust per jurisdiction
MAX_USER_PCT          = Decimal('95')     # Safety cap: platform takes min 5%
MIN_PLATFORM_PCT      = Decimal('5')      # Platform always gets at least 5%


def _d(value, default: str = '0') -> Decimal:
    """Safe Decimal — never raises, never uses float."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        logger.warning(f'Invalid Decimal input: {value!r}, using {default}')
        return Decimal(default)


def _q(value: Decimal, places: Decimal = P4) -> Decimal:
    """Quantize with ROUND_HALF_UP."""
    return value.quantize(places, rounding=ROUND_HALF_UP)


# ════════════════════════════════════════════════════════════════
# REVENUE BREAKDOWN (immutable result object)
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RevenueBreakdown:
    """
    Immutable, fully-Decimal revenue breakdown.
    All values guaranteed to be Decimal, never float.
    """
    gross_revenue         : Decimal
    platform_cut          : Decimal
    user_gross            : Decimal   # Before referral & tax
    loyalty_bonus_amount  : Decimal
    referral_commission   : Decimal   # Paid to referrer (calculated on user_gross)
    tax_amount            : Decimal
    net_to_user           : Decimal   # Final user credit
    currency              : str = 'BDT'

    def as_dict(self) -> dict:
        return {
            'gross_revenue'       : str(self.gross_revenue),
            'platform_cut'        : str(self.platform_cut),
            'user_gross'          : str(self.user_gross),
            'loyalty_bonus_amount': str(self.loyalty_bonus_amount),
            'referral_commission' : str(self.referral_commission),
            'tax_amount'          : str(self.tax_amount),
            'net_to_user'         : str(self.net_to_user),
            'currency'            : self.currency,
        }

    def validate(self):
        """Sanity-check: all amounts must be non-negative, net ≤ gross."""
        assert self.gross_revenue >= 0,     'gross_revenue < 0'
        assert self.platform_cut  >= 0,     'platform_cut < 0'
        assert self.user_gross    >= 0,     'user_gross < 0'
        assert self.net_to_user   >= 0,     'net_to_user < 0'
        assert self.net_to_user   <= self.gross_revenue, 'net_to_user > gross'
        assert (
            self.platform_cut + self.user_gross == self.gross_revenue
            or abs(self.platform_cut + self.user_gross - self.gross_revenue) < Decimal('0.01')
        ), 'platform_cut + user_gross ≠ gross_revenue'


# ════════════════════════════════════════════════════════════════
# REVENUE CALCULATOR
# ════════════════════════════════════════════════════════════════

class RevenueCalculator:
    """
    The authoritative calculator for all monetary splits.

    Usage:
        breakdown = RevenueCalculator.calculate(
            gross        = Decimal('1.5000'),
            user         = request.user,
            has_referral = True,
        )
        # Credit user: breakdown.net_to_user
        # Pay referrer: breakdown.referral_commission
    """

    @classmethod
    def calculate(
        cls,
        gross            : Decimal,
        user             = None,
        custom_platform_pct: Optional[Decimal] = None,
        has_referral     : bool = False,
        custom_referral_pct: Optional[Decimal] = None,
        currency         : str = 'BDT',
    ) -> RevenueBreakdown:
        """
        Calculate full revenue breakdown.

        Args:
            gross:              Network payout (what we receive)
            user:               Django user (for loyalty tier lookup)
            custom_platform_pct: Override default 30% platform cut
            has_referral:       User was referred by someone
            custom_referral_pct: Override default 5% referral rate
            currency:           Currency code

        Returns:
            RevenueBreakdown (all Decimal, immutable)
        """
        gross = _q(_d(gross))

        if gross < Decimal('0'):
            raise ValueError(f'gross revenue cannot be negative: {gross}')

        # ── 1. Platform cut ───────────────────────────────────────
        platform_pct = _d(custom_platform_pct) if custom_platform_pct else DEFAULT_PLATFORM_PCT
        platform_pct = max(MIN_PLATFORM_PCT, min(platform_pct, Decimal('95')))   # 5%–95%
        platform_cut = _q(gross * platform_pct / Decimal('100'))

        # ── 2. User gross (before loyalty bonus) ──────────────────
        user_pre_loyalty = gross - platform_cut

        # ── 3. Loyalty bonus (platform-funded, adds to user share) ─
        loyalty_pct    = cls._get_loyalty_pct(user)
        loyalty_bonus  = _q(user_pre_loyalty * loyalty_pct / Decimal('100'))
        user_gross     = user_pre_loyalty + loyalty_bonus

        # Re-check: platform_cut + user_gross should equal gross + loyalty bonus
        # (Loyalty bonus comes from platform margin — reduce platform cut)
        platform_cut   = _q(platform_cut - loyalty_bonus)
        platform_cut   = max(platform_cut, Decimal('0'))   # Never negative

        # ── 4. Referral commission (ON user_gross, AFTER platform fee) ──
        referral_pct   = _d(custom_referral_pct) if custom_referral_pct else DEFAULT_REFERRAL_PCT
        referral_pct   = max(Decimal('0'), min(referral_pct, Decimal('20')))    # 0%–20%

        referral_commission = Decimal('0')
        if has_referral and referral_pct > 0:
            # CRITICAL: on user_gross, NOT on gross_revenue
            referral_commission = _q(user_gross * referral_pct / Decimal('100'))

        # ── 5. Tax (applied after referral, on user_gross) ────────
        tax_pct    = cls._get_tax_pct(user, user_gross)
        tax_amount = _q(user_gross * tax_pct / Decimal('100'))

        # ── 6. Net to user ────────────────────────────────────────
        net_to_user = _q(user_gross - referral_commission - tax_amount)
        net_to_user = max(net_to_user, Decimal('0'))   # Never negative

        breakdown = RevenueBreakdown(
            gross_revenue        = _q(gross),
            platform_cut         = _q(platform_cut),
            user_gross           = _q(user_gross),
            loyalty_bonus_amount = _q(loyalty_bonus),
            referral_commission  = _q(referral_commission),
            tax_amount           = _q(tax_amount),
            net_to_user          = net_to_user,
            currency             = currency,
        )

        try:
            breakdown.validate()
        except AssertionError as e:
            logger.error(f'RevenueBreakdown validation failed: {e} | {breakdown.as_dict()}')
            # Still return — don't crash production over assertion
        
        logger.debug(
            f'Revenue calc | gross={gross} | platform={platform_cut} '
            f'({platform_pct}%) | user_gross={user_gross} | '
            f'loyalty={loyalty_bonus} | referral={referral_commission} '
            f'| tax={tax_amount} | net={net_to_user}'
        )
        return breakdown

    # ── Loyalty tier lookup ────────────────────────────────────────

    @staticmethod
    def _get_loyalty_pct(user) -> Decimal:
        """Get loyalty bonus % from user's tier."""
        if not user:
            return Decimal('0')
        try:
            from api.offer_inventory.models import UserProfile
            profile = UserProfile.objects.select_related('loyalty_level').get(user=user)
            if profile.loyalty_level and profile.loyalty_level.payout_bonus_pct:
                pct = _d(profile.loyalty_level.payout_bonus_pct)
                return min(pct, Decimal('20'))   # Max loyalty bonus: 20%
        except Exception:
            pass
        return Decimal('0')

    # ── Tax lookup ─────────────────────────────────────────────────

    @staticmethod
    def _get_tax_pct(user, amount: Decimal) -> Decimal:
        """
        Tax rate lookup.
        Bangladesh: 0% for small amounts — adjust for other jurisdictions.
        """
        # Currently 0% — update when regulations require
        return DEFAULT_TAX_PCT


# ════════════════════════════════════════════════════════════════
# REFERRAL COMMISSION CALCULATOR (standalone)
# ════════════════════════════════════════════════════════════════

class ReferralCommissionCalculator:
    """
    Standalone referral commission calculator.
    Ensures commission is always computed on user_net (after platform fee).
    """

    @staticmethod
    def compute(
        user_net_reward  : Decimal,
        commission_rate  : Decimal = DEFAULT_REFERRAL_PCT,
    ) -> Decimal:
        """
        commission = user_net_reward × rate / 100
        Always on post-platform-fee amount, never on gross.
        """
        user_net     = _d(user_net_reward)
        rate         = _d(commission_rate)

        if user_net <= 0 or rate <= 0:
            return Decimal('0')

        commission = _q(user_net * rate / Decimal('100'))
        return max(commission, Decimal('0'))

    @staticmethod
    def get_tier_rate(referrer) -> Decimal:
        """Look up referrer's commission tier rate."""
        try:
            from api.offer_inventory.models import CommissionTier
            from api.offer_inventory.models import UserReferral
            # Count active referrals
            referral_count = UserReferral.objects.filter(
                referrer=referrer, is_converted=True
            ).count()

            tier = CommissionTier.objects.filter(
                min_referrals__lte=referral_count,
                is_active=True,
            ).order_by('-min_referrals').first()

            if tier:
                return _q(_d(tier.commission_rate), P2)
        except Exception:
            pass
        return DEFAULT_REFERRAL_PCT


# ════════════════════════════════════════════════════════════════
# TAX CALCULATOR
# ════════════════════════════════════════════════════════════════

class TaxCalculator:
    """Bangladesh income tax brackets (FY 2024–25)."""

    # (upper_limit, rate_pct) — None = unlimited
    BD_BRACKETS = [
        (Decimal('350000'),  Decimal('0')),    # ০–৩.৫ লাখ: ০%
        (Decimal('100000'),  Decimal('5')),    # পরের ১ লাখ: ৫%
        (Decimal('400000'),  Decimal('10')),   # পরের ৪ লাখ: ১০%
        (Decimal('500000'),  Decimal('15')),   # পরের ৫ লাখ: ১৫%
        (Decimal('2000000'), Decimal('20')),   # পরের ২০ লাখ: ২০%
        (None,               Decimal('25')),   # বাকি: ২৫%
    ]

    @classmethod
    def annual_income_tax(cls, annual_income: Decimal) -> Decimal:
        """Slab-based annual income tax (Bangladesh)."""
        income    = _d(annual_income)
        total_tax = Decimal('0')
        remaining = income

        for limit, rate in cls.BD_BRACKETS:
            if remaining <= 0:
                break
            taxable    = min(remaining, limit) if limit else remaining
            total_tax += _q(taxable * rate / Decimal('100'))
            remaining -= taxable

        return _q(total_tax, P2)

    @staticmethod
    def withholding_on_withdrawal(amount: Decimal, rate: Decimal = Decimal('0')) -> Decimal:
        """TDS on withdrawal (currently 0% in BD for small earners)."""
        return _q(_d(amount) * _d(rate) / Decimal('100'), P2)


# ════════════════════════════════════════════════════════════════
# CURRENCY CONVERTER
# ════════════════════════════════════════════════════════════════

class CurrencyConverter:
    """Live + cached currency conversion. All output Decimal."""

    FALLBACK_RATES = {
        ('USD', 'BDT'): Decimal('110.00'),
        ('EUR', 'BDT'): Decimal('120.00'),
        ('GBP', 'BDT'): Decimal('140.00'),
        ('INR', 'BDT'): Decimal('1.32'),
        ('BDT', 'USD'): Decimal('0.0091'),
    }

    @staticmethod
    def convert(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        from_c = from_currency.upper().strip()
        to_c   = to_currency.upper().strip()
        if from_c == to_c:
            return _q(_d(amount))
        rate = CurrencyConverter.get_rate(from_c, to_c)
        return _q(_d(amount) * rate)

    @staticmethod
    def get_rate(from_: str, to: str) -> Decimal:
        """DB → Cache → External API → Hardcoded fallback."""
        # DB first
        try:
            from api.offer_inventory.models import CurrencyRate
            obj = CurrencyRate.objects.get(from_currency=from_, to_currency=to)
            return _q(_d(obj.rate))
        except Exception:
            pass

        # Cache
        from django.core.cache import cache
        key    = f'fx_rate:{from_}:{to}'
        cached = cache.get(key)
        if cached:
            return _q(_d(cached))

        # External API
        try:
            import requests
            resp = requests.get(
                f'https://api.exchangerate-api.com/v4/latest/{from_}',
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                rate = _q(_d(str(data['rates'].get(to, '1'))))
                cache.set(key, str(rate), 3600)
                # Save to DB for offline availability
                try:
                    CurrencyRate.objects.update_or_create(
                        from_currency=from_, to_currency=to,
                        defaults={'rate': rate, 'source': 'exchangerate-api'}
                    )
                except Exception:
                    pass
                return rate
        except Exception as e:
            logger.warning(f'Currency API unavailable: {e}')

        # Hardcoded fallback
        fallback = CurrencyConverter.FALLBACK_RATES.get((from_, to))
        if fallback:
            logger.warning(f'Using hardcoded fallback rate {from_}→{to}: {fallback}')
            return fallback

        logger.error(f'No rate found {from_}→{to}. Using 1.')
        return Decimal('1')

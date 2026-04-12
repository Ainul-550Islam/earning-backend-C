# api/offer_inventory/finance_payment/tax_calculator.py
"""
Tax Calculator — Full Implementation.
Bangladesh income tax rules, TDS on withdrawals,
VAT calculations, and tax record management.
All calculations use Decimal — zero float operations.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

P2 = Decimal('0.01')
P4 = Decimal('0.0001')


def _d(v) -> Decimal:
    try:
        return Decimal(str(v or '0'))
    except Exception:
        return Decimal('0')


class TaxCalculator:
    """
    Bangladesh income tax calculation.
    FY 2024–25 slab rates.
    """

    # Bangladesh income tax slabs (FY 2024–25)
    # (limit, rate%) — None limit = unlimited
    BD_SLABS = [
        (Decimal('350000'),  Decimal('0')),    # ০–৩.৫ লাখ: ০%
        (Decimal('100000'),  Decimal('5')),    # পরের ১ লাখ: ৫%
        (Decimal('300000'),  Decimal('10')),   # পরের ৩ লাখ: ১০%
        (Decimal('400000'),  Decimal('15')),   # পরের ৪ লাখ: ১৫%
        (Decimal('500000'),  Decimal('20')),   # পরের ৫ লাখ: ২০%
        (None,               Decimal('25')),   # বাকি সব: ২৫%
    ]

    # Minimum taxable income
    MIN_TAXABLE = Decimal('350000')   # ৩.৫ লাখ

    # TDS rates
    TDS_ON_WITHDRAWAL_PCT = Decimal('0')      # Currently 0% for small earners
    TDS_THRESHOLD         = Decimal('100000') # ১ লাখ+ withdrawal triggers TDS consideration

    # VAT rate (on platform fee)
    VAT_RATE = Decimal('15')   # 15% VAT on service fee (Bangladesh standard)

    @classmethod
    def calculate_annual_tax(cls, annual_income: Decimal) -> Decimal:
        """
        Slab-based annual income tax.
        Returns tax amount (Decimal).
        """
        income    = _d(annual_income)
        total_tax = Decimal('0')
        remaining = income

        for limit, rate in cls.BD_SLABS:
            if remaining <= 0:
                break
            taxable    = min(remaining, limit) if limit else remaining
            slab_tax   = (taxable * rate / Decimal('100')).quantize(P2, rounding=ROUND_HALF_UP)
            total_tax += slab_tax
            remaining -= taxable

        return total_tax.quantize(P2, rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_effective_rate(cls, annual_income: Decimal) -> Decimal:
        """Effective tax rate as percentage."""
        income = _d(annual_income)
        if income <= 0:
            return Decimal('0')
        tax  = cls.calculate_annual_tax(income)
        rate = (tax / income * Decimal('100')).quantize(P2, rounding=ROUND_HALF_UP)
        return rate

    @classmethod
    def calculate_tds_on_withdrawal(cls, amount: Decimal) -> Decimal:
        """
        TDS (Tax Deducted at Source) on withdrawal.
        Currently 0% in Bangladesh for small earners.
        Will be non-zero if platform is required to withhold.
        """
        amount = _d(amount)
        if amount < cls.TDS_THRESHOLD:
            return Decimal('0')
        return (amount * cls.TDS_ON_WITHDRAWAL_PCT / Decimal('100')).quantize(P2, rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_vat_on_fee(cls, platform_fee: Decimal) -> Decimal:
        """
        VAT on the platform service fee (15% in Bangladesh).
        This is charged to advertisers, NOT to users.
        """
        fee = _d(platform_fee)
        return (fee * cls.VAT_RATE / Decimal('100')).quantize(P2, rounding=ROUND_HALF_UP)

    @classmethod
    def is_taxable(cls, annual_income: Decimal) -> bool:
        """Check if income exceeds minimum taxable threshold."""
        return _d(annual_income) > cls.MIN_TAXABLE

    @classmethod
    def get_quarterly_advance_tax(cls, annual_income: Decimal) -> Decimal:
        """Quarterly advance tax payment amount."""
        annual_tax = cls.calculate_annual_tax(annual_income)
        return (annual_tax / Decimal('4')).quantize(P2, rounding=ROUND_HALF_UP)

    # ── Tax record management ──────────────────────────────────────

    @staticmethod
    def record_tax(user, tax_type: str, base_amount: Decimal,
                    rate: Decimal, tax_amount: Decimal,
                    reference: str = '') -> object:
        """Create a TaxRecord for audit purposes."""
        from api.offer_inventory.models import TaxRecord
        from django.utils import timezone

        return TaxRecord.objects.create(
            user       =user,
            tax_type   =tax_type,
            rate       =rate,
            base_amount=base_amount,
            tax_amount =tax_amount,
            fiscal_year=f'{timezone.now().year}-{timezone.now().year + 1}',
            reference  =reference,
        )

    @staticmethod
    def get_user_tax_summary(user, year: int = None) -> dict:
        """Get a user's tax summary for a fiscal year."""
        from api.offer_inventory.models import TaxRecord
        from django.db.models import Sum
        from django.utils import timezone

        if year is None:
            year = timezone.now().year

        fiscal_year = f'{year}-{year + 1}'
        records = TaxRecord.objects.filter(user=user, fiscal_year=fiscal_year)
        agg     = records.aggregate(
            total_base=Sum('base_amount'),
            total_tax =Sum('tax_amount'),
        )

        return {
            'fiscal_year'    : fiscal_year,
            'total_income'   : float(agg['total_base'] or 0),
            'total_tax_paid' : float(agg['total_tax']  or 0),
            'effective_rate' : float(
                TaxCalculator.calculate_effective_rate(_d(agg['total_base']))
            ),
            'is_taxable'     : TaxCalculator.is_taxable(_d(agg['total_base'])),
        }

    @staticmethod
    def generate_tax_certificate(user, year: int = None) -> dict:
        """Generate tax certificate data for a user."""
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        if year is None:
            year = timezone.now().year

        summary = TaxCalculator.get_user_tax_summary(user, year)
        return {
            'certificate_type': 'TDS Certificate',
            'platform_name'   : 'Earning Platform',
            'user_name'       : user.get_full_name() or user.username,
            'user_email'      : user.email,
            'fiscal_year'     : summary['fiscal_year'],
            'total_income'    : summary['total_income'],
            'total_tax_deducted': summary['total_tax_paid'],
            'generated_at'    : timezone.now().isoformat(),
        }

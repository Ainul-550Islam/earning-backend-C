# api/promotions/auditing/tax_calculator.py
# Tax Calculator — Country-specific withholding tax, GST/VAT, 1099 reporting
import logging
from dataclasses import dataclass
from decimal import Decimal
logger = logging.getLogger('auditing.tax')

# Withholding tax rates by country (%)
WITHHOLDING_TAX = {
    'US': Decimal('30.0'),   # Non-resident alien withholding
    'IN': Decimal('10.0'),   # TDS on professional services
    'BD': Decimal('10.0'),
    'PK': Decimal('12.5'),
    'PH': Decimal('25.0'),
    'DEFAULT': Decimal('0'),
}

# GST/VAT rates
GST_RATES = {
    'AU': Decimal('10.0'),
    'IN': Decimal('18.0'),
    'GB': Decimal('20.0'),
    'DE': Decimal('19.0'),
    'FR': Decimal('20.0'),
    'BD': Decimal('15.0'),
    'DEFAULT': Decimal('0'),
}

@dataclass
class TaxCalculation:
    gross_usd:       Decimal
    withholding_usd: Decimal
    gst_usd:         Decimal
    net_usd:         Decimal
    country:         str
    tax_breakdown:   dict

class TaxCalculator:
    """
    Tax calculation for payouts.
    Withholding tax + GST/VAT.
    US 1099-K threshold: $600/year.
    """
    US_1099_THRESHOLD = Decimal('600')

    def calculate(self, gross_usd: Decimal, country: str, is_business: bool = False) -> TaxCalculation:
        c          = country.upper()
        w_rate     = WITHHOLDING_TAX.get(c, WITHHOLDING_TAX['DEFAULT'])
        gst_rate   = GST_RATES.get(c, GST_RATES['DEFAULT'])

        # Business accounts — reduced withholding (with valid tax form)
        if is_business:
            w_rate = w_rate * Decimal('0.5')

        w_tax  = (gross_usd * w_rate / 100).quantize(Decimal('0.01'))
        gst    = (gross_usd * gst_rate / 100).quantize(Decimal('0.01'))
        net    = gross_usd - w_tax - gst

        return TaxCalculation(
            gross_usd=gross_usd, withholding_usd=w_tax, gst_usd=gst,
            net_usd=net, country=c,
            tax_breakdown={'withholding_rate': float(w_rate), 'gst_rate': float(gst_rate),
                           'withholding': float(w_tax), 'gst': float(gst)},
        )

    def requires_1099(self, user_id: int, year: int) -> bool:
        """US user এর annual earnings $600+ হলে 1099 required।"""
        try:
            from api.promotions.models import PromotionTransaction
            from django.db.models import Sum
            total = PromotionTransaction.objects.filter(
                user_id=user_id, created_at__year=year
            ).aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')
            return Decimal(str(total)) >= self.US_1099_THRESHOLD
        except Exception:
            return False

    def get_annual_summary(self, user_id: int, year: int) -> dict:
        """Annual tax summary।"""
        try:
            from api.promotions.models import PromotionTransaction
            from django.db.models import Sum, Count
            stats = PromotionTransaction.objects.filter(user_id=user_id, created_at__year=year).aggregate(
                total=Sum('amount_usd'), count=Count('id'))
            gross = Decimal(str(stats['total'] or 0))
            return {'year': year, 'gross_usd': float(gross), 'transactions': stats['count'] or 0,
                    'requires_1099': gross >= self.US_1099_THRESHOLD}
        except Exception:
            return {}

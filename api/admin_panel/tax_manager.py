# api/admin_panel/tax_manager.py
"""Tax calculation, withholding, VAT management for earnings platform."""
from __future__ import annotations
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict
from django.utils import timezone

logger = logging.getLogger(__name__)

# Bangladesh tax rates (example)
VAT_RATE        = Decimal('0.15')   # 15% VAT on commission
TDS_RATE        = Decimal('0.10')   # 10% TDS on payments > 5000
TDS_THRESHOLD   = Decimal('5000')   # BDT


class TaxManager:
    """Tax calculation and withholding management."""

    @classmethod
    def calculate_vat(cls, amount: Decimal) -> Decimal:
        """Calculate VAT on amount."""
        return (amount * VAT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_tds(cls, amount: Decimal) -> Decimal:
        """Calculate TDS (Tax Deducted at Source) for BD payments."""
        if amount >= TDS_THRESHOLD:
            return (amount * TDS_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    @classmethod
    def calculate_net_payout(cls, gross_amount: Decimal,
                              apply_tds: bool = True, apply_vat: bool = False) -> Dict:
        """Calculate net payout after tax deductions."""
        gross = Decimal(str(gross_amount))
        tds = cls.calculate_tds(gross) if apply_tds else Decimal('0')
        vat = cls.calculate_vat(gross) if apply_vat else Decimal('0')
        net = gross - tds - vat
        return {
            'gross_amount': float(gross),
            'tds':          float(tds),
            'vat':          float(vat),
            'total_deduction': float(tds + vat),
            'net_amount':   float(net),
            'tds_applied':  apply_tds,
            'vat_applied':  apply_vat,
        }

    @classmethod
    def get_tax_report(cls, days: int = 30) -> Dict:
        """Generate tax summary report."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.payout_queue.models import PayoutItem
            from django.db.models import Sum, Count
            paid = PayoutItem.objects.filter(
                status='SUCCESS', processed_at__gte=cutoff
            ).aggregate(gross=Sum('gross_amount'), fee=Sum('fee_amount'), net=Sum('net_amount'))
            gross = Decimal(str(paid['gross'] or 0))
            estimated_tds = cls.calculate_tds(gross)
            return {
                'period_days': days,
                'total_gross': float(gross),
                'total_fees':  float(paid['fee'] or 0),
                'total_net':   float(paid['net'] or 0),
                'estimated_tds': float(estimated_tds),
                'tds_rate': float(TDS_RATE),
                'currency': 'BDT',
            }
        except Exception as e:
            return {'error': str(e)}

    @classmethod
    def set_custom_tax_rate(cls, rate_type: str, rate: float, actor=None) -> bool:
        """Update tax rates in SystemConfig."""
        try:
            from api.admin_panel.models.config import SystemConfig
            SystemConfig.objects.update_or_create(
                key=f'tax_rate_{rate_type}',
                defaults={'value': str(rate), 'group': 'finance', 'value_type': 'float'}
            )
            return True
        except Exception:
            return False

tax_manager = TaxManager()
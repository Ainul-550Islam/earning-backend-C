# api/wallet/reporting/tax_report_generator.py
"""Annual tax report generator."""
import logging
from decimal import Decimal
from datetime import date

logger = logging.getLogger("wallet.reporting.tax")


class TaxReportGenerator:
    """Generate annual tax records (1099-style)."""

    @staticmethod
    def generate_annual(wallet, year: int) -> dict:
        """Generate tax record for a wallet for a given year."""
        from ..models.core import WalletTransaction
        from ..models_cpalead_extra import TaxRecord

        start = date(year, 1, 1)
        end   = date(year, 12, 31)

        # Sum earnings by type
        from django.db.models import Sum
        earnings = WalletTransaction.objects.filter(
            wallet=wallet,
            type__in=["earning","reward","referral","bonus","cpa","cpi","cpc","survey"],
            status__in=["approved","completed"],
            created_at__date__gte=start,
            created_at__date__lte=end,
        )

        total_earned     = earnings.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        total_withdrawn  = WalletTransaction.objects.filter(
            wallet=wallet, type="withdrawal",
            status__in=["approved","completed"],
            created_at__date__gte=start, created_at__date__lte=end,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        total_withdrawn  = abs(total_withdrawn)
        total_fees       = WalletTransaction.objects.filter(
            wallet=wallet, type="withdrawal_fee",
            created_at__date__gte=start, created_at__date__lte=end,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        breakdown = {}
        for txn in earnings.values("type"):
            t = txn["type"]
            sub = earnings.filter(type=t).aggregate(s=Sum("amount"))["s"] or Decimal("0")
            breakdown[t] = str(sub)

        # Create or update TaxRecord
        try:
            rec, created = TaxRecord.objects.update_or_create(
                user=wallet.user, wallet=wallet, tax_year=year,
                defaults={
                    "total_earned":   total_earned,
                    "total_withdrawn":total_withdrawn,
                    "total_fees":     abs(total_fees),
                    "breakdown":      breakdown,
                    "currency":       wallet.currency or "BDT",
                    "status":         "generated",
                }
            )
            logger.info(f"Tax record generated: user={wallet.user_id} year={year}")
            return {"success": True, "tax_record_id": rec.id,
                    "total_earned": float(total_earned), "year": year}
        except Exception as e:
            logger.error(f"Tax record error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_summary(wallet, year: int) -> dict:
        """Get tax summary for display."""
        try:
            from ..models_cpalead_extra import TaxRecord
            rec = TaxRecord.objects.get(user=wallet.user, tax_year=year)
            return {
                "year": year,
                "total_earned": float(rec.total_earned),
                "total_withdrawn": float(rec.total_withdrawn),
                "total_fees": float(rec.total_fees),
                "breakdown": rec.breakdown,
                "status": rec.status,
            }
        except Exception:
            return {"year": year, "total_earned": 0, "status": "not_generated"}

"""database_models/transaction_model.py — Financial transaction view of Conversion."""
from ..models import Conversion
from ..enums import ConversionStatus

class TransactionModel:
    Model = Conversion

    @staticmethod
    def get_credited(days=30):
        from django.utils import timezone
        from datetime import timedelta
        return Conversion.objects.filter(
            wallet_credited=True,
            wallet_credited_at__gte=timezone.now() - timedelta(days=days),
        ).select_related("user", "network")

    @staticmethod
    def get_pending_credit():
        return Conversion.objects.not_credited()

    @staticmethod
    def total_credited_usd(days=30) -> float:
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        result = Conversion.objects.filter(
            wallet_credited=True,
            wallet_credited_at__gte=timezone.now() - timedelta(days=days),
        ).aggregate(t=Sum("actual_payout"))
        return float(result["t"] or 0)

    @staticmethod
    def count_by_status():
        from django.db.models import Count
        return dict(
            Conversion.objects.values("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )

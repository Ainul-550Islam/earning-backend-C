"""database_models/conversion_model.py — Typed proxy for Conversion model."""
from ..models import Conversion
from ..enums import ConversionStatus
from decimal import Decimal

class ConversionModel:
    Model = Conversion

    @staticmethod
    def get_by_id(pk):
        return Conversion.objects.filter(pk=pk).select_related("user", "network", "raw_log").first()

    @staticmethod
    def get_pending():
        return Conversion.objects.pending()

    @staticmethod
    def get_approved():
        return Conversion.objects.approved()

    @staticmethod
    def get_for_user(user, days=30):
        from django.utils import timezone
        from datetime import timedelta
        return Conversion.objects.filter(
            user=user,
            converted_at__gte=timezone.now() - timedelta(days=days),
        ).order_by("-converted_at")

    @staticmethod
    def total_revenue(days=30) -> Decimal:
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        result = Conversion.objects.filter(
            converted_at__gte=timezone.now() - timedelta(days=days),
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        ).aggregate(t=Sum("actual_payout"))
        return result["t"] or Decimal("0")

    @staticmethod
    def get_uncredited():
        return Conversion.objects.not_credited()

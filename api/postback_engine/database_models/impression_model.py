"""database_models/impression_model.py — Typed proxy for Impression model."""
from ..models import Impression

class ImpressionModel:
    Model = Impression

    @staticmethod
    def get_recent(network=None, hours=24):
        from django.utils import timezone
        from datetime import timedelta
        qs = Impression.objects.filter(
            impressed_at__gte=timezone.now() - timedelta(hours=hours)
        )
        return qs.filter(network=network) if network else qs

    @staticmethod
    def count_viewable(offer_id, days=7):
        from django.utils import timezone
        from datetime import timedelta
        return Impression.objects.filter(
            offer_id=offer_id,
            is_viewable=True,
            impressed_at__gte=timezone.now() - timedelta(days=days),
        ).count()

    @staticmethod
    def get_viewability_rate(offer_id, days=7) -> float:
        total = ImpressionModel.get_recent(hours=days * 24).filter(offer_id=offer_id).count()
        viewable = ImpressionModel.count_viewable(offer_id, days)
        return round((viewable / total * 100) if total > 0 else 0, 2)

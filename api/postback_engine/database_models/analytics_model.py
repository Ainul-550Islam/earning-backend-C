"""database_models/analytics_model.py — Typed proxy for NetworkPerformance and HourlyStat."""
from ..models import NetworkPerformance, HourlyStat

class AnalyticsModel:
    NetworkPerformance = NetworkPerformance
    HourlyStat = HourlyStat

    @staticmethod
    def get_network_performance(network, date):
        return NetworkPerformance.objects.filter(network=network, date=date).first()

    @staticmethod
    def get_hourly_series(network, hours=24):
        return HourlyStat.objects.filter(
            network=network
        ).order_by("-date", "-hour")[:hours]

    @staticmethod
    def get_all_performance(days=30):
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        return NetworkPerformance.objects.filter(date__gte=cutoff).order_by("-date")

    @staticmethod
    def get_best_networks(days=30, limit=10):
        from django.db.models import Sum
        from datetime import timedelta
        from django.utils import timezone
        cutoff = timezone.now().date() - timedelta(days=days)
        return (
            NetworkPerformance.objects.filter(date__gte=cutoff)
            .values("network__name", "network__network_key")
            .annotate(total_revenue=Sum("total_payout_usd"), total_convs=Sum("approved_conversions"))
            .order_by("-total_revenue")[:limit]
        )

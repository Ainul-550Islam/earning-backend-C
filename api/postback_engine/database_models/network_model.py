"""database_models/network_model.py — Typed proxy for AdNetworkConfig model."""
from ..models import AdNetworkConfig

class NetworkModel:
    Model = AdNetworkConfig

    @staticmethod
    def get_by_key(key):
        return AdNetworkConfig.objects.get_by_key(key)

    @staticmethod
    def get_all_active():
        return AdNetworkConfig.objects.active()

    @staticmethod
    def count_by_type():
        from django.db.models import Count
        return dict(
            AdNetworkConfig.objects.values("network_type")
            .annotate(c=Count("id"))
            .values_list("network_type", "c")
        )

    @staticmethod
    def get_by_id(pk):
        return AdNetworkConfig.objects.filter(pk=pk).select_related("tenant").first()

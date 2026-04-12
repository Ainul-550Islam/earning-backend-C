"""database_models/click_model.py — Typed proxy for ClickLog model."""
from ..models import ClickLog
from ..enums import ClickStatus

class ClickModel:
    Model = ClickLog

    @staticmethod
    def get_by_click_id(click_id):
        return ClickLog.objects.get_by_click_id(click_id)

    @staticmethod
    def get_valid():
        return ClickLog.objects.valid()

    @staticmethod
    def get_converted():
        return ClickLog.objects.converted()

    @staticmethod
    def get_fraud():
        return ClickLog.objects.fraud()

    @staticmethod
    def get_for_offer(offer_id, days=30):
        from django.utils import timezone
        from datetime import timedelta
        return ClickLog.objects.filter(
            offer_id=offer_id,
            clicked_at__gte=timezone.now() - timedelta(days=days),
        )

    @staticmethod
    def count_for_ip(ip, hours=1):
        from django.utils import timezone
        from datetime import timedelta
        return ClickLog.objects.filter(
            ip_address=ip,
            clicked_at__gte=timezone.now() - timedelta(hours=hours),
        ).count()

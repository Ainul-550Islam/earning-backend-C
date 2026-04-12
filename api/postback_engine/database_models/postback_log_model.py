"""database_models/postback_log_model.py — Typed proxy for PostbackRawLog."""
from ..models import PostbackRawLog
from ..enums import PostbackStatus

class PostbackLogModel:
    Model = PostbackRawLog

    @staticmethod
    def get_by_id(pk):
        return PostbackRawLog.objects.filter(pk=pk).select_related("network").first()

    @staticmethod
    def get_received(limit=100):
        return PostbackRawLog.objects.filter(
            status=PostbackStatus.RECEIVED
        ).order_by("-received_at")[:limit]

    @staticmethod
    def get_failed(limit=100):
        return PostbackRawLog.objects.failed()[:limit]

    @staticmethod
    def get_rewarded(days=30):
        from django.utils import timezone
        from datetime import timedelta
        return PostbackRawLog.objects.filter(
            status=PostbackStatus.REWARDED,
            received_at__gte=timezone.now() - timedelta(days=days),
        )

    @staticmethod
    def count_by_status():
        from django.db.models import Count
        return dict(
            PostbackRawLog.objects
            .values("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )

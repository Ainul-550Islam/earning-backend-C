"""database_models/retry_log_model.py — Typed proxy for RetryLog model."""
from ..models import RetryLog

class RetryLogModel:
    Model = RetryLog

    @staticmethod
    def get_for_object(object_id, retry_type="postback"):
        return RetryLog.objects.filter(
            object_id=object_id, retry_type=retry_type
        ).order_by("-attempted_at")

    @staticmethod
    def get_pending():
        from django.utils import timezone
        return RetryLog.objects.filter(
            succeeded=False,
            next_retry_at__lte=timezone.now(),
        )

    @staticmethod
    def count_by_type():
        from django.db.models import Count
        return dict(
            RetryLog.objects.values("retry_type")
            .annotate(c=Count("id"))
            .values_list("retry_type", "c")
        )

    @staticmethod
    def mark_succeeded(object_id, retry_type="postback"):
        RetryLog.objects.filter(
            object_id=object_id, retry_type=retry_type, succeeded=False
        ).update(succeeded=True, next_retry_at=None)

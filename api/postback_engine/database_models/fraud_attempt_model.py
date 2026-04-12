"""database_models/fraud_attempt_model.py — Typed proxy for FraudAttemptLog."""
from ..models import FraudAttemptLog

class FraudAttemptModel:
    Model = FraudAttemptLog

    @staticmethod
    def get_unreviewed(limit=50):
        return FraudAttemptLog.objects.unreviewed().order_by("-detected_at")[:limit]

    @staticmethod
    def get_auto_blocked():
        return FraudAttemptLog.objects.auto_blocked()

    @staticmethod
    def get_high_score(threshold=80):
        return FraudAttemptLog.objects.high_score(threshold)

    @staticmethod
    def count_by_type():
        from django.db.models import Count
        return dict(
            FraudAttemptLog.objects.values("fraud_type")
            .annotate(c=Count("id"))
            .values_list("fraud_type", "c")
        )

    @staticmethod
    def count_for_ip(ip, hours=24):
        return FraudAttemptLog.objects.recent_count_for_ip(ip, hours)

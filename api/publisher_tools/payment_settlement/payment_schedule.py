# api/publisher_tools/payment_settlement/payment_schedule.py
"""Payment Schedule — Automated payment scheduling."""
from decimal import Decimal
from datetime import date, timedelta
from calendar import monthrange
from typing import Dict, List


def get_next_payment_date(frequency: str, last_payment: date = None) -> date:
    from django.utils import timezone
    today = timezone.now().date()
    if frequency == "monthly":
        # 15th of next month
        if today.month == 12:
            return date(today.year + 1, 1, 15)
        return date(today.year, today.month + 1, 15)
    elif frequency == "bimonthly":
        if today.day < 15:
            return date(today.year, today.month, 15)
        if today.month == 12:
            return date(today.year + 1, 1, 1)
        return date(today.year, today.month + 1, 1)
    elif frequency == "weekly":
        days_ahead = 7 - today.weekday()
        return today + timedelta(days=days_ahead)
    return today + timedelta(days=30)


def get_publishers_due_for_payment() -> List:
    """Payment due publishers list।"""
    from api.publisher_tools.publisher_management.publisher_payout import PayoutSchedule
    from django.utils import timezone
    today = timezone.now().date()
    due_schedules = PayoutSchedule.objects.filter(
        is_automatic=True, is_paused=False, next_payout_date__lte=today,
    ).select_related("publisher")
    return [s.publisher for s in due_schedules if s.publisher.available_balance >= s.min_threshold]


def schedule_batch_payments(publishers: List) -> Dict:
    """Batch payment scheduling।"""
    from django.utils import timezone
    scheduled = []
    for pub in publishers:
        try:
            eligibility = __import__(
                "api.publisher_tools.payment_settlement.payout_manager",
                fromlist=["check_payout_eligibility"]
            ).check_payout_eligibility(pub)
            if eligibility["eligible"]:
                scheduled.append({"publisher_id": pub.publisher_id, "amount": eligibility["balance"], "status": "scheduled"})
        except Exception as e:
            scheduled.append({"publisher_id": pub.publisher_id, "status": "error", "error": str(e)})
    return {"scheduled_at": timezone.now().isoformat(), "count": len(scheduled), "publishers": scheduled}

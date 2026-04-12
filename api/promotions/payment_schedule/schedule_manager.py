# =============================================================================
# promotions/payment_schedule/schedule_manager.py
# Payment Schedule Config — Daily / Net-7 / Net-15 / Net-30
# Based on publisher tier and performance
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

SCHEDULES = {
    'daily':   {'days': 1,  'min_payout': Decimal('1.00'),   'label': 'Daily Pay'},
    'net7':    {'days': 7,  'min_payout': Decimal('10.00'),  'label': 'Weekly (Net-7)'},
    'net15':   {'days': 15, 'min_payout': Decimal('10.00'),  'label': 'Bi-weekly (Net-15)'},
    'net30':   {'days': 30, 'min_payout': Decimal('10.00'),  'label': 'Monthly (Net-30)'},
}

TIER_SCHEDULES = {
    'starter':  'net30',
    'bronze':   'net15',
    'silver':   'net7',
    'gold':     'net7',
    'platinum': 'daily',
}


class PaymentScheduleManager:
    def get_publisher_schedule(self, user_id: int) -> dict:
        from django.core.cache import cache
        tier = 'starter'
        try:
            from api.promotions.models import PublisherProfile
            profile = PublisherProfile.objects.get(user_id=user_id)
            tier = profile.tier
        except Exception:
            pass
        schedule_key = TIER_SCHEDULES.get(tier, 'net30')
        schedule = SCHEDULES[schedule_key]
        return {
            'schedule': schedule_key, 'label': schedule['label'],
            'min_payout': str(schedule['min_payout']),
            'days': schedule['days'],
            'tier': tier,
            'next_payout_date': self._get_next_payout_date(schedule['days']),
        }

    def _get_next_payout_date(self, days: int) -> str:
        from datetime import timedelta
        next_date = timezone.now().date() + timedelta(days=days)
        return str(next_date)

    def get_all_schedules(self) -> dict:
        return {k: {'label': v['label'], 'min': str(v['min_payout']), 'days': v['days']}
                for k, v in SCHEDULES.items()}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_payment_schedule_view(request):
    mgr = PaymentScheduleManager()
    return Response(mgr.get_publisher_schedule(request.user.id))

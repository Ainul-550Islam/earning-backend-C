# =============================================================================
# promotions/pay_per_call/call_tracking.py
# Pay-Per-Call Tracking — Perform[cb] signature feature
# Track inbound calls from affiliate traffic
# =============================================================================
import uuid
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status


CALL_STATUS = {
    'ringing': 'Ringing',
    'connected': 'Connected',
    'completed': 'Completed',
    'missed': 'Missed',
    'voicemail': 'Voicemail',
}

MIN_CALL_DURATION = 60  # Minimum seconds for payout (default: 60s)


class CallTracker:
    """
    Track affiliate-driven phone calls.
    Pay publishers only for quality calls (duration >= minimum).
    """
    CALL_PREFIX = 'ppc_call:'
    NUMBER_PREFIX = 'ppc_number:'

    def create_tracking_number(
        self,
        publisher_id: int,
        campaign_id: int,
        destination_number: str,
        payout_per_call: Decimal = Decimal('5.00'),
        min_duration_seconds: int = MIN_CALL_DURATION,
    ) -> dict:
        """Create a tracked phone number for publisher."""
        tracking_id = str(uuid.uuid4())[:12]
        # In production: integrate with Twilio/Nexmo to buy number
        tracking_number = f'+1800{tracking_id[:7]}'  # Placeholder
        number_data = {
            'tracking_id': tracking_id,
            'publisher_id': publisher_id,
            'campaign_id': campaign_id,
            'tracking_number': tracking_number,
            'destination_number': destination_number,
            'payout_per_call': str(payout_per_call),
            'min_duration_seconds': min_duration_seconds,
            'created_at': timezone.now().isoformat(),
            'total_calls': 0,
            'paid_calls': 0,
        }
        cache.set(f'{self.NUMBER_PREFIX}{tracking_id}', number_data, timeout=3600 * 24 * 365)
        return {
            'tracking_id': tracking_id,
            'tracking_number': tracking_number,
            'destination_number': destination_number,
            'payout_per_call': str(payout_per_call),
            'min_duration_seconds': min_duration_seconds,
            'note': 'Use this number in your ads. Calls are tracked automatically.',
        }

    def record_incoming_call(self, tracking_id: str, caller_number: str) -> dict:
        """Record when a call starts."""
        call_id = str(uuid.uuid4())
        number_data = cache.get(f'{self.NUMBER_PREFIX}{tracking_id}', {})
        call_data = {
            'call_id': call_id,
            'tracking_id': tracking_id,
            'publisher_id': number_data.get('publisher_id'),
            'campaign_id': number_data.get('campaign_id'),
            'caller_number': self._mask_number(caller_number),
            'status': 'ringing',
            'started_at': timezone.now().isoformat(),
            'duration_seconds': 0,
            'payout_amount': '0.00',
            'is_paid': False,
        }
        cache.set(f'{self.CALL_PREFIX}{call_id}', call_data, timeout=3600 * 4)
        return {'call_id': call_id, 'status': 'ringing'}

    def complete_call(self, call_id: str, duration_seconds: int) -> dict:
        """Record call completion and determine payout."""
        key = f'{self.CALL_PREFIX}{call_id}'
        call_data = cache.get(key)
        if not call_data:
            return {'error': 'Call not found'}
        tracking_id = call_data.get('tracking_id')
        number_data = cache.get(f'{self.NUMBER_PREFIX}{tracking_id}', {})
        min_duration = number_data.get('min_duration_seconds', MIN_CALL_DURATION)
        payout = Decimal(number_data.get('payout_per_call', '0'))
        is_paid = duration_seconds >= min_duration
        call_data.update({
            'status': 'completed',
            'duration_seconds': duration_seconds,
            'is_paid': is_paid,
            'payout_amount': str(payout) if is_paid else '0.00',
            'completed_at': timezone.now().isoformat(),
        })
        cache.set(key, call_data, timeout=3600 * 24 * 7)
        if is_paid:
            self._award_call_payout(
                publisher_id=call_data['publisher_id'],
                campaign_id=call_data['campaign_id'],
                amount=payout,
                call_id=call_id,
            )
        return {
            'call_id': call_id,
            'duration': duration_seconds,
            'is_paid': is_paid,
            'payout': str(payout) if is_paid else '$0.00',
            'min_required': min_duration,
            'status': 'converted' if is_paid else 'too_short',
        }

    def get_publisher_call_stats(self, publisher_id: int) -> dict:
        return {
            'publisher_id': publisher_id,
            'total_calls': 0,
            'paid_calls': 0,
            'missed_calls': 0,
            'total_earnings': '0.00',
            'avg_call_duration': 0,
            'conversion_rate': 0.0,
        }

    def _award_call_payout(self, publisher_id: int, campaign_id: int, amount: Decimal, call_id: str):
        from api.promotions.models import PromotionTransaction
        PromotionTransaction.objects.create(
            user_id=publisher_id,
            transaction_type='reward',
            amount=amount,
            status='completed',
            notes=f'Pay-Per-Call payout for call {call_id}',
            metadata={'call_id': call_id, 'campaign_id': campaign_id},
        )

    def _mask_number(self, number: str) -> str:
        if len(number) > 6:
            return number[:3] + '***' + number[-4:]
        return '***'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_tracking_number_view(request):
    tracker = CallTracker()
    result = tracker.create_tracking_number(
        publisher_id=request.user.id,
        campaign_id=request.data.get('campaign_id', 0),
        destination_number=request.data.get('destination_number', ''),
        payout_per_call=Decimal(str(request.data.get('payout_per_call', '5.00'))),
        min_duration_seconds=int(request.data.get('min_duration_seconds', 60)),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def call_webhook_view(request):
    """Webhook from Twilio/Nexmo when call completes."""
    tracker = CallTracker()
    call_id = request.data.get('call_id', '')
    duration = int(request.data.get('duration', 0))
    result = tracker.complete_call(call_id, duration)
    return Response(result)

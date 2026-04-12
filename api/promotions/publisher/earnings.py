# =============================================================================
# promotions/publisher/earnings.py
# Publisher Earnings — Payout requests, history, minimum threshold
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


MINIMUM_PAYOUT = Decimal('10.00')   # CPAlead: $10 minimum
PAYOUT_METHODS = ['paypal', 'payoneer', 'wire_transfer', 'ach', 'crypto_usdt', 'crypto_btc']


class PublisherEarnings:
    """
    Payout management:
    - Check available balance
    - Request payout
    - Payout history
    - Minimum threshold enforcement
    """

    def __init__(self, user_id: int):
        self.user_id = user_id

    def get_balance(self) -> dict:
        """Get current wallet balance breakdown."""
        from api.promotions.models import PromotionTransaction
        txns = PromotionTransaction.objects.filter(user_id=self.user_id)
        rewards = txns.filter(transaction_type='reward').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        commissions = txns.filter(transaction_type='referral').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        bonuses = txns.filter(transaction_type='bonus').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        withdrawals = txns.filter(transaction_type='withdrawal').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        penalties = txns.filter(transaction_type='penalty').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        available = rewards + commissions + bonuses - withdrawals - penalties
        return {
            'available_balance': str(max(available, Decimal('0'))),
            'lifetime_rewards': str(rewards),
            'referral_commissions': str(commissions),
            'bonuses': str(bonuses),
            'total_withdrawn': str(withdrawals),
            'penalties': str(penalties),
            'can_withdraw': available >= MINIMUM_PAYOUT,
            'minimum_payout': str(MINIMUM_PAYOUT),
            'amount_until_payout': str(max(MINIMUM_PAYOUT - available, Decimal('0'))),
        }

    def request_payout(self, amount: Decimal, method: str, method_details: dict) -> dict:
        """Request a payout — validates balance and method."""
        if method not in PAYOUT_METHODS:
            raise ValidationError(f'Invalid payout method. Allowed: {", ".join(PAYOUT_METHODS)}')
        balance = self.get_balance()
        available = Decimal(balance['available_balance'])
        if amount < MINIMUM_PAYOUT:
            raise ValidationError(f'Minimum payout is ${MINIMUM_PAYOUT}')
        if amount > available:
            raise ValidationError(f'Insufficient balance. Available: ${available}')
        from api.promotions.models import PromotionTransaction
        txn = PromotionTransaction.objects.create(
            user_id=self.user_id,
            transaction_type='withdrawal',
            amount=-amount,
            status='pending',
            notes=f'Payout request via {method}',
            metadata={
                'method': method,
                'method_details': method_details,
                'requested_at': timezone.now().isoformat(),
            },
        )
        return {
            'transaction_id': txn.id,
            'amount': str(amount),
            'method': method,
            'status': 'pending',
            'estimated_arrival': self._get_payment_eta(method),
            'message': 'Payout request submitted successfully',
        }

    def get_payout_history(self, page: int = 1, page_size: int = 20) -> dict:
        """Paginated payout history."""
        from api.promotions.models import PromotionTransaction
        offset = (page - 1) * page_size
        withdrawals = PromotionTransaction.objects.filter(
            user_id=self.user_id,
            transaction_type='withdrawal',
        ).order_by('-created_at')[offset:offset + page_size]
        total = PromotionTransaction.objects.filter(
            user_id=self.user_id,
            transaction_type='withdrawal',
        ).count()
        return {
            'count': total,
            'page': page,
            'pages': -(-total // page_size),
            'results': [
                {
                    'id': w.id,
                    'amount': str(abs(w.amount)),
                    'status': w.status,
                    'method': w.metadata.get('method', 'unknown') if w.metadata else 'unknown',
                    'requested_at': w.created_at.isoformat(),
                }
                for w in withdrawals
            ]
        }

    def get_earnings_breakdown(self, days: int = 30) -> dict:
        """Detailed earnings breakdown by source."""
        from api.promotions.models import PromotionTransaction
        cutoff = timezone.now() - timezone.timedelta(days=days)
        by_type = {}
        for txn_type in ['reward', 'referral', 'bonus']:
            amount = PromotionTransaction.objects.filter(
                user_id=self.user_id,
                transaction_type=txn_type,
                created_at__gte=cutoff,
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            by_type[txn_type] = str(amount)
        return {
            'period_days': days,
            'breakdown': by_type,
            'total': str(sum(Decimal(v) for v in by_type.values())),
        }

    def _get_payment_eta(self, method: str) -> str:
        etas = {
            'paypal': '1-2 business days',
            'payoneer': '1-3 business days',
            'ach': '3-5 business days',
            'wire_transfer': '3-7 business days',
            'crypto_usdt': '1-24 hours',
            'crypto_btc': '1-24 hours',
        }
        return etas.get(method, '3-5 business days')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_balance_view(request):
    earnings = PublisherEarnings(user_id=request.user.id)
    return Response(earnings.get_balance())


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_payout_view(request):
    data = request.data
    earnings = PublisherEarnings(user_id=request.user.id)
    try:
        result = earnings.request_payout(
            amount=Decimal(str(data.get('amount', '0'))),
            method=data.get('method', ''),
            method_details=data.get('method_details', {}),
        )
        return Response(result, status=status.HTTP_201_CREATED)
    except (ValidationError, Exception) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_history_view(request):
    earnings = PublisherEarnings(user_id=request.user.id)
    data = earnings.get_payout_history(
        page=int(request.query_params.get('page', 1)),
        page_size=int(request.query_params.get('page_size', 20)),
    )
    return Response(data)

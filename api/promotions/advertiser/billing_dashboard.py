# =============================================================================
# promotions/advertiser/billing_dashboard.py
# Advertiser Billing Dashboard — deposits, spending, invoices
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import uuid


class AdvertiserBillingDashboard:
    """Complete advertiser billing: balance, deposits, spending, invoices."""

    def get_billing_summary(self, advertiser_id: int) -> dict:
        from api.promotions.models import AdvertiserProfile, PromotionTransaction, Campaign
        try:
            profile = AdvertiserProfile.objects.get(user_id=advertiser_id)
            total_deposited = profile.total_deposited
            credit_balance = profile.credit_balance
        except AdvertiserProfile.DoesNotExist:
            total_deposited = credit_balance = Decimal('0')

        campaigns = Campaign.objects.filter(advertiser_id=advertiser_id)
        active_campaigns = campaigns.filter(status='active').count()
        total_budget_locked = campaigns.filter(
            status__in=['active', 'pending', 'paused']
        ).aggregate(t=Sum('total_budget'))['t'] or Decimal('0')

        return {
            'advertiser_id':       advertiser_id,
            'credit_balance':      str(credit_balance),
            'total_deposited':     str(total_deposited),
            'budget_in_campaigns': str(total_budget_locked),
            'available_to_add':    str(max(credit_balance, Decimal('0'))),
            'active_campaigns':    active_campaigns,
            'payment_methods':     self._get_payment_methods(advertiser_id),
            'next_invoice_date':   str(timezone.now().date().replace(day=1)),
        }

    def get_transaction_history(self, advertiser_id: int, page: int = 1, per_page: int = 20) -> dict:
        from api.promotions.models import PromotionTransaction
        offset = (page - 1) * per_page
        txns = PromotionTransaction.objects.filter(
            user_id=advertiser_id,
        ).order_by('-created_at')[offset:offset + per_page]
        total = PromotionTransaction.objects.filter(user_id=advertiser_id).count()
        return {
            'count': total, 'page': page,
            'pages': -(-total // per_page),
            'transactions': [
                {
                    'id': t.id, 'type': t.transaction_type,
                    'amount': str(abs(t.amount)),
                    'status': t.status,
                    'notes': t.notes,
                    'date': t.created_at.isoformat(),
                }
                for t in txns
            ]
        }

    def generate_invoice(self, advertiser_id: int, month: str) -> dict:
        """Generate monthly invoice for advertiser."""
        from api.promotions.models import PromotionTransaction
        from datetime import datetime
        try:
            start = datetime.strptime(month, '%Y-%m').replace(tzinfo=timezone.utc)
        except ValueError:
            return {'error': 'Invalid month format. Use YYYY-MM'}
        import calendar
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])

        spend = PromotionTransaction.objects.filter(
            user_id=advertiser_id,
            transaction_type__in=['escrow_lock', 'escrow_release'],
            created_at__gte=start, created_at__lte=end,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        invoice_id = f'INV-{advertiser_id}-{month.replace("-", "")}-{str(uuid.uuid4())[:4].upper()}'
        return {
            'invoice_id':    invoice_id,
            'advertiser_id': advertiser_id,
            'period':        month,
            'total_spend':   str(abs(spend)),
            'currency':      'USD',
            'status':        'generated',
            'pdf_url':       f'/api/promotions/billing/invoice/{invoice_id}/pdf/',
            'generated_at':  timezone.now().isoformat(),
        }

    def _get_payment_methods(self, advertiser_id: int) -> list:
        return [
            {'type': 'stripe', 'label': 'Credit/Debit Card (Stripe)', 'min': '$10'},
            {'type': 'wire', 'label': 'Wire Transfer', 'min': '$500'},
            {'type': 'crypto', 'label': 'USDT/BTC Crypto', 'min': '$100'},
        ]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def advertiser_billing_view(request):
    """GET /api/promotions/advertiser/billing/"""
    dashboard = AdvertiserBillingDashboard()
    return Response(dashboard.get_billing_summary(request.user.id))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def advertiser_transactions_view(request):
    """GET /api/promotions/advertiser/billing/transactions/"""
    dashboard = AdvertiserBillingDashboard()
    return Response(dashboard.get_transaction_history(
        advertiser_id=request.user.id,
        page=int(request.query_params.get('page', 1)),
    ))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def advertiser_invoice_view(request):
    """GET /api/promotions/advertiser/billing/invoice/?month=2025-04"""
    month = request.query_params.get('month', timezone.now().strftime('%Y-%m'))
    dashboard = AdvertiserBillingDashboard()
    result = dashboard.generate_invoice(request.user.id, month)
    if 'error' in result:
        from rest_framework import status
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)

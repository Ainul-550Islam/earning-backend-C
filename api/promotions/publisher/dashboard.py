# =============================================================================
# promotions/publisher/dashboard.py
# Publisher Dashboard — MaxBounty / CPAlead style real-time dashboard
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class PublisherDashboard:
    """
    Real-time publisher dashboard:
    - Today's earnings, clicks, conversions
    - Campaign performance breakdown
    - Top offers
    - Payout status
    - EPC tracker
    """
    CACHE_TTL = 120  # 2 minutes cache

    def __init__(self, user_id: int):
        self.user_id = user_id

    def get_overview(self, timezone_name: str = 'UTC') -> dict:
        """Main dashboard data — cached for 2 minutes."""
        cache_key = f'publisher_dashboard:{self.user_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        data = self._build_overview()
        cache.set(cache_key, data, timeout=self.CACHE_TTL)
        return data

    def _build_overview(self) -> dict:
        from api.promotions.models import PromotionTransaction, TaskSubmission, UserReputation
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timezone.timedelta(days=7)
        month_start = today_start.replace(day=1)

        # Today's stats
        today_txns = PromotionTransaction.objects.filter(
            user_id=self.user_id,
            transaction_type='reward',
            created_at__gte=today_start,
        )
        today_earnings = today_txns.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        today_conversions = TaskSubmission.objects.filter(
            user_id=self.user_id,
            status='approved',
            updated_at__gte=today_start,
        ).count()

        # Week stats
        week_earnings = PromotionTransaction.objects.filter(
            user_id=self.user_id,
            transaction_type='reward',
            created_at__gte=week_start,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Month stats
        month_earnings = PromotionTransaction.objects.filter(
            user_id=self.user_id,
            transaction_type='reward',
            created_at__gte=month_start,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Total lifetime
        total_earnings = PromotionTransaction.objects.filter(
            user_id=self.user_id,
            transaction_type='reward',
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Pending earnings (submitted not yet approved)
        pending_count = TaskSubmission.objects.filter(
            user_id=self.user_id,
            status='pending',
        ).count()

        # Reputation
        try:
            from api.promotions.models import UserReputation
            rep = UserReputation.objects.get(user_id=self.user_id)
            trust_score = float(rep.trust_score)
            approval_rate = float(rep.approval_rate) if hasattr(rep, 'approval_rate') else 0.0
        except Exception:
            trust_score = 100.0
            approval_rate = 0.0

        # Wallet balance
        available_balance = PromotionTransaction.objects.filter(
            user_id=self.user_id,
        ).aggregate(
            bal=Sum('amount')
        )['bal'] or Decimal('0')

        return {
            'user_id': self.user_id,
            'generated_at': now.isoformat(),
            'earnings': {
                'today': str(today_earnings),
                'this_week': str(week_earnings),
                'this_month': str(month_earnings),
                'total_lifetime': str(total_earnings),
                'available_balance': str(available_balance),
                'pending_approval': str(Decimal('0')),
            },
            'conversions': {
                'today': today_conversions,
                'pending_review': pending_count,
            },
            'performance': {
                'trust_score': trust_score,
                'approval_rate_pct': approval_rate,
                'rank': self._get_publisher_rank(),
            },
            'quick_stats': self._get_quick_stats(),
        }

    def _get_quick_stats(self) -> dict:
        from api.promotions.models import TaskSubmission
        all_subs = TaskSubmission.objects.filter(user_id=self.user_id)
        total = all_subs.count()
        approved = all_subs.filter(status='approved').count()
        rejected = all_subs.filter(status='rejected').count()
        pending = all_subs.filter(status='pending').count()
        return {
            'total_submissions': total,
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
            'approval_rate': round(approved / total * 100, 2) if total > 0 else 0.0,
        }

    def _get_publisher_rank(self) -> int:
        """Get publisher's rank by earnings this month."""
        from api.promotions.models import PromotionTransaction
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        my_earnings = PromotionTransaction.objects.filter(
            user_id=self.user_id,
            transaction_type='reward',
            created_at__gte=month_start,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        better_count = PromotionTransaction.objects.filter(
            transaction_type='reward',
            created_at__gte=month_start,
        ).values('user').annotate(
            total=Sum('amount')
        ).filter(total__gt=my_earnings).count()
        return better_count + 1

    def get_campaign_breakdown(self, limit: int = 10) -> list:
        """Publisher's performance per campaign."""
        from api.promotions.models import TaskSubmission
        from django.db.models import F
        results = TaskSubmission.objects.filter(
            user_id=self.user_id,
        ).values(
            'campaign__id',
            'campaign__title',
        ).annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            pending=Count('id', filter=Q(status='pending')),
            rejected=Count('id', filter=Q(status='rejected')),
        ).order_by('-approved')[:limit]
        return list(results)

    def get_daily_earnings_chart(self, days: int = 30) -> list:
        """Daily earnings for chart — last N days."""
        from api.promotions.models import PromotionTransaction
        from django.db.models.functions import TruncDate
        cutoff = timezone.now() - timezone.timedelta(days=days)
        daily = PromotionTransaction.objects.filter(
            user_id=self.user_id,
            transaction_type='reward',
            created_at__gte=cutoff,
        ).annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            earnings=Sum('amount'),
            count=Count('id'),
        ).order_by('day')
        return [
            {
                'date': str(item['day']),
                'earnings': str(item['earnings']),
                'conversions': item['count'],
            }
            for item in daily
        ]

    def invalidate_cache(self):
        cache.delete(f'publisher_dashboard:{self.user_id}')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_dashboard_view(request):
    """GET /api/promotions/publisher/dashboard/"""
    dashboard = PublisherDashboard(user_id=request.user.id)
    data = dashboard.get_overview()
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_campaign_breakdown_view(request):
    """GET /api/promotions/publisher/campaigns/"""
    dashboard = PublisherDashboard(user_id=request.user.id)
    data = dashboard.get_campaign_breakdown(limit=int(request.query_params.get('limit', 10)))
    return Response({'campaigns': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publisher_earnings_chart_view(request):
    """GET /api/promotions/publisher/earnings/chart/?days=30"""
    days = int(request.query_params.get('days', 30))
    dashboard = PublisherDashboard(user_id=request.user.id)
    data = dashboard.get_daily_earnings_chart(days=days)
    return Response({'chart_data': data, 'days': days})

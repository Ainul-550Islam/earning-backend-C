# api/djoyalty/services/engagement/LeaderboardService.py
import logging
from django.db.models import Sum, F
from ...models.points import LoyaltyPoints

logger = logging.getLogger(__name__)


class LeaderboardService:

    @staticmethod
    def get_top_customers(tenant=None, limit: int = 10, period: str = 'all'):
        """Get top customers by lifetime earned points (basic leaderboard)."""
        try:
            qs = LoyaltyPoints.objects.select_related('customer')
            if tenant:
                qs = qs.filter(tenant=tenant)
            if period == 'monthly':
                from django.utils import timezone
                from datetime import timedelta
                qs = qs.filter(
                    customer__transactions__timestamp__gte=timezone.now() - timedelta(days=30)
                )
            return qs.order_by('-lifetime_earned')[:limit].values(
                'customer__id', 'customer__code',
                'customer__firstname', 'customer__lastname',
                'balance', 'lifetime_earned',
            )
        except Exception as e:
            logger.error('LeaderboardService.get_top_customers error: %s', e)
            return []

    @staticmethod
    def get_top(season=None, limit: int = 10, tenant=None) -> list:
        """
        Get top entries for a LeaderboardSeason.
        If no season given, falls back to all-time top customers.
        Returns: [{'rank': 1, 'customer_id': ..., 'score': ..., 'customer_code': ...}, ...]
        """
        try:
            if season is not None:
                # Season-based: query LoyaltyPoints or a season-specific score model
                from ...models.gamification import LeaderboardSeason
                if hasattr(season, 'id'):
                    season_obj = season
                else:
                    season_obj = LeaderboardSeason.objects.get(id=season)

                # Use earn transactions within season date range as score
                from ...models.points import PointsLedger
                from django.db.models import Sum as DSum
                from ...choices import LEDGER_CREDIT
                from django.db.models import Q

                qs = PointsLedger.objects.filter(txn_type=LEDGER_CREDIT)
                if season_obj.start_date:
                    qs = qs.filter(created_at__gte=season_obj.start_date)
                if season_obj.end_date:
                    qs = qs.filter(created_at__lte=season_obj.end_date)

                scores = (
                    qs.values('customer_id', 'customer__code',
                              'customer__firstname', 'customer__lastname')
                    .annotate(score=DSum('points'))
                    .order_by('-score')[:limit]
                )
                return [
                    {
                        'rank': idx + 1,
                        'customer_id': row['customer_id'],
                        'customer_code': row.get('customer__code', ''),
                        'name': f"{row.get('customer__firstname','')} {row.get('customer__lastname','')}".strip(),
                        'score': str(row['score'] or 0),
                    }
                    for idx, row in enumerate(scores)
                ]
            else:
                rows = LeaderboardService.get_top_customers(limit=limit)
                return [
                    {
                        'rank': idx + 1,
                        'customer_id': row['customer__id'],
                        'customer_code': row.get('customer__code', ''),
                        'name': f"{row.get('customer__firstname','')} {row.get('customer__lastname','')}".strip(),
                        'score': str(row.get('lifetime_earned') or 0),
                    }
                    for idx, row in enumerate(rows)
                ]
        except Exception as e:
            logger.error('LeaderboardService.get_top error: %s', e)
            return []

    @staticmethod
    def get_customer_rank(customer, season=None, tenant=None) -> int:
        """
        Get a specific customer's rank on the leaderboard.
        Returns 0 if not ranked.
        """
        try:
            entries = LeaderboardService.get_top(season=season, limit=1000, tenant=tenant)
            for entry in entries:
                if entry.get('customer_id') == customer.id:
                    return entry['rank']
            return 0
        except Exception as e:
            logger.error('LeaderboardService.get_customer_rank error: %s', e)
            return 0

    @staticmethod
    def get_customer_score(customer, season=None, tenant=None):
        """
        Get a customer's leaderboard score (points earned in period).
        Returns Decimal string.
        """
        try:
            from ...models.points import LoyaltyPoints
            if season is None:
                lp = LoyaltyPoints.objects.filter(customer=customer).first()
                return str(lp.lifetime_earned if lp else 0)
            else:
                from ...models.points import PointsLedger
                from django.db.models import Sum as DSum
                from ...choices import LEDGER_CREDIT

                if hasattr(season, 'id'):
                    season_obj = season
                else:
                    from ...models.gamification import LeaderboardSeason
                    season_obj = LeaderboardSeason.objects.get(id=season)

                qs = PointsLedger.objects.filter(
                    customer=customer, txn_type=LEDGER_CREDIT,
                )
                if season_obj.start_date:
                    qs = qs.filter(created_at__gte=season_obj.start_date)
                if season_obj.end_date:
                    qs = qs.filter(created_at__lte=season_obj.end_date)

                result = qs.aggregate(score=DSum('points'))
                return str(result.get('score') or 0)
        except Exception as e:
            logger.error('LeaderboardService.get_customer_score error: %s', e)
            return '0'

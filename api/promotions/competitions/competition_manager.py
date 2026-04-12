# =============================================================================
# promotions/competitions/competition_manager.py
# Publisher Competitions — MaxBounty monthly contests
# Top earner wins: Cash bonus, MacBook, Travel trip
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import uuid, logging

logger = logging.getLogger(__name__)


class CompetitionManager:
    """Publisher competitions with prizes."""
    COMP_PREFIX = 'competition:'

    def create_competition(self, name: str, prize: str, prize_value: Decimal,
                           start_date: str, end_date: str, metric: str = 'earnings',
                           min_conversions: int = 10) -> dict:
        comp_id = str(uuid.uuid4())[:12]
        comp = {
            'comp_id': comp_id, 'name': name, 'prize': prize,
            'prize_value': str(prize_value), 'start_date': start_date,
            'end_date': end_date, 'metric': metric,
            'min_conversions': min_conversions,
            'status': 'active', 'winner': None,
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.COMP_PREFIX}{comp_id}', comp, timeout=3600 * 24 * 90)
        all_comps = cache.get('all_competitions', [])
        all_comps.insert(0, comp_id)
        cache.set('all_competitions', all_comps[:20], timeout=3600 * 24 * 90)
        return {'comp_id': comp_id, 'name': name, 'prize': prize, 'start': start_date, 'end': end_date}

    def get_leaderboard(self, comp_id: str, limit: int = 20) -> dict:
        comp = cache.get(f'{self.COMP_PREFIX}{comp_id}')
        if not comp: return {'error': 'Competition not found'}
        from api.promotions.models import PromotionTransaction
        from datetime import datetime
        try:
            start = datetime.fromisoformat(comp['start_date'])
            end = datetime.fromisoformat(comp['end_date'])
        except Exception:
            return {'error': 'Invalid dates'}
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if comp['metric'] == 'earnings':
            from django.db.models import Sum as DSum, Count
            leaders = PromotionTransaction.objects.filter(
                transaction_type='reward',
                created_at__gte=start, created_at__lte=end,
            ).values('user__id', 'user__username').annotate(
                total=DSum('amount'), convs=Count('id'),
            ).filter(convs__gte=comp['min_conversions']).order_by('-total')[:limit]
            entries = [
                {
                    'rank': i+1, 'user_id': l['user__id'],
                    'username': l['user__username'],
                    'value': str(l['total'] or Decimal('0')),
                    'conversions': l['convs'],
                    'medal': {1:'🥇', 2:'🥈', 3:'🥉'}.get(i+1, ''),
                }
                for i, l in enumerate(leaders)
            ]
        else:
            entries = []
        return {
            'comp_id': comp_id, 'name': comp['name'],
            'prize': comp['prize'], 'prize_value': comp['prize_value'],
            'end_date': comp['end_date'], 'metric': comp['metric'],
            'leaderboard': entries,
        }

    def get_active_competitions(self) -> list:
        comp_ids = cache.get('all_competitions', [])
        result = []
        now = timezone.now().isoformat()
        for cid in comp_ids:
            c = cache.get(f'{self.COMP_PREFIX}{cid}')
            if c and c.get('end_date', '') > now and c.get('status') == 'active':
                result.append({
                    'comp_id': c['comp_id'], 'name': c['name'],
                    'prize': c['prize'], 'prize_value': c['prize_value'],
                    'end_date': c['end_date'],
                })
        return result


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def active_competitions_view(request):
    mgr = CompetitionManager()
    return Response({'competitions': mgr.get_active_competitions()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def competition_leaderboard_view(request, comp_id):
    mgr = CompetitionManager()
    return Response(mgr.get_leaderboard(comp_id, limit=int(request.query_params.get('limit', 20))))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_competition_view(request):
    mgr = CompetitionManager()
    d = request.data
    result = mgr.create_competition(
        name=d.get('name', ''), prize=d.get('prize', ''),
        prize_value=Decimal(str(d.get('prize_value', '0'))),
        start_date=d.get('start_date', timezone.now().isoformat()),
        end_date=d.get('end_date', ''),
        metric=d.get('metric', 'earnings'),
        min_conversions=int(d.get('min_conversions', 10)),
    )
    return Response(result, status=status.HTTP_201_CREATED)

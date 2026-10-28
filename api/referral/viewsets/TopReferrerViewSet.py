# api/referral/viewsets/TopReferrerViewSet.py
# Public and admin leaderboard — top referrers snapshot
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class TopReferrerViewSet(APIView):
    """
    GET /api/referral/top-referrers/?period=weekly&date=2025-01-01
    Public top referrers leaderboard from snapshots।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.models import TopReferrer
        from django.utils import timezone

        period = request.query_params.get('period', 'weekly')
        if period not in ['daily', 'weekly', 'monthly', 'alltime']:
            period = 'weekly'

        date_str = request.query_params.get('date')
        if date_str:
            try:
                from datetime import date
                query_date = date.fromisoformat(date_str)
            except ValueError:
                query_date = timezone.now().date()
        else:
            query_date = timezone.now().date()

        top = TopReferrer.objects.filter(
            period=period,
            date=query_date,
        ).select_related('user').order_by('rank')[:50]

        # Fallback: live query if no snapshot
        if not top.exists():
            from api.referral.models import Referral
            from django.db.models import Count, Q
            from django.contrib.auth import get_user_model
            User = get_user_model()

            live_top = Referral.objects.values('referrer').annotate(
                total=Count('id'),
                active=Count('id', filter=Q(referred_user__is_active=True))
            ).order_by('-total')[:20]

            leaderboard = []
            for rank, item in enumerate(live_top, 1):
                try:
                    u = User.objects.get(id=item['referrer'])
                    leaderboard.append({
                        'rank': rank,
                        'username': u.username,
                        'referral_count': item['total'],
                        'active_referral_count': item['active'],
                        'commission_earned': 0,
                        'is_me': u.id == request.user.id,
                    })
                except User.DoesNotExist:
                    continue

            return Response({
                'success': True,
                'period': period,
                'source': 'live',
                'leaderboard': leaderboard,
            })

        leaderboard = [{
            'rank': t.rank,
            'username': t.user.username,
            'referral_count': t.referral_count,
            'active_referral_count': t.active_referral_count,
            'commission_earned': float(t.commission_earned),
            'rank_change': t.rank_change,
            'is_me': t.user.id == request.user.id,
        } for t in top]

        return Response({
            'success': True,
            'period': period,
            'date': str(query_date),
            'source': 'snapshot',
            'leaderboard': leaderboard,
        })
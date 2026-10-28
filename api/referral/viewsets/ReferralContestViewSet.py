# api/referral/viewsets/ReferralContestViewSet.py
# Contest: leaderboard, join, prize distribution
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class ReferralContestViewSet(APIView):
    """
    GET  /api/referral/contests/       — active contests list
    POST /api/referral/contests/       — create contest (admin)
    """
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get(self, request):
        from api.referral.services.ReferralContestService import ReferralContestService
        contests = ReferralContestService.get_active_contests()
        return Response({'success': True, 'contests': contests})

    def post(self, request):
        from api.referral.models import ReferralContest
        from django.utils.text import slugify

        data = request.data
        required = ['title', 'start_date', 'end_date', 'prize_pool']
        for field in required:
            if not data.get(field):
                return Response(
                    {'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        contest = ReferralContest.objects.create(
            title=data['title'],
            slug=slugify(data['title']),
            description=data.get('description', ''),
            start_date=data['start_date'],
            end_date=data['end_date'],
            prize_pool=data['prize_pool'],
            contest_type=data.get('contest_type', 'most_referrals'),
            leaderboard_size=data.get('leaderboard_size', 10),
            is_public=data.get('is_public', True),
            created_by=request.user,
        )
        contest.update_status()

        return Response({
            'success': True,
            'contest_id': contest.id,
        }, status=status.HTTP_201_CREATED)


class ContestLeaderboardView(APIView):
    """GET /api/referral/contests/<contest_id>/leaderboard/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, contest_id):
        from api.referral.services.ReferralContestService import ReferralContestService
        limit = min(100, int(request.query_params.get('limit', 10)))
        data = ReferralContestService.get_leaderboard(contest_id, limit=limit)
        if 'error' in data:
            return Response(data, status=404)
        return Response({'success': True, **data})


class ContestMyRankView(APIView):
    """GET /api/referral/contests/<contest_id>/my-rank/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, contest_id):
        from api.referral.services.ReferralContestService import ReferralContestService
        data = ReferralContestService.get_my_contest_rank(
            contest_id=contest_id, user=request.user
        )
        return Response({'success': True, **data})


class AdminContestFinalizeView(APIView):
    """POST /api/referral/admin/contests/<contest_id>/finalize/"""
    permission_classes = [IsAdminUser]

    def post(self, request, contest_id):
        from api.referral.services.ReferralContestService import ReferralContestService
        result = ReferralContestService.finalize_contest(contest_id)
        return Response(result)


class AdminContestLeaderboardUpdateView(APIView):
    """POST /api/referral/admin/contests/<contest_id>/update-leaderboard/"""
    permission_classes = [IsAdminUser]

    def post(self, request, contest_id):
        from api.referral.services.ReferralContestService import ReferralContestService
        result = ReferralContestService.update_leaderboard(contest_id)
        return Response(result)
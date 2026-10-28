# api/referral/viewsets/ReferralLTVViewSet.py
# LTV: user lifetime value analytics — user + admin views
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class ReferralLTVViewSet(APIView):
    """
    GET /api/referral/ltv/              — my referred users LTV report
    GET /api/referral/ltv/churn-risk/  — at-risk referred users
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.LTVService import LTVService

        limit = min(100, int(request.query_params.get('limit', 50)))
        report = LTVService.get_ltv_report(
            referrer=request.user, limit=limit
        )
        return Response({'success': True, **report})


class LTVChurnRiskView(APIView):
    """GET /api/referral/ltv/churn-risk/?level=high"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.LTVService import LTVService

        risk_level = request.query_params.get('level', 'high')
        if risk_level not in ['low', 'medium', 'high', 'churned']:
            risk_level = 'high'

        at_risk = LTVService.get_churn_at_risk(
            referrer=request.user, risk_level=risk_level
        )
        return Response({
            'success': True,
            'risk_level': risk_level,
            'users': at_risk,
            'total': len(at_risk),
        })


class LTVUserDetailView(APIView):
    """
    GET /api/referral/ltv/<username>/
    LTV detail for a specific referred user。
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        from api.referral.models import ReferralLTV
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            referred_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

        try:
            ltv = ReferralLTV.objects.get(
                user=referred_user, referred_by=request.user
            )
        except ReferralLTV.DoesNotExist:
            return Response(
                {'error': 'This user was not referred by you'},
                status=404,
            )

        return Response({
            'success': True,
            'username': referred_user.username,
            'lifetime_value': float(ltv.lifetime_value),
            'total_user_earnings': float(ltv.total_user_earnings),
            'task_count': ltv.task_count,
            'offer_count': ltv.offer_count,
            'days_active': ltv.days_active,
            'engagement_score': ltv.engagement_score,
            'churn_risk': ltv.churn_risk,
            'value_category': ltv.value_category,
            'consecutive_active_days': ltv.consecutive_active_days,
            'longest_streak_days': ltv.longest_streak_days,
            'first_activity_at': (
                ltv.first_activity_at.strftime('%Y-%m-%d')
                if ltv.first_activity_at else None
            ),
            'last_activity': (
                ltv.last_activity.strftime('%Y-%m-%d')
                if ltv.last_activity else None
            ),
        })


class AdminLTVOverviewView(APIView):
    """
    GET /api/referral/admin/ltv/overview/
    Admin: platform-wide LTV stats।
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import ReferralLTV
        from django.db.models import Sum, Avg, Count, Q

        stats = ReferralLTV.objects.aggregate(
            total_ltv=Sum('lifetime_value'),
            avg_ltv=Avg('lifetime_value'),
            total_users=Count('id'),
            high_value=Count('id', filter=Q(value_category='high_value')),
            mid_value=Count('id', filter=Q(value_category='mid_value')),
            low_value=Count('id', filter=Q(value_category='low_value')),
            inactive=Count('id', filter=Q(value_category='inactive')),
            churned=Count('id', filter=Q(churn_risk='churned')),
            high_risk=Count('id', filter=Q(churn_risk='high')),
            med_risk=Count('id', filter=Q(churn_risk='medium')),
            low_risk=Count('id', filter=Q(churn_risk='low')),
        )

        return Response({
            'success': True,
            'overview': {
                'total_ltv': float(stats['total_ltv'] or 0),
                'avg_ltv': float(stats['avg_ltv'] or 0),
                'total_referred_users': stats['total_users'] or 0,
                'value_breakdown': {
                    'high_value': stats['high_value'] or 0,
                    'mid_value': stats['mid_value'] or 0,
                    'low_value': stats['low_value'] or 0,
                    'inactive': stats['inactive'] or 0,
                },
                'churn_breakdown': {
                    'churned': stats['churned'] or 0,
                    'high_risk': stats['high_risk'] or 0,
                    'medium_risk': stats['med_risk'] or 0,
                    'low_risk': stats['low_risk'] or 0,
                },
            },
        })


class AdminLTVRecalcView(APIView):
    """POST /api/referral/admin/ltv/recalc/ — trigger LTV recalculation"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        from api.referral.services.LTVService import LTVService

        # Specific user recalc
        user_id = request.data.get('user_id')
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                result = LTVService.recalculate_all_for_referrer(user)
                return Response({'success': True, **result})
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)

        # Full platform recalc
        result = LTVService.recalculate_all()
        return Response({'success': True, **result})
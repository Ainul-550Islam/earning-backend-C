# api/referral/viewsets/ReferralInsightViewSet.py
# Admin dashboard: referral insights, chart data, summary
# ============================================================

from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class ReferralInsightViewSet(APIView):
    """
    GET /api/referral/admin/insights/           — dashboard summary
    GET /api/referral/admin/insights/chart/     — chart data (days param)
    GET /api/referral/admin/insights/today/     — today's snapshot
    POST /api/referral/admin/insights/recalc/  — force recalculate
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )

        days = min(365, int(request.query_params.get('days', 30)))
        summary = ReferralAnalyticsService.get_dashboard_summary(days=days)
        return Response({'success': True, **summary})


class InsightChartView(APIView):
    """GET /api/referral/admin/insights/chart/?days=30"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )

        days = min(365, int(request.query_params.get('days', 30)))
        chart_data = ReferralAnalyticsService.get_insight_chart_data(days=days)
        return Response({'success': True, 'chart_data': chart_data, 'days': days})


class InsightTodayView(APIView):
    """GET /api/referral/admin/insights/today/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import ReferralInsight
        from django.utils import timezone

        today = timezone.now().date()
        insight = ReferralInsight.objects.filter(date=today).first()

        if not insight:
            return Response({
                'success': True,
                'date': str(today),
                'data': None,
                'message': 'No insight calculated yet for today',
            })

        return Response({
            'success': True,
            'date': str(today),
            'data': {
                'new_referrals': insight.new_referrals,
                'commission_paid': float(insight.commission_paid),
                'commission_l1': float(insight.commission_l1),
                'commission_l2': float(insight.commission_l2),
                'commission_l3': float(insight.commission_l3),
                'total_clicks': insight.total_clicks,
                'total_signups': insight.total_signups,
                'conversion_rate': float(insight.conversion_rate),
                'flagged_referrals': insight.flagged_referrals,
                'blocked_referrals': insight.blocked_referrals,
                'fraud_rate': float(insight.fraud_rate),
                'active_referrers': insight.active_referrers,
                'milestone_bonuses_paid': float(insight.milestone_bonuses_paid),
                'campaign_commissions': float(insight.campaign_commissions),
            },
        })


class InsightRecalcView(APIView):
    """
    POST /api/referral/admin/insights/recalc/
    Force recalculate insight for a given date (or today).
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from api.referral.services.ReferralAnalyticsService import (
            ReferralAnalyticsService,
        )
        from django.utils import timezone

        date_str = request.data.get('date')
        if date_str:
            try:
                from datetime import date
                target_date = date.fromisoformat(date_str)
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=400,
                )
        else:
            target_date = timezone.now().date()

        insight = ReferralAnalyticsService.calculate_daily_insight(
            date=target_date
        )
        return Response({
            'success': True,
            'date': str(target_date),
            'new_referrals': insight.new_referrals,
            'commission_paid': float(insight.commission_paid),
        })


class InsightDateRangeView(APIView):
    """
    GET /api/referral/admin/insights/range/?from=2025-01-01&to=2025-01-31
    Date range insight data।
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from api.referral.models import ReferralInsight
        from django.db.models import Sum

        date_from = request.query_params.get('from')
        date_to = request.query_params.get('to')

        qs = ReferralInsight.objects.order_by('date')

        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        totals = qs.aggregate(
            total_refs=Sum('new_referrals'),
            total_commission=Sum('commission_paid'),
            total_clicks=Sum('total_clicks'),
            total_flagged=Sum('flagged_referrals'),
        )

        daily = [{
            'date': str(i.date),
            'new_referrals': i.new_referrals,
            'commission_paid': float(i.commission_paid),
            'conversion_rate': float(i.conversion_rate),
            'active_referrers': i.active_referrers,
            'flagged': i.flagged_referrals,
        } for i in qs]

        return Response({
            'success': True,
            'totals': {
                'total_referrals': totals['total_refs'] or 0,
                'total_commission': float(totals['total_commission'] or 0),
                'total_clicks': totals['total_clicks'] or 0,
                'total_flagged': totals['total_flagged'] or 0,
            },
            'daily': daily,
        })
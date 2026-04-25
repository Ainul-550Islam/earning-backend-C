# viewsets/PublisherEarningsViewSet.py
# Real-time publisher earnings dashboard API

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.views import BaseViewSet
from decimal import Decimal


class PublisherEarningsViewSet(BaseViewSet):
    """
    Publisher real-time earnings API.
    Provides balance, history, per-offer breakdown, and payout stats.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Dashboard overview — balance, today's earnings, all-time totals."""
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta

        user  = request.user
        today = timezone.now().date()

        # Try getting balance from user model
        balance = float(getattr(user, 'balance', 0) or 0)

        # Today's conversions
        try:
            from api.payment_gateways.tracking.models import Conversion
            today_convs = Conversion.objects.filter(
                publisher=user, status='approved', created_at__date=today
            ).aggregate(revenue=Sum('payout'), count=Count('id'))

            # 7-day trend
            last7 = Conversion.objects.filter(
                publisher=user, status='approved',
                created_at__date__gte=today - timedelta(days=7)
            ).aggregate(revenue=Sum('payout'), count=Count('id'))

            # All time
            alltime = Conversion.objects.filter(
                publisher=user, status='approved'
            ).aggregate(revenue=Sum('payout'), count=Count('id'))

        except Exception:
            today_convs = last7 = alltime = {'revenue': 0, 'count': 0}

        # Pending payouts
        try:
            from api.payment_gateways.models.core import PayoutRequest
            pending_payout = float(PayoutRequest.objects.filter(
                user=user, status='pending'
            ).aggregate(t=Sum('amount'))['t'] or 0)
        except Exception:
            pending_payout = 0

        # Referral earnings
        try:
            from api.payment_gateways.referral.models import ReferralCommission
            referral_earnings = float(ReferralCommission.objects.filter(
                referrer=user, status='paid'
            ).aggregate(t=Sum('commission_amount'))['t'] or 0)
        except Exception:
            referral_earnings = 0

        return Response({'success': True, 'data': {
            'balance':            balance,
            'pending_payout':     pending_payout,
            'today_earnings':     float(today_convs.get('revenue') or 0),
            'today_conversions':  today_convs.get('count') or 0,
            'last7d_earnings':    float(last7.get('revenue') or 0),
            'last7d_conversions': last7.get('count') or 0,
            'alltime_earnings':   float(alltime.get('revenue') or 0),
            'alltime_conversions':alltime.get('count') or 0,
            'referral_earnings':  referral_earnings,
        }})

    @action(detail=False, methods=['get'])
    def by_offer(self, request):
        """Earnings breakdown per offer."""
        from django.db.models import Sum, Count
        from api.payment_gateways.tracking.models import Conversion

        qs = Conversion.objects.filter(
            publisher=request.user, status='approved'
        ).values('offer__name', 'offer__offer_type').annotate(
            revenue=Sum('payout'),
            conversions=Count('id'),
        ).order_by('-revenue')[:20]

        return Response({'success': True, 'data': list(qs)})

    @action(detail=False, methods=['get'])
    def by_date(self, request):
        """Daily earnings for the past 30 days."""
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta
        from api.payment_gateways.tracking.models import Conversion

        days  = int(request.GET.get('days', 30))
        since = timezone.now().date() - timedelta(days=days)

        qs = Conversion.objects.filter(
            publisher=request.user, status='approved',
            created_at__date__gte=since,
        ).values('created_at__date').annotate(
            revenue=Sum('payout'),
            conversions=Count('id'),
        ).order_by('created_at__date')

        return Response({'success': True, 'data': list(qs)})

    @action(detail=False, methods=['get'])
    def payout_history(self, request):
        """Completed payout history."""
        from api.payment_gateways.models.core import PayoutRequest
        from rest_framework import serializers as s

        class PS(s.ModelSerializer):
            class Meta:
                model  = PayoutRequest
                fields = ['id','amount','net_amount','payout_method','status',
                          'reference_id','processed_at','created_at']

        qs = PayoutRequest.objects.filter(
            user=request.user, status='completed'
        ).order_by('-created_at')[:50]
        return Response({'success': True, 'data': PS(qs, many=True).data})

    @action(detail=False, methods=['get'])
    def top_offers(self, request):
        """Top performing offers for this publisher."""
        from api.payment_gateways.tracking.models import PublisherDailyStats
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta

        since = timezone.now().date() - timedelta(days=30)

        try:
            qs = PublisherDailyStats.objects.filter(
                publisher=request.user, date__gte=since
            ).values('offer__name', 'offer__id').annotate(
                revenue=Sum('revenue'),
                conversions=Sum('conversions'),
                clicks=Sum('clicks'),
            ).order_by('-revenue')[:10]
            return Response({'success': True, 'data': list(qs)})
        except Exception:
            return Response({'success': True, 'data': []})

    @action(detail=False, methods=['get'])
    def fast_pay_status(self, request):
        """Check publisher's Fast Pay eligibility (like CPAlead)."""
        try:
            from api.payment_gateways.publisher.models import PublisherProfile
            profile  = PublisherProfile.objects.get(user=request.user)
            return Response({'success': True, 'data': {
                'is_fast_pay_eligible': profile.is_fast_pay_eligible,
                'quality_score':        profile.quality_score,
                'tier':                 profile.tier,
                'minimum_payout':       float(profile.minimum_payout),
                'fast_pay_threshold':   1.00,
            }})
        except Exception:
            return Response({'success': True, 'data': {
                'is_fast_pay_eligible': False,
                'quality_score':        50,
                'tier':                 'standard',
            }})

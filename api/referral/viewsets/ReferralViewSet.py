# api/referral/viewsets/ReferralViewSet.py
# Main user-facing referral API — stats, earnings, leaderboard
# All original views preserved + new endpoints added
# ============================================================

from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ReferralStatsView(APIView):
    """
    GET /api/referral/
    GET /api/referral/stats/
    User এর referral dashboard stats।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.ReferralService import ReferralService
        from api.referral.models import ReferralSettings

        stats = ReferralService.get_referral_stats(request.user)
        settings = ReferralSettings.objects.select_related(
            'active_campaign'
        ).first()

        campaign_data = None
        if settings and settings.active_campaign_id:
            try:
                c = settings.active_campaign
                if c.is_currently_active():
                    campaign_data = {
                        'name': c.name,
                        'multiplier': float(c.bonus_multiplier),
                        'end_date': c.end_date.strftime('%Y-%m-%d %H:%M'),
                    }
            except Exception:
                pass

        return Response({
            'success': True,
            'stats': stats,
            'commission_rates': {
                'level1': float(settings.level1_commission_rate) if settings else 10,
                'level2': float(settings.level2_commission_rate) if settings else 5,
                'level3': float(settings.level3_commission_rate) if settings else 2,
            },
            'referral_link': (
                f"https://yoursite.com/register?ref={stats['referral_code']}"
            ),
            'active_campaign': campaign_data,
        })


class MyReferralsView(APIView):
    """
    GET /api/referral/my-referrals/?level=1
    আমার refer করা users এর list।
    level=1 (default), level=2, level=3
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.services.ReferralService import ReferralService

        level = int(request.query_params.get('level', 1))
        if level not in [1, 2, 3]:
            return Response(
                {'error': 'level must be 1, 2, or 3'},
                status=status.HTTP_400_BAD_REQUEST
            )

        referrals = ReferralService.get_my_referrals(request.user, level=level)
        return Response({
            'success': True,
            'level': level,
            'referrals': referrals,
            'total': len(referrals),
        })


class ReferralEarningsView(APIView):
    """
    GET /api/referral/earnings/?days=30&level=0
    Referral থেকে earned commissions।
    level=0 → সব level, level=1/2/3 → specific
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.models import ReferralEarning
        from datetime import timedelta

        days = min(365, int(request.query_params.get('days', 30)))
        level = request.query_params.get('level', '0')

        cutoff = timezone.now() - timedelta(days=days)

        qs = ReferralEarning.objects.filter(
            referrer=request.user,
            created_at__gte=cutoff
        )

        if level and level != '0':
            qs = qs.filter(level=int(level))

        earnings = qs.order_by('-created_at')[:50]

        data = [{
            'id': e.id,
            'from_user': e.referred_user.username,
            'level': e.level,
            'amount': float(e.amount),
            'rate': float(e.commission_rate) if e.commission_rate else 0,
            'source_type': e.source_type,
            'status': e.status,
            'campaign_multiplier': float(e.campaign_multiplier),
            'date': e.created_at.strftime('%Y-%m-%d %H:%M'),
        } for e in earnings]

        total = qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return Response({
            'success': True,
            'earnings': data,
            'total': float(total),
            'period_days': days,
        })


class ReferralLeaderboardView(APIView):
    """
    GET /api/referral/leaderboard/?period=weekly
    Top referrers leaderboard।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.referral.models import Referral
        from django.contrib.auth import get_user_model

        period = request.query_params.get('period', 'weekly')
        if period not in ['weekly', 'monthly', 'alltime']:
            period = 'weekly'

        User = get_user_model()

        top = Referral.objects.values('referrer').annotate(
            total=Count('id'),
            active=Count('id', filter=Q(referred_user__is_active=True))
        ).order_by('-total')[:50]

        leaderboard = []
        for i, item in enumerate(top, 1):
            try:
                user = User.objects.get(id=item['referrer'])
                leaderboard.append({
                    'rank': i,
                    'username': user.username,
                    'avatar': (
                        user.avatar.url
                        if hasattr(user, 'avatar') and user.avatar else None
                    ),
                    'total_referrals': item['total'],
                    'active_referrals': item['active'],
                    'is_me': user.id == request.user.id,
                })
            except User.DoesNotExist:
                continue

        my_rank = next(
            (r for r in leaderboard if r['is_me']), None
        )

        return Response({
            'success': True,
            'period': period,
            'leaderboard': leaderboard,
            'my_rank': my_rank,
        })


# ─── Backward-compatible function-based views ──────────────────────────────

@api_view(['GET'])
@api_view(['DELETE'])
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def get_referral_stats(request):
    """পুরনো endpoint — backward compatible"""
    from api.referral.services.ReferralService import ReferralService
    stats = ReferralService.get_referral_stats(request.user)
    return Response(stats)
@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def admin_referral_overview(request):
    """Admin: সব referral stats একসাথে"""
    from api.referral.models import Referral, ReferralEarning, ReferralChain

    total_referrals = Referral.objects.count()
    total_commission = ReferralEarning.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0
    suspicious = Referral.objects.filter(is_suspicious=True).count()

    return Response({
        'total_referrals': total_referrals,
        'total_commission_paid': float(total_commission),
        'suspicious_referrals': suspicious,
        'level1_count': Referral.objects.count(),
        'level2_count': ReferralChain.objects.filter(level=2).count(),
        'level3_count': ReferralChain.objects.filter(level=3).count(),
    })
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_referrals_list(request):
    from api.referral.models import Referral

    refs = Referral.objects.select_related(
        'referrer', 'referred_user'
    ).order_by('-created_at')[:100]
    data = [{
        'id': r.id,
        'referrer': r.referrer.username,
        'referred_user': r.referred_user.username,
        'commission': float(r.total_commission_earned),
        'is_suspicious': r.is_suspicious,
        'suspicious_reason': r.suspicious_reason,
        'created': r.created_at.strftime('%Y-%m-%d'),
    } for r in refs]
    return Response({'referrals': data, 'total': len(data)})
@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_delete_referral(request, referral_id):
    from api.referral.models import Referral
    try:
        Referral.objects.get(id=referral_id).delete()
        return Response({'success': True})
    except Referral.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_referral_settings(request):
    from api.referral.models import ReferralSettings
    from django.core.cache import cache

    settings = ReferralSettings.objects.first()
    if not settings:
        settings = ReferralSettings.objects.create()

    if request.method == 'GET':
        return Response({
            'direct_signup_bonus': float(settings.direct_signup_bonus),
            'referrer_signup_bonus': float(settings.referrer_signup_bonus),
            'level1_commission_rate': float(settings.level1_commission_rate),
            'level2_commission_rate': float(settings.level2_commission_rate),
            'level3_commission_rate': float(settings.level3_commission_rate),
            'is_active': settings.is_active,
            'commission_hold_days': settings.commission_hold_days,
            'max_referral_depth': settings.max_referral_depth,
        })

    for field in [
        'direct_signup_bonus', 'referrer_signup_bonus',
        'level1_commission_rate', 'level2_commission_rate',
        'level3_commission_rate', 'is_active',
        'commission_hold_days', 'max_referral_depth',
    ]:
        if field in request.data:
            setattr(settings, field, request.data[field])
    settings.save()
    cache.delete('referral_settings')

    return Response({'success': True, 'message': 'Settings updated'})
@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_recent_earnings(request):
    from api.referral.models import ReferralEarning

    earnings = ReferralEarning.objects.select_related(
        'referrer', 'referred_user'
    ).order_by('-created_at')[:100]

    data = [{
        'id': e.id,
        'referrer': e.referrer.username,
        'from': e.referred_user.username,
        'level': e.level,
        'amount': float(e.amount),
        'rate': float(e.commission_rate) if e.commission_rate else 0,
        'source': e.source_type,
        'status': e.status,
        'date': e.created_at.strftime('%Y-%m-%d %H:%M'),
    } for e in earnings]
    return Response({'earnings': data})
@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_delete_earning(request, earning_id):
    from api.referral.models import ReferralEarning
    try:
        ReferralEarning.objects.get(id=earning_id).delete()
        return Response({'success': True})
    except ReferralEarning.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_stats_by_date(request):
    from api.referral.models import Referral
    from django.db.models.functions import TruncDate

    data = list(
        Referral.objects.annotate(date=TruncDate('created_at'))
        .values('date').annotate(count=Count('id')).order_by('date')
    )
    return Response({'data': data})
@permission_classes([IsAdminUser])
def admin_create_referral(request):
    from django.contrib.auth import get_user_model
    from api.referral.services.ReferralService import ReferralService
    User = get_user_model()

    try:
        referrer = User.objects.get(id=request.data.get('referrer_id'))
        referred = User.objects.get(id=request.data.get('referred_user_id'))
        result = ReferralService.process_signup_with_fraud_check(
            referred, referrer
        )
        return Response(result)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

@permission_classes([IsAdminUser])
def admin_give_bonus(request, referral_id):
    from api.referral.models import Referral, ReferralSettings
    from api.wallet.services import WalletService
    from api.wallet.models import Wallet

    try:
        ref = Referral.objects.get(id=referral_id)
        settings = ReferralSettings.objects.first()
        wallet, _ = Wallet.objects.get_or_create(user=ref.referrer)
        bonus = Decimal(str(
            request.data.get(
                'amount',
                settings.referrer_signup_bonus if settings else 50
            )
        ))
        WalletService.add_earnings(
            wallet, bonus, description='Admin manual referral bonus'
        )
        return Response({'success': True, 'amount': float(bonus)})
    except Referral.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

@permission_classes([IsAdminUser])
def admin_adjust_commission(request, referral_id):
    from api.referral.models import Referral

    try:
        ref = Referral.objects.get(id=referral_id)
        amount = Decimal(str(request.data.get('amount', 0)))
        ref.total_commission_earned += amount
        ref.save()
        return Response({
            'success': True,
            'new_total': float(ref.total_commission_earned)
        })
    except Referral.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

@permission_classes([IsAdminUser])
def admin_toggle_program(request):
    from api.referral.models import ReferralSettings
    from django.core.cache import cache

    settings = ReferralSettings.objects.first()
    if not settings:
        settings = ReferralSettings.objects.create()
    settings.is_active = not settings.is_active
    settings.save()
    cache.delete('referral_settings')
    return Response({'is_active': settings.is_active})
@permission_classes([IsAdminUser])
def admin_search_users(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    q = request.query_params.get('q', '')
    users = User.objects.filter(
        Q(username__icontains=q) | Q(email__icontains=q)
    )[:20]
    return Response({
        'users': [
            {'id': u.id, 'username': u.username, 'email': u.email}
            for u in users
        ]
    })


# Expose class-based views at module level for backward compat
ReferralViewSet = ReferralStatsView
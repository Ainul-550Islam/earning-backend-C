# api/engagement/views.py  —  COMPLETE (all missing endpoints added)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from .models import Leaderboard, DailyCheckIn, SpinWheel, LeaderboardReward
from .serializers import (
    DailyCheckInSerializer, SpinWheelSerializer,
    LeaderboardSerializer, LeaderboardRewardSerializer,
)
from datetime import date
from django.db.models import Sum, Count, Avg
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def get_coin_balance(user):
    try:
        return float(user.coin_balance)
    except AttributeError:
        try:
            return float(user.wallet.balance)
        except Exception:
            return 0.0


# ═══════════════════════════════ DAILY CHECK-IN ════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def daily_checkin(request):
    try:
        from .services import EngagementService
        checkin, message = EngagementService.process_daily_checkin(request.user)
        if checkin:
            return Response({
                'success': True,
                'message': message,
                'coins_earned': float(checkin.coins_earned),
                'consecutive_days': checkin.consecutive_days,
                'new_balance': get_coin_balance(request.user),
            })
        return Response({'success': False, 'message': message}, status=400)
    except Exception as e:
        logger.error(f"Daily checkin error: {e}")
        return Response({'success': False, 'message': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def checkins_list(request):
    """
    ✅ NEW — GET /engagement/checkins/
    Admin sees all; user sees own. Filterable by user, date, page.
    """
    qs = DailyCheckIn.objects.all() if request.user.is_staff else \
         DailyCheckIn.objects.filter(user=request.user)

    user_id = request.query_params.get('user')
    dt      = request.query_params.get('date')
    if user_id: qs = qs.filter(user_id=user_id)
    if dt:      qs = qs.filter(date=dt)

    qs = qs.select_related('user').order_by('-date')
    serializer = DailyCheckInSerializer(qs[:100], many=True)
    return Response({'results': serializer.data, 'count': qs.count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def checkins_stats(request):
    """
    ✅ NEW — GET /engagement/checkins/stats/
    """
    today = date.today()
    qs = DailyCheckIn.objects.all()
    return Response({
        'total_checkins_today':  qs.filter(date=today).count(),
        'total_checkins_ever':   qs.count(),
        'avg_consecutive_days':  qs.aggregate(avg=Avg('consecutive_days'))['avg'] or 0,
        'unique_users_today':    qs.filter(date=today).values('user').distinct().count(),
        'my_streak':             qs.filter(user=request.user).order_by('-date').first().consecutive_days
                                 if qs.filter(user=request.user).exists() else 0,
        'my_total_checkins':     qs.filter(user=request.user).count(),
    })


# ═══════════════════════════════ SPIN WHEEL ════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def spin_wheel(request):
    try:
        from .services import EngagementService
        spin, message = EngagementService.spin_wheel(request.user)
        if spin:
            today = date.today()
            spins_used = SpinWheel.objects.filter(user=request.user, spun_at__date=today).count()
            return Response({
                'success': True,
                'message': message,
                'coins_won': float(spin.coins_won),
                'new_balance': get_coin_balance(request.user),
                'spins_remaining': max(0, 5 - spins_used),
            })
        return Response({'success': False, 'message': message}, status=400)
    except Exception as e:
        logger.error(f"Spin wheel error: {e}")
        return Response({'success': False, 'message': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spins_list(request):
    """
    ✅ NEW — GET /engagement/spins/
    Admin sees all; user sees own.
    """
    qs = SpinWheel.objects.all() if request.user.is_staff else \
         SpinWheel.objects.filter(user=request.user)

    user_id = request.query_params.get('user')
    if user_id: qs = qs.filter(user_id=user_id)

    qs = qs.select_related('user').order_by('-spun_at')
    serializer = SpinWheelSerializer(qs[:100], many=True)
    return Response({'results': serializer.data, 'count': qs.count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spins_stats(request):
    """
    ✅ NEW — GET /engagement/spins/stats/
    """
    today = date.today()
    qs = SpinWheel.objects.all()
    user_qs = qs.filter(user=request.user)
    return Response({
        'total_spins_today':      qs.filter(spun_at__date=today).count(),
        'total_coins_won_today':  float(qs.filter(spun_at__date=today).aggregate(s=Sum('coins_won'))['s'] or 0),
        'total_spins_ever':       qs.count(),
        'total_coins_won_ever':   float(qs.aggregate(s=Sum('coins_won'))['s'] or 0),
        'my_spins_today':         user_qs.filter(spun_at__date=today).count(),
        'my_spins_remaining':     max(0, 5 - user_qs.filter(spun_at__date=today).count()),
        'my_total_coins_won':     float(user_qs.aggregate(s=Sum('coins_won'))['s'] or 0),
    })


# ═══════════════════════════════ LEADERBOARD ═══════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_leaderboard(request):
    """GET /engagement/leaderboard/ — supports ?date= param"""
    try:
        target_date = request.query_params.get('date', str(date.today()))
        leaderboard = Leaderboard.objects.filter(
            date=target_date
        ).select_related('user').order_by('rank')[:50]

        user_rank = None
        try:
            user_entry = Leaderboard.objects.get(user=request.user, date=target_date)
            user_rank = user_entry.rank
        except Leaderboard.DoesNotExist:
            pass

        data = LeaderboardSerializer(leaderboard, many=True, context={'request': request}).data
        return Response({
            'date':       target_date,
            'user_rank':  user_rank,
            'leaderboard': [
                {**entry, 'coins_earned': entry['total_coins_earned']}
                for entry in data
            ],
            'results': data,
        })
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return Response({'error': str(e)}, status=500)


# ═══════════════════════════════ LEADERBOARD REWARDS ═══════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leaderboard_rewards_list(request):
    """✅ NEW — GET /engagement/leaderboard-rewards/"""
    rewards = LeaderboardReward.objects.all().order_by('rank')
    return Response(LeaderboardRewardSerializer(rewards, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def leaderboard_reward_update(request, rank):
    """✅ NEW — PATCH /engagement/leaderboard-rewards/{rank}/"""
    try:
        reward = LeaderboardReward.objects.get(rank=rank)
    except LeaderboardReward.DoesNotExist:
        # Create if not exists
        reward = LeaderboardReward.objects.create(rank=rank, reward_coins=0)

    reward_coins = request.data.get('reward_coins')
    if reward_coins is None:
        return Response({'error': 'reward_coins is required'}, status=400)

    reward.reward_coins = reward_coins
    reward.save()
    return Response(LeaderboardRewardSerializer(reward).data)


# ═══════════════════════════════ ENGAGEMENT STATS ═════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_engagement_stats(request):
    """✅ NEW — GET /engagement/stats/ — overall engagement score"""
    today = date.today()
    user = request.user

    checkin_today = DailyCheckIn.objects.filter(user=user, date=today).first()
    streak = checkin_today.consecutive_days if checkin_today else 0

    spins_today = SpinWheel.objects.filter(user=user, spun_at__date=today).count()
    total_checkins = DailyCheckIn.objects.filter(user=user).count()
    total_spins = SpinWheel.objects.filter(user=user).count()

    # Engagement score: simple formula
    score = min(100, (
        (1 if checkin_today else 0) * 30 +
        (spins_today / 5) * 20 +
        min(streak / 7, 1) * 30 +
        min(total_checkins / 30, 1) * 20
    ))

    return Response({
        'engagement_score':    round(score, 1),
        'streak':              streak,
        'has_checked_in':      checkin_today is not None,
        'spins_today':         spins_today,
        'spins_remaining':     max(0, 5 - spins_today),
        'total_checkins':      total_checkins,
        'total_spins':         total_spins,
        'coin_balance':        get_coin_balance(user),
    })


# ═══════════════════════════════ DAILY STATS ══════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_daily_stats(request):
    try:
        today = date.today()
        user  = request.user

        checkin = DailyCheckIn.objects.filter(user=user, date=today).first()
        spins_used = SpinWheel.objects.filter(user=user, spun_at__date=today).count()

        todays_earnings = 0.0
        try:
            from api.analytics.models import AnalyticsEvent
            from django.db.models import Sum
            events_today = AnalyticsEvent.objects.filter(
                user=user,
                event_type__in=['task_completed', 'offer_completed'],
                event_time__date=today
            ).aggregate(total=Sum('value'))['total'] or 0
            todays_earnings = float(events_today)
        except Exception:
            pass

        return Response({
            'check_in': {
                'has_checked_in':  checkin is not None,
                'consecutive_days': checkin.consecutive_days if checkin else 0,
                'coins_earned':     float(checkin.coins_earned) if checkin else 0,
            },
            'spin_wheel': {
                'spins_used':      spins_used,
                'spins_remaining': max(0, 5 - spins_used),
                'can_spin':        spins_used < 5,
            },
            'todays_earnings': todays_earnings,
            'coin_balance':    get_coin_balance(user),
        })
    except Exception as e:
        logger.error(f"Daily stats error: {e}")
        return Response({'error': str(e)}, status=500)
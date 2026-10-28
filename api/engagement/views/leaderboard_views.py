# engagement/views/leaderboard_views.py
from datetime import date
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from ..services import LeaderboardService
from ..models.leaderboard import Leaderboard, LeaderboardReward, LeaderboardSeason
from ..serializers import (
    LeaderboardSerializer, LeaderboardRewardSerializer, LeaderboardSeasonSerializer,
)
from ..utils.throttling import LeaderboardThrottle
from ..utils.cache import get_leaderboard_cache, set_leaderboard_cache


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([LeaderboardThrottle])
def get_leaderboard(request):
    """GET /engagement/leaderboard/?date=YYYY-MM-DD"""
    target_date = request.query_params.get("date", str(date.today()))
    tenant      = getattr(request.user, "tenant", None)
    tenant_id   = getattr(tenant, "pk", None)

    cached = get_leaderboard_cache(target_date, tenant_id)
    if cached:
        user_rank = LeaderboardService.get_user_rank(request.user, target_date, tenant)
        return Response({**cached, "user_rank": user_rank})

    entries    = LeaderboardService.get_leaderboard(target_date, tenant, limit=50)
    user_rank  = LeaderboardService.get_user_rank(request.user, target_date, tenant)
    serialized = LeaderboardSerializer(entries, many=True, context={"request": request}).data

    payload = {"date": target_date, "leaderboard": serialized, "count": len(serialized)}
    set_leaderboard_cache(payload, target_date, tenant_id)
    return Response({**payload, "user_rank": user_rank})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def rebuild_leaderboard(request):
    """POST /engagement/leaderboard/rebuild/ — admin trigger."""
    target_date = request.data.get("date", str(date.today()))
    tenant      = getattr(request.user, "tenant", None)
    count       = LeaderboardService.rebuild_daily(target_date, tenant)
    return Response({"rebuilt": count, "date": target_date})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def distribute_leaderboard_rewards(request):
    """POST /engagement/leaderboard/distribute-rewards/"""
    target_date = request.data.get("date")
    tenant      = getattr(request.user, "tenant", None)
    count       = LeaderboardService.distribute_rewards(target_date, tenant)
    return Response({"rewarded": count})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leaderboard_rewards_list(request):
    """GET /engagement/leaderboard-rewards/"""
    tenant  = getattr(request.user, "tenant", None)
    rewards = LeaderboardReward.objects.filter(tenant=tenant).order_by("season_type", "rank")
    return Response(LeaderboardRewardSerializer(rewards, many=True).data)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAdminUser])
def leaderboard_reward_detail(request, rank):
    """GET|PATCH /engagement/leaderboard-rewards/<rank>/"""
    tenant = getattr(request.user, "tenant", None)
    try:
        reward = LeaderboardReward.objects.get(rank=rank, tenant=tenant)
    except LeaderboardReward.DoesNotExist:
        reward = LeaderboardReward(rank=rank, tenant=tenant, season_type="daily", reward_coins=0)

    if request.method == "GET":
        return Response(LeaderboardRewardSerializer(reward).data)

    coins = request.data.get("reward_coins")
    xp    = request.data.get("reward_xp", reward.reward_xp)
    if coins is None:
        return Response({"error": "reward_coins required"}, status=400)
    reward.reward_coins = coins
    reward.reward_xp    = xp
    reward.save()
    return Response(LeaderboardRewardSerializer(reward).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leaderboard_seasons(request):
    """GET /engagement/leaderboard/seasons/"""
    tenant  = getattr(request.user, "tenant", None)
    seasons = LeaderboardSeason.objects.filter(tenant=tenant).order_by("-start_date")[:10]
    return Response(LeaderboardSeasonSerializer(seasons, many=True).data)

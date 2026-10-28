# engagement/views/achievement_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from ..services import AchievementService
from ..models.achievement import Achievement, UserAchievement
from ..serializers import (
    AchievementSerializer, UserAchievementSerializer,
    AchievementStatusSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def achievements_list(request):
    """GET /engagement/achievements/ — all achievements with user lock/unlock status."""
    data = AchievementService.get_all_with_status(request.user)
    serializer = AchievementStatusSerializer(data, many=True)
    return Response({"results": serializer.data, "count": len(data)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_achievements(request):
    """GET /engagement/achievements/mine/ — only unlocked achievements."""
    uas = (
        UserAchievement.objects
        .filter(user=request.user)
        .select_related("achievement")
        .order_by("-unlocked_at")
    )
    return Response({
        "results": UserAchievementSerializer(uas, many=True).data,
        "count":   uas.count(),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def claim_achievement_reward(request, achievement_id):
    """POST /engagement/achievements/<id>/claim/ — claim coins+XP for an unlocked achievement."""
    try:
        ua = UserAchievement.objects.get(pk=achievement_id, user=request.user)
    except UserAchievement.DoesNotExist:
        return Response({"error": "Achievement not found."}, status=404)

    if ua.reward_claimed:
        return Response({"already_claimed": True})

    a = ua.achievement
    from ..services import CoinService, XPService
    result = {}
    if a.coin_reward > 0:
        result["new_balance"] = float(CoinService.add(request.user, a.coin_reward,
                                       source="achievement", ref_id=str(a.pk)))
    if a.xp_reward > 0:
        result["xp"] = XPService.grant(request.user, a.xp_reward,
                                        source="achievement", ref_id=str(a.pk))
    ua.reward_claimed = True
    ua.save(update_fields=["reward_claimed"])
    return Response({"success": True, **result})


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def achievements_admin(request):
    """Admin: GET list or POST create achievement definition."""
    if request.method == "GET":
        qs = Achievement.objects.all().order_by("type", "order")
        return Response(AchievementSerializer(qs, many=True).data)

    serializer = AchievementSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def achievement_admin_detail(request, pk):
    """Admin: GET|PATCH|DELETE a single achievement."""
    try:
        obj = Achievement.objects.get(pk=pk)
    except Achievement.DoesNotExist:
        return Response(status=404)

    if request.method == "GET":
        return Response(AchievementSerializer(obj).data)
    if request.method == "PATCH":
        s = AchievementSerializer(obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)
    obj.delete()
    return Response(status=204)

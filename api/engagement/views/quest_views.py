# engagement/views/quest_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..services import QuestService
from ..models.quest import Quest, UserQuest
from ..serializers import QuestSerializer, UserQuestSerializer
from ..utils.decorators import engagement_endpoint


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_quests(request):
    """GET /engagement/quests/ — active daily + weekly quests for user."""
    quests = QuestService.active_for_user(request.user)
    return Response({
        "daily":  UserQuestSerializer(quests["daily"],  many=True).data,
        "weekly": UserQuestSerializer(quests["weekly"], many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def init_daily_quests(request):
    """POST /engagement/quests/init-daily/ — initialise today's quests for user."""
    tenant  = getattr(request.user, "tenant", None)
    created = QuestService.init_daily(request.user, tenant=tenant)
    return Response({"created": len(created)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def claim_quest_reward(request, pk):
    """POST /engagement/quests/<pk>/claim/ — claim reward for completed quest."""
    result = QuestService.claim_reward(request.user, pk)
    return Response({"success": True, **result})


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def quest_admin_list(request):
    """Admin: GET all quests or POST create new quest."""
    if request.method == "GET":
        qs = Quest.objects.all().order_by("type", "order")
        return Response(QuestSerializer(qs, many=True).data)
    s = QuestSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    s.save()
    return Response(s.data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def quest_admin_detail(request, pk):
    """Admin: GET|PATCH|DELETE a quest."""
    try:
        obj = Quest.objects.get(pk=pk)
    except Quest.DoesNotExist:
        return Response(status=404)
    if request.method == "GET":
        return Response(QuestSerializer(obj).data)
    if request.method == "PATCH":
        s = QuestSerializer(obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)
    obj.delete()
    return Response(status=204)

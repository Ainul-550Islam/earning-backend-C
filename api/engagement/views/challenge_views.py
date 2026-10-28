# engagement/views/challenge_views.py
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..models.challenge import Challenge, ChallengeParticipant
from ..serializers import ChallengeSerializer, ChallengeParticipantSerializer
from ..utils.decorators import engagement_endpoint
from ..exceptions import ChallengeNotActiveError


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def challenges_list(request):
    """GET /engagement/challenges/ — list public active challenges."""
    now = timezone.now()
    qs  = Challenge.objects.filter(is_public=True, ends_at__gte=now).order_by("-starts_at")
    return Response(ChallengeSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def challenge_detail(request, pk):
    """GET /engagement/challenges/<pk>/"""
    try:
        obj = Challenge.objects.get(pk=pk)
    except Challenge.DoesNotExist:
        return Response(status=404)
    participants = obj.participants.select_related("user").order_by("rank")[:20]
    return Response({
        **ChallengeSerializer(obj).data,
        "top_participants": ChallengeParticipantSerializer(participants, many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@engagement_endpoint
def join_challenge(request, pk):
    """POST /engagement/challenges/<pk>/join/"""
    try:
        challenge = Challenge.objects.get(pk=pk)
    except Challenge.DoesNotExist:
        return Response(status=404)

    if not challenge.is_active:
        raise ChallengeNotActiveError()

    if challenge.max_participants > 0:
        if challenge.participants.count() >= challenge.max_participants:
            return Response({"error": "Challenge is full."}, status=400)

    tenant = getattr(request.user, "tenant", None)
    cp, created = ChallengeParticipant.objects.get_or_create(
        user=request.user, challenge=challenge,
        defaults={"tenant": tenant},
    )
    return Response({
        "joined":    created,
        "participant": ChallengeParticipantSerializer(cp).data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_challenges(request):
    """GET /engagement/challenges/mine/"""
    qs = (
        ChallengeParticipant.objects
        .filter(user=request.user)
        .select_related("challenge")
        .order_by("-joined_at")
    )
    return Response(ChallengeParticipantSerializer(qs, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def challenge_admin_list(request):
    if request.method == "GET":
        return Response(ChallengeSerializer(Challenge.objects.all().order_by("-starts_at"), many=True).data)
    s = ChallengeSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    s.save()
    return Response(s.data, status=201)

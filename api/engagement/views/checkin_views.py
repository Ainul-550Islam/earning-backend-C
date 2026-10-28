# engagement/views/checkin_views.py
from datetime import date
from django.db.models import Avg, Sum
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..services import CheckInService, GamificationEngine
from ..models.checkin import DailyCheckIn
from ..serializers import DailyCheckInSerializer
from ..utils.throttling import CheckInThrottle
from ..utils.decorators import engagement_endpoint
from ..utils.cache import invalidate_user_stats_cache


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([CheckInThrottle])
@engagement_endpoint
def daily_checkin(request):
    """POST /engagement/daily-checkin/ — perform today's check-in."""
    tenant = getattr(request.user, "tenant", None)
    result = CheckInService.process(request.user, tenant=tenant)
    GamificationEngine.on_checkin(request.user, result["checkin"], tenant=tenant)
    invalidate_user_stats_cache(request.user.pk)
    result_safe = {k: v for k, v in result.items() if k != "checkin"}
    return Response({"success": True, **result_safe})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def checkins_list(request):
    """GET /engagement/checkins/ — list check-ins (admin: all; user: own)."""
    qs = (
        DailyCheckIn.objects.all()
        if request.user.is_staff
        else DailyCheckIn.objects.filter(user=request.user)
    )
    if uid := request.query_params.get("user"):
        qs = qs.filter(user_id=uid)
    if dt := request.query_params.get("date"):
        qs = qs.filter(date=dt)
    qs = qs.select_related("user").order_by("-date")
    serializer = DailyCheckInSerializer(qs[:100], many=True)
    return Response({"results": serializer.data, "count": qs.count()})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def checkins_stats(request):
    """GET /engagement/checkins/stats/"""
    today = date.today()
    qs = DailyCheckIn.objects.all()
    my_qs = qs.filter(user=request.user)
    latest = my_qs.order_by("-date").first()
    return Response({
        "total_checkins_today":  qs.filter(date=today).count(),
        "total_checkins_ever":   qs.count(),
        "avg_consecutive_days":  qs.aggregate(avg=Avg("consecutive_days"))["avg"] or 0,
        "unique_users_today":    qs.filter(date=today).values("user").distinct().count(),
        "my_streak":             latest.consecutive_days if latest and latest.consecutive_days is not None else 0,
        "my_total_checkins":     my_qs.count(),
        "my_total_coins":        float(my_qs.aggregate(s=Sum("coins_earned"))["s"] or 0),
        "checked_in_today":      latest.date == today if latest and latest.date else False,
    })

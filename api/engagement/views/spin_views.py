# engagement/views/spin_views.py
from datetime import date
from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..services import SpinService, GamificationEngine
from ..models.spinwheel import SpinWheel
from ..serializers import SpinWheelSerializer
from ..utils.throttling import SpinThrottle
from ..utils.decorators import engagement_endpoint
from ..utils.cache import invalidate_user_stats_cache
from ..constants import SPIN_MAX_PER_DAY


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SpinThrottle])
@engagement_endpoint
def spin_wheel(request):
    """POST /engagement/spin-wheel/ — execute one spin."""
    tenant = getattr(request.user, "tenant", None)
    result = SpinService.spin(request.user, tenant=tenant)
    GamificationEngine.on_spin(request.user, result["spin"], tenant=tenant)
    invalidate_user_stats_cache(request.user.pk)
    result_safe = {k: v for k, v in result.items() if k != "spin"}
    return Response({"success": True, **result_safe})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def spins_list(request):
    """GET /engagement/spins/ — spin history."""
    qs = (
        SpinWheel.objects.all()
        if request.user.is_staff
        else SpinWheel.objects.filter(user=request.user)
    )
    if uid := request.query_params.get("user"):
        qs = qs.filter(user_id=uid)
    qs = qs.select_related("user").order_by("-spun_at")
    serializer = SpinWheelSerializer(qs[:100], many=True)
    return Response({"results": serializer.data, "count": qs.count()})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def spins_stats(request):
    """GET /engagement/spins/stats/"""
    today  = date.today()
    qs     = SpinWheel.objects.all()
    my_qs  = qs.filter(user=request.user)
    my_today = my_qs.filter(spun_at__date=today)
    return Response({
        "total_spins_today":     qs.filter(spun_at__date=today).count(),
        "total_coins_won_today": float(qs.filter(spun_at__date=today).aggregate(s=Sum("coins_won"))["s"] or 0),
        "total_spins_ever":      qs.count(),
        "total_coins_won_ever":  float(qs.aggregate(s=Sum("coins_won"))["s"] or 0),
        "my_spins_today":        my_today.count(),
        "my_spins_remaining":    max(0, SPIN_MAX_PER_DAY - my_today.count()),
        "my_total_coins_won":    float(my_qs.aggregate(s=Sum("coins_won"))["s"] or 0),
        "max_spins_per_day":     SPIN_MAX_PER_DAY,
    })

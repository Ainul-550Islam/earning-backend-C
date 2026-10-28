# engagement/views/xp_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ..services import XPService
from ..models.xp import XPTransaction
from ..serializers import UserXPSerializer, XPTransactionSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_xp(request):
    """GET /engagement/xp/ — current user's XP and level."""
    xp_obj = XPService.get_or_create(request.user)
    return Response(UserXPSerializer(xp_obj).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def xp_history(request):
    """GET /engagement/xp/history/ — XP transaction log."""
    qs = XPTransaction.objects.filter(user=request.user).order_by("-created_at")[:50]
    return Response({
        "results": XPTransactionSerializer(qs, many=True).data,
        "count":   qs.count(),
    })


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_grant_xp(request):
    """POST /engagement/xp/grant/ — admin grant XP to any user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user_id = request.data.get("user_id")
    amount  = request.data.get("amount")
    note    = request.data.get("note", "Admin grant")

    if not user_id or not amount:
        return Response({"error": "user_id and amount required"}, status=400)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    result = XPService.grant(user, int(amount), source="admin", note=note)
    return Response({"success": True, **result})

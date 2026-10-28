# engagement/views/notification_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from ..services import NotificationService
from ..models.notification import Notification, UserPushToken
from ..serializers import NotificationSerializer, UserPushTokenSerializer
from ..utils.pagination import EngagementPagination


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_list(request):
    """
    GET /engagement/notifications/
    Returns paginated notifications for the current user.
    Query params: ?unread_only=true, ?type=<notif_type>
    """
    qs = Notification.objects.filter(user=request.user).order_by("-created_at")

    if request.query_params.get("unread_only") == "true":
        qs = qs.filter(is_read=False)

    if notif_type := request.query_params.get("type"):
        qs = qs.filter(type=notif_type)

    paginator = EngagementPagination()
    page      = paginator.paginate_queryset(qs, request)
    serializer = NotificationSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_unread_count(request):
    """
    GET /engagement/notifications/unread-count/
    Returns the count of unread notifications for the current user.
    """
    count = NotificationService.unread_count(request.user)
    return Response({"unread_count": count})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, pk):
    """
    POST /engagement/notifications/<pk>/read/
    Marks a single notification as read.
    """
    NotificationService.mark_read(request.user, pk)
    return Response({"success": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """
    POST /engagement/notifications/read-all/
    Marks all of the current user's notifications as read.
    """
    NotificationService.mark_all_read(request.user)
    return Response({"success": True})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_notification(request, pk):
    """
    DELETE /engagement/notifications/<pk>/
    Deletes a single notification (only owner or admin can delete).
    """
    try:
        notif = Notification.objects.get(pk=pk, user=request.user)
    except Notification.DoesNotExist:
        return Response({"error": "Not found."}, status=404)
    notif.delete()
    return Response(status=204)


# ── Push Token Registration ───────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_push_token(request):
    """
    POST /engagement/notifications/push-token/
    Body: { "platform": "fcm", "token": "...", "device_id": "..." }
    Registers or updates a push notification token for the current device.
    """
    tenant = getattr(request.user, "tenant", None)
    data   = request.data.copy()
    data["user"] = request.user.pk

    token     = data.get("token")
    device_id = data.get("device_id", "")
    platform  = data.get("platform", "fcm")

    if not token:
        return Response({"error": "token is required."}, status=400)

    obj, created = UserPushToken.objects.update_or_create(
        user      = request.user,
        device_id = device_id,
        defaults  = {
            "platform":  platform,
            "token":     token,
            "is_active": True,
            "tenant":    tenant,
        },
    )
    return Response({
        "registered": True,
        "created":    created,
        "platform":   obj.platform,
        "device_id":  obj.device_id,
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def unregister_push_token(request):
    """
    DELETE /engagement/notifications/push-token/
    Body: { "device_id": "..." }
    Deactivates the push token for the given device.
    """
    device_id = request.data.get("device_id", "")
    updated   = UserPushToken.objects.filter(
        user=request.user, device_id=device_id
    ).update(is_active=False)
    return Response({"deactivated": updated > 0})


# ── Admin ─────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_send_notification(request):
    """
    POST /engagement/admin/notifications/send/
    Admin broadcast: send a notification to a specific user or all users.
    Body: { "user_id": 5, "type": "reward", "title": "...", "body": "..." }
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user_id    = request.data.get("user_id")
    notif_type = request.data.get("type", "reward")
    title      = request.data.get("title", "")
    body       = request.data.get("body", "")
    data_extra = request.data.get("data", {})
    tenant     = getattr(request.user, "tenant", None)

    if not title:
        return Response({"error": "title is required."}, status=400)

    if user_id:
        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        NotificationService.send(
            target_user, notif_type, title=title, body=body,
            data=data_extra, tenant=tenant,
        )
        return Response({"sent": 1})

    # Bulk broadcast to all active users
    users = User.objects.filter(is_active=True)
    NotificationService.bulk_send(users, notif_type, title=title, body=body,
                                  data=data_extra, tenant=tenant)
    return Response({"sent": users.count()})

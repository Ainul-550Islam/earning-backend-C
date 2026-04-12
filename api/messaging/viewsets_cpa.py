"""
CPA Messaging ViewSets — REST API endpoints for CPA notification system.
"""
from __future__ import annotations
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from .models import CPANotification, CPABroadcast, MessageTemplate, AffiliateConversationThread
from . import services_cpa

logger = logging.getLogger(__name__)


class CPANotificationViewSet(viewsets.GenericViewSet):
    """
    CPA Notification Inbox — Smart inbox for affiliate notifications.
    GET  /messaging/cpa-notifications/          → list all
    GET  /messaging/cpa-notifications/counts/   → unread counts by category
    POST /messaging/cpa-notifications/mark_read/ → mark read
    POST /messaging/cpa-notifications/mark_all_read/ → mark all read
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CPANotification.objects.filter(
            recipient=self.request.user,
            is_dismissed=False,
        ).order_by("-created_at")

    def list(self, request: Request) -> Response:
        """
        GET /messaging/cpa-notifications/?type=offers&unread=1&page=1
        """
        qs = self.get_queryset()

        # Filter by category
        cat = request.query_params.get("type", "")
        TYPE_MAP = {
            "offers":      ["offer.approved", "offer.rejected", "offer.paused",
                            "offer.new", "offer.expiring", "offer.reactivated"],
            "conversions": ["conversion.received", "conversion.approved",
                            "conversion.rejected", "conversion.chargeback", "postback.failed"],
            "payments":    ["payout.processed", "payout.reminder",
                            "payout.threshold", "payout.failed", "payout.hold"],
            "account":     ["affiliate.approved", "affiliate.rejected", "affiliate.suspended",
                            "affiliate.reinstated", "affiliate.banned", "affiliate.manager"],
            "system":      ["system.maintenance", "system.announcement",
                            "api.key_expiring", "terms.updated"],
            "performance": ["milestone.reached", "epc.drop", "fraud.alert"],
        }
        if cat and cat in TYPE_MAP:
            qs = qs.filter(notification_type__in=TYPE_MAP[cat])

        if request.query_params.get("unread") == "1":
            qs = qs.filter(is_read=False)

        page = self.paginate_queryset(qs[:100])
        data = [{
            "id":                str(n.id),
            "type":              n.notification_type,
            "title":             n.title,
            "body":              n.body,
            "priority":          n.priority,
            "object_type":       n.object_type,
            "object_id":         n.object_id,
            "action_url":        n.action_url,
            "action_label":      n.action_label,
            "payload":           n.payload,
            "is_read":           n.is_read,
            "read_at":           n.read_at.isoformat() if n.read_at else None,
            "created_at":        n.created_at.isoformat(),
        } for n in (page or qs)]

        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

    @action(detail=False, methods=["get"])
    def counts(self, request: Request) -> Response:
        """GET /messaging/cpa-notifications/counts/ — Unread counts by category."""
        counts = services_cpa.get_unread_notification_counts(request.user.pk)
        return Response(counts)

    @action(detail=True, methods=["post"])
    def mark_read(self, request: Request, pk=None) -> Response:
        ok = services_cpa.mark_notification_read(notification_id=pk, user_id=request.user.pk)
        return Response({"marked_read": ok})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request: Request) -> Response:
        notif_type = request.data.get("type")
        count = services_cpa.mark_all_notifications_read(
            user_id=request.user.pk,
            notification_type=notif_type,
        )
        return Response({"marked_read": count})

    @action(detail=True, methods=["post"])
    def dismiss(self, request: Request, pk=None) -> Response:
        CPANotification.objects.filter(pk=pk, recipient=request.user).update(is_dismissed=True)
        return Response({"dismissed": True})

    @action(detail=False, methods=["post"])
    def dismiss_all(self, request: Request) -> Response:
        count = CPANotification.objects.filter(
            recipient=request.user, is_read=True, is_dismissed=False
        ).update(is_dismissed=True)
        return Response({"dismissed": count})


class CPABroadcastViewSet(viewsets.GenericViewSet):
    """
    CPA Broadcast management — admin sends targeted messages to affiliates.
    POST /messaging/cpa-broadcasts/send/          → send immediately
    POST /messaging/cpa-broadcasts/schedule/      → schedule for later
    GET  /messaging/cpa-broadcasts/{id}/analytics/ → open/click rates
    POST /messaging/cpa-broadcasts/{id}/track_open/
    POST /messaging/cpa-broadcasts/{id}/track_click/
    """
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return CPABroadcast.objects.all().order_by("-created_at")

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()[:50]
        data = [{
            "id":               str(b.id),
            "title":            b.title,
            "status":           b.status,
            "audience_filter":  b.audience_filter,
            "recipient_count":  b.recipient_count,
            "delivered_count":  b.delivered_count,
            "opened_count":     b.opened_count,
            "clicked_count":    b.clicked_count,
            "open_rate":        b.open_rate,
            "click_rate":       b.click_rate,
            "scheduled_at":     b.scheduled_at.isoformat() if b.scheduled_at else None,
            "sent_at":          b.sent_at.isoformat() if b.sent_at else None,
            "created_at":       b.created_at.isoformat(),
        } for b in qs]
        return Response(data)

    @action(detail=False, methods=["post"])
    def send(self, request: Request) -> Response:
        """Send a broadcast immediately."""
        try:
            broadcast = services_cpa.send_cpa_broadcast(
                title=request.data.get("title", ""),
                body=request.data.get("body", ""),
                audience_filter=request.data.get("audience_filter", "all"),
                audience_params=request.data.get("audience_params", {}),
                notification_type=request.data.get("notification_type", "system.announcement"),
                priority=request.data.get("priority", "NORMAL"),
                send_push=request.data.get("send_push", True),
                send_email=request.data.get("send_email", False),
                send_inbox=request.data.get("send_inbox", True),
                action_url=request.data.get("action_url", ""),
                action_label=request.data.get("action_label", ""),
                template_id=request.data.get("template_id"),
                created_by_id=request.user.pk,
                tenant=getattr(request, "tenant", None),
            )
            return Response({"id": str(broadcast.id), "status": broadcast.status}, status=201)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)

    @action(detail=False, methods=["post"])
    def schedule(self, request: Request) -> Response:
        """Schedule a broadcast for a future time."""
        from django.utils.dateparse import parse_datetime
        scheduled_at_str = request.data.get("scheduled_at")
        scheduled_at = parse_datetime(scheduled_at_str) if scheduled_at_str else None
        if not scheduled_at:
            return Response({"detail": "scheduled_at is required (ISO datetime)."}, status=400)

        broadcast = services_cpa.send_cpa_broadcast(
            title=request.data.get("title", ""),
            body=request.data.get("body", ""),
            audience_filter=request.data.get("audience_filter", "all"),
            audience_params=request.data.get("audience_params", {}),
            notification_type=request.data.get("notification_type", "system.announcement"),
            priority=request.data.get("priority", "NORMAL"),
            send_push=request.data.get("send_push", True),
            send_email=request.data.get("send_email", False),
            created_by_id=request.user.pk,
            scheduled_at=scheduled_at,
            tenant=getattr(request, "tenant", None),
        )
        return Response({"id": str(broadcast.id), "status": "SCHEDULED",
                         "scheduled_at": scheduled_at.isoformat()}, status=201)

    @action(detail=True, methods=["get"])
    def analytics(self, request: Request, pk=None) -> Response:
        try:
            b = CPABroadcast.objects.get(pk=pk)
        except CPABroadcast.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        return Response({
            "id":              str(b.id),
            "title":           b.title,
            "status":          b.status,
            "recipient_count": b.recipient_count,
            "delivered_count": b.delivered_count,
            "opened_count":    b.opened_count,
            "clicked_count":   b.clicked_count,
            "open_rate":       b.open_rate,
            "click_rate":      b.click_rate,
            "delivery_rate":   round(b.delivered_count / b.recipient_count * 100, 1) if b.recipient_count else 0,
        })

    @action(detail=True, methods=["post"])
    def track_open(self, request: Request, pk=None) -> Response:
        """Track that the current user opened this broadcast."""
        services_cpa.track_broadcast_open(broadcast_id=pk, user_id=request.user.pk)
        return Response({"tracked": True})

    @action(detail=True, methods=["post"])
    def track_click(self, request: Request, pk=None) -> Response:
        """Track CTA button click."""
        services_cpa.track_broadcast_click(broadcast_id=pk, user_id=request.user.pk)
        return Response({"tracked": True})

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk=None) -> Response:
        updated = CPABroadcast.objects.filter(pk=pk, status__in=["DRAFT", "SCHEDULED"]).update(status="CANCELLED")
        return Response({"cancelled": bool(updated)})


class MessageTemplateViewSet(viewsets.ModelViewSet):
    """
    Message template management for admins.
    Reusable templates with variable substitution.
    """
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return MessageTemplate.objects.filter(is_active=True).order_by("-usage_count")

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        cat = request.query_params.get("category")
        if cat:
            qs = qs.filter(category=cat)
        data = [{
            "id":          str(t.id),
            "name":        t.name,
            "category":    t.category,
            "subject":     t.subject,
            "body":        t.body[:200] + ("…" if len(t.body) > 200 else ""),
            "tags":        t.tags,
            "usage_count": t.usage_count,
        } for t in qs]
        return Response(data)

    def create(self, request: Request) -> Response:
        t = services_cpa.create_template(
            name=request.data.get("name", ""),
            body=request.data.get("body", ""),
            subject=request.data.get("subject", ""),
            category=request.data.get("category", "custom"),
            tags=request.data.get("tags", []),
            created_by_id=request.user.pk,
            tenant=getattr(request, "tenant", None),
        )
        return Response({"id": str(t.id), "name": t.name}, status=201)

    def retrieve(self, request: Request, pk=None) -> Response:
        try:
            t = MessageTemplate.objects.get(pk=pk)
            return Response({
                "id": str(t.id), "name": t.name, "category": t.category,
                "subject": t.subject, "body": t.body, "tags": t.tags, "usage_count": t.usage_count,
            })
        except MessageTemplate.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

    def destroy(self, request: Request, pk=None) -> Response:
        MessageTemplate.objects.filter(pk=pk).update(is_active=False)
        return Response(status=204)

    @action(detail=True, methods=["post"])
    def preview(self, request: Request, pk=None) -> Response:
        """Preview a template with sample context variables."""
        try:
            t = MessageTemplate.objects.get(pk=pk)
            context = request.data.get("context", {
                "affiliate_name": "John Doe",
                "offer_name": "Sample Offer",
                "amount": "$150.00",
                "manager_name": "Jane Smith",
                "platform_name": "CPANet",
            })
            subject, body = t.render(context)
            # Rollback usage count increment for preview
            MessageTemplate.objects.filter(pk=pk).update(usage_count=t.usage_count)
            return Response({"subject": subject, "body": body})
        except MessageTemplate.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

    @action(detail=True, methods=["post"])
    def send_to_user(self, request: Request, pk=None) -> Response:
        """Send a template-based notification to a specific user."""
        recipient_id = request.data.get("recipient_id")
        context = request.data.get("context", {})
        if not recipient_id:
            return Response({"detail": "recipient_id required."}, status=400)
        try:
            notif = services_cpa.send_from_template(
                template_id=pk,
                recipient_id=recipient_id,
                context=context,
                tenant=getattr(request, "tenant", None),
            )
            return Response({"notification_id": str(notif.id)}, status=201)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=404)


class AffiliateThreadViewSet(viewsets.GenericViewSet):
    """
    Affiliate ↔ Manager conversation threads.
    Managers can see all their affiliate threads.
    Affiliates can only see their own thread.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return AffiliateConversationThread.objects.filter(
                manager=user
            ).select_related("affiliate", "manager").order_by("-last_message_at")
        else:
            return AffiliateConversationThread.objects.filter(
                affiliate=user
            ).select_related("affiliate", "manager")

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        data = [{
            "id":               str(t.id),
            "affiliate_id":     str(t.affiliate_id),
            "manager_id":       str(t.manager_id) if t.manager_id else None,
            "chat_id":          str(t.chat_id) if t.chat_id else None,
            "status":           t.status,
            "affiliate_unread": t.affiliate_unread,
            "manager_unread":   t.manager_unread,
            "last_message_at":  t.last_message_at.isoformat() if t.last_message_at else None,
            "tags":             t.tags,
        } for t in qs]
        return Response(data)

    @action(detail=False, methods=["post"])
    def get_or_create_my_thread(self, request: Request) -> Response:
        """Get or create the current user's affiliate thread."""
        thread = services_cpa.get_or_create_affiliate_thread(
            affiliate_id=request.user.pk,
            tenant=getattr(request, "tenant", None),
        )
        return Response({
            "thread_id": str(thread.id),
            "chat_id": str(thread.chat_id) if thread.chat_id else None,
            "manager_id": str(thread.manager_id) if thread.manager_id else None,
        })

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def reassign_manager(self, request: Request, pk=None) -> Response:
        new_manager_id = request.data.get("manager_id")
        if not new_manager_id:
            return Response({"detail": "manager_id required."}, status=400)
        try:
            thread = AffiliateConversationThread.objects.get(pk=pk)
            thread = services_cpa.reassign_affiliate_manager(
                affiliate_id=thread.affiliate_id,
                new_manager_id=new_manager_id,
                notify=True,
                tenant=getattr(request, "tenant", None),
            )
            return Response({"manager_id": str(new_manager_id), "reassigned": True})
        except AffiliateConversationThread.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def add_tags(self, request: Request, pk=None) -> Response:
        tags = request.data.get("tags", [])
        thread = AffiliateConversationThread.objects.get(pk=pk)
        existing = thread.tags or []
        new_tags = list(set(existing + tags))
        AffiliateConversationThread.objects.filter(pk=pk).update(tags=new_tags)
        return Response({"tags": new_tags})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def add_note(self, request: Request, pk=None) -> Response:
        note = request.data.get("note", "")
        AffiliateConversationThread.objects.filter(pk=pk).update(notes=note)
        return Response({"saved": True})

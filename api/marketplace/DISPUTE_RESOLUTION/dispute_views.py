"""
DISPUTE_RESOLUTION/dispute_views.py — ViewSets for Dispute domain
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .dispute_model import Dispute, DisputeMessage, DisputeEvidence
from .dispute_serializers import (
    DisputeSerializer, DisputeListSerializer,
    DisputeMessageSerializer, DisputeEvidenceSerializer,
)
from .dispute_resolution import DisputeResolutionService, DisputeAlreadyExists


class DisputeViewSet(viewsets.ModelViewSet):
    """Full dispute lifecycle management."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "list":
            return DisputeListSerializer
        return DisputeSerializer

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        qs = Dispute.objects.filter(tenant=tenant).select_related(
            "order", "raised_by", "against_seller"
        ).prefetch_related("messages", "evidences")
        user = self.request.user
        if not user.is_staff:
            # Buyers see disputes they raised; sellers see disputes against them
            from api.marketplace.models import SellerProfile
            try:
                seller = SellerProfile.objects.get(user=user, tenant=tenant)
                qs = qs.filter(raised_by=user) | qs.filter(against_seller=seller)
            except SellerProfile.DoesNotExist:
                qs = qs.filter(raised_by=user)
        return qs.distinct().order_by("-created_at")

    def perform_create(self, serializer):
        data = serializer.validated_data
        try:
            dispute = DisputeResolutionService.raise_dispute(
                order_item=data["order_item"],
                buyer=self.request.user,
                dispute_type=data["dispute_type"],
                description=data.get("description", ""),
            )
            serializer.instance = dispute
        except DisputeAlreadyExists as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})
        except Exception as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        """Seller responds to a dispute."""
        dispute = self.get_object()
        message = request.data.get("message", "")
        DisputeResolutionService.seller_respond(dispute, request.user, message)
        return Response({"status": "response recorded"})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def escalate(self, request, pk=None):
        dispute = self.get_object()
        note = request.data.get("note", "")
        DisputeResolutionService.admin_escalate(dispute, request.user, note)
        return Response({"status": "escalated"})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def arbitrate(self, request, pk=None):
        dispute = self.get_object()
        _VERDICT_MAP = {
            "resolved_buyer": "buyer_wins",
            "resolved_seller": "seller_wins",
            "buyer_wins": "buyer_wins",
            "seller_wins": "seller_wins",
            "partial": "partial",
        }
        raw_verdict = request.data.get("verdict", "")
        verdict = _VERDICT_MAP.get(raw_verdict, raw_verdict)
        note = request.data.get("note", "")
        try:
            DisputeResolutionService.admin_arbitrate(
                dispute=dispute,
                admin_user=request.user,
                verdict=verdict,
                reason=note,
                refund_percent=float(request.data.get("refund_percent", 100.0)),
            )
        except Exception as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})
        dispute.refresh_from_db()
        return Response(DisputeSerializer(dispute).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Buyer voluntarily closes the dispute."""
        dispute = self.get_object()
        reason = request.data.get("reason", "")
        DisputeResolutionService.buyer_close(dispute, request.user, reason)
        return Response({"status": "closed"})

    @action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        dispute = self.get_object()
        if request.method == "GET":
            msgs = dispute.messages.all().order_by("created_at")
            return Response(DisputeMessageSerializer(msgs, many=True).data)
        serializer = DisputeMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            dispute=dispute,
            sender=request.user,
            tenant=getattr(request, "tenant", None),
        )
        return Response(serializer.data, status=201)

    @action(detail=True, methods=["post"])
    def add_evidence(self, request, pk=None):
        dispute = self.get_object()
        serializer = DisputeEvidenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            dispute=dispute,
            uploader=request.user,
            tenant=getattr(request, "tenant", None),
        )
        return Response(serializer.data, status=201)

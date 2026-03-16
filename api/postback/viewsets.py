"""viewsets.py – DRF ViewSets for the postback module."""
import logging
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .filters import NetworkPostbackConfigFilter, PostbackLogFilter
from .models import DuplicateLeadCheck, LeadValidator, NetworkPostbackConfig, PostbackLog
from .permissions import IsPostbackAdmin, IsReadOnlyOrAdmin
from .serializers import (
    DuplicateLeadCheckSerializer,
    LeadValidatorSerializer,
    NetworkPostbackConfigDetailSerializer,
    NetworkPostbackConfigListSerializer,
    NetworkPostbackConfigWriteSerializer,
    PostbackLogDetailSerializer,
    PostbackLogSerializer,
)

logger = logging.getLogger(__name__)


class NetworkPostbackConfigViewSet(viewsets.ModelViewSet):
    """
    CRUD for network postback configurations.
    Staff only. Secret key is write-only.
    """
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = NetworkPostbackConfigFilter
    search_fields = ["name", "network_key"]
    ordering_fields = ["name", "created_at", "status"]
    ordering = ["name"]

    def get_queryset(self):
        return NetworkPostbackConfig.objects.all().order_by("name")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return NetworkPostbackConfigWriteSerializer
        if self.action == "retrieve":
            return NetworkPostbackConfigDetailSerializer
        return NetworkPostbackConfigListSerializer

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        """Switch a network to ACTIVE status."""
        from .choices import ValidatorStatus
        network = self.get_object()
        network.status = ValidatorStatus.ACTIVE
        network.save(update_fields=["status", "updated_at"])
        logger.info("Admin %s activated network %s", request.user.pk, network.network_key)
        return Response(NetworkPostbackConfigDetailSerializer(network).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        """Switch a network to INACTIVE status."""
        from .choices import ValidatorStatus
        network = self.get_object()
        network.status = ValidatorStatus.INACTIVE
        network.save(update_fields=["status", "updated_at"])
        logger.info("Admin %s deactivated network %s", request.user.pk, network.network_key)
        return Response(NetworkPostbackConfigDetailSerializer(network).data)

    @action(detail=True, methods=["get", "post"], url_path="validators")
    def validators(self, request, pk=None):
        """List or create LeadValidators for this network."""
        network = self.get_object()
        if request.method == "GET":
            qs = LeadValidator.objects.filter(network=network).order_by("sort_order")
            return Response(LeadValidatorSerializer(qs, many=True).data)
        # POST – create a new validator
        serializer = LeadValidatorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(network=network)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        """Quick stats for a specific network."""
        from django.db.models import Count, Q
        from .choices import PostbackStatus
        network = self.get_object()
        agg = PostbackLog.objects.filter(network=network).aggregate(
            total=Count("id"),
            rewarded=Count("id", filter=Q(status=PostbackStatus.REWARDED)),
            rejected=Count("id", filter=Q(status=PostbackStatus.REJECTED)),
            duplicate=Count("id", filter=Q(status=PostbackStatus.DUPLICATE)),
            failed=Count("id", filter=Q(status=PostbackStatus.FAILED)),
        )
        return Response({"network": network.network_key, **agg})


class PostbackLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only log viewer for admins.
    retry action re-queues a failed log.
    """
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = PostbackLogFilter
    ordering_fields = ["received_at", "processed_at", "status", "payout"]
    ordering = ["-received_at"]

    def get_queryset(self):
        return PostbackLog.objects.select_related("network", "resolved_user").all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostbackLogDetailSerializer
        return PostbackLogSerializer

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        """Re-queue a failed/rejected log for reprocessing."""
        from .tasks import process_postback
        from .choices import PostbackStatus
        log = self.get_object()
        if log.status not in (PostbackStatus.FAILED, PostbackStatus.REJECTED):
            return Response(
                {"detail": "Only FAILED or REJECTED logs can be retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        process_postback.delay(
            str(log.pk),
            signature="", timestamp_str="", nonce="",
            body_bytes_hex="", path="", query_params={},
        )
        logger.info("Admin %s retried postback log %s", request.user.pk, pk)
        return Response({"status": "queued"})


class DuplicateLeadCheckViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Admin view of the dedup table.
    DELETE on a specific entry allows manual dedup clearance (re-allow a lead).
    """
    serializer_class = DuplicateLeadCheckSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ["-first_seen_at"]

    def get_queryset(self):
        return DuplicateLeadCheck.objects.select_related("network").all()

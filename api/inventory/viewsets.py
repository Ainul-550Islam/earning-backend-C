"""viewsets.py – DRF ViewSets for the inventory module."""
import logging
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .exceptions import ItemNotFoundException
from .filters import RedemptionCodeFilter, RewardItemFilter, UserInventoryFilter
from .models import RedemptionCode, RewardItem, StockEvent, UserInventory
from .pagination import CodePagination, InventoryPagination, StandardPagination
from .permissions import CanAwardItems, CanManageInventory, IsAdminOrReadOnly, IsInventoryOwner
from .serializers import (
    AdjustStockSerializer,
    AwardItemSerializer,
    BulkImportCodesSerializer,
    GenerateCodesSerializer,
    RedemptionCodeSerializer,
    RestockSerializer,
    RewardItemDetailSerializer,
    RewardItemListSerializer,
    RewardItemWriteSerializer,
    RevokeInventorySerializer,
    StockEventSerializer,
    UserInventorySerializer,
)
from .services import (
    adjust_stock,
    award_item_to_user,
    bulk_import_codes,
    generate_and_import_codes,
    get_active_items,
    restock_item,
    revoke_inventory,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class RewardItemViewSet(viewsets.ModelViewSet):
    """
    CRUD for reward items.
    Public read access; write operations require staff.
    Custom actions: restock, adjust_stock, bulk_import_codes, generate_codes, stock_history, award.
    """
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = RewardItemFilter
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["sort_order", "name", "points_cost", "current_stock", "created_at"]
    ordering = ["sort_order", "name"]
    pagination_class = StandardPagination
    lookup_field = "slug"

    def get_queryset(self):
        qs = RewardItem.objects.with_stock_manager()
        if not self.request.user.is_staff:
            qs = qs.active().in_stock()
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RewardItemWriteSerializer
        if self.action == "retrieve":
            return RewardItemDetailSerializer
        return RewardItemListSerializer

    @action(detail=True, methods=["post"], url_path="restock", permission_classes=[IsAdminUser])
    def restock(self, request, slug=None):
        item = self.get_object()
        serializer = RestockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = restock_item(
            item.pk,
            quantity=serializer.validated_data["quantity"],
            performed_by=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(RewardItemDetailSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="adjust-stock", permission_classes=[IsAdminUser])
    def adjust_stock_action(self, request, slug=None):
        item = self.get_object()
        serializer = AdjustStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = adjust_stock(
            item.pk,
            delta=serializer.validated_data["delta"],
            performed_by=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(RewardItemDetailSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="bulk-import-codes", permission_classes=[IsAdminUser])
    def bulk_import_codes_action(self, request, slug=None):
        item = self.get_object()
        serializer = BulkImportCodesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        count = bulk_import_codes(
            item.pk,
            codes=d["codes"],
            batch_id=d.get("batch_id", ""),
            expires_at=d.get("expires_at"),
            performed_by=request.user,
        )
        return Response({"imported": count}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="generate-codes", permission_classes=[IsAdminUser])
    def generate_codes_action(self, request, slug=None):
        item = self.get_object()
        serializer = GenerateCodesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        count = generate_and_import_codes(
            item.pk,
            count=d["count"],
            batch_id=d.get("batch_id", ""),
            expires_at=d.get("expires_at"),
            performed_by=request.user,
        )
        return Response({"generated": count}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="stock-history", permission_classes=[IsAdminUser])
    def stock_history(self, request, slug=None):
        item = self.get_object()
        events = StockEvent.objects.filter(item=item).order_by("-created_at")
        page = self.paginate_queryset(events)
        serializer = StockEventSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"], url_path="award", permission_classes=[CanAwardItems])
    def award(self, request, slug=None):
        """Award this item to a user directly (staff action)."""
        item = self.get_object()
        serializer = AwardItemSerializer(data={**request.data, "item_id": str(item.pk)})
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            user = User.objects.get(pk=d["user_id"])
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        inventory = award_item_to_user(
            user=user,
            item_id=item.pk,
            delivery_method=d.get("delivery_method", "email"),
            postback_reference=d.get("postback_reference", ""),
            expires_at=d.get("expires_at"),
            awarded_by=request.user,
        )
        return Response(UserInventorySerializer(inventory).data, status=status.HTTP_201_CREATED)


class UserInventoryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    User's own inventory. Staff see all.
    Custom actions: claim, revoke.
    """
    serializer_class = UserInventorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = InventoryPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = UserInventoryFilter
    ordering_fields = ["created_at", "delivered_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = UserInventory.objects.with_item()
        if self.request.user.is_staff:
            return qs.all()
        return qs.filter(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="claim")
    def claim(self, request, pk=None):
        """Mark a delivered inventory entry as claimed."""
        inv = self.get_object()
        if inv.user != request.user and not request.user.is_staff:
            return Response({"detail": "Not your inventory."}, status=status.HTTP_403_FORBIDDEN)
        if not inv.is_claimable:
            return Response(
                {"detail": "Item is not claimable."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        inv.mark_claimed()
        return Response(UserInventorySerializer(inv).data)

    @action(detail=True, methods=["post"], url_path="revoke", permission_classes=[IsAdminUser])
    def revoke(self, request, pk=None):
        """Revoke an inventory entry (admin only). Restores stock."""
        inv = self.get_object()
        serializer = RevokeInventorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = revoke_inventory(
            inv.pk,
            reason=serializer.validated_data["reason"],
            revoked_by=request.user,
        )
        return Response(UserInventorySerializer(updated).data)


class RedemptionCodeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Admin-only view of redemption codes."""
    serializer_class = RedemptionCodeSerializer
    permission_classes = [IsAdminUser]
    pagination_class = CodePagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = RedemptionCodeFilter
    ordering_fields = ["created_at", "status", "expires_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return RedemptionCode.objects.select_related("item", "redeemed_by").all()

    @action(detail=True, methods=["post"], url_path="void")
    def void(self, request, pk=None):
        code = self.get_object()
        reason = request.data.get("reason", "Voided by admin.")
        code.void(reason=reason)
        return Response(RedemptionCodeSerializer(code).data)

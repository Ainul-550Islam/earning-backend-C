from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers

from .choices import DeliveryMethod, InventoryStatus, ItemType
from .models import RedemptionCode, RewardItem, StockEvent, StockManager, UserInventory


class StockManagerSerializer(serializers.ModelSerializer):
    alert_level_display = serializers.CharField(
        source="get_alert_level_display", read_only=True
    )

    class Meta:
        model = StockManager
        fields = [
            "low_stock_threshold", "critical_stock_threshold",
            "alert_level", "alert_level_display", "reorder_quantity",
        ]


class RewardItemListSerializer(serializers.ModelSerializer):
    item_type_display = serializers.CharField(source="get_item_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    is_unlimited = serializers.BooleanField(read_only=True)

    class Meta:
        model = RewardItem
        fields = [
            "id", "name", "slug", "description", "item_type", "item_type_display",
            "status", "status_display", "points_cost", "cash_value",
            "current_stock", "is_in_stock", "is_unlimited", "total_redeemed",
            "delivery_method", "max_per_user", "image_url", "thumbnail_url",
            "sort_order", "is_featured", "tags",
        ]


class RewardItemDetailSerializer(RewardItemListSerializer):
    stock_manager = StockManagerSerializer(read_only=True)

    class Meta(RewardItemListSerializer.Meta):
        fields = RewardItemListSerializer.Meta.fields + [
            "delivery_template", "delivery_callback_url",
            "is_transferable", "requires_shipping_address",
            "stock_manager", "metadata", "created_at", "updated_at",
        ]


class RewardItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RewardItem
        fields = [
            "name", "slug", "description", "item_type", "status",
            "points_cost", "cash_value", "current_stock", "delivery_method",
            "delivery_template", "delivery_callback_url", "max_per_user",
            "is_transferable", "requires_shipping_address",
            "image_url", "thumbnail_url", "sort_order", "is_featured",
            "tags", "metadata",
        ]

    def validate_current_stock(self, value):
        from .constants import UNLIMITED_STOCK
        if value != UNLIMITED_STOCK and value < 0:
            raise serializers.ValidationError(
                f"Stock must be ≥ 0 or {UNLIMITED_STOCK} for unlimited."
            )
        return value


class RestockSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class AdjustStockSerializer(serializers.Serializer):
    delta = serializers.IntegerField()
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_delta(self, value):
        if value == 0:
            raise serializers.ValidationError("Delta cannot be zero.")
        return value


class BulkImportCodesSerializer(serializers.Serializer):
    codes = serializers.ListField(
        child=serializers.CharField(max_length=100, trim_whitespace=True),
        min_length=1,
    )
    batch_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future.")
        return value


class GenerateCodesSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=1, max_value=10_000)
    batch_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class RedemptionCodeSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = RedemptionCode
        fields = [
            "id", "code", "status", "status_display", "batch_id",
            "expires_at", "redeemed_at", "is_available", "is_expired",
            "created_at",
        ]
        read_only_fields = fields


class AwardItemSerializer(serializers.Serializer):
    """Input for awarding an item to a specific user."""
    item_id = serializers.UUIDField()
    user_id = serializers.IntegerField()
    delivery_method = serializers.ChoiceField(
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.EMAIL,
        required=False,
    )
    postback_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_item_id(self, value):
        if not RewardItem.objects.filter(pk=value, status="active").exists():
            raise serializers.ValidationError("Active item not found.")
        return value


class UserInventorySerializer(serializers.ModelSerializer):
    item = RewardItemListSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    delivery_method_display = serializers.CharField(
        source="get_delivery_method_display", read_only=True
    )
    is_claimable = serializers.BooleanField(read_only=True)
    code_value = serializers.SerializerMethodField()

    class Meta:
        model = UserInventory
        fields = [
            "id", "item", "status", "status_display",
            "delivery_method", "delivery_method_display",
            "delivered_at", "claimed_at", "expires_at",
            "delivery_attempts", "delivery_error",
            "is_claimable", "code_value",
            "awarded_by_postback", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_code_value(self, obj) -> str:
        """Expose code only after delivery."""
        if obj.status in (InventoryStatus.DELIVERED, InventoryStatus.CLAIMED):
            if obj.redemption_code:
                return obj.redemption_code.code
        return ""


class RevokeInventorySerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class StockEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(
        source="get_event_type_display", read_only=True
    )
    performed_by_username = serializers.SerializerMethodField()

    class Meta:
        model = StockEvent
        fields = [
            "id", "event_type", "event_type_display",
            "quantity_delta", "stock_before", "stock_after",
            "reference_id", "performed_by_username", "note", "created_at",
        ]

    def get_performed_by_username(self, obj) -> str:
        return obj.performed_by.username if obj.performed_by else ""

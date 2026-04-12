from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .choices import CodeStatus, InventoryStatus, StockAlertLevel
from .models import RedemptionCode, RewardItem, StockEvent, StockManager, UserInventory


class StockManagerInline(admin.StackedInline):
    model = StockManager
    extra = 0
    fields = (
        "low_stock_threshold", "critical_stock_threshold",
        "alert_level", "alert_sent", "reorder_quantity", "notes",
    )
    readonly_fields = ("alert_level", "alert_sent")


class StockEventInline(admin.TabularInline):
    model = StockEvent
    extra = 0
    readonly_fields = (
        "event_type", "quantity_delta", "stock_before", "stock_after",
        "reference_id", "performed_by", "note", "created_at",
    )
    can_delete = False
    max_num = 20
    ordering = ("-created_at",)


@admin.register(RewardItem)
class RewardItemAdmin(admin.ModelAdmin):
    list_display = (
        "name", "item_type", "status_badge", "stock_display",
        "points_cost", "total_redeemed", "is_featured",
    )
    list_filter = ("status", "item_type", "delivery_method", "is_featured")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = (
        "id", "total_redeemed", "created_at", "updated_at",
        "is_in_stock", "is_unlimited",
    )
    inlines = [StockManagerInline, StockEventInline]
    list_editable = ("is_featured",)

    fieldsets = (
        (None, {"fields": ("id", "name", "slug", "description", "item_type", "status")}),
        (_("Pricing"), {"fields": ("points_cost", "cash_value")}),
        (_("Stock"), {"fields": (
            "current_stock", "total_redeemed", "is_in_stock", "is_unlimited"
        )}),
        (_("Delivery"), {"fields": (
            "delivery_method", "delivery_template", "delivery_callback_url"
        )}),
        (_("Limits"), {"fields": ("max_per_user", "is_transferable", "requires_shipping_address")}),
        (_("Presentation"), {"fields": (
            "image_url", "thumbnail_url", "sort_order", "is_featured", "tags"
        )}),
        (_("Metadata"), {"fields": ("metadata",), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        colors = {
            "active": "green", "draft": "gray", "paused": "orange",
            "out_of_stock": "red", "discontinued": "darkred", "archived": "black",
        }
        return format_html(
            '<b style="color:{};">{}</b>', colors.get(obj.status, "black"),
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")

    def stock_display(self, obj):
        if obj.is_unlimited:
            return format_html('<span style="color:blue;">∞ Unlimited</span>')
        color = "green" if obj.current_stock > 10 else ("orange" if obj.current_stock > 0 else "red")
        return format_html('<b style="color:{};">{}</b>', color, obj.current_stock)
    stock_display.short_description = _("Stock")


@admin.register(RedemptionCode)
class RedemptionCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "item", "status_badge", "batch_id", "expires_at", "redeemed_at")
    list_filter = ("status", "item")
    search_fields = ("code", "batch_id", "redeemed_by__email")
    readonly_fields = ("id", "created_at", "updated_at", "redeemed_at", "redeemed_by")

    def status_badge(self, obj):
        colors = {
            CodeStatus.AVAILABLE: "green",
            CodeStatus.REDEEMED: "blue",
            CodeStatus.EXPIRED: "gray",
            CodeStatus.VOIDED: "red",
            CodeStatus.RESERVED: "orange",
        }
        return format_html(
            '<b style="color:{};">{}</b>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")


@admin.register(UserInventory)
class UserInventoryAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "item", "status_badge",
        "delivery_method", "delivered_at", "delivery_attempts",
    )
    list_filter = ("status", "delivery_method", "item")
    search_fields = ("user__email", "user__username", "item__name", "awarded_by_postback")
    raw_id_fields = ("user", "item", "redemption_code", "revoked_by")
    readonly_fields = (
        "id", "created_at", "updated_at", "delivered_at", "claimed_at",
        "delivery_attempts", "last_delivery_attempt_at",
    )

    def status_badge(self, obj):
        colors = {
            InventoryStatus.PENDING: "orange",
            InventoryStatus.DELIVERED: "green",
            InventoryStatus.CLAIMED: "blue",
            InventoryStatus.FAILED: "red",
            InventoryStatus.REVOKED: "darkred",
            InventoryStatus.EXPIRED: "gray",
        }
        return format_html(
            '<b style="color:{};">{}</b>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")

    @admin.action(description=_("Retry delivery for selected inventory items"))
    def retry_delivery(self, request, queryset):
        from .tasks import deliver_inventory_item
        queued = 0
        for inv in queryset.filter(status=InventoryStatus.FAILED):
            deliver_inventory_item.delay(str(inv.pk))
            queued += 1
        self.message_user(request, f"Queued {queued} delivery retry task(s).")

    actions = ["retry_delivery"]


# Force register all models
from django.apps import apps as _apps
_app_label = __name__.split(chr(46))[1]
for _model in _apps.get_app_config(_app_label).get_models():
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass


def _force_register_inventory():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(RewardItem, RewardItemAdmin), (RedemptionCode, RedemptionCodeAdmin), (UserInventory, UserInventoryAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] inventory registered {registered} models")
    except Exception as e:
        print(f"[WARN] inventory: {e}")

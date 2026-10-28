# engagement/admin/shop_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from ..models.shop import ShopItem, ShopPurchase, UserInventory
from .mixins import TenantFilterMixin, UserLinkMixin


@admin.register(ShopItem)
class ShopItemAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = [
        "icon_display", "name", "type_badge", "price_badge",
        "stock_display", "max_per_user", "effect_days", "is_active", "order",
    ]
    list_filter   = ["type", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering      = ["order", "price_coins"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Item",    {"fields": ("slug", "name", "description", "type", "icon")}),
        ("Pricing", {"fields": ("price_coins", "stock", "max_per_user", "effect_days")}),
        ("Visibility", {"fields": ("is_active", "order", "tenant")}),
        ("Meta",    {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def icon_display(self, obj):
        return format_html('<span style="font-size:18px;">{}</span>', obj.icon or "🛍️")
    icon_display.short_description = ""

    def type_badge(self, obj):
        return format_html(
            '<span style="background:#607D8B;color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            obj.type.replace("_", " "),
        )
    type_badge.short_description = "Type"

    def price_badge(self, obj):
        return format_html('<span style="color:#D4AF37;font-weight:600;">💰 {}</span>', obj.price_coins)
    price_badge.short_description = "Price"

    def stock_display(self, obj):
        if obj.stock == -1:
            return format_html('<span style="color:#4CAF50;">∞ Unlimited</span>')
        if obj.stock == 0:
            return format_html('<span style="color:#F44336;">Out of Stock</span>')
        return format_html('<span style="color:#FF9800;">{} left</span>', obj.stock)
    stock_display.short_description = "Stock"


@admin.register(ShopPurchase)
class ShopPurchaseAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = [
        "user_link", "item_name", "quantity",
        "coins_spent_badge", "expires_at_display", "is_active", "created_at",
    ]
    list_filter   = ["is_active", "item__type"]
    search_fields = ["user__username", "item__name"]
    ordering      = ["-created_at"]
    readonly_fields = ["coins_spent", "created_at", "updated_at"]

    def item_name(self, obj):
        return format_html("<strong>{}</strong>", obj.item.name)
    item_name.short_description = "Item"

    def coins_spent_badge(self, obj):
        return format_html('<span style="color:#F44336;font-weight:600;">💰 -{}</span>', obj.coins_spent)
    coins_spent_badge.short_description = "Spent"

    def expires_at_display(self, obj):
        if not obj.expires_at:
            return "Never"
        if obj.expires_at < timezone.now():
            return format_html('<span style="color:#F44336;">Expired</span>')
        return format_html(
            '<span style="color:#4CAF50;">{}</span>',
            obj.expires_at.strftime("%Y-%m-%d %H:%M"),
        )
    expires_at_display.short_description = "Expires"


@admin.register(UserInventory)
class UserInventoryAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "item_name", "quantity_badge", "expires_at_display"]
    list_filter   = ["item__type"]
    search_fields = ["user__username", "item__name"]
    readonly_fields = ["created_at", "updated_at"]

    def item_name(self, obj):
        return obj.item.name
    item_name.short_description = "Item"

    def quantity_badge(self, obj):
        color = "#4CAF50" if obj.quantity > 0 else "#F44336"
        return format_html('<span style="color:{};font-weight:600;">×{}</span>', color, obj.quantity)
    quantity_badge.short_description = "Qty"

    def expires_at_display(self, obj):
        if not obj.expires_at:
            return "Never"
        if obj.expires_at < timezone.now():
            return format_html('<span style="color:#F44336;">Expired</span>')
        return obj.expires_at.strftime("%Y-%m-%d")
    expires_at_display.short_description = "Expires"

# engagement/admin/loot_box_admin.py
from django.contrib import admin
from django.utils.html import format_html
from ..models.loot_box import ChestType, ChestDropTable, UserChest, ChestOpening
from .mixins import TenantFilterMixin, UserLinkMixin


@admin.register(ChestType)
class ChestTypeAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["icon_display", "name", "rarity_badge", "price_coins",
                     "drop_count", "is_active", "order"]
    list_filter   = ["rarity", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering      = ["order"]
    readonly_fields = ["created_at", "updated_at"]

    def icon_display(self, obj):
        return format_html('<span style="font-size:20px;">{}</span>', obj.icon or "📦")
    icon_display.short_description = ""

    def rarity_badge(self, obj):
        colors = {
            "common": "#888", "rare": "#2196F3",
            "epic": "#9C27B0", "legendary": "#FFD700",
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.rarity, "#888"), obj.rarity.upper(),
        )
    rarity_badge.short_description = "Rarity"

    def drop_count(self, obj):
        return obj.drop_table.count()
    drop_count.short_description = "Drops"


class ChestDropTableInline(admin.TabularInline):
    model  = ChestDropTable
    extra  = 1
    fields = ["reward_type", "reward_slug", "coins_min", "coins_max",
              "xp_min", "xp_max", "quantity", "weight", "is_active"]


@admin.register(ChestDropTable)
class ChestDropTableAdmin(TenantFilterMixin, admin.ModelAdmin):
    list_display  = ["chest_type", "reward_type", "reward_slug_display",
                     "coins_range", "weight_badge", "is_active"]
    list_filter   = ["reward_type", "is_active", "chest_type"]
    ordering      = ["-weight"]
    readonly_fields = ["created_at", "updated_at"]

    def reward_slug_display(self, obj):
        return obj.reward_slug or "—"
    reward_slug_display.short_description = "Slug"

    def coins_range(self, obj):
        if obj.coins_max > 0:
            return format_html('<span style="color:#D4AF37;">💰 {}–{}</span>',
                               int(obj.coins_min), int(obj.coins_max))
        return "—"
    coins_range.short_description = "Coins"

    def weight_badge(self, obj):
        color = "#4CAF50" if obj.weight >= 20 else "#FF9800" if obj.weight >= 5 else "#F44336"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">W:{}</span>',
            color, obj.weight,
        )
    weight_badge.short_description = "Weight"


@admin.register(UserChest)
class UserChestAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "chest_type", "quantity_badge", "source", "expires_at", "created_at"]
    list_filter   = ["chest_type", "source"]
    search_fields = ["user__username"]
    ordering      = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]

    def quantity_badge(self, obj):
        color = "#4CAF50" if obj.quantity > 0 else "#F44336"
        return format_html('<span style="color:{};font-weight:600;">×{}</span>', color, obj.quantity)
    quantity_badge.short_description = "Qty"


@admin.register(ChestOpening)
class ChestOpeningAdmin(TenantFilterMixin, UserLinkMixin, admin.ModelAdmin):
    list_display  = ["user_link", "chest_type", "reward_type_badge",
                     "coins_won_display", "xp_won", "opened_at"]
    list_filter   = ["reward_type", "chest_type"]
    search_fields = ["user__username"]
    ordering      = ["-opened_at"]
    readonly_fields = ["opened_at", "created_at", "updated_at"]

    def reward_type_badge(self, obj):
        colors = {"coins": "#D4AF37", "xp": "#9C27B0", "shop_item": "#4CAF50",
                  "spin": "#2196F3", "chest": "#FF9800", "achievement": "#F44336"}
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:8px;">{}</span>',
            colors.get(obj.reward_type, "#888"), obj.reward_type,
        )
    reward_type_badge.short_description = "Reward"

    def coins_won_display(self, obj):
        if obj.coins_won > 0:
            return format_html('<span style="color:#D4AF37;font-weight:600;">💰 {}</span>', obj.coins_won)
        return "—"
    coins_won_display.short_description = "Coins"

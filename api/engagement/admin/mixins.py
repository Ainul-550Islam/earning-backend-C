# engagement/admin/mixins.py
from django.contrib import admin
from django.utils.html import format_html


class TenantFilterMixin:
    """Automatically filter queryset to request.user's tenant for non-superusers."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        tenant = getattr(request.user, "tenant", None)
        if tenant:
            return qs.filter(tenant=tenant)
        return qs

    def save_model(self, request, obj, form, change):
        if not change and not obj.tenant_id:
            obj.tenant = getattr(request.user, "tenant", None)
        super().save_model(request, obj, form, change)


class UserLinkMixin:
    """Provides a clickable user_link column for list_display."""

    def user_link(self, obj):
        if not obj.user_id:
            return "—"
        url = f"/admin/auth/user/{obj.user.pk}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = "User"


class CoinsBadgeMixin:
    """Provides a gold-coloured coins display method."""

    def coins_badge(self, obj, field="coins_earned"):
        value = getattr(obj, field, 0)
        return format_html(
            '<span style="color:#D4AF37;font-weight:600;">💰 {}</span>', value
        )
    coins_badge.short_description = "Coins"


class RankBadgeMixin:
    """Provides a rank badge with medal icons for top-3."""

    def rank_badge(self, obj):
        rank = getattr(obj, "rank", 0)
        if rank == 1:
            icon, color = "🥇", "#FFD700"
        elif rank == 2:
            icon, color = "🥈", "#C0C0C0"
        elif rank == 3:
            icon, color = "🥉", "#CD7F32"
        else:
            icon, color = "#️⃣", "#2196F3"
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;">'
            '{} {}</span>',
            color, icon, rank,
        )
    rank_badge.short_description = "Rank"

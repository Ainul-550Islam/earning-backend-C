"""
SmartLink Admin — Base Classes
================================
Before this file, 5 admin files each repeated the same 2–4 methods:

    def has_add_permission(self, request):    return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

These appeared in:
    click_admin.py      (4×)
    stat_admin.py       (4×)
    offer_pool_admin.py (3×)
    postback_admin.py   (2×)
    insight_admin.py    (2×)

Now those classes extend ReadOnlyAdmin or AuditAdmin from here.
"""
from django.contrib import admin


# ─────────────────────────────────────────────────────────────────────────────
# ReadOnlyAdmin — completely immutable: no add / change / delete
# ─────────────────────────────────────────────────────────────────────────────

class ReadOnlyAdmin(admin.ModelAdmin):
    """
    Admin class for purely analytical/log models that must never be
    created, edited or deleted from the admin UI.

    Used by:
        ClickAdmin, BotClickAdmin, ClickSessionAdmin, ClickMetadataAdmin,
        SmartLinkDailyStatAdmin, SmartLinkStatAdmin, GeoPerformanceStatAdmin,
        DevicePerformanceStatAdmin, OfferCapTrackerAdmin, OfferRotationLogAdmin,
        PostbackLogAdmin, WebhookDeliveryLogAdmin, ImpressionLogAdmin,
        RedirectLogAdmin, RedirectChainAdmin, ABTestResultAdmin

    Override readonly_fields in subclasses (default: all list_display fields).
    """

    def get_readonly_fields(self, request, obj=None):
        """Mark list_display fields as readonly if no explicit readonly_fields set."""
        if self.readonly_fields:
            return self.readonly_fields
        return self.list_display or []

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# AuditAdmin — read + delete allowed, but no add / change
# ─────────────────────────────────────────────────────────────────────────────

class AuditAdmin(admin.ModelAdmin):
    """
    Admin class for audit-trail models: admins can review and delete records
    but must never add or edit them (would corrupt the audit trail).

    Used by:
        ClickFraudFlagAdmin, OfferScoreCacheAdmin, MLInsightAdmin
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow super-admins to delete audit records (e.g. GDPR erasure)."""
        return request.user.is_superuser


# ─────────────────────────────────────────────────────────────────────────────
# SmartLinkAdminMixin — common search/filter fields used across many admins
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkAdminMixin:
    """
    Mixin for admin classes that are scoped to a SmartLink.
    Provides slug-based search and publisher-based filter.

    Used by:
        ClickAdmin, SmartLinkStatAdmin, OfferPoolAdmin, TargetingRuleAdmin,
        OfferPoolEntryAdmin, RedirectLogAdmin, etc.
    """
    search_fields    = ("smartlink__slug",)
    list_select_related = True

    def smartlink_slug(self, obj):
        return obj.smartlink.slug
    smartlink_slug.short_description = "SmartLink"
    smartlink_slug.admin_order_field = "smartlink__slug"

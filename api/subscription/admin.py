"""admin.py – Django admin for the subscription module."""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .choices import SubscriptionStatus, PaymentStatus
from .models import MembershipBenefit, SubscriptionPayment, SubscriptionPlan, UserSubscription


# ─── Inlines ──────────────────────────────────────────────────────────────────

class MembershipBenefitInline(admin.TabularInline):
    model = MembershipBenefit
    extra = 1
    fields = ("benefit_type", "label", "value", "is_highlighted", "sort_order")
    ordering = ("sort_order",)


class SubscriptionPaymentInline(admin.TabularInline):
    model = SubscriptionPayment
    extra = 0
    readonly_fields = (
        "id", "status", "payment_method", "amount", "currency",
        "amount_refunded", "transaction_id", "paid_at", "created_at",
    )
    fields = readonly_fields
    can_delete = False
    show_change_link = True
    ordering = ("-created_at",)
    max_num = 10


# ─── SubscriptionPlan ─────────────────────────────────────────────────────────

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name", "slug", "status_badge", "price_display",
        "interval", "trial_period_days", "is_featured", "sort_order",
    )
    list_filter = ("status", "interval", "is_featured", "currency")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("sort_order", "is_featured")
    ordering = ("sort_order", "price")
    readonly_fields = ("id", "created_at", "updated_at", "discounted_price", "has_trial", "is_free")
    inlines = [MembershipBenefitInline]

    fieldsets = (
        (None, {"fields": ("id", "name", "slug", "description", "status", "is_featured", "sort_order")}),
        (_("Pricing"), {"fields": (
            "price", "currency", "interval", "interval_count",
            "discount_percent", "discounted_price", "setup_fee",
        )}),
        (_("Trial"), {"fields": ("trial_period_days", "has_trial")}),
        (_("Limits"), {"fields": ("max_users",)}),
        (_("Metadata"), {"fields": ("metadata",), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        colors = {"active": "green", "inactive": "orange", "archived": "red"}
        color = colors.get(obj.status, "grey")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")
    status_badge.admin_order_field = "status"

    def price_display(self, obj):
        return f"{obj.currency} {obj.price}"
    price_display.short_description = _("Price")
    price_display.admin_order_field = "price"


# ─── UserSubscription ─────────────────────────────────────────────────────────

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "plan", "status_badge",
        "current_period_end", "renewal_count", "cancel_at_period_end",
    )
    list_filter = ("status", "plan", "cancel_at_period_end")
    search_fields = ("user__email", "user__username", "external_subscription_id")
    raw_id_fields = ("user", "plan")
    readonly_fields = (
        "id", "created_at", "updated_at",
        "is_active", "is_trialing", "days_until_renewal",
        "renewal_count", "payment_retry_count",
    )
    inlines = [SubscriptionPaymentInline]

    fieldsets = (
        (None, {"fields": ("id", "user", "plan", "status")}),
        (_("Billing Cycle"), {"fields": (
            "current_period_start", "current_period_end",
            "days_until_renewal", "renewal_count",
        )}),
        (_("Trial"), {"fields": ("trial_start", "trial_end")}),
        (_("Cancellation"), {"fields": (
            "cancel_at_period_end", "cancelled_at",
            "cancellation_reason", "cancellation_comment",
        )}),
        (_("Pause"), {"fields": ("paused_at", "pause_resumes_at")}),
        (_("External"), {"fields": ("external_subscription_id", "payment_retry_count")}),
        (_("Metadata"), {"fields": ("metadata",), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    actions = ["mark_expired", "mark_cancelled"]

    def status_badge(self, obj):
        color_map = {
            SubscriptionStatus.ACTIVE: "green",
            SubscriptionStatus.TRIALING: "blue",
            SubscriptionStatus.PAST_DUE: "orange",
            SubscriptionStatus.CANCELLED: "red",
            SubscriptionStatus.EXPIRED: "gray",
            SubscriptionStatus.PAUSED: "purple",
        }
        color = color_map.get(obj.status, "black")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")

    @admin.action(description=_("Mark selected subscriptions as expired"))
    def mark_expired(self, request, queryset):
        count = 0
        for sub in queryset:
            sub.expire()
            count += 1
        self.message_user(request, f"{count} subscription(s) marked as expired.")

    @admin.action(description=_("Cancel selected subscriptions immediately"))
    def mark_cancelled(self, request, queryset):
        count = 0
        for sub in queryset:
            sub.cancel(reason="other", comment="Bulk admin action.", at_period_end=False)
            count += 1
        self.message_user(request, f"{count} subscription(s) cancelled.")


# ─── SubscriptionPayment ──────────────────────────────────────────────────────

@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "subscription", "status_badge", "amount_display",
        "payment_method", "transaction_id", "paid_at",
    )
    list_filter = ("status", "payment_method", "currency")
    search_fields = ("transaction_id", "subscription__user__email")
    raw_id_fields = ("subscription",)
    readonly_fields = (
        "id", "created_at", "updated_at",
        "net_amount", "is_fully_refunded",
    )

    fieldsets = (
        (None, {"fields": ("id", "subscription", "status")}),
        (_("Amount"), {"fields": (
            "amount", "currency", "amount_refunded", "net_amount",
            "tax_amount", "discount_amount",
        )}),
        (_("Payment"), {"fields": (
            "payment_method", "transaction_id", "invoice_url", "paid_at",
        )}),
        (_("Billing Period"), {"fields": ("period_start", "period_end")}),
        (_("Failure"), {"fields": ("failure_code", "failure_message"), "classes": ("collapse",)}),
        (_("Gateway"), {"fields": ("gateway_response",), "classes": ("collapse",)}),
        (_("Timestamps"), {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        color_map = {
            PaymentStatus.SUCCEEDED: "green",
            PaymentStatus.FAILED: "red",
            PaymentStatus.PENDING: "orange",
            PaymentStatus.REFUNDED: "blue",
        }
        color = color_map.get(obj.status, "black")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = _("Status")

    def amount_display(self, obj):
        return f"{obj.currency} {obj.amount}"
    amount_display.short_description = _("Amount")
    amount_display.admin_order_field = "amount"


# ─── MembershipBenefit ────────────────────────────────────────────────────────

@admin.register(MembershipBenefit)
class MembershipBenefitAdmin(admin.ModelAdmin):
    list_display = ("label", "plan", "benefit_type", "value", "is_highlighted", "sort_order")
    list_filter = ("benefit_type", "is_highlighted", "plan")
    search_fields = ("label", "value", "plan__name")
    list_editable = ("sort_order", "is_highlighted")
    raw_id_fields = ("plan",)
    ordering = ("plan", "sort_order")
    
    



# api/subscription/admin.py - এর একদম শেষে এই code টি যোগ করুন

# ============================================================
# FORCE ADMIN REGISTRATION - AUTO REGISTER MODELS
# ============================================================

def force_register_models():
    """
    জোর করে সব subscription models register করে
    """
    try:
        from django.contrib import admin
        from django.contrib.admin.sites import AlreadyRegistered
        from .models import SubscriptionPlan, UserSubscription, MembershipBenefit, SubscriptionPayment
        
        models_to_register = [
            (SubscriptionPlan, SubscriptionPlanAdmin),
            (UserSubscription, UserSubscriptionAdmin),
            (MembershipBenefit, MembershipBenefitAdmin),
            (SubscriptionPayment, SubscriptionPaymentAdmin),
        ]
        
        for model, admin_class in models_to_register:
            try:
                if not admin.site.is_registered(model):
                    admin.site.register(model, admin_class)
                    print(f"[OK] Force registered: {model.__name__}")
                else:
                    # Already registered - no problem
                    pass
            except AlreadyRegistered:
                # Already registered - ignore
                pass
            except Exception as e:
                print(f"[WARN] Could not register {model.__name__}: {e}")
                
    except Exception as e:
        print(f"[ERROR] Force registration error: {e}")

# Auto-run when module loads
force_register_models()

def _force_register_subscription():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(SubscriptionPlan, SubscriptionPlanAdmin), (UserSubscription, UserSubscriptionAdmin), (SubscriptionPayment, SubscriptionPaymentAdmin), (MembershipBenefit, MembershipBenefitAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] subscription registered {registered} models")
    except Exception as e:
        print(f"[WARN] subscription: {e}")

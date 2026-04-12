from django.contrib import admin
from .models import Tenant, TenantSettings, TenantBilling, TenantInvoice


class TenantSettingsInline(admin.StackedInline):
    model = TenantSettings
    can_delete = False
    verbose_name_plural = 'Settings'


class TenantBillingInline(admin.StackedInline):
    model = TenantBilling
    can_delete = False
    verbose_name_plural = 'Billing'


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "plan", "is_active", "max_users", "get_user_count", "created_at"]
    list_filter = ["plan", "is_active"]
    search_fields = ["name", "slug", "domain", "admin_email"]
    readonly_fields = ["id", "api_key", "created_at", "updated_at"]
    inlines = [TenantSettingsInline, TenantBillingInline]

    def get_user_count(self, obj):
        return obj.get_active_user_count()
    get_user_count.short_description = "Active Users"


@admin.register(TenantBilling)
class TenantBillingAdmin(admin.ModelAdmin):
    list_display = ["tenant", "status", "monthly_price", "trial_ends_at", "subscription_ends_at"]
    list_filter = ["status"]


@admin.register(TenantInvoice)
class TenantInvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "tenant", "amount", "status", "due_date", "paid_at"]
    list_filter = ["status"]


def _force_register_tenants():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(Tenant, TenantAdmin), (TenantBilling, TenantBillingAdmin), (TenantInvoice, TenantInvoiceAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] tenants registered {registered} models")
    except Exception as e:
        print(f"[WARN] tenants: {e}")

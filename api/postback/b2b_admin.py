"""b2b_admin.py — Django admin for all B2B models."""
from django.contrib import admin
from .b2b_models import (
    OrganizationAccount, B2BAPIKey, OrganizationRole, OrganizationMember,
    RevenueShareRule, AdvertiserBudgetCap, B2BContract, B2BInvoice,
    OutboundWebhookSubscription, WhiteLabelConfig,
    ImpersonationLog, PartnerCreditLedger,
)


@admin.register(OrganizationAccount)
class OrganizationAccountAdmin(admin.ModelAdmin):
    list_display  = ("name", "account_type", "status", "contact_email", "country_code", "created_at")
    list_filter   = ("account_type", "status", "country_code")
    search_fields = ("name", "slug", "contact_email")
    readonly_fields = ("id", "created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("status",)


@admin.register(B2BAPIKey)
class B2BAPIKeyAdmin(admin.ModelAdmin):
    list_display  = ("key_prefix", "organization", "name", "scopes", "is_active", "last_used_at", "expires_at")
    list_filter   = ("is_active",)
    search_fields = ("key_prefix", "organization__name", "name")
    readonly_fields = ("id", "key_prefix", "key_hash", "last_used_at", "created_at")
    def has_add_permission(self, r): return False  # Keys generated via API only


@admin.register(OrganizationRole)
class OrganizationRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "preset", "is_system")
    list_filter  = ("preset", "is_system")
    readonly_fields = ("id",)


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display  = ("user", "organization", "role", "status", "joined_at")
    list_filter   = ("status",)
    search_fields = ("user__username", "organization__name")
    readonly_fields = ("id", "joined_at", "created_at")


@admin.register(RevenueShareRule)
class RevenueShareRuleAdmin(admin.ModelAdmin):
    list_display = ("organization", "network", "rule_type", "rev_share_pct", "is_active", "valid_from", "valid_until")
    list_filter  = ("rule_type", "is_active")
    readonly_fields = ("id",)


@admin.register(AdvertiserBudgetCap)
class AdvertiserBudgetCapAdmin(admin.ModelAdmin):
    list_display  = ("organization", "network", "period", "cap_bdt", "current_spend", "is_active")
    list_filter   = ("period", "is_active")
    readonly_fields = ("id", "current_spend", "current_conversions")


@admin.register(B2BContract)
class B2BContractAdmin(admin.ModelAdmin):
    list_display  = ("contract_number", "organization", "status", "valid_from", "valid_until", "created_at")
    list_filter   = ("status",)
    search_fields = ("contract_number", "title", "organization__name")
    readonly_fields = ("id", "contract_number", "created_at", "updated_at")


@admin.register(B2BInvoice)
class B2BInvoiceAdmin(admin.ModelAdmin):
    list_display  = ("invoice_number", "organization", "invoice_type", "status", "total_bdt", "due_date", "paid_at")
    list_filter   = ("status", "invoice_type")
    search_fields = ("invoice_number", "organization__name")
    readonly_fields = ("id", "invoice_number", "total_bdt", "created_at", "updated_at")


@admin.register(OutboundWebhookSubscription)
class OutboundWebhookSubAdmin(admin.ModelAdmin):
    list_display  = ("organization", "endpoint_url", "event_types", "is_active", "failure_count", "last_success_at")
    list_filter   = ("is_active",)
    readonly_fields = ("id", "failure_count", "last_triggered_at", "last_success_at", "created_at")
    extra_kwargs = {"secret": {"write_only": True}}


@admin.register(WhiteLabelConfig)
class WhiteLabelConfigAdmin(admin.ModelAdmin):
    list_display  = ("brand_name", "organization", "custom_domain", "ssl_verified", "is_active")
    list_filter   = ("is_active", "ssl_verified")
    readonly_fields = ("id", "ssl_verified", "created_at", "updated_at")


@admin.register(ImpersonationLog)
class ImpersonationLogAdmin(admin.ModelAdmin):
    list_display  = ("admin_user", "impersonated_user", "organization", "started_at", "ended_at", "source_ip")
    readonly_fields = [f.name for f in ImpersonationLog._meta.fields]
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, o=None): return False


@admin.register(PartnerCreditLedger)
class PartnerCreditLedgerAdmin(admin.ModelAdmin):
    list_display  = ("organization", "entry_type", "amount_bdt", "balance_after", "reference", "created_at")
    list_filter   = ("entry_type",)
    search_fields = ("organization__name", "reference")
    readonly_fields = ("id", "balance_after", "created_at")
    def has_change_permission(self, r, o=None): return False

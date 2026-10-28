"""b2b_serializers.py — Serializers for all B2B models."""
from decimal import Decimal
from rest_framework import serializers
from .b2b_models import (
    OrganizationAccount, B2BAPIKey, OrganizationRole, OrganizationMember,
    RevenueShareRule, AdvertiserBudgetCap, B2BContract, B2BInvoice,
    OutboundWebhookSubscription, WhiteLabelConfig,
    ImpersonationLog, PartnerCreditLedger,
)


class OrganizationAccountSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    class Meta:
        model = OrganizationAccount
        fields = [
            "id","account_type","name","slug","status",
            "contact_name","contact_email","contact_phone",
            "website","country_code","currency","payment_terms_days",
            "tax_id","notes","metadata","member_count","created_at",
        ]
        read_only_fields = ["id","created_at","member_count"]
    def get_member_count(self, obj):
        return obj.members.filter(status="active").count()


class B2BAPIKeyListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    class Meta:
        model = B2BAPIKey
        fields = [
            "id","organization","organization_name","name","key_prefix",
            "scopes","is_active","ip_whitelist","last_used_at","expires_at","created_at",
        ]
        read_only_fields = ["id","key_prefix","last_used_at","created_at"]


class B2BAPIKeyCreateSerializer(serializers.Serializer):
    name       = serializers.CharField(max_length=200)
    scopes     = serializers.ListField(child=serializers.CharField(), min_length=1)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    ip_whitelist = serializers.ListField(child=serializers.IPAddressField(), required=False, default=list)


class OrganizationRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationRole
        fields = ["id","organization","name","preset","permissions","is_system"]
        read_only_fields = ["id","is_system"]


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user_email    = serializers.CharField(source="user.email",    read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    role_name     = serializers.CharField(source="role.name",     read_only=True)
    class Meta:
        model = OrganizationMember
        fields = [
            "id","organization","user","user_email","user_username",
            "role","role_name","status","invited_by","joined_at","created_at",
        ]
        read_only_fields = ["id","invited_by","joined_at","created_at"]


class RevenueShareRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevenueShareRule
        fields = [
            "id","organization","network","rule_type","flat_cpa_bdt",
            "rev_share_pct","min_payout_bdt","max_payout_bdt","tiers",
            "is_active","valid_from","valid_until","created_at",
        ]
        read_only_fields = ["id","created_at"]


class AdvertiserBudgetCapSerializer(serializers.ModelSerializer):
    remaining_bdt    = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    utilisation_pct  = serializers.FloatField(read_only=True)
    is_exhausted     = serializers.BooleanField(read_only=True)
    class Meta:
        model = AdvertiserBudgetCap
        fields = [
            "id","organization","network","period","cap_bdt","cap_conversions",
            "current_spend","current_conversions","period_start","is_active",
            "alert_threshold_pct","remaining_bdt","utilisation_pct","is_exhausted","created_at",
        ]
        read_only_fields = ["id","current_spend","current_conversions","created_at",
                            "remaining_bdt","utilisation_pct","is_exhausted"]


class B2BContractSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)
    class Meta:
        model = B2BContract
        fields = [
            "id","organization","title","status","contract_number",
            "signed_at","valid_from","valid_until","document_url","terms_summary",
            "monthly_minimum","revenue_share_rule","is_valid","created_at",
        ]
        read_only_fields = ["id","contract_number","created_at","is_valid"]


class B2BInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = B2BInvoice
        fields = [
            "id","organization","invoice_number","invoice_type","status",
            "period_start","period_end","subtotal_bdt","tax_bdt","total_bdt",
            "conversions","line_items","issued_at","due_date","paid_at",
            "payment_reference","notes","created_at",
        ]
        read_only_fields = ["id","invoice_number","total_bdt","created_at"]


class OutboundWebhookSubSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboundWebhookSubscription
        fields = [
            "id","organization","endpoint_url","event_types","is_active",
            "failure_count","last_triggered_at","last_success_at","created_at",
        ]
        read_only_fields = ["id","failure_count","last_triggered_at","last_success_at","created_at"]
        extra_kwargs = {"secret": {"write_only": True}}


class WhiteLabelConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhiteLabelConfig
        fields = [
            "id","organization","brand_name","custom_domain","logo_url","favicon_url",
            "primary_color","secondary_color","font_family","support_email","support_url",
            "privacy_url","terms_url","hide_platform_branding",
            "custom_css","custom_js","ssl_verified","is_active","created_at",
        ]
        read_only_fields = ["id","ssl_verified","created_at"]


class ImpersonationLogSerializer(serializers.ModelSerializer):
    admin_username       = serializers.CharField(source="admin_user.username",       read_only=True)
    impersonated_username= serializers.CharField(source="impersonated_user.username",read_only=True)
    duration_minutes     = serializers.IntegerField(read_only=True)
    class Meta:
        model = ImpersonationLog
        fields = [
            "id","admin_user","admin_username","impersonated_user","impersonated_username",
            "organization","reason","started_at","ended_at","source_ip",
            "actions_log","duration_minutes",
        ]
        read_only_fields = ["id","session_token","started_at","actions_log","duration_minutes"]


class PartnerCreditLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerCreditLedger
        fields = [
            "id","organization","entry_type","amount_bdt","balance_after",
            "reference","note","performed_by","created_at",
        ]
        read_only_fields = ["id","balance_after","created_at"]


class CreditTopupSerializer(serializers.Serializer):
    amount_bdt = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("1"))
    reference  = serializers.CharField(required=False, default="")
    note       = serializers.CharField(required=False, default="")

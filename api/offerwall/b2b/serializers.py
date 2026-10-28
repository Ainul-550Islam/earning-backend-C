"""
api/offerwall/b2b/serializers.py

Fix applied:
  B2BClientRegisterSerializer had NO validate_* methods — any payload
  passed. Added:
    • validate_company_name  — min 3 chars, no HTML
    • validate_contact_email — reject disposable domains
    • validate_country       — must be valid ISO 2-letter code
    • validate_company_website — must be https
"""
import re
from decimal import Decimal
from rest_framework import serializers
from .models import B2BPlan, B2BClient, B2BUsageRecord, B2BInvoice, B2BOnboarding

# Disposable email domains blocklist (subset — extend as needed)
_DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'tempmail.com',
    'throwaway.email', 'sharklasers.com', 'yopmail.com',
}


class B2BPlanSerializer(serializers.ModelSerializer):
    feature_list = serializers.SerializerMethodField()

    class Meta:
        model  = B2BPlan
        fields = [
            'id', 'name', 'plan_type',
            'monthly_price_bdt', 'monthly_price_usd',
            'monthly_api_calls', 'monthly_conversions',
            'max_active_walls', 'max_api_keys',
            'revenue_share_pct',
            'allow_content_lock', 'allow_bulk_webhook',
            'allow_custom_domain', 'allow_white_label',
            'allow_survey_offers', 'allow_analytics_api',
            'support_level', 'feature_list',
        ]

    def get_feature_list(self, obj):
        return obj.get_feature_list()


class B2BOnboardingSerializer(serializers.ModelSerializer):
    completion_pct = serializers.SerializerMethodField()
    next_step      = serializers.SerializerMethodField()

    class Meta:
        model  = B2BOnboarding
        fields = [
            'completed_steps', 'current_step', 'is_complete',
            'completion_pct', 'next_step',
            'signup_at', 'profile_at', 'plan_at', 'api_key_at',
            'integration_at', 'test_conv_at', 'live_at',
        ]

    def get_completion_pct(self, obj):
        return obj.completion_pct()

    def get_next_step(self, obj):
        return obj.next_step_display()


class B2BUsageSerializer(serializers.ModelSerializer):
    quota_pct = serializers.SerializerMethodField()

    class Meta:
        model  = B2BUsageRecord
        fields = [
            'period_year', 'period_month',
            'api_calls', 'conversions', 'offer_views',
            'offer_clicks', 'content_unlocks', 'webhook_calls',
            'gross_revenue_usd', 'publisher_share_usd',
            'quota_pct', 'updated_at',
        ]

    def get_quota_pct(self, obj):
        return obj.quota_pct()


class B2BClientSerializer(serializers.ModelSerializer):
    plan_name           = serializers.CharField(source='plan.name', read_only=True)
    effective_rev_share = serializers.DecimalField(
        source='effective_revenue_share',
        max_digits=5, decimal_places=2, read_only=True)
    onboarding    = B2BOnboardingSerializer(read_only=True)
    current_usage = serializers.SerializerMethodField()
    is_plan_valid = serializers.SerializerMethodField()

    class Meta:
        model  = B2BClient
        fields = [
            'id', 'company_name', 'company_website', 'business_type',
            'country', 'contact_email', 'contact_phone',
            'plan', 'plan_name', 'plan_started_at', 'plan_expires_at',
            'billing_cycle', 'status', 'verified_at',
            'effective_rev_share', 'is_plan_valid',
            'onboarding', 'current_usage',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'verified_at', 'effective_rev_share',
            'is_plan_valid', 'onboarding', 'created_at', 'updated_at',
        ]

    def get_current_usage(self, obj):
        try:
            return B2BUsageSerializer(obj.get_current_usage()).data
        except Exception:
            return None

    def get_is_plan_valid(self, obj):
        return obj.is_plan_valid()


class B2BClientRegisterSerializer(serializers.ModelSerializer):
    plan_type = serializers.ChoiceField(
        choices=['free', 'starter', 'pro', 'enterprise'],
        default='free', write_only=True)
    description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model  = B2BClient
        fields = [
            'company_name', 'company_website', 'business_type',
            'country', 'contact_email', 'contact_phone',
            'vat_number', 'description', 'plan_type',
        ]

    # ── Validation fixes ─────────────────────────────────────

    def validate_company_name(self, value):
        """Min 3 chars, no HTML injection."""
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError(
                'Company name must be at least 3 characters.')
        if re.search(r'<[^>]+>', value):
            raise serializers.ValidationError('HTML is not allowed.')
        return value

    def validate_contact_email(self, value):
        """Block disposable email domains."""
        domain = value.split('@')[-1].lower()
        if domain in _DISPOSABLE_DOMAINS:
            raise serializers.ValidationError(
                'Please use a valid business email address.')
        return value

    def validate_country(self, value):
        """Must be a 2-letter ISO code."""
        if not value or len(value) != 2 or not value.isalpha():
            raise serializers.ValidationError(
                'Country must be a 2-letter ISO code (e.g. BD, US, GB).')
        return value.upper()

    def validate_company_website(self, value):
        """Require HTTPS for production security."""
        if value and not value.startswith('https://'):
            raise serializers.ValidationError(
                'Company website must start with https://')
        return value

    def validate(self, data):
        """Cross-field: contact phone required for non-free plans."""
        plan_type = data.get('plan_type', 'free')
        if plan_type != 'free' and not data.get('contact_phone', '').strip():
            raise serializers.ValidationError(
                {'contact_phone': 'Phone number is required for paid plans.'})
        return data

    def create(self, validated_data):
        plan_type = validated_data.pop('plan_type', 'free')
        plan = (B2BPlan.objects.filter(plan_type=plan_type, is_active=True).first()
                or B2BPlan.get_free())
        owner  = self.context['request'].user
        client = B2BClient.objects.create(owner=owner, plan=plan, **validated_data)
        onboarding = B2BOnboarding.objects.create(client=client)
        onboarding.complete_step('signup')
        return client


class B2BInvoiceSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.company_name', read_only=True)

    class Meta:
        model  = B2BInvoice
        fields = [
            'id', 'invoice_number', 'client', 'client_name',
            'period_year', 'period_month',
            'plan_fee_bdt', 'revenue_share_usd', 'revenue_share_bdt',
            'tax_bdt', 'total_due_bdt', 'total_payable_bdt',
            'status', 'issued_at', 'due_date', 'paid_at',
            'payment_method', 'payment_ref', 'created_at',
        ]
        read_only_fields = ['id', 'invoice_number', 'created_at']

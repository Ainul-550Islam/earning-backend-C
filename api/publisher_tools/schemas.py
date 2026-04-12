# api/publisher_tools/schemas.py
"""Publisher Tools — Request/Response Schemas & Validation."""
from decimal import Decimal
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _


class PaginationSchema(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=200, default=20)
    ordering = serializers.CharField(required=False, default='-created_at')


class DateRangeSchema(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    granularity = serializers.ChoiceField(choices=['hourly', 'daily', 'weekly', 'monthly'], default='daily')
    timezone = serializers.CharField(default='UTC', required=False)

    def validate(self, attrs):
        if attrs['start_date'] > attrs['end_date']:
            raise serializers.ValidationError(_('start_date must be before end_date.'))
        if (attrs['end_date'] - attrs['start_date']).days > 365:
            raise serializers.ValidationError(_('Date range cannot exceed 365 days.'))
        return attrs


class GeoTargetSchema(serializers.Serializer):
    countries = serializers.ListField(child=serializers.CharField(max_length=2), required=False, default=list)
    regions = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    cities = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    exclude_countries = serializers.ListField(child=serializers.CharField(max_length=2), required=False, default=list)


class DeviceTargetSchema(serializers.Serializer):
    device_types = serializers.ListField(child=serializers.ChoiceField(choices=['mobile', 'tablet', 'desktop', 'all']), default=['all'])
    os_types = serializers.ListField(child=serializers.ChoiceField(choices=['android', 'ios', 'windows', 'macos', 'linux', 'all']), default=['all'])
    min_os_version = serializers.CharField(required=False, allow_blank=True)
    browsers = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class MoneySchema(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal('0'))
    currency = serializers.ChoiceField(choices=['USD', 'BDT', 'EUR', 'GBP', 'INR'], default='USD')


class SuccessResponseSchema(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    message = serializers.CharField(default='Success')
    data = serializers.DictField(required=False)


class ErrorResponseSchema(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    message = serializers.CharField()
    code = serializers.CharField(required=False)
    errors = serializers.DictField(required=False)


class BulkOperationSchema(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)
    action = serializers.CharField()
    params = serializers.DictField(required=False, default=dict)


class PublisherRegistrationSchema(serializers.Serializer):
    display_name = serializers.CharField(max_length=200, min_length=2)
    business_type = serializers.ChoiceField(choices=['individual', 'company', 'agency', 'ngo', 'startup'])
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, default='Bangladesh')
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    agree_to_terms = serializers.BooleanField()

    def validate_agree_to_terms(self, value):
        if not value:
            raise serializers.ValidationError(_('You must agree to the Terms of Service.'))
        return value

    def validate_contact_email(self, value):
        return value.lower().strip()


class PublisherApprovalSchema(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject', 'suspend', 'ban', 'request_info'])
    reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    tier = serializers.ChoiceField(choices=['standard', 'premium', 'enterprise'], required=False)
    revenue_share = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)


class PublisherFilterSchema(serializers.Serializer):
    status = serializers.CharField(required=False)
    tier = serializers.CharField(required=False)
    country = serializers.CharField(required=False)
    kyc_verified = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False)
    min_revenue = serializers.DecimalField(max_digits=14, decimal_places=4, required=False)
    max_revenue = serializers.DecimalField(max_digits=14, decimal_places=4, required=False)


class SiteRegistrationSchema(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    domain = serializers.CharField(max_length=255)
    url = serializers.URLField()
    category = serializers.ChoiceField(choices=[
        'news', 'blog', 'entertainment', 'technology', 'finance',
        'health', 'sports', 'education', 'ecommerce', 'gaming',
        'travel', 'food', 'automotive', 'real_estate', 'other'
    ])
    subcategory = serializers.CharField(required=False, allow_blank=True)
    language = serializers.CharField(max_length=10, default='en')
    target_countries = serializers.ListField(child=serializers.CharField(), default=['ALL'])
    content_rating = serializers.ChoiceField(choices=['G', 'PG', 'PG13', 'R'], default='G')
    monthly_pageviews = serializers.IntegerField(min_value=0, default=0)
    monthly_unique_visitors = serializers.IntegerField(min_value=0, default=0)
    verification_method = serializers.ChoiceField(choices=['ads_txt', 'meta_tag', 'dns_record', 'file'], default='ads_txt')

    def validate_domain(self, value):
        from .validators import validate_domain
        return validate_domain(value)


class SiteVerificationSchema(serializers.Serializer):
    method = serializers.ChoiceField(choices=['ads_txt', 'meta_tag', 'dns_record', 'file', 'api'])
    force_recheck = serializers.BooleanField(default=False)


class SiteFilterSchema(serializers.Serializer):
    publisher_id = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    min_quality = serializers.IntegerField(min_value=0, max_value=100, required=False)
    ads_txt_verified = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False)


class AppRegistrationSchema(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    platform = serializers.ChoiceField(choices=['android', 'ios', 'both', 'web_app'])
    package_name = serializers.CharField(max_length=255)
    category = serializers.ChoiceField(choices=[
        'games', 'tools', 'entertainment', 'social', 'finance',
        'health', 'education', 'shopping', 'travel', 'news',
        'photography', 'productivity', 'lifestyle', 'sports', 'other'
    ])
    play_store_url = serializers.URLField(required=False, allow_blank=True)
    app_store_url = serializers.URLField(required=False, allow_blank=True)
    content_rating = serializers.ChoiceField(choices=['Everyone', 'Everyone10+', 'Teen', 'Mature17', 'Adults'], default='Everyone')
    description = serializers.CharField(required=False, allow_blank=True)
    icon_url = serializers.URLField(required=False, allow_blank=True)
    version = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_package_name(self, value):
        if '.' not in value:
            raise serializers.ValidationError(_('Invalid package name. Use: com.example.app'))
        return value.lower().strip()


class AdUnitCreateSchema(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    inventory_type = serializers.ChoiceField(choices=['site', 'app'])
    site_id = serializers.CharField(required=False)
    app_id = serializers.CharField(required=False)
    format = serializers.ChoiceField(choices=[
        'banner', 'leaderboard', 'rectangle', 'skyscraper', 'billboard',
        'native', 'sticky', 'interstitial', 'rewarded_video', 'app_open',
        'offerwall', 'instream_video', 'outstream_video', 'audio', 'playable'
    ])
    width = serializers.IntegerField(min_value=50, required=False)
    height = serializers.IntegerField(min_value=20, required=False)
    is_responsive = serializers.BooleanField(default=True)
    floor_price = serializers.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.0000'))
    description = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        inv_type = attrs.get('inventory_type', 'site')
        if inv_type == 'site' and not attrs.get('site_id'):
            raise serializers.ValidationError({'site_id': _('Required for site ad units.')})
        if inv_type == 'app' and not attrs.get('app_id'):
            raise serializers.ValidationError({'app_id': _('Required for app ad units.')})
        return attrs


class WaterfallReorderSchema(serializers.Serializer):
    items = serializers.ListField(child=serializers.DictField(child=serializers.IntegerField()))

    def validate_items(self, value):
        priorities = [item.get('priority') for item in value]
        if len(priorities) != len(set(priorities)):
            raise serializers.ValidationError(_('Duplicate priorities not allowed.'))
        return value


class EarningFilterSchema(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    granularity = serializers.ChoiceField(choices=['hourly', 'daily', 'weekly', 'monthly'], default='daily')
    earning_type = serializers.CharField(required=False)
    country = serializers.CharField(required=False)
    site_id = serializers.CharField(required=False)
    app_id = serializers.CharField(required=False)
    ad_unit_id = serializers.CharField(required=False)
    status = serializers.CharField(required=False)


class InvoiceGenerateSchema(serializers.Serializer):
    publisher_id = serializers.CharField()
    year = serializers.IntegerField(min_value=2020, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)
    auto_issue = serializers.BooleanField(default=False)


class PayoutRequestSchema(serializers.Serializer):
    bank_account_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=4)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError(_('Amount must be positive.'))
        return value


class FraudActionSchema(serializers.Serializer):
    action = serializers.ChoiceField(choices=['flagged', 'deducted', 'warned', 'suspended', 'blocked', 'no_action'])
    notes = serializers.CharField(required=False, allow_blank=True)
    deduction_amount = serializers.DecimalField(max_digits=12, decimal_places=4, required=False)


class WebhookCreateSchema(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    endpoint_url = serializers.URLField()
    subscribed_events = serializers.ListField(child=serializers.CharField(), default=list)
    subscribe_all = serializers.BooleanField(default=False)
    timeout_seconds = serializers.IntegerField(min_value=5, max_value=60, default=10)
    max_retries = serializers.IntegerField(min_value=0, max_value=5, default=3)
    custom_headers = serializers.DictField(required=False, default=dict)


class ABTestCreateSchema(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    ad_unit_id = serializers.CharField()
    test_type = serializers.ChoiceField(choices=['placement', 'ad_format', 'floor_price', 'waterfall', 'creative'])
    hypothesis = serializers.CharField(required=False, allow_blank=True)
    confidence_level = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal('95.00'))
    min_sample_size = serializers.IntegerField(min_value=100, default=1000)
    min_duration_days = serializers.IntegerField(min_value=1, default=7)
    variants = serializers.ListField(child=serializers.DictField(), min_length=2, max_length=5)

    def validate_variants(self, value):
        total = sum(v.get('traffic_split', 0) for v in value)
        if abs(total - 100.0) > 0.01:
            raise serializers.ValidationError(_(f'Traffic splits must sum to 100%. Got {total}%.'))
        return value


class ReportFilterSchema(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    granularity = serializers.ChoiceField(choices=['hourly', 'daily', 'weekly', 'monthly'], default='daily')
    dimensions = serializers.ListField(child=serializers.CharField(), required=False, default=['date'])
    metrics = serializers.ListField(child=serializers.CharField(), required=False)
    filters = serializers.DictField(required=False, default=dict)
    format = serializers.ChoiceField(choices=['json', 'csv', 'xlsx'], default='json')

    def validate(self, attrs):
        if attrs['start_date'] > attrs['end_date']:
            raise serializers.ValidationError(_('start_date must be before end_date.'))
        return attrs


class KYCSubmissionSchema(serializers.Serializer):
    kyc_type = serializers.ChoiceField(choices=['individual', 'business'])
    full_legal_name = serializers.CharField(max_length=300)
    date_of_birth = serializers.DateField(required=False)
    nationality = serializers.CharField(max_length=100)
    permanent_address = serializers.CharField()
    city = serializers.CharField(max_length=100)
    country = serializers.CharField(max_length=100)
    primary_document_type = serializers.ChoiceField(choices=['national_id', 'passport', 'driving_license', 'trade_license'])
    primary_document_number = serializers.CharField(max_length=100)
    tax_country = serializers.CharField(max_length=100, default='Bangladesh')
    # Business fields
    business_name = serializers.CharField(required=False, allow_blank=True)
    tin_number = serializers.CharField(required=False, allow_blank=True)
    trade_license_number = serializers.CharField(required=False, allow_blank=True)


class PlacementCreateSchema(serializers.Serializer):
    ad_unit_id = serializers.CharField()
    name = serializers.CharField(max_length=200)
    position = serializers.ChoiceField(choices=[
        'above_fold', 'below_fold', 'header', 'footer', 'sidebar_left', 'sidebar_right',
        'in_content', 'between_posts', 'popup', 'sticky_bottom', 'sticky_top',
        'app_start', 'level_end', 'pause_menu', 'exit_intent', 'in_feed'
    ])
    is_active = serializers.BooleanField(default=True)
    show_on_mobile = serializers.BooleanField(default=True)
    show_on_tablet = serializers.BooleanField(default=True)
    show_on_desktop = serializers.BooleanField(default=True)
    refresh_type = serializers.ChoiceField(choices=['none', 'time_based', 'scroll', 'click'], default='none')
    refresh_interval_seconds = serializers.IntegerField(min_value=15, max_value=300, default=30)
    floor_price_override = serializers.DecimalField(max_digits=8, decimal_places=4, required=False)
    min_viewability_percentage = serializers.IntegerField(min_value=0, max_value=100, default=50)
    css_selector = serializers.CharField(required=False, allow_blank=True)


class MediationGroupSchema(serializers.Serializer):
    ad_unit_id = serializers.CharField()
    name = serializers.CharField(max_length=200)
    mediation_type = serializers.ChoiceField(choices=['waterfall', 'header_bidding', 'hybrid'])
    auto_optimize = serializers.BooleanField(default=False)
    optimization_interval_hours = serializers.IntegerField(min_value=1, max_value=168, default=24)

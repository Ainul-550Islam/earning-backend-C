from rest_framework import serializers


# ─── Currency ─────────────────────────────────────────────────────────────────

class CurrencyConvertSerializer(serializers.Serializer):
    """Input for the currency conversion endpoint."""
    amount = serializers.FloatField(
        min_value=0,
        help_text='Amount to convert.',
    )
    from_currency = serializers.CharField(
        max_length=3,
        help_text='Source currency code (ISO 4217).',
    )
    to_currency = serializers.CharField(
        max_length=3,
        default='USD',
        help_text='Target currency code (ISO 4217).',
    )

    def validate_from_currency(self, value):
        return value.upper()

    def validate_to_currency(self, value):
        return value.upper()


class CurrencyConvertResultSerializer(serializers.Serializer):
    """Result from currency conversion."""
    amount = serializers.FloatField()
    from_currency = serializers.CharField()
    to_currency = serializers.CharField()
    converted_amount = serializers.FloatField()
    formatted = serializers.CharField()
    rate = serializers.FloatField()


class CurrencyRateSerializer(serializers.Serializer):
    """Single currency rate entry."""
    code = serializers.CharField()
    name = serializers.CharField()
    symbol = serializers.CharField(allow_blank=True)
    rate_to_usd = serializers.FloatField()
    formatted_1_usd = serializers.CharField(
        help_text='How 1 USD is expressed in this currency.',
    )


class CurrencyListSerializer(serializers.Serializer):
    """Full supported currency list with rates."""
    base = serializers.CharField(default='USD')
    rates_updated_at = serializers.DateTimeField(allow_null=True)
    currencies = CurrencyRateSerializer(many=True)


# ─── GeoIP ────────────────────────────────────────────────────────────────────

class GeoIPLookupSerializer(serializers.Serializer):
    """Input for the IP lookup endpoint."""
    ip = serializers.IPAddressField(
        help_text='IPv4 or IPv6 address to look up.',
    )


class GeoIPResultSerializer(serializers.Serializer):
    """
    Full IP intelligence result returned by GeoIPEnricher.enrich().
    """
    ip = serializers.IPAddressField()
    country = serializers.CharField(max_length=2, allow_blank=True)
    country_name = serializers.CharField(allow_blank=True)
    region = serializers.CharField(allow_blank=True)
    region_code = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True)
    postal_code = serializers.CharField(allow_blank=True)
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    timezone = serializers.CharField(allow_blank=True)
    asn = serializers.CharField(allow_blank=True)
    asn_org = serializers.CharField(allow_blank=True)
    isp = serializers.CharField(allow_blank=True)
    is_mobile = serializers.BooleanField()
    is_proxy = serializers.BooleanField()
    is_vpn = serializers.BooleanField()
    is_tor = serializers.BooleanField()
    is_datacenter = serializers.BooleanField()
    connection_type = serializers.CharField(allow_blank=True)
    fraud_risk = serializers.ChoiceField(choices=['low', 'medium', 'high'])


# ─── Cache Stats ──────────────────────────────────────────────────────────────

class CacheStatsSerializer(serializers.Serializer):
    """Full cache statistics returned by CacheWarmupOrchestrator.get_cache_stats()."""
    total_cached_links = serializers.IntegerField()
    total_cached_pools = serializers.IntegerField()
    cache_hit_rate_percent = serializers.FloatField(allow_null=True)
    memory_used_mb = serializers.FloatField(allow_null=True)
    last_warmup_at = serializers.DateTimeField(allow_null=True)
    last_warmup_duration_seconds = serializers.FloatField(allow_null=True)


class WarmupResultSerializer(serializers.Serializer):
    """Result from cache warmup actions."""
    warmed = serializers.IntegerField()
    failed = serializers.IntegerField()
    skipped = serializers.IntegerField()
    duration_seconds = serializers.FloatField()
    details = serializers.ListField(
        child=serializers.DictField(),
        required=False,
    )


class WarmupSingleSerializer(serializers.Serializer):
    """Input for warming up a single SmartLink slug."""
    slug = serializers.SlugField(help_text='SmartLink slug to warm up.')


# ─── Security / Rate Limiter ──────────────────────────────────────────────────

class RateLimitBanSerializer(serializers.Serializer):
    """A single IP/identifier ban entry."""
    identifier = serializers.CharField()
    identifier_type = serializers.ChoiceField(
        choices=['ip', 'publisher_id', 'slug'],
    )
    violation_count = serializers.IntegerField()
    banned_until = serializers.DateTimeField(allow_null=True)
    is_permanent = serializers.BooleanField()


class ManualBanSerializer(serializers.Serializer):
    """Input for manually banning an IP."""
    ip = serializers.IPAddressField()
    duration_hours = serializers.IntegerField(
        min_value=1,
        max_value=720,
        default=24,
        help_text='Ban duration in hours (1–720). Default: 24.',
    )
    reason = serializers.CharField(
        max_length=200,
        required=False,
        default='',
        help_text='Internal reason for the ban.',
    )


class ManualUnbanSerializer(serializers.Serializer):
    """Input for manually unbanning an IP."""
    ip = serializers.IPAddressField()


# ─── Notification Preferences ────────────────────────────────────────────────

class NotificationPreferenceSerializer(serializers.Serializer):
    """
    Publisher notification preferences.
    Stored in publisher profile JSON or a separate table.
    """
    cap_reached_email = serializers.BooleanField(default=True)
    cap_reached_telegram = serializers.BooleanField(default=False)
    cap_reached_slack = serializers.BooleanField(default=False)
    fraud_spike_email = serializers.BooleanField(default=True)
    fraud_spike_telegram = serializers.BooleanField(default=True)
    broken_smartlink_email = serializers.BooleanField(default=True)
    ab_winner_email = serializers.BooleanField(default=True)
    daily_report_email = serializers.BooleanField(default=True)
    daily_report_telegram = serializers.BooleanField(default=False)
    telegram_chat_id = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default='',
        help_text='Telegram chat ID for notifications.',
    )
    slack_webhook_url = serializers.URLField(
        required=False,
        allow_blank=True,
        default='',
        help_text='Slack webhook URL for notifications.',
    )

    def validate_telegram_chat_id(self, value):
        if value and not value.lstrip('-').isdigit():
            raise serializers.ValidationError(
                'Telegram chat ID must be numeric (may start with -).'
            )
        return value

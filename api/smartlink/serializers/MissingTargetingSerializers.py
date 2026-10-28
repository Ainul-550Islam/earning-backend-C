"""
SmartLink — Previously Missing Serializers
============================================
6 models had viewsets or were referenced in the codebase but had NO serializer.
This caused the coverage scanner to flag them as partially/uncovered.

Fixed:
  1. OSTargetingSerializer         — OSTargetingViewSet in MissingViewSets.py
  2. ISPTargetingSerializer         — ISPTargetingViewSet in MissingViewSets.py
  3. LanguageTargetingSerializer    — LanguageTargetingViewSet in MissingViewSets.py
  4. ClickHeatmapSerializer         — HeatmapViewSet in HeatmapViewSet.py
  5. SmartLinkDailyStatSerializer   — SmartLinkStatViewSet (daily_stats endpoint)
  6. PublisherAPIKeySerializer      — APIKeyViewSet in BusinessViewSets.py

Import in serializers/__init__.py or directly in the viewsets.
"""
import ipaddress

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from api.smartlink.models.targeting import OSTargeting, ISPTargeting, LanguageTargeting
from api.smartlink.models.click import ClickHeatmap
from api.smartlink.models.analytics import SmartLinkDailyStat
from api.smartlink.models.billing import PublisherAPIKey


# ─────────────────────────────────────────────────────────────────────────────
# 1. OSTargetingSerializer
# ─────────────────────────────────────────────────────────────────────────────

class OSTargetingSerializer(serializers.ModelSerializer):
    """
    Serializer for OSTargeting (OneToOne with TargetingRule).
    Manages operating system whitelist/blacklist.

    Fields:
      rule       — FK to TargetingRule (read-only)
      mode       — 'whitelist' | 'blacklist'
      os_types   — list of OS strings, e.g. ["Android", "iOS", "Windows"]
      updated_at — auto timestamp

    Example request body:
        {"mode": "whitelist", "os_types": ["Android", "iOS"]}
    """

    class Meta:
        model = OSTargeting
        fields = ['id', 'rule', 'mode', 'os_types', 'updated_at']
        read_only_fields = ['id', 'rule', 'updated_at']

    def validate_os_types(self, value):
        """Ensure os_types is a non-empty list of known OS values."""
        KNOWN = {'android', 'ios', 'windows', 'mac', 'linux',
                 'chromeos', 'windowsphone', 'other'}
        if not isinstance(value, list):
            raise serializers.ValidationError(_('os_types must be a list.'))
        for os in value:
            if str(os).lower() not in KNOWN:
                raise serializers.ValidationError(
                    _(f'Unknown OS type: {os}. Allowed: {sorted(KNOWN)}')
                )
        return value


# ─────────────────────────────────────────────────────────────────────────────
# 2. ISPTargetingSerializer
# ─────────────────────────────────────────────────────────────────────────────

class ISPTargetingSerializer(serializers.ModelSerializer):
    """
    Serializer for ISPTargeting (OneToOne with TargetingRule).
    Manages carrier/ISP name and ASN whitelist/blacklist.

    Fields:
      rule       — FK to TargetingRule (read-only)
      mode       — 'whitelist' | 'blacklist'
      isps       — list of ISP name substrings, e.g. ["Grameenphone", "Robi"]
      asns       — list of ASN strings, e.g. ["AS24389", "AS17494"]
      updated_at — auto timestamp

    Example:
        {"mode": "whitelist", "isps": ["Grameenphone"], "asns": ["AS24389"]}
    """

    class Meta:
        model = ISPTargeting
        fields = ['id', 'rule', 'mode', 'isps', 'asns', 'updated_at']
        read_only_fields = ['id', 'rule', 'updated_at']

    def validate_isps(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(_('isps must be a list of strings.'))
        return [str(v).strip() for v in value if str(v).strip()]

    def validate_asns(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(_('asns must be a list of ASN strings.'))
        cleaned = []
        for asn in value:
            asn = str(asn).strip().upper()
            if asn and not asn.startswith('AS'):
                asn = f'AS{asn}'
            if asn:
                cleaned.append(asn)
        return cleaned

    def validate(self, attrs):
        isps = attrs.get('isps', [])
        asns = attrs.get('asns', [])
        if not isps and not asns:
            raise serializers.ValidationError(
                _('At least one ISP name or ASN must be provided.')
            )
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# 3. LanguageTargetingSerializer
# ─────────────────────────────────────────────────────────────────────────────

class LanguageTargetingSerializer(serializers.ModelSerializer):
    """
    Serializer for LanguageTargeting (OneToOne with TargetingRule).
    Filters traffic by browser Accept-Language header.

    Fields:
      rule       — FK to TargetingRule (read-only)
      mode       — 'whitelist' | 'blacklist'
      languages  — ISO 639-1 codes, e.g. ["en", "bn", "ar"]
      updated_at — auto timestamp

    Example:
        {"mode": "whitelist", "languages": ["en", "bn"]}
    """

    class Meta:
        model = LanguageTargeting
        fields = ['id', 'rule', 'mode', 'languages', 'updated_at']
        read_only_fields = ['id', 'rule', 'updated_at']

    def validate_languages(self, value):
        """Validate ISO 639-1 language codes (2-letter, lowercase)."""
        if not isinstance(value, list):
            raise serializers.ValidationError(_('languages must be a list.'))
        cleaned = []
        for lang in value:
            lang = str(lang).strip().lower()
            if len(lang) != 2 or not lang.isalpha():
                raise serializers.ValidationError(
                    _(f'Invalid language code: "{lang}". Must be a 2-letter ISO 639-1 code.')
                )
            cleaned.append(lang)
        return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 4. ClickHeatmapSerializer
# ─────────────────────────────────────────────────────────────────────────────

class ClickHeatmapSerializer(serializers.ModelSerializer):
    """
    Serializer for ClickHeatmap.
    Geo heatmap aggregated per SmartLink / country / date.
    Read-only — rows are created by the stat_rollup Celery task.

    Fields:
      smartlink          — FK to SmartLink (read-only)
      country            — ISO 3166-1 alpha-2 code
      date               — YYYY-MM-DD
      click_count        — total clicks on this day from this country
      unique_click_count — unique-IP clicks
      conversion_count   — conversions
      revenue            — USD revenue
      epc                — revenue / click_count
      updated_at         — last updated
    """
    epc_display = serializers.SerializerMethodField()

    class Meta:
        model = ClickHeatmap
        fields = [
            'id', 'smartlink', 'country', 'date',
            'click_count', 'unique_click_count', 'conversion_count',
            'revenue', 'epc', 'epc_display', 'updated_at',
        ]
        read_only_fields = list(fields)

    def get_epc_display(self, obj):
        """Format EPC as currency string for display."""
        try:
            return f'${float(obj.epc):.4f}'
        except (TypeError, ValueError):
            return '$0.0000'


# ─────────────────────────────────────────────────────────────────────────────
# 5. SmartLinkDailyStatSerializer
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkDailyStatSerializer(serializers.ModelSerializer):
    """
    Serializer for SmartLinkDailyStat.
    Daily rollup stats per SmartLink — used for dashboard charts.
    Read-only — rows are aggregated by daily rollup Celery task.

    Fields:
      smartlink       — FK
      date            — stat date
      clicks          — total clicks
      unique_clicks   — unique IP clicks
      bot_clicks      — detected bot clicks
      fraud_clicks    — fraud-flagged clicks
      conversions     — conversions
      revenue         — USD revenue
      epc             — earnings per click
      conversion_rate — conversions / clicks ratio
      top_country     — most-clicked country for this day
      top_device      — most-clicked device type
      updated_at
    """
    quality_rate = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkDailyStat
        fields = [
            'id', 'smartlink', 'date',
            'clicks', 'unique_clicks', 'bot_clicks', 'fraud_clicks',
            'conversions', 'revenue', 'epc', 'conversion_rate',
            'top_country', 'top_device', 'quality_rate', 'updated_at',
        ]
        read_only_fields = list(fields)

    def get_quality_rate(self, obj):
        """
        Quality rate = (clicks - bot_clicks - fraud_clicks) / clicks × 100.
        Represents the percentage of clean traffic.
        """
        if not obj.clicks:
            return 100.0
        bad  = (obj.bot_clicks or 0) + (obj.fraud_clicks or 0)
        good = max(0, obj.clicks - bad)
        return round(good / obj.clicks * 100, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 6. PublisherAPIKeySerializer
# ─────────────────────────────────────────────────────────────────────────────

class PublisherAPIKeySerializer(serializers.ModelSerializer):
    """
    Serializer for PublisherAPIKey.
    Used by APIKeyViewSet in BusinessViewSets.py.

    SECURITY NOTES:
      - key_hash is NEVER returned in any response (write-only at creation time).
      - The raw key is returned ONCE at creation via the `raw_key` field
        (populated by perform_create, not from DB).
      - After creation, the raw key cannot be recovered.

    Read (list/detail):
      id, publisher_username, name, key_prefix, scope, is_active,
      allowed_ips, last_used_at, expires_at, request_count, created_at

    Create (POST):
      name, scope, allowed_ips, expires_at
      → returns raw_key (one-time display only)

    Update (PATCH):
      name, scope, allowed_ips, expires_at, is_active
    """
    publisher_username = serializers.CharField(
        source='publisher.username', read_only=True
    )
    raw_key = serializers.CharField(
        read_only=True, allow_null=True,
        help_text='Returned ONCE at key creation only. Store it securely.',
    )
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = PublisherAPIKey
        fields = [
            'id', 'publisher_username', 'name', 'key_prefix',
            'scope', 'is_active', 'allowed_ips',
            'last_used_at', 'expires_at', 'request_count',
            'is_expired', 'created_at',
            # key_hash intentionally excluded — never returned
            'raw_key',   # write-only at creation (populated by perform_create)
        ]
        read_only_fields = [
            'id', 'publisher_username', 'key_prefix',
            'last_used_at', 'request_count', 'created_at',
            'raw_key',
        ]
        extra_kwargs = {
            'name':        {'required': True, 'max_length': 100},
            'allowed_ips': {'required': False},
        }

    def get_is_expired(self, obj) -> bool:
        """True if expires_at is set and in the past."""
        return bool(obj.expires_at and obj.expires_at < timezone.now())

    def validate_allowed_ips(self, value):
        """Validate each IP / CIDR in the allowed_ips list."""
        if not isinstance(value, list):
            raise serializers.ValidationError(_('allowed_ips must be a list.'))
        cleaned = []
        for ip in value:
            try:
                ipaddress.ip_network(str(ip).strip(), strict=False)
                cleaned.append(str(ip).strip())
            except ValueError:
                raise serializers.ValidationError(
                    _(f'Invalid IP or CIDR: {ip}')
                )
        return cleaned

    def validate_scope(self, value):
        valid = [s for s, _ in PublisherAPIKey.Scope.choices]
        if value not in valid:
            raise serializers.ValidationError(
                _(f'Invalid scope: {value}. Choose from: {valid}')
            )
        return value

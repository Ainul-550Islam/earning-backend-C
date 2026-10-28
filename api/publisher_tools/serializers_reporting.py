# publisher_tools/serializers_reporting.py
"""
Serializers for the 4 new DRY-audit viewsets:
  ReportingViewSet      → views_reporting.py
  PayoutViewSet         → views_payout.py
  FraudReportViewSet    → views_fraud_report.py
  RealtimeViewSet       → views_realtime.py

Design principles (DRY):
  - Input serializers validate request.data before it reaches the view.
  - Output serializers are plain Serializer (not ModelSerializer) because
    the data is assembled by subfolder functions, not queried as ORM objects.
  - Shared field patterns (period, days, country) defined as module-level
    constants and re-used — not copy-pasted.
  - No serializer duplicates logic already validated in the view (e.g. date
    range business rules stay in the view; field presence stays here).
"""

from datetime import date
from decimal import Decimal
from rest_framework import serializers

# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL SHARED FIELD DEFINITIONS (DRY — reference, not copy-paste)
# ─────────────────────────────────────────────────────────────────────────────

VALID_PERIODS = (
    'today', 'yesterday', 'last_7_days', 'last_30_days',
    'last_90_days', 'this_month', 'last_month', 'this_year',
)

VALID_METRICS = ('revenue', 'impressions', 'ecpm', 'ctr', 'fill_rate')

VALID_DIMENSIONS = ('country', 'format', 'device', 'site', 'ad_unit')


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING SERIALIZERS  (ReportingViewSet)
# ══════════════════════════════════════════════════════════════════════════════

class MonthlyReportQuerySerializer(serializers.Serializer):
    """
    Input: GET /reports/monthly/?year=2025&month=6
    Validates year/month before the view calls generate_monthly_report().
    """
    year  = serializers.IntegerField(
        default=None, allow_null=True,
        min_value=2000, max_value=date.today().year + 1,
        help_text='Calendar year (default: current year).',
    )
    month = serializers.IntegerField(
        default=None, allow_null=True,
        min_value=1, max_value=12,
        help_text='Month (1–12, default: current month).',
    )


class RevenueForecastQuerySerializer(serializers.Serializer):
    """
    Input: GET /reports/revenue-forecast/?days=30
    """
    days = serializers.IntegerField(
        default=30, min_value=1, max_value=365,
        help_text='Number of days ahead to forecast.',
    )


class EcpmBreakdownQuerySerializer(serializers.Serializer):
    """
    Input: GET /reports/ecpm-breakdown/?by=country&days=30
    """
    by   = serializers.ChoiceField(
        choices=['country', 'format'],
        default='country',
    )
    days  = serializers.IntegerField(default=30, min_value=1, max_value=365)
    start = serializers.DateField(required=False, allow_null=True)
    end   = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        start = data.get('start')
        end   = data.get('end')
        if start and end and start > end:
            raise serializers.ValidationError(
                {'start': 'start must not be after end.'}
            )
        return data


class ChartDataQuerySerializer(serializers.Serializer):
    """
    Input: GET /reports/chart-data/?period=last_30_days&metric=revenue
    """
    period = serializers.ChoiceField(
        choices=list(VALID_PERIODS),
        default='last_30_days',
    )
    metric = serializers.ChoiceField(
        choices=list(VALID_METRICS),
        default='revenue',
    )


class TopUnitsQuerySerializer(serializers.Serializer):
    """
    Input: GET /reports/top-units/?days=30&limit=10
    """
    days  = serializers.IntegerField(default=30, min_value=1, max_value=365)
    limit = serializers.IntegerField(default=10, min_value=1, max_value=100)


class RevenueDimensionQuerySerializer(serializers.Serializer):
    """
    Input: GET /reports/revenue-by-dimension/?dimension=country&days=30
    """
    dimension = serializers.ChoiceField(
        choices=list(VALID_DIMENSIONS),
        default='country',
    )
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)


class FillImpactQuerySerializer(serializers.Serializer):
    """
    Input: GET /reports/fill-impact/?unit_id=UNIT-001&target_fill=80
    """
    unit_id     = serializers.CharField(max_length=100)
    target_fill = serializers.FloatField(
        default=80.0, min_value=0.0, max_value=100.0,
        help_text='Target fill rate percentage (0–100).',
    )


class FillRateIssuesQuerySerializer(serializers.Serializer):
    """
    Input: GET /reports/fill-rate-issues/?threshold=50&days=30
    """
    threshold = serializers.FloatField(
        default=50.0, min_value=0.0, max_value=100.0,
        help_text='Flag units with fill rate below this percentage.',
    )
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)


class ExportReportInputSerializer(serializers.Serializer):
    """
    Input: POST /reports/export/
    {
      "metrics":    ["revenue", "impressions", "ecpm"],
      "dimensions": ["date", "country"],
      "start_date": "2025-01-01",
      "end_date":   "2025-01-31",
      "format":     "csv"
    }
    """
    metrics    = serializers.ListField(
        child=serializers.ChoiceField(choices=list(VALID_METRICS)),
        min_length=1,
        default=['revenue', 'impressions', 'ecpm'],
    )
    dimensions = serializers.ListField(
        child=serializers.ChoiceField(choices=list(VALID_DIMENSIONS) + ['date']),
        min_length=1,
        default=['date'],
    )
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date   = serializers.DateField(required=False, allow_null=True)
    format     = serializers.ChoiceField(
        choices=['csv', 'json'], default='json',
        help_text="Export format: 'csv' or 'json'.",
    )

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end and start > end:
            raise serializers.ValidationError(
                {'start_date': 'start_date must not be after end_date.'}
            )
        return data


# ══════════════════════════════════════════════════════════════════════════════
# PAYOUT SERIALIZERS  (PayoutViewSet)
# ══════════════════════════════════════════════════════════════════════════════

class PayoutRequestInputSerializer(serializers.Serializer):
    """
    Input: POST /payout/request/
    {
      "amount":          123.45,
      "bank_account_id": "uuid-or-int",
      "notes":           "Optional"
    }
    """
    amount          = serializers.DecimalField(
        max_digits=14, decimal_places=4,
        min_value=Decimal('0.0001'),
    )
    bank_account_id = serializers.CharField(max_length=200)
    notes           = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default='',
    )


class WithholdingTaxInputSerializer(serializers.Serializer):
    """
    Input: POST /payout/withholding-tax/
    {
      "amount":  100.00,
      "country": "US",
      "has_w8":  false
    }
    """
    amount  = serializers.DecimalField(
        max_digits=14, decimal_places=4,
        min_value=Decimal('0.0001'),
    )
    country = serializers.RegexField(
        r'^[A-Z]{2}$',
        error_messages={'invalid': 'country must be a 2-letter ISO 3166-1 alpha-2 code.'},
    )
    has_w8  = serializers.BooleanField(default=False)


class PayoutHistoryQuerySerializer(serializers.Serializer):
    """
    Input: GET /payout/history/?limit=20
    """
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)


class PaymentHistoryQuerySerializer(serializers.Serializer):
    """
    Input: GET /payout/payment-history/?limit=50
    """
    limit = serializers.IntegerField(default=50, min_value=1, max_value=200)


class PaymentSummaryQuerySerializer(serializers.Serializer):
    """
    Input: GET /payout/payment-summary/?year=2025
    """
    year = serializers.IntegerField(
        default=None, allow_null=True,
        min_value=2000, max_value=date.today().year,
    )


class TaxRateQuerySerializer(serializers.Serializer):
    """
    Input: GET /payout/tax-rate/?country=BD
    """
    country = serializers.RegexField(
        r'^[A-Z]{2}$',
        error_messages={'invalid': 'country must be a 2-letter ISO 3166-1 alpha-2 code.'},
    )


# ══════════════════════════════════════════════════════════════════════════════
# FRAUD REPORT SERIALIZERS  (FraudReportViewSet)
# ══════════════════════════════════════════════════════════════════════════════

class FraudReportQuerySerializer(serializers.Serializer):
    """
    Input: GET /fraud-reports/report/?days=30
    """
    days = serializers.IntegerField(default=30, min_value=1, max_value=365)


class GeoValidateInputSerializer(serializers.Serializer):
    """
    Input: POST /fraud-reports/geo-validate/
    {
      "ip_country":      "KP",
      "claimed_country": "US"
    }
    """
    ip_country      = serializers.RegexField(
        r'^[A-Z]{2}$',
        error_messages={'invalid': 'ip_country must be a 2-letter country code.'},
    )
    claimed_country = serializers.RegexField(
        r'^[A-Z]{2}$', required=False, allow_null=True, default=None,
        error_messages={'invalid': 'claimed_country must be a 2-letter country code.'},
    )


class ImpossibleTravelInputSerializer(serializers.Serializer):
    """
    Input: POST /fraud-reports/impossible-travel/
    {
      "user_id":         "user_xyz",
      "current_country": "US",
      "prev_country":    "BD",
      "time_diff_hours": 0.5
    }
    """
    user_id         = serializers.CharField(max_length=200, required=False, default='')
    current_country = serializers.RegexField(
        r'^[A-Z]{2}$',
        error_messages={'invalid': 'current_country must be a 2-letter country code.'},
    )
    prev_country    = serializers.RegexField(
        r'^[A-Z]{2}$', required=False, allow_null=True, default=None,
        error_messages={'invalid': 'prev_country must be a 2-letter country code.'},
    )
    time_diff_hours = serializers.FloatField(
        min_value=0.0,
        help_text='Hours since last geo event for this user.',
    )


class CountryRiskQuerySerializer(serializers.Serializer):
    """
    Input: GET /fraud-reports/country-risk/?country=KP
    """
    country = serializers.RegexField(
        r'^[A-Z]{2}$',
        error_messages={'invalid': 'country must be a 2-letter country code.'},
    )


class VelocityCheckInputSerializer(serializers.Serializer):
    """
    Input: POST /fraud-reports/velocity-check/
    {
      "identifier": "ip:192.168.1.1",
      "event_type": "click"
    }
    """
    identifier = serializers.CharField(max_length=500)
    event_type = serializers.CharField(max_length=100)


class ClickVelocityInputSerializer(serializers.Serializer):
    """
    Input: POST /fraud-reports/click-velocity/
    """
    identifier = serializers.CharField(max_length=500)
    unit_id    = serializers.CharField(max_length=100)


class ImpressionVelocityInputSerializer(serializers.Serializer):
    """
    Input: POST /fraud-reports/impression-velocity/
    """
    ip      = serializers.IPAddressField(protocol='both')
    unit_id = serializers.CharField(max_length=100)


class ConversionVelocityInputSerializer(serializers.Serializer):
    """
    Input: POST /fraud-reports/conversion-velocity/
    """
    identifier = serializers.CharField(max_length=500)


# ══════════════════════════════════════════════════════════════════════════════
# REALTIME SERIALIZERS  (RealtimeViewSet)
# ══════════════════════════════════════════════════════════════════════════════

class DashboardQuerySerializer(serializers.Serializer):
    """
    Input: GET /realtime/dashboard/?period=last_30_days
    """
    period = serializers.ChoiceField(
        choices=list(VALID_PERIODS),
        default='last_30_days',
    )


class RealtimeFillRateQuerySerializer(serializers.Serializer):
    """
    Input: GET /realtime/fill-rate/?unit_id=UNIT-001
    """
    unit_id = serializers.CharField(max_length=100)


class TrackAdRequestInputSerializer(serializers.Serializer):
    """
    Input: POST /realtime/track-request/
    {
      "unit_id": "UNIT-001"
    }
    """
    unit_id = serializers.CharField(max_length=100)


class DailyReportQuerySerializer(serializers.Serializer):
    """
    Input: GET /realtime/daily-report/?date=2025-06-11
    """
    date = serializers.DateField(
        required=False, allow_null=True,
        help_text='Date to report (default: today). Format: YYYY-MM-DD.',
    )


class DailyComparisonQuerySerializer(serializers.Serializer):
    """
    Input: GET /realtime/daily-comparison/?days=7
    """
    days = serializers.IntegerField(
        default=7, min_value=1, max_value=90,
        help_text='Number of days to compare current vs prior.',
    )


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT SERIALIZERS (shared across viewsets)
# ══════════════════════════════════════════════════════════════════════════════

class PayoutEligibilitySerializer(serializers.Serializer):
    """
    Output: GET /payout/eligibility/
    """
    eligible       = serializers.BooleanField()
    reason         = serializers.CharField(required=False, allow_null=True)
    balance        = serializers.FloatField(required=False, allow_null=True)
    payment_method = serializers.CharField(required=False, allow_null=True)
    threshold      = serializers.FloatField(required=False, allow_null=True)


class PayoutRequestOutputSerializer(serializers.Serializer):
    """
    Output: POST /payout/request/ (success case)
    """
    success    = serializers.BooleanField()
    payout_id  = serializers.CharField()
    amount     = serializers.FloatField()
    net_amount = serializers.FloatField()


class WithholdingTaxOutputSerializer(serializers.Serializer):
    """
    Output: POST /payout/withholding-tax/
    """
    gross_amount = serializers.FloatField()
    country      = serializers.CharField()
    tax_rate_pct = serializers.FloatField()
    tax_amount   = serializers.FloatField()
    net_amount   = serializers.FloatField()
    has_w8_form  = serializers.BooleanField()


class FraudReportSummarySerializer(serializers.Serializer):
    """
    Output: GET /fraud-reports/report/ → data.summary
    """
    total_ivt_events      = serializers.IntegerField()
    avg_fraud_score       = serializers.FloatField()
    revenue_at_risk_usd   = serializers.FloatField()
    revenue_deducted_usd  = serializers.FloatField()
    ivt_rate_pct          = serializers.FloatField()
    affected_impressions  = serializers.IntegerField()
    total_impressions     = serializers.IntegerField()


class GeoValidateOutputSerializer(serializers.Serializer):
    """
    Output: POST /fraud-reports/geo-validate/
    """
    score        = serializers.IntegerField()
    is_suspicious = serializers.BooleanField()
    signals      = serializers.ListField(child=serializers.CharField())
    ip_country   = serializers.CharField()


class CountryRiskOutputSerializer(serializers.Serializer):
    """
    Output: GET /fraud-reports/country-risk/
    """
    country        = serializers.CharField()
    risk_score     = serializers.IntegerField()
    is_high_risk   = serializers.BooleanField()
    is_vpn_country = serializers.BooleanField()
    risk_level     = serializers.CharField()


class LiveStatsOutputSerializer(serializers.Serializer):
    """
    Output: GET /realtime/live/
    """
    timestamp          = serializers.CharField()
    today_revenue      = serializers.FloatField()
    today_impressions  = serializers.IntegerField()
    today_clicks       = serializers.IntegerField()
    ivt_today          = serializers.IntegerField()
    account_status     = serializers.CharField()
    pending_balance    = serializers.FloatField()

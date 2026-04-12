"""
analytics_reporting/custom_report.py
──────────────────────────────────────
Custom report builder with flexible filtering.
Admin can build ad-hoc reports with any combination of:
  - Date range, network, offer, publisher, country, device type
  - Metrics: clicks, conversions, revenue, fraud rate, EPC
  - Group by: day, week, month, network, offer, country, device
  - Export: JSON, CSV
"""
from __future__ import annotations
import csv
import io
import logging
from datetime import timedelta
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from ..models import Conversion, ClickLog
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)

VALID_GROUP_BY = ("day", "week", "month", "network", "offer_id", "country", "device_type")
VALID_METRICS  = ("clicks", "conversions", "revenue_usd", "fraud_clicks", "cr_pct", "epc_usd")


class CustomReport:

    def build(
        self,
        start_date=None,
        end_date=None,
        network_key: str = None,
        offer_id: str = None,
        sub_id: str = None,
        country: str = None,
        device_type: str = None,
        group_by: str = "day",
        metrics: list = None,
    ) -> list:
        """
        Build a custom report with flexible filters.
        Returns list of dicts.
        """
        if group_by not in VALID_GROUP_BY:
            raise ValueError(f"group_by must be one of: {VALID_GROUP_BY}")

        now = timezone.now()
        end = end_date or now
        start = start_date or (now - timedelta(days=30))

        # Clicks query
        clicks_qs = ClickLog.objects.filter(clicked_at__gte=start, clicked_at__lte=end)
        # Conversions query
        convs_qs = Conversion.objects.filter(
            converted_at__gte=start, converted_at__lte=end,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )

        # Apply filters
        if network_key:
            clicks_qs = clicks_qs.filter(network__network_key=network_key)
            convs_qs  = convs_qs.filter(network__network_key=network_key)
        if offer_id:
            clicks_qs = clicks_qs.filter(offer_id=offer_id)
            convs_qs  = convs_qs.filter(offer_id=offer_id)
        if sub_id:
            clicks_qs = clicks_qs.filter(sub_id=sub_id)
        if country:
            clicks_qs = clicks_qs.filter(country__iexact=country)
            convs_qs  = convs_qs.filter(country__iexact=country)
        if device_type:
            clicks_qs = clicks_qs.filter(device_type=device_type)

        # Group by
        trunc_fns = {"day": TruncDate, "week": TruncWeek, "month": TruncMonth}
        dimension_fields = {
            "network":     ("network__name", "network__network_key"),
            "offer_id":    ("offer_id",),
            "country":     ("country",),
            "device_type": ("device_type",),
        }

        if group_by in trunc_fns:
            trunc_fn = trunc_fns[group_by]
            click_data = dict(
                clicks_qs
                .annotate(period=trunc_fn("clicked_at"))
                .values("period")
                .annotate(
                    total=Count("id"),
                    fraud=Count("id", filter={"is_fraud": True}),
                )
                .values_list("period", "total")
            )
            conv_data = (
                convs_qs
                .annotate(period=trunc_fn("converted_at"))
                .values("period")
                .annotate(
                    conversions=Count("id"),
                    revenue=Sum("actual_payout"),
                )
            )
            results = []
            for row in conv_data:
                period = row["period"]
                clicks = click_data.get(period, 0)
                convs = row["conversions"]
                rev = float(row["revenue"] or 0)
                results.append({
                    "period": str(period.date() if hasattr(period, "date") else period),
                    "clicks": clicks,
                    "conversions": convs,
                    "revenue_usd": round(rev, 4),
                    "cr_pct": round((convs / clicks * 100) if clicks > 0 else 0, 2),
                    "epc_usd": round(rev / clicks if clicks > 0 else 0, 4),
                })
            return sorted(results, key=lambda x: x["period"])

        # Group by dimension (network, offer_id, country, device_type)
        fields = dimension_fields.get(group_by, ("offer_id",))
        rows = (
            convs_qs.values(*fields)
            .annotate(
                conversions=Count("id"),
                revenue=Sum("actual_payout"),
            )
            .order_by("-conversions")
        )
        return [
            {**{f.split("__")[-1]: r[f] for f in fields},
             "conversions": r["conversions"],
             "revenue_usd": float(r["revenue"] or 0)}
            for r in rows
        ]

    def to_csv(self, data: list) -> str:
        """Export report data to CSV string."""
        if not data:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    def to_json(self, data: list) -> list:
        """Return data as JSON-serialisable list."""
        return data


custom_report = CustomReport()

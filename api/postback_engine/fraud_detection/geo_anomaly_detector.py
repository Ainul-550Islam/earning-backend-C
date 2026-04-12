"""
fraud_detection/geo_anomaly_detector.py
─────────────────────────────────────────
Geographic anomaly detection for postback fraud.

Detects:
  - Click from country A, conversion from country B (geo mismatch)
  - High concentration of conversions from sanctioned/high-fraud countries
  - Impossible travel (two conversions from distant locations in short time)
  - Offer restricted to specific countries being converted from wrong geo
"""
from __future__ import annotations
import logging
from typing import Tuple, List, Optional
from django.utils import timezone
from datetime import timedelta
from ..models import ClickLog, Conversion

logger = logging.getLogger(__name__)

# High-fraud-risk countries (ISO 3166-1 alpha-2)
# These are known sources of click fraud — flag but don't auto-block
HIGH_FRAUD_COUNTRIES = {
    # Adjust based on your actual traffic patterns and business rules
}

# Countries with high conversion fraud rates for specific offer types
SANCTIONED_COUNTRIES = set()  # Add as needed per legal compliance


class GeoAnomalyDetector:

    def check(
        self,
        click_country: str = "",
        conversion_country: str = "",
        click_ip: str = "",
        conversion_ip: str = "",
        offer_allowed_countries: list = None,
        offer_blocked_countries: list = None,
    ) -> Tuple[bool, float, List[str]]:
        """
        Detect geographic anomalies.
        Returns (is_anomaly, score, signals).
        """
        signals = []
        score = 0.0

        # 1. Country mismatch (click vs conversion)
        if click_country and conversion_country and click_country != conversion_country:
            signals.append(
                f"GEO_MISMATCH: click from {click_country}, conversion from {conversion_country}"
            )
            score = max(score, 55.0)

        # 2. High fraud country
        conv_country = conversion_country or click_country
        if conv_country in HIGH_FRAUD_COUNTRIES:
            signals.append(f"HIGH_FRAUD_COUNTRY: {conv_country}")
            score = max(score, 45.0)

        # 3. Sanctioned country
        if conv_country in SANCTIONED_COUNTRIES:
            signals.append(f"SANCTIONED_COUNTRY: {conv_country}")
            score = max(score, 95.0)

        # 4. Geo-restricted offer converted from wrong country
        if offer_allowed_countries and conv_country:
            if conv_country.upper() not in [c.upper() for c in offer_allowed_countries]:
                signals.append(
                    f"GEO_RESTRICTED: offer only allowed in {offer_allowed_countries}, got {conv_country}"
                )
                score = max(score, 80.0)

        if offer_blocked_countries and conv_country:
            if conv_country.upper() in [c.upper() for c in offer_blocked_countries]:
                signals.append(f"GEO_BLOCKED: {conv_country} is blocked for this offer")
                score = max(score, 80.0)

        is_anomaly = score >= 60
        return is_anomaly, score, signals

    def check_impossible_travel(
        self,
        user,
        new_country: str,
        hours_back: int = 1,
    ) -> Optional[str]:
        """
        Check if user appears to have 'teleported' between countries.
        Returns a signal string if impossible travel detected.
        """
        if not user or not new_country:
            return None
        cutoff = timezone.now() - timedelta(hours=hours_back)
        recent_countries = set(
            Conversion.objects.filter(
                user=user,
                converted_at__gte=cutoff,
            )
            .exclude(country="")
            .values_list("country", flat=True)
            .distinct()
        )
        if len(recent_countries) >= 2 and new_country not in recent_countries:
            return (
                f"IMPOSSIBLE_TRAVEL: user has conversions from "
                f"{', '.join(recent_countries)} and now {new_country} within {hours_back}h"
            )
        return None

    def get_country_conversion_stats(self, days: int = 30) -> list:
        """Return conversion breakdown by country for fraud analysis."""
        from django.db.models import Count, Sum
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            Conversion.objects.filter(converted_at__gte=cutoff)
            .exclude(country="")
            .values("country")
            .annotate(conversions=Count("id"), revenue=Sum("actual_payout"))
            .order_by("-conversions")
        )
        return [
            {
                "country": r["country"],
                "conversions": r["conversions"],
                "revenue_usd": float(r["revenue"] or 0),
                "is_high_fraud": r["country"] in HIGH_FRAUD_COUNTRIES,
            }
            for r in rows
        ]


geo_anomaly_detector = GeoAnomalyDetector()

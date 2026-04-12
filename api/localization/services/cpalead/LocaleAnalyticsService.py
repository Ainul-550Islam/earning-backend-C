# services/cpalead/LocaleAnalyticsService.py
"""User locale analytics — conversion rates by language, country, currency."""
import logging
from typing import Dict, List
logger = logging.getLogger(__name__)


class LocaleAnalyticsService:
    """CPAlead locale-based analytics — who converts, in which language."""

    def get_conversion_by_language(self, days: int = 30) -> List[Dict]:
        """Language-wise offer completion rates।"""
        try:
            from ..models.analytics import LocalizationInsight, LanguageUsageStat
            from django.db.models import Sum, F, ExpressionWrapper, FloatField
            from django.utils import timezone
            from datetime import timedelta
            cutoff = (timezone.now() - timedelta(days=days)).date()
            data = list(
                LanguageUsageStat.objects.filter(date__gte=cutoff, language__isnull=False)
                .values("language__code", "language__name", "language__flag_emoji")
                .annotate(
                    total_sessions=Sum("total_sessions"),
                    offer_views=Sum("offer_views"),
                    conversions=Sum("conversions"),
                    total_revenue_usd=Sum("total_revenue_usd"),
                ).order_by("-conversions")[:20]
            )
            # Add conversion rate
            for row in data:
                views = row.get("offer_views") or 0
                convs = row.get("conversions") or 0
                row["conversion_rate"] = round(convs / views * 100, 2) if views > 0 else 0
            return data
        except Exception as e:
            logger.error(f"get_conversion_by_language failed: {e}")
            return []

    def get_revenue_by_country(self, days: int = 30) -> List[Dict]:
        """Country-wise revenue distribution।"""
        try:
            from ..models.analytics import GeoInsight
            from django.db.models import Sum
            from django.utils import timezone
            from datetime import timedelta
            cutoff = (timezone.now() - timedelta(days=days)).date()
            return list(
                GeoInsight.objects.filter(date__gte=cutoff)
                .values("country_code")
                .annotate(
                    total_users=Sum("total_users"),
                    total_revenue_usd=Sum("total_revenue_usd"),
                    conversions=Sum("conversions"),
                ).order_by("-total_revenue_usd")[:20]
            )
        except Exception as e:
            logger.error(f"get_revenue_by_country failed: {e}")
            return []

    def get_language_funnel(self, language_code: str, days: int = 7) -> Dict:
        """Single language conversion funnel।"""
        try:
            from ..models.analytics import LanguageUsageStat
            from django.db.models import Sum
            from django.utils import timezone
            from datetime import timedelta
            cutoff = (timezone.now() - timedelta(days=days)).date()
            agg = LanguageUsageStat.objects.filter(
                language__code=language_code, date__gte=cutoff,
            ).aggregate(
                sessions=Sum("total_sessions"),
                offer_views=Sum("offer_views"),
                offer_clicks=Sum("offer_clicks"),
                conversions=Sum("conversions"),
                revenue=Sum("total_revenue_usd"),
            )
            sessions = agg.get("sessions") or 0
            offer_views = agg.get("offer_views") or 0
            conversions = agg.get("conversions") or 0
            return {
                "language": language_code,
                "days": days,
                "funnel": {
                    "sessions": sessions,
                    "offer_views": offer_views,
                    "offer_clicks": agg.get("offer_clicks") or 0,
                    "conversions": conversions,
                    "revenue_usd": float(agg.get("revenue") or 0),
                },
                "rates": {
                    "offer_view_rate": round(offer_views / sessions * 100, 2) if sessions else 0,
                    "conversion_rate": round(conversions / offer_views * 100, 2) if offer_views else 0,
                    "revenue_per_session": round(float(agg.get("revenue") or 0) / sessions, 4) if sessions else 0,
                }
            }
        except Exception as e:
            logger.error(f"get_language_funnel failed: {e}")
            return {"language": language_code, "error": str(e)}

    def log_locale_event(
        self, event_type: str, language_code: str,
        country_code: str = "", extra: Dict = None
    ):
        """Locale event log করে।"""
        try:
            from ..models.analytics import LocalizationAnalytics
            LocalizationAnalytics.log_event(
                event_type=event_type,
                language_code=language_code,
                country_code=country_code,
                extra_data=extra or {},
            )
        except Exception as e:
            logger.debug(f"log_locale_event failed: {e}")

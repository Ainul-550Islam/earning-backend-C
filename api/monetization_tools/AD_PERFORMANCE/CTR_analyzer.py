"""AD_PERFORMANCE/CTR_analyzer.py — Click-through rate analysis."""
from decimal import Decimal
from django.db.models import Avg, Sum


class CTRAnalyzer:
    """Click-through rate analysis and benchmarking."""

    BENCHMARKS = {
        "banner":          Decimal("0.35"),
        "interstitial":    Decimal("2.50"),
        "rewarded_video":  Decimal("1.50"),
        "native":          Decimal("1.20"),
        "video":           Decimal("0.80"),
    }

    @staticmethod
    def current(ad_unit_id: int, days: int = 7) -> Decimal:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        agg    = AdPerformanceDaily.objects.filter(
            ad_unit_id=ad_unit_id, date__gte=cutoff
        ).aggregate(imp=Sum("impressions"), clk=Sum("clicks"))
        if not agg["imp"]:
            return Decimal("0")
        return (Decimal(agg["clk"] or 0) / agg["imp"] * 100).quantize(Decimal("0.0001"))

    @staticmethod
    def benchmark(ad_format: str) -> Decimal:
        return CTRAnalyzer.BENCHMARKS.get(ad_format, Decimal("0.5"))

    @staticmethod
    def vs_benchmark(ad_unit_id: int, ad_format: str, days: int = 7) -> dict:
        actual    = CTRAnalyzer.current(ad_unit_id, days)
        benchmark = CTRAnalyzer.benchmark(ad_format)
        diff      = actual - benchmark
        return {
            "actual": actual, "benchmark": benchmark,
            "diff": diff, "above_benchmark": diff > 0,
            "pct_diff": ((diff / benchmark * 100).quantize(Decimal("0.01")) if benchmark else Decimal("0")),
        }

    @staticmethod
    def top_performers(tenant=None, days: int = 7, limit: int = 10) -> list:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        qs = AdPerformanceDaily.objects.filter(date__gte=cutoff, impressions__gt=0)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("ad_unit_id", "ad_unit__name")
              .annotate(avg_ctr=Avg("ctr"))
              .order_by("-avg_ctr")[:limit]
        )

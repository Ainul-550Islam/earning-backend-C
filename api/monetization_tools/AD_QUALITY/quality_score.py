"""AD_QUALITY/quality_score.py — Composite ad quality score."""
from decimal import Decimal
from django.db.models import Avg


class AdQualityScorer:
    """Computes a composite quality score (0–100) for ad units."""

    @classmethod
    def score(cls, ad_unit_id: int, days: int = 7) -> dict:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        agg    = AdPerformanceDaily.objects.filter(
            ad_unit_id=ad_unit_id, date__gte=cutoff
        ).aggregate(ecpm=Avg("ecpm"), fill=Avg("fill_rate"), ctr=Avg("ctr"))

        ecpm_score = min(100, float(agg["ecpm"] or 0) * 10)
        fill_score = float(agg["fill"] or 0)
        ctr_score  = min(100, float(agg["ctr"] or 0) * 20)
        composite  = (ecpm_score * 0.5 + fill_score * 0.3 + ctr_score * 0.2)

        return {
            "ad_unit_id":  ad_unit_id,
            "ecpm_score":  round(ecpm_score, 1),
            "fill_score":  round(fill_score, 1),
            "ctr_score":   round(ctr_score, 1),
            "composite":   round(composite, 1),
            "grade":       "A" if composite >= 80 else "B" if composite >= 60 else "C" if composite >= 40 else "D",
        }

    @classmethod
    def rank_units(cls, tenant=None, days: int = 7) -> list:
        from ..models import AdUnit
        qs = AdUnit.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        scored = [cls.score(u["id"], days) for u in qs.values("id")[:50]]
        return sorted(scored, key=lambda x: x["composite"], reverse=True)

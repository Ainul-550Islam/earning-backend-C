# api/publisher_tools/mediation_management/hybrid_mediation.py
"""Hybrid Mediation — Combining waterfall and header bidding."""
from decimal import Decimal
from typing import List, Dict
from django.utils import timezone


def get_hybrid_ad_response(group, request_context: Dict) -> Dict:
    """
    Hybrid mediation flow:
    1. Header bidding (parallel bids)
    2. Compare with waterfall floor prices
    3. Return highest bid
    """
    hb_bids = _run_header_bidding(group, request_context)
    waterfall_floor = _get_waterfall_floor(group, request_context)
    best_bid = max(hb_bids, key=lambda b: b.get("cpm", 0), default=None)
    if best_bid and best_bid.get("cpm", 0) >= float(waterfall_floor):
        return {"winner": "header_bidding", "cpm": best_bid["cpm"], "bidder": best_bid["bidder"], "ad_markup": best_bid.get("markup", "")}
    return {"winner": "waterfall", "floor": float(waterfall_floor)}


def _run_header_bidding(group, context: Dict) -> List[Dict]:
    from api.publisher_tools.models import HeaderBiddingConfig
    configs = HeaderBiddingConfig.objects.filter(mediation_group=group, status="active")
    bids = []
    for config in configs:
        # Simulated bid — production-এ real RTB call করো
        bids.append({"bidder": config.bidder_name, "cpm": float(config.avg_bid_cpm), "timeout_ms": config.timeout_ms})
    return [b for b in bids if b["cpm"] > 0]


def _get_waterfall_floor(group, context: Dict) -> Decimal:
    from api.publisher_tools.models import WaterfallItem
    first_item = group.waterfall_items.filter(status="active").order_by("priority").first()
    return first_item.floor_ecpm if first_item else Decimal("0")


def compare_strategies(group, days: int = 30) -> Dict:
    """Waterfall vs header bidding revenue compare করে।"""
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Sum
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    hb_rev = float(
        PublisherEarning.objects.filter(
            ad_unit=group.ad_unit, date__gte=start, earning_type="header_bidding",
        ).aggregate(r=Sum("publisher_revenue")).get("r") or 0
    )
    wf_rev = float(
        PublisherEarning.objects.filter(
            ad_unit=group.ad_unit, date__gte=start, earning_type="programmatic",
        ).aggregate(r=Sum("publisher_revenue")).get("r") or 0
    )
    total = hb_rev + wf_rev
    return {
        "header_bidding_revenue": hb_rev,
        "waterfall_revenue": wf_rev,
        "total_revenue": total,
        "hb_revenue_share": round(hb_rev / total * 100, 2) if total > 0 else 0,
        "recommendation": "Increase header bidding budget" if hb_rev > wf_rev else "Optimize waterfall first",
    }

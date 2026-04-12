# api/publisher_tools/mediation_management/bidding_optimizer.py
"""Bidding Optimizer — Bid optimization algorithms."""
from decimal import Decimal
from typing import List, Dict
from django.utils import timezone
from datetime import timedelta


def optimize_bid_timeout(group) -> Dict:
    """Optimal bid timeout calculate করে।"""
    from api.publisher_tools.models import WaterfallItem
    items = group.waterfall_items.filter(status="active")
    if not items.exists():
        return {"recommended_timeout_ms": 1000}
    avg_latency = sum(i.avg_latency_ms for i in items) / items.count()
    recommended = min(3000, max(500, int(avg_latency * 1.5)))
    return {
        "avg_network_latency_ms": avg_latency,
        "recommended_timeout_ms": recommended,
        "current_timeout_ms":    getattr(group, "timeout_ms", 3000),
    }


def analyze_lost_bids(group, days: int = 30) -> Dict:
    """Lost bids analyze করে revenue opportunity identify করে।"""
    from api.publisher_tools.models import WaterfallItem
    items = group.waterfall_items.filter(status="active")
    lost_revenue = Decimal("0")
    insights = []
    for item in items:
        if float(item.fill_rate) < 50 and item.total_ad_requests > 100:
            est_lost = item.total_ad_requests * (1 - float(item.fill_rate)/100) * float(item.avg_ecpm) / 1000
            lost_revenue += Decimal(str(est_lost))
            insights.append({
                "network": item.network.name,
                "fill_rate": float(item.fill_rate),
                "estimated_lost_revenue_usd": round(est_lost, 4),
                "recommendation": f"Add {item.network.name} as backup network or lower floor price",
            })
    return {"total_estimated_lost_revenue": float(lost_revenue), "insights": insights}


def get_bid_density_report(group) -> Dict:
    """Bid density — কতগুলো bids আসছে vs fill হচ্ছে।"""
    from api.publisher_tools.models import WaterfallItem
    items = group.waterfall_items.filter(status="active")
    return {
        "total_requests":    group.total_ad_requests,
        "total_impressions": group.total_impressions,
        "overall_fill_rate": float(group.fill_rate),
        "networks": [
            {"name": i.network.name, "requests": i.total_ad_requests, "impressions": i.total_impressions, "fill": float(i.fill_rate)}
            for i in items.order_by("priority")
        ],
    }

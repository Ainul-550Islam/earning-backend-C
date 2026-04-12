# api/publisher_tools/optimization_tools/latency_optimizer.py
"""Latency Optimizer — Reduce ad loading latency."""
from typing import Dict, List


LATENCY_THRESHOLDS = {
    "excellent": 300,
    "good":      600,
    "acceptable":1000,
    "poor":      1500,
    "critical":  3000,
}


def classify_latency(latency_ms: int) -> str:
    for level, threshold in LATENCY_THRESHOLDS.items():
        if latency_ms <= threshold:
            return level
    return "critical"


def get_latency_recommendations(group) -> List[Dict]:
    """Mediation group latency recommendations।"""
    from api.publisher_tools.models import WaterfallItem
    items = WaterfallItem.objects.filter(mediation_group=group, status="active").order_by("priority")
    recommendations = []
    for item in items:
        if item.avg_latency_ms > LATENCY_THRESHOLDS["poor"]:
            recommendations.append({
                "network": item.network.name, "latency_ms": item.avg_latency_ms,
                "classification": classify_latency(item.avg_latency_ms),
                "action": "Move to lower priority in waterfall or remove",
                "potential_revenue_impact": f"High latency reduces fill rate by ~{min(50, item.avg_latency_ms // 100)}%",
            })
        elif item.priority == 1 and item.avg_latency_ms > LATENCY_THRESHOLDS["acceptable"]:
            recommendations.append({
                "network": item.network.name, "latency_ms": item.avg_latency_ms,
                "classification": classify_latency(item.avg_latency_ms),
                "action": "Move a faster network to priority #1",
            })
    return recommendations


def estimate_revenue_impact_of_latency(latency_ms: int, base_ecpm: float) -> Dict:
    fill_loss_pct = min(60, latency_ms / 100 * 1.5)
    lost_ecpm = base_ecpm * fill_loss_pct / 100
    return {
        "latency_ms": latency_ms,
        "estimated_fill_loss_pct": round(fill_loss_pct, 2),
        "estimated_ecpm_loss": round(lost_ecpm, 4),
        "recommendation": "Reduce latency below 600ms for optimal fill rates.",
    }

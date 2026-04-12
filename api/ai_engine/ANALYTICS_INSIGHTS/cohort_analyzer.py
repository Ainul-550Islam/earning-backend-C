"""
api/ai_engine/ANALYTICS_INSIGHTS/cohort_analyzer.py
====================================================
Cohort Analyzer — user retention, LTV, behavior by cohort।
Acquisition cohorts, behavior cohorts, RFM cohorts।
"""
import logging
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class CohortAnalyzer:
    """User cohort analysis engine।"""

    def retention_analysis(self, cohorts: Dict[str, List[float]]) -> dict:
        """Retention curve by cohort।"""
        results = {}
        for cohort_name, retention_rates in cohorts.items():
            if not retention_rates: continue
            day_1   = retention_rates[0] if len(retention_rates) > 0 else 0
            day_7   = retention_rates[6] if len(retention_rates) > 6 else 0
            day_30  = retention_rates[29] if len(retention_rates) > 29 else 0
            drop_d1_d7 = round((day_1 - day_7) / max(day_1, 0.001), 4) if day_1 > 0 else 0
            results[cohort_name] = {
                "day_1_retention":  round(day_1, 4),
                "day_7_retention":  round(day_7, 4),
                "day_30_retention": round(day_30, 4),
                "d1_to_d7_drop":    round(drop_d1_d7, 4),
                "health":           "excellent" if day_7 > 0.40 else "good" if day_7 > 0.20 else "poor",
            }
        best  = max(results, key=lambda k: results[k]["day_7_retention"]) if results else None
        worst = min(results, key=lambda k: results[k]["day_7_retention"]) if results else None
        return {"cohorts": results, "best_cohort": best, "worst_cohort": worst}

    def ltv_by_cohort(self, cohorts: Dict[str, Dict]) -> dict:
        results = {}
        for cohort, data in cohorts.items():
            arpu       = float(data.get("avg_revenue_per_user", 0))
            churn_rate = float(data.get("churn_rate", 0.05))
            ltv        = round(arpu / max(churn_rate, 0.001), 2)
            results[cohort] = {
                "arpu":       arpu,
                "churn_rate": churn_rate,
                "ltv":        ltv,
                "ltv_tier":   "high" if ltv >= 2000 else "medium" if ltv >= 500 else "low",
            }
        if results:
            best_cohort = max(results, key=lambda k: results[k]["ltv"])
            return {"cohorts": results, "best_ltv_cohort": best_cohort,
                    "avg_ltv": round(sum(v["ltv"] for v in results.values()) / len(results), 2)}
        return {"cohorts": {}}

    def behavior_segmentation(self, users: List[Dict]) -> dict:
        segments: Dict[str, List] = {"champions": [], "loyal": [], "at_risk": [], "lost": [], "new": []}
        for user in users:
            recency   = int(user.get("days_since_last_activity", 999))
            frequency = int(user.get("activity_count", 0))
            account_age = int(user.get("account_age_days", 0))
            uid = str(user.get("user_id", ""))
            if recency <= 7 and frequency >= 10:   segments["champions"].append(uid)
            elif recency <= 14 and frequency >= 3:  segments["loyal"].append(uid)
            elif account_age <= 14:                 segments["new"].append(uid)
            elif recency > 60:                      segments["lost"].append(uid)
            else:                                   segments["at_risk"].append(uid)
        return {
            "segments":     {k: {"users": v, "count": len(v)} for k, v in segments.items()},
            "total_users":  len(users),
            "distribution": {k: round(len(v)/max(len(users),1), 4) for k, v in segments.items()},
        }

    def weekly_cohort_matrix(self, weekly_data: Dict[str, List[float]]) -> dict:
        """Weekly retention matrix।"""
        matrix = {}
        for week, retention in weekly_data.items():
            matrix[week] = {f"week_{i}": round(r, 4) for i, r in enumerate(retention)}
        return {"matrix": matrix, "weeks": len(matrix)}

    def activation_funnel(self, cohort: List[Dict]) -> dict:
        """Activation funnel analysis per cohort।"""
        total     = len(cohort)
        activated = sum(1 for u in cohort if u.get("completed_first_offer"))
        verified  = sum(1 for u in cohort if u.get("email_verified"))
        deposited = sum(1 for u in cohort if u.get("made_withdrawal"))
        return {
            "total":            total,
            "verified":         verified,
            "activated":        activated,
            "withdrew":         deposited,
            "activation_rate":  round(activated / max(total, 1), 4),
            "verification_rate": round(verified / max(total, 1), 4),
            "withdrawal_rate":  round(deposited / max(total, 1), 4),
        }

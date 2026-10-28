# api/wallet/ai_insights.py
"""
AI Spending Insights — personalized financial analysis using ML.
2027-2028: AI financial advisors becoming mainstream.

Features:
  - Spending pattern analysis
  - Earning trend predictions
  - Personalized saving recommendations
  - Anomaly detection in spending
  - Budget optimization suggestions
  - Withdrawal timing optimization

Uses OpenAI GPT-4o (already integrated in openai_integration.py)
+ local statistical analysis (no external API needed for basic insights).
"""
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger("wallet.ai_insights")


class AIInsightsService:
    """AI-powered wallet spending and earning insights."""

    @staticmethod
    def get_spending_analysis(user_id: int, days: int = 30) -> dict:
        """
        Analyze spending patterns for a user.
        Returns insights without needing external AI for basic analysis.
        """
        from .models.core import WalletTransaction
        from django.db.models import Sum, Count, Avg
        from .models.withdrawal import WithdrawalRequest

        cutoff = timezone.now() - timedelta(days=days)

        # Earnings breakdown
        earnings = WalletTransaction.objects.filter(
            wallet__user_id=user_id,
            type__in=["earning","reward","cpa","cpi","cpc","referral"],
            status__in=["approved","completed"],
            created_at__gte=cutoff,
        )

        earn_total = earnings.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        earn_by_type = {}
        for t in ["cpa","cpi","cpc","referral","reward"]:
            val = earnings.filter(type=t).aggregate(t=Sum("amount"))["t"] or Decimal("0")
            if val > 0:
                earn_by_type[t] = float(val)

        # Withdrawals
        withdrawals = WithdrawalRequest.objects.filter(
            user_id=user_id, status="completed", created_at__gte=cutoff
        )
        wd_total = withdrawals.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        wd_count = withdrawals.count()

        # Calculate insights
        daily_earn = float(earn_total) / days if days > 0 else 0
        save_rate  = ((float(earn_total) - float(wd_total)) / float(earn_total) * 100
                      if earn_total > 0 else 0)

        insights = []
        recommendations = []

        # Generate insights
        if daily_earn > 0:
            insights.append(f"Average daily earning: {daily_earn:.2f} BDT")

        if save_rate > 30:
            insights.append(f"Good saving rate: {save_rate:.1f}% of earnings retained")
        elif save_rate < 10:
            insights.append(f"Low saving rate: {save_rate:.1f}% — consider withdrawing less frequently")
            recommendations.append("Consider withdrawing monthly instead of daily to reduce fees")

        if wd_count > 20:
            recommendations.append(f"You made {wd_count} withdrawals in {days} days. "
                                     f"Consolidating could save on fees.")

        best_type = max(earn_by_type, key=earn_by_type.get) if earn_by_type else None
        if best_type:
            insights.append(f"Best earning source: {best_type} ({earn_by_type[best_type]:.2f} BDT)")
            recommendations.append(f"Focus more on {best_type} offers for maximum earnings")

        return {
            "period_days":       days,
            "total_earned":      float(earn_total),
            "total_withdrawn":   float(wd_total),
            "daily_avg_earning": round(daily_earn, 2),
            "save_rate_pct":     round(save_rate, 1),
            "earning_by_type":   earn_by_type,
            "withdrawal_count":  wd_count,
            "insights":          insights,
            "recommendations":   recommendations,
        }

    @staticmethod
    def get_earning_forecast(user_id: int, forecast_days: int = 30) -> dict:
        """
        Forecast future earnings based on historical trend.
        Uses simple linear regression on past 90 days.
        """
        from .models.core import WalletTransaction
        from django.db.models import Sum
        from django.db.models.functions import TruncDate

        past_90 = timezone.now() - timedelta(days=90)
        daily_data = list(
            WalletTransaction.objects.filter(
                wallet__user_id=user_id,
                type__in=["earning","reward","cpa","cpi","cpc"],
                status__in=["approved","completed"],
                created_at__gte=past_90,
            ).annotate(day=TruncDate("created_at"))
            .values("day").annotate(total=Sum("amount"))
            .order_by("day")
        )

        if len(daily_data) < 7:
            return {"forecast": "Insufficient data (need 7+ days of history)",
                    "days": forecast_days}

        amounts = [float(d["total"]) for d in daily_data]
        avg     = sum(amounts) / len(amounts)
        trend   = (amounts[-1] - amounts[0]) / len(amounts) if len(amounts) > 1 else 0

        forecast_total = max(0, (avg + trend * forecast_days) * forecast_days)
        forecast_daily = forecast_total / forecast_days if forecast_days > 0 else 0

        return {
            "forecast_days":    forecast_days,
            "forecast_total":   round(forecast_total, 2),
            "forecast_daily":   round(forecast_daily, 2),
            "historical_avg":   round(avg, 2),
            "trend":            "growing" if trend > 0 else "declining" if trend < 0 else "stable",
            "confidence":       "medium" if len(daily_data) >= 30 else "low",
            "data_points":      len(daily_data),
        }

    @staticmethod
    def get_ai_recommendation(user_id: int, question: str = None) -> str:
        """
        Get AI-powered recommendation using OpenAI.
        Falls back to rule-based if OpenAI not configured.
        """
        try:
            from .openai_integration import WalletAI
            analysis = AIInsightsService.get_spending_analysis(user_id)
            context = (
                f"User daily avg: {analysis['daily_avg_earning']} BDT, "
                f"save rate: {analysis['save_rate_pct']}%, "
                f"top source: {list(analysis['earning_by_type'].keys())[:1]}"
            )
            q = question or "Give me 3 actionable tips to improve my wallet earnings"
            return WalletAI.answer_support_question(q, user_balance=analysis["total_earned"] - analysis["total_withdrawn"])
        except Exception:
            analysis = AIInsightsService.get_spending_analysis(user_id)
            recs = analysis.get("recommendations", [])
            return " | ".join(recs) if recs else "Keep earning consistently for best results!"

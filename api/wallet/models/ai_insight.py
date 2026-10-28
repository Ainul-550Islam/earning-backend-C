# api/wallet/models/ai_insight.py
"""
AIInsight — persisted result of a single AIInsightsService run.

Stores the JSON payload returned by:
  • AIInsightsService.get_spending_analysis()
  • AIInsightsService.get_earning_forecast()
  • AIInsightsService.get_ai_recommendation()

One row per (wallet, insight_type, period_days) combination; refreshed
on every new computation so historical snapshots are NOT kept (use the
WalletTransaction ledger for history).  Set ``keep_history=True`` in the
factory if you want an append-only audit trail instead.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AIInsightType(models.TextChoices):
    SPENDING    = "spending",    "Spending Analysis"
    FORECAST    = "forecast",   "Earning Forecast"
    RECOMMEND   = "recommend",  "AI Recommendation"


class AIInsight(models.Model):
    """
    Cached / persisted output from AIInsightsService.

    Fields
    ──────
    wallet          FK to the wallet this insight belongs to.
    insight_type    One of AIInsightType (spending / forecast / recommend).
    period_days     The ``days`` parameter used when the insight was computed.
    payload         Full JSON output of the service method.
    text_summary    Plain-text summary (for recommendation type).
    computed_at     When the insight was last refreshed.
    is_stale        Set to True when the underlying data changes significantly;
                    cleared on next compute run.
    """

    wallet = models.ForeignKey(
        "wallet.Wallet",
        on_delete=models.CASCADE,
        related_name="ai_insights",
        db_index=True,
    )
    insight_type = models.CharField(
        max_length=12,
        choices=AIInsightType.choices,
        db_index=True,
    )
    period_days = models.PositiveSmallIntegerField(
        default=30,
        help_text="Window (in days) used when computing this insight.",
    )
    payload = models.JSONField(
        default=dict,
        help_text="Full JSON payload from AIInsightsService.",
    )
    text_summary = models.TextField(
        blank=True,
        help_text="Human-readable summary (populated for recommend type).",
    )
    computed_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_stale = models.BooleanField(
        default=False,
        help_text="True when the insight needs refreshing.",
    )

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_ai_insight"
        # One live record per (wallet, type, period) — upsert pattern
        unique_together = [("wallet", "insight_type", "period_days")]
        ordering = ["-computed_at"]
        indexes = [
            models.Index(fields=["wallet", "insight_type"]),
        ]

    def __str__(self):
        return (
            f"AIInsight [{self.insight_type}] wallet={self.wallet_id} "
            f"period={self.period_days}d @ {self.computed_at:%Y-%m-%d %H:%M}"
        )

    # ── Convenience factory ───────────────────────────────────────────

    @classmethod
    def refresh(cls, wallet, insight_type: str, period_days: int = 30) -> "AIInsight":
        """
        Compute a fresh insight and upsert the DB row.

        Usage:
            insight = AIInsight.refresh(wallet, AIInsightType.SPENDING, days=30)
        """
        from ..ai_insights import AIInsightsService

        user_id = wallet.user_id

        if insight_type == AIInsightType.SPENDING:
            payload      = AIInsightsService.get_spending_analysis(user_id, period_days)
            text_summary = " | ".join(payload.get("recommendations", []))

        elif insight_type == AIInsightType.FORECAST:
            payload      = AIInsightsService.get_earning_forecast(user_id, period_days)
            text_summary = (
                f"Forecast: {payload.get('forecast_total', 0)} BDT "
                f"over {period_days} days ({payload.get('trend', 'unknown')} trend)"
            )

        elif insight_type == AIInsightType.RECOMMEND:
            text_summary = AIInsightsService.get_ai_recommendation(user_id)
            payload      = {"recommendation": text_summary}

        else:
            raise ValueError(f"Unknown insight_type: {insight_type!r}")

        obj, _ = cls.objects.update_or_create(
            wallet=wallet,
            insight_type=insight_type,
            period_days=period_days,
            defaults={
                "payload":      payload,
                "text_summary": text_summary,
                "computed_at":  timezone.now(),
                "is_stale":     False,
            },
        )
        return obj

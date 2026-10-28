# api/wallet/survey_router.py
"""
SurveyRouter — Route users to the highest-paying available survey.

CPALead serves surveys via multiple providers (Lucid, Toluna, etc.).
This router:
  1. Checks user profile match (age, gender, country)
  2. Ranks available surveys by eCPM
  3. Tracks survey starts/completions
  4. Credits wallet on verified completion
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger("wallet.survey_router")


# ════════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════════

class SurveyProvider(models.Model):
    """External survey provider (Lucid, Toluna, Dynata, etc.)."""

    name         = models.CharField(max_length=80, unique=True)
    api_endpoint = models.URLField()
    api_key      = models.CharField(max_length=256, blank=True)
    is_active    = models.BooleanField(default=True, db_index=True)
    payout_rate  = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.00"),
        help_text="Base payout per completion (BDT)",
    )
    priority     = models.PositiveSmallIntegerField(
        default=50, help_text="Higher = shown first (0-100)"
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_surveyprovider"
        ordering  = ["-priority", "name"]

    def __str__(self) -> str:
        return f"{self.name} | payout={self.payout_rate}"


class Survey(models.Model):
    """Individual survey available to users."""

    STATUS_ACTIVE   = "active"
    STATUS_PAUSED   = "paused"
    STATUS_FULL     = "full"       # Quota reached
    STATUS_EXPIRED  = "expired"
    STATUS_CHOICES  = [
        (STATUS_ACTIVE,  "Active"),
        (STATUS_PAUSED,  "Paused"),
        (STATUS_FULL,    "Full"),
        (STATUS_EXPIRED, "Expired"),
    ]

    survey_id       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    provider        = models.ForeignKey(
        SurveyProvider, on_delete=models.CASCADE, related_name="surveys",
    )
    external_id     = models.CharField(
        max_length=128, db_index=True,
        help_text="Provider's own survey ID",
    )
    title           = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    survey_url      = models.URLField()

    # ── Payout ────────────────────────────────────────────────────
    payout_amount   = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text="User payout on completion (BDT)",
    )
    currency        = models.CharField(max_length=10, default="BDT")

    # ── Targeting ────────────────────────────────────────────────
    target_country  = models.CharField(max_length=5, blank=True, db_index=True)
    min_age         = models.PositiveSmallIntegerField(null=True, blank=True)
    max_age         = models.PositiveSmallIntegerField(null=True, blank=True)
    target_gender   = models.CharField(
        max_length=1, blank=True,
        choices=[("M", "Male"), ("F", "Female"), ("", "All")],
    )

    # ── Quota & timing ───────────────────────────────────────────
    quota           = models.PositiveIntegerField(
        default=0, help_text="0 = unlimited"
    )
    completions     = models.PositiveIntegerField(default=0)
    estimated_mins  = models.PositiveSmallIntegerField(
        default=5, help_text="Estimated completion time in minutes"
    )

    # ── Status ────────────────────────────────────────────────────
    status     = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_survey"
        ordering  = ["-payout_amount"]
        indexes   = [
            models.Index(fields=["status", "target_country"]),
            models.Index(fields=["provider", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} | {self.payout_amount} {self.currency} | {self.status}"

    @property
    def is_available(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.quota and self.completions >= self.quota:
            return False
        return True

    @property
    def ecpm(self) -> Decimal:
        """Effective CPM — higher is better for routing priority."""
        if not self.estimated_mins:
            return self.payout_amount
        return (self.payout_amount / Decimal(str(self.estimated_mins))) * 1000


class SurveyAttempt(models.Model):
    """Tracks a user's attempt at a survey (start → complete/disqualify)."""

    RESULT_STARTED       = "started"
    RESULT_COMPLETED     = "completed"
    RESULT_DISQUALIFIED  = "disqualified"
    RESULT_QUOTA_FULL    = "quota_full"
    RESULT_ABANDONED     = "abandoned"
    RESULT_CHOICES       = [
        (RESULT_STARTED,      "Started"),
        (RESULT_COMPLETED,    "Completed"),
        (RESULT_DISQUALIFIED, "Disqualified"),
        (RESULT_QUOTA_FULL,   "Quota Full"),
        (RESULT_ABANDONED,    "Abandoned"),
    ]

    attempt_id  = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    survey      = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="attempts")
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="survey_attempts"
    )
    wallet      = models.ForeignKey(
        "wallet.Wallet", on_delete=models.SET_NULL, null=True, related_name="survey_attempts"
    )
    result      = models.CharField(
        max_length=16, choices=RESULT_CHOICES, default=RESULT_STARTED, db_index=True,
    )
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    started_at  = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    payout_txn_id = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_surveyattempt"
        unique_together = [("survey", "user")]  # 1 attempt per user per survey
        indexes   = [
            models.Index(fields=["user", "result"]),
            models.Index(fields=["survey", "result"]),
        ]


# ════════════════════════════════════════════════════════════════
# SERVICE
# ════════════════════════════════════════════════════════════════

class SurveyRouter:
    """
    Route users to best-matching surveys and handle completion payouts.
    Uses eCPM ranking + targeting filters.
    """

    @staticmethod
    def get_surveys_for_user(
        user,
        wallet,
        country_code: str = "",
        limit: int = 10,
    ) -> list:
        """
        Return ranked list of available surveys for this user.
        Ranked by eCPM descending (highest payout-per-minute first).
        Filters out: completed, disqualified, out-of-quota, expired.
        """
        # Exclude already-attempted surveys
        attempted_ids = SurveyAttempt.objects.filter(
            user=user,
            result__in=[
                SurveyAttempt.RESULT_COMPLETED,
                SurveyAttempt.RESULT_DISQUALIFIED,
            ],
        ).values_list("survey_id", flat=True)

        qs = Survey.objects.filter(
            status=Survey.STATUS_ACTIVE,
        ).exclude(
            id__in=attempted_ids,
        ).select_related("provider")

        if country_code:
            qs = qs.filter(
                models.Q(target_country="") | models.Q(target_country=country_code.upper())
            )

        # Sort by eCPM in Python (avoids complex DB annotation)
        surveys = sorted(
            [s for s in qs if s.is_available],
            key=lambda s: s.ecpm,
            reverse=True,
        )[:limit]

        return [
            {
                "survey_id":       str(s.survey_id),
                "provider":        s.provider.name,
                "title":           s.title,
                "description":     s.description,
                "payout_amount":   str(s.payout_amount),
                "currency":        s.currency,
                "estimated_mins":  s.estimated_mins,
                "ecpm":            str(s.ecpm),
                "survey_url":      f"{s.survey_url}?uid={user.pk}&sid={s.survey_id}",
            }
            for s in surveys
        ]

    @staticmethod
    def start_attempt(survey_id: str, user, wallet, ip_address: str = "") -> dict:
        """Record that user started a survey. Returns attempt_id."""
        try:
            survey = Survey.objects.get(survey_id=survey_id, status=Survey.STATUS_ACTIVE)
        except Survey.DoesNotExist:
            raise ValueError(f"Survey {survey_id} not found or inactive")

        attempt, created = SurveyAttempt.objects.get_or_create(
            survey=survey,
            user=user,
            defaults={
                "wallet":     wallet,
                "ip_address": ip_address or None,
                "result":     SurveyAttempt.RESULT_STARTED,
            },
        )
        if not created and attempt.result == SurveyAttempt.RESULT_COMPLETED:
            raise ValueError("Survey already completed by this user")

        return {"attempt_id": str(attempt.attempt_id)}

    @classmethod
    def complete(
        cls,
        attempt_id: str,
        result: str = SurveyAttempt.RESULT_COMPLETED,
        ip_address: str = "",
    ) -> dict:
        """
        Record survey completion/disqualification.
        Credits wallet on COMPLETED result.
        Returns {"credited": bool, "amount": str, "txn_id": str}
        """
        try:
            attempt = SurveyAttempt.objects.select_related(
                "survey", "wallet"
            ).get(attempt_id=attempt_id)
        except SurveyAttempt.DoesNotExist:
            raise ValueError(f"Attempt {attempt_id} not found")

        if attempt.result == SurveyAttempt.RESULT_COMPLETED:
            raise ValueError("Attempt already completed")

        attempt.result       = result
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["result", "completed_at"])

        txn_id = ""
        credited = result == SurveyAttempt.RESULT_COMPLETED

        if credited and attempt.wallet:
            try:
                from .services.core.WalletService import WalletService
                from .choices import TransactionType
                txn = WalletService.credit(
                    wallet=attempt.wallet,
                    amount=attempt.survey.payout_amount,
                    txn_type=TransactionType.SURVEY,
                    description=f"Survey completed: {attempt.survey.title}",
                    reference_id=str(attempt.attempt_id),
                    reference_type="survey",
                    ip_address=ip_address,
                    skip_multipliers=False,  # GEO + tier apply to surveys
                )
                txn_id = str(txn.txn_id)
                attempt.payout_txn_id = txn_id
                attempt.save(update_fields=["payout_txn_id"])

                # Update survey completion counter
                Survey.objects.filter(pk=attempt.survey_id).update(
                    completions=models.F("completions") + 1
                )
                logger.info(
                    f"Survey completed: attempt={attempt_id} "
                    f"user={attempt.user_id} payout={attempt.survey.payout_amount}"
                )
            except Exception as e:
                logger.error(f"Survey credit failed attempt={attempt_id}: {e}")
                credited = False

        return {
            "credited": credited,
            "amount":   str(attempt.survey.payout_amount) if credited else "0",
            "txn_id":   txn_id,
            "result":   result,
        }

    @staticmethod
    def provider_stats() -> list:
        """Aggregate stats per provider for admin dashboard."""
        from django.db.models import Sum, Count
        providers = SurveyProvider.objects.annotate(
            survey_count=Count("surveys"),
            total_completions=Count(
                "surveys__attempts",
                filter=models.Q(surveys__attempts__result=SurveyAttempt.RESULT_COMPLETED),
            ),
        ).values("name", "is_active", "survey_count", "total_completions", "payout_rate")
        return list(providers)

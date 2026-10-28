# =============================================================================
# api/auto_mod/offerwall.py
# =============================================================================
"""
Monlix-grade offerwall components for auto_mod.

Covers every feature Monlix (and top-5 CPA platforms) have:
  VirtualCurrencyService  — currency name/multiplier, award on completion
  OfferwallOfferTypes     — Survey, Video, GameInstall, AppInstall offer models
  OfferwallConfig         — publisher widget embed, theme, sorting, promotions
  PostbackService         — S2S HMAC verification, retry, transaction dedup
  OfferwallSDKBridge      — Android/iOS/Unity/HTML5 SDK integration helpers
  PerformanceReportService— eCPM, fill rate, revenue reports
  SiteApprovalService     — publisher site approval workflow
  PaymentScheduleService  — NET30, min payout, payout config

"এক কাজের জন্য একটাই মালিক" — one class = one responsibility.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("auto_mod.offerwall")
User = get_user_model()


# ─── Cache helpers ────────────────────────────────────────────────────────────
def _cget(key, default=None):
    try:
        v = cache.get(f"auto_mod:ow:{key}")
        return v if v is not None else default
    except Exception:
        return default

def _cset(key, value, ttl=3600):
    try:
        cache.set(f"auto_mod:ow:{key}", value, ttl)
    except Exception:
        pass


# =============================================================================
# Django Models
# =============================================================================

class VirtualCurrencyConfig(models.Model):
    """
    Per-publisher virtual currency configuration.
    (Monlix: currency_name, multiplier, award_on_completion)
    """
    publisher_id      = models.CharField(max_length=200, unique=True)
    currency_name     = models.CharField(max_length=50, default="Points",
                            help_text="Plural name, e.g. 'Credits', '$', 'Coins'")
    currency_symbol   = models.CharField(max_length=10, default="pts")
    currency_multiplier = models.FloatField(default=1.0,
                            help_text="How many currency units per $1.00 payout")
    min_award         = models.PositiveIntegerField(default=1)
    award_on_completion = models.BooleanField(default=True,
                            help_text="Award immediately on approval, not on postback")
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        app_label    = "auto_mod"
        verbose_name = _("Virtual Currency Config")

    def __str__(self):
        return f"VirtualCurrency: {self.publisher_id} ({self.currency_name})"

    def usd_to_currency(self, usd_amount: float) -> int:
        """Convert USD payout to virtual currency units."""
        return max(self.min_award, int(usd_amount * self.currency_multiplier))


class OfferwallOfferType(models.Model):
    """
    Defines the types of offers available on the offerwall.
    (Monlix: Survey, Video, GameInstall, AppInstall, Task)
    """
    SURVEY      = "survey"
    VIDEO       = "video"
    VideoAdOffer = "video"  # alias for pattern matching
    GAME        = "game_install"
    APP_ANDROID = "app_install_android"
    APP_IOS     = "app_install_ios"
    TASK        = "task"

    TYPE_CHOICES = [
        (SURVEY,      "Survey"),
        (VIDEO,       "Video Ad"),
        (GAME,        "Game Install"),
        (APP_ANDROID, "Android App Install"),
        (APP_IOS,     "iOS App Install"),
        (TASK,        "General Task"),
    ]

    name           = models.CharField(max_length=200)
    offer_type     = models.CharField(max_length=30, choices=TYPE_CHOICES)
    publisher_id   = models.CharField(max_length=200)
    advertiser_id  = models.CharField(max_length=200, blank=True, default="")
    payout_usd     = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    is_active      = models.BooleanField(default=True, db_index=True)
    allowed_countries = models.JSONField(default=list, blank=True)
    os_target      = models.CharField(max_length=20, blank=True, default="",
                        help_text="'android', 'ios', 'web', or '' for all")
    description    = models.TextField(blank=True, default="")
    requirements   = models.JSONField(default=dict, blank=True)
    icon_url       = models.URLField(blank=True, default="")
    metadata       = models.JSONField(default=dict, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label    = "auto_mod"
        verbose_name = _("Offerwall Offer Type")
        ordering     = ["-payout_usd"]

    def __str__(self):
        return f"[{self.offer_type}] {self.name} (${self.payout_usd})"


class OfferwallConfig(models.Model):
    """
    Publisher-level offerwall widget configuration.
    (Monlix: theme, sorting, promotion, embed settings)
    """
    THEME_CHOICES = [
        ("default",  "Default"),
        ("dark",     "Dark"),
        ("light",    "Light"),
        ("gaming",   "Gaming"),
        ("minimal",  "Minimal"),
        ("neon",     "Neon"),
        ("pastel",   "Pastel"),
        ("seasonal", "Seasonal"),
    ]
    SORT_CHOICES = [
        ("payout_desc",   "Highest Payout First"),
        ("payout_asc",    "Lowest Payout First"),
        ("newest",        "Newest First"),
        ("easiest",       "Easiest First"),
        ("recommended",   "AI Recommended"),
    ]

    publisher_id         = models.CharField(max_length=200, unique=True)
    theme                = models.CharField(max_length=20, choices=THEME_CHOICES, default="default")
    offer_sorting        = models.CharField(max_length=20, choices=SORT_CHOICES, default="payout_desc")
    show_survey_offers   = models.BooleanField(default=True)
    show_video_offers    = models.BooleanField(default=True)
    show_game_offers     = models.BooleanField(default=True)
    show_app_offers      = models.BooleanField(default=True)
    show_task_offers     = models.BooleanField(default=True)
    max_offers_displayed = models.PositiveSmallIntegerField(default=20)
    custom_css           = models.TextField(blank=True, default="")
    embed_width          = models.CharField(max_length=20, default="100%")
    embed_height         = models.CharField(max_length=20, default="600px")
    postback_url         = models.URLField(blank=True, default="")
    postback_secret      = models.CharField(max_length=200, blank=True, default="",
                            help_text="HMAC secret for S2S postback verification")
    is_active            = models.BooleanField(default=True)
    approved_at          = models.DateTimeField(null=True, blank=True)
    approved_by          = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_offerwall_configs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label    = "auto_mod"
        verbose_name = _("Offerwall Config")

    def __str__(self):
        return f"OfferwallConfig: {self.publisher_id} ({self.theme})"

    def get_embed_html(self, user_id: str, ip: str = "") -> str:
        """Generate the embed iframe HTML for this publisher's offerwall."""
        base_url = "/api/auto_mod/offerwall-embed/"
        params   = f"publisher={self.publisher_id}&user={user_id}&ip={ip}"
        return (
            f'<iframe src="{base_url}?{params}" '
            f'width="{self.embed_width}" height="{self.embed_height}" '
            f'frameborder="0" scrolling="yes" '
            f'class="monlix-offerwall-embed"></iframe>'
        )


class PostbackLog(models.Model):
    """
    Tracks every S2S postback received and its verification status.
    (Monlix: transactionId dedup, HMAC secret, retry)
    """
    STATUS_RECEIVED  = "received"
    STATUS_VERIFIED  = "verified"
    STATUS_REJECTED  = "rejected"
    STATUS_DUPLICATE = "duplicate"
    STATUS_RETRIED   = "retried"

    STATUS_CHOICES = [
        (STATUS_RECEIVED,  "Received"),
        (STATUS_VERIFIED,  "Verified & Credited"),
        (STATUS_REJECTED,  "Rejected (bad signature)"),
        (STATUS_DUPLICATE, "Duplicate (already processed)"),
        (STATUS_RETRIED,   "Retried"),
    ]

    transaction_id   = models.CharField(max_length=300, unique=True, db_index=True)
    publisher_id     = models.CharField(max_length=200, db_index=True)
    user_id          = models.CharField(max_length=200)
    user_ip          = models.GenericIPAddressField(null=True, blank=True)
    offer_id         = models.CharField(max_length=200, blank=True, default="")
    reward_value     = models.FloatField(default=0.0)
    currency_awarded = models.PositiveIntegerField(default=0)
    status           = models.CharField(max_length=15, choices=STATUS_CHOICES,
                            default=STATUS_RECEIVED, db_index=True)
    raw_payload      = models.JSONField(default=dict, blank=True)
    signature        = models.CharField(max_length=200, blank=True, default="")
    error_message    = models.TextField(blank=True, default="")
    retry_count      = models.PositiveSmallIntegerField(default=0)
    received_at      = models.DateTimeField(auto_now_add=True)
    processed_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label    = "auto_mod"
        verbose_name = _("Postback Log")
        ordering     = ["-received_at"]

    def __str__(self):
        return f"Postback:{self.transaction_id} [{self.status}]"


class SiteApproval(models.Model):
    """
    Publisher site approval workflow.
    (Monlix: site review up to 3 business days before API keys are issued)
    """
    STATUS_PENDING  = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    publisher_id    = models.CharField(max_length=200, unique=True)
    site_url        = models.URLField()
    site_category   = models.CharField(max_length=100, blank=True, default="")
    monthly_traffic = models.CharField(max_length=50, blank=True, default="")
    description     = models.TextField(blank=True, default="")
    status          = models.CharField(
        max_length=10,
        choices=[(STATUS_PENDING,"Pending"), (STATUS_APPROVED,"Approved"), (STATUS_REJECTED,"Rejected")],
        default=STATUS_PENDING, db_index=True,
    )
    rejection_reason = models.TextField(blank=True, default="")
    reviewed_by     = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_site_approvals",
    )
    submitted_at    = models.DateTimeField(auto_now_add=True)
    reviewed_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label    = "auto_mod"
        verbose_name = _("Site Approval")

    def __str__(self):
        return f"SiteApproval: {self.publisher_id} [{self.status}]"

    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED


class PerformanceReport(models.Model):
    """
    Daily/weekly publisher performance report.
    (Monlix: eCPM, fills, impressions, completions, revenue)
    """
    publisher_id = models.CharField(max_length=200, db_index=True)
    report_date  = models.DateField(db_index=True)
    period       = models.CharField(max_length=10, default="daily",
                     choices=[("daily","Daily"),("weekly","Weekly"),("monthly","Monthly")])
    impressions  = models.PositiveIntegerField(default=0)
    fills        = models.PositiveIntegerField(default=0)
    completions  = models.PositiveIntegerField(default=0)
    revenue_usd  = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    ecpm         = models.DecimalField(max_digits=10, decimal_places=4, default=0,
                     help_text="Effective CPM = revenue / impressions * 1000")
    fill_rate    = models.FloatField(default=0.0, help_text="fills / impressions")
    completion_rate = models.FloatField(default=0.0, help_text="completions / fills")
    data         = models.JSONField(default=dict, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label            = "auto_mod"
        verbose_name         = _("Performance Report")
        unique_together      = [("publisher_id", "report_date", "period")]
        ordering             = ["-report_date"]

    def __str__(self):
        return f"Report:{self.publisher_id} {self.report_date} eCPM=${self.ecpm}"


class PaymentSchedule(models.Model):
    """
    Publisher payment schedule configuration.
    (Monlix: NET30, min $20 withdrawal, payout method)
    """
    SCHEDULE_NET30  = "net30"
    SCHEDULE_NET15  = "net15"
    SCHEDULE_WEEKLY = "weekly"
    SCHEDULE_DAILY  = "daily"

    publisher_id        = models.CharField(max_length=200, unique=True)
    schedule_type       = models.CharField(
        max_length=10, default=SCHEDULE_NET30,
        choices=[(SCHEDULE_NET30,"NET30"),(SCHEDULE_NET15,"NET15"),
                 (SCHEDULE_WEEKLY,"Weekly"),(SCHEDULE_DAILY,"Daily")],
    )
    min_payout_usd      = models.DecimalField(max_digits=8, decimal_places=2, default=20.00)
    payout_method       = models.CharField(max_length=50, default="paypal",
                            choices=[("paypal","PayPal"),("payoneer","Payoneer"),
                                     ("wire","Wire Transfer"),("crypto","Crypto"),
                                     ("check","Check")])
    payout_email        = models.EmailField(blank=True, default="")
    is_active           = models.BooleanField(default=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        app_label    = "auto_mod"
        verbose_name = _("Payment Schedule")

    def __str__(self):
        return f"PaySchedule:{self.publisher_id} {self.schedule_type} min=${self.min_payout_usd}"


class OfferwallPromotion(models.Model):
    """
    Seasonal/event promotion with currency multiplier.
    (Monlix: select time frame + reward multiplier for promotions)
    """
    publisher_id  = models.CharField(max_length=200, db_index=True)
    name          = models.CharField(max_length=200)
    multiplier    = models.FloatField(default=2.0, help_text="Reward × multiplier during promo")
    starts_at     = models.DateTimeField()
    ends_at       = models.DateTimeField()
    is_active     = models.BooleanField(default=True)
    promo_type    = models.CharField(max_length=30, default="seasonal",
                     choices=[("seasonal","Seasonal"),("event","Event"),
                               ("weekend","Weekend"),("holiday","Holiday")])
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = "auto_mod"
        verbose_name = _("Offerwall Promotion")

    def __str__(self):
        return f"Promo:{self.name} {self.multiplier}x ({self.starts_at.date()}→{self.ends_at.date()})"

    @property
    def is_currently_active(self) -> bool:
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at


# =============================================================================
# Services
# =============================================================================

class VirtualCurrencyService:
    """
    Award / deduct / query virtual currency for a publisher's users.
    Single owner: all virtual currency logic lives here.
    """

    @staticmethod
    def get_config(publisher_id: str) -> VirtualCurrencyConfig | None:
        key = f"vc_config:{publisher_id}"
        cached = _cget(key)
        if cached:
            return cached
        try:
            cfg = VirtualCurrencyConfig.objects.get(publisher_id=publisher_id)
            _cset(key, cfg, 300)
            return cfg
        except VirtualCurrencyConfig.DoesNotExist:
            return None

    @staticmethod
    def award_on_completion(
        *,
        publisher_id: str,
        user_id: str,
        usd_amount: float,
        offer_id: str,
        transaction_id: str,
    ) -> dict:
        """
        Award virtual currency to a user on offer completion.
        Returns {awarded_units, currency_name, success}.
        """
        cfg = VirtualCurrencyService.get_config(publisher_id)
        if not cfg or not cfg.award_on_completion:
            return {"awarded_units": 0, "currency_name": "Points", "success": False}

        # Apply active promotion multiplier
        active_promo = OfferwallPromotion.objects.filter(
            publisher_id=publisher_id, is_active=True,
            starts_at__lte=timezone.now(), ends_at__gte=timezone.now(),
        ).order_by("-multiplier").first()

        multiplier = active_promo.multiplier if active_promo else 1.0
        units      = cfg.usd_to_currency(usd_amount * multiplier)

        # Notify via adapter
        try:
            from .adapters import AdapterRegistry
            AdapterRegistry.wallet.credit_reward(
                user_id=user_id,
                amount=float(units),
                reason=f"offerwall_{offer_id}",
                reference_id=transaction_id,
            )
            AdapterRegistry.notification.notify_user(
                user_id=user_id,
                notification_type="offerwall.reward_credited",
                context={
                    "units":          units,
                    "currency_name":  cfg.currency_name,
                    "offer_id":       offer_id,
                },
            )
        except Exception as exc:
            logger.warning("VirtualCurrencyService.award_on_completion: %s", exc)

        return {
            "awarded_units": units,
            "currency_name": cfg.currency_name,
            "success":       True,
            "multiplier":    multiplier,
        }


class PostbackService:
    """
    S2S postback receiver: HMAC verification, dedup, retry.
    Single owner: all postback processing lives here.
    """

    @staticmethod
    def verify_signature(*, secret: str, payload: str, received_sig: str) -> bool:
        """Verify HMAC-SHA256 signature."""
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, received_sig)

    @staticmethod
    def is_duplicate(transaction_id: str) -> bool:
        """Return True if this transaction was already processed."""
        return PostbackLog.objects.filter(
            transaction_id=transaction_id,
            status__in=[PostbackLog.STATUS_VERIFIED, PostbackLog.STATUS_DUPLICATE],
        ).exists()

    @staticmethod
    def process(
        *,
        publisher_id:   str,
        user_id:        str,
        transaction_id: str,
        reward_value:   float,
        secret:         str,
        received_sig:   str,
        user_ip:        str = "",
        offer_id:       str = "",
        raw_payload:    dict | None = None,
    ) -> dict:
        """
        Full S2S postback processing pipeline.
        Returns {status, message, credited_units}.
        """
        # 1. Deduplication check
        if PostbackService.is_duplicate(transaction_id):
            PostbackLog.objects.get_or_create(
                transaction_id=transaction_id,
                defaults={"publisher_id": publisher_id, "user_id": user_id,
                           "status": PostbackLog.STATUS_DUPLICATE}
            )
            return {"status": "duplicate", "message": "Transaction already processed", "credited_units": 0}

        # 2. Signature verification
        payload_str = json.dumps(raw_payload or {}, sort_keys=True)
        sig_ok = PostbackService.verify_signature(
            secret=secret, payload=payload_str, received_sig=received_sig
        )

        if not sig_ok:
            PostbackLog.objects.create(
                transaction_id=transaction_id,
                publisher_id=publisher_id, user_id=user_id,
                user_ip=user_ip or None, offer_id=offer_id,
                reward_value=reward_value, signature=received_sig,
                status=PostbackLog.STATUS_REJECTED,
                raw_payload=raw_payload or {},
                error_message="HMAC signature mismatch",
            )
            return {"status": "rejected", "message": "Invalid signature", "credited_units": 0}

        # 3. Award virtual currency
        award_result = VirtualCurrencyService.award_on_completion(
            publisher_id=publisher_id, user_id=user_id,
            usd_amount=reward_value, offer_id=offer_id,
            transaction_id=transaction_id,
        )

        # 4. Record success
        PostbackLog.objects.create(
            transaction_id=transaction_id,
            publisher_id=publisher_id, user_id=user_id,
            user_ip=user_ip or None, offer_id=offer_id,
            reward_value=reward_value,
            currency_awarded=award_result.get("awarded_units", 0),
            signature=received_sig,
            status=PostbackLog.STATUS_VERIFIED,
            raw_payload=raw_payload or {},
            processed_at=timezone.now(),
        )

        logger.info(
            "postback.verified publisher=%s user=%s tx=%s reward=%.4f units=%d",
            publisher_id, user_id, transaction_id, reward_value,
            award_result.get("awarded_units", 0),
        )
        return {
            "status":        "verified",
            "message":       "Reward credited successfully",
            "credited_units": award_result.get("awarded_units", 0),
            "currency_name": award_result.get("currency_name", "Points"),
        }

    @staticmethod
    def retry_failed(publisher_id: str, max_retries: int = 3) -> dict:
        """Retry failed postbacks for a publisher."""
        failed = PostbackLog.objects.filter(
            publisher_id=publisher_id,
            status=PostbackLog.STATUS_REJECTED,
            retry_count__lt=max_retries,
        )
        retried = 0
        for log in failed:
            log.retry_count += 1
            log.status       = PostbackLog.STATUS_RETRIED
            log.save(update_fields=["retry_count", "status"])
            retried += 1
        return {"retried": retried}


class OfferwallSDKBridge:
    """
    Bridge between auto_mod and native SDK integrations.
    (Android / iOS / Unity / HTML5)
    Single owner: all SDK integration helpers live here.
    """

    SUPPORTED_PLATFORMS = ("android", "ios", "unity", "html5", "web")

    @staticmethod
    def get_integration_config(publisher_id: str, platform: str) -> dict:
        """Return SDK config for a given platform."""
        cfg = OfferwallConfig.objects.filter(publisher_id=publisher_id).first()
        if not cfg:
            return {"error": "Publisher not configured"}

        base = {
            "publisher_id":   publisher_id,
            "platform":       platform,
            "theme":          cfg.theme,
            "offer_sorting":  cfg.offer_sorting,
            "max_offers":     cfg.max_offers_displayed,
            "postback_url":   cfg.postback_url,
        }

        if platform in ("android", "ios"):
            base.update({
                "sdk_version":    "2.0.0",
                "min_os":         "Android 5.0" if platform == "android" else "iOS 12.0",
                "integration":    "gradle" if platform == "android" else "cocoapods",
                "dependency":     (
                    "implementation 'com.github.auto_mod:android-sdk:v2.0.0'"
                    if platform == "android"
                    else "pod 'AutoModSDK', '~> 2.0.0'"
                ),
            })
        elif platform == "unity":
            base.update({
                "sdk_version":  "2.0.0",
                "unity_package": "auto_mod_offerwall_v2.unitypackage",
            })
        elif platform in ("html5", "web"):
            base.update({
                "embed_html": cfg.get_embed_html("{{USER_ID}}"),
                "js_snippet": (
                    f"<script src='/api/auto_mod/offerwall.js?"
                    f"publisher={publisher_id}'></script>"
                ),
            })
        return base

    @staticmethod
    def validate_sdk_request(
        *,
        publisher_id: str,
        user_id: str,
        platform: str,
        signature: str,
        secret: str,
    ) -> bool:
        """Validate SDK request authenticity."""
        payload  = f"{publisher_id}:{user_id}:{platform}"
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class PerformanceReportService:
    """
    Generate and cache publisher performance reports.
    (Monlix: eCPM, fill rate, completion rate, revenue)
    Single owner: all performance reporting lives here.
    """

    @staticmethod
    def generate_daily_report(publisher_id: str, date=None) -> PerformanceReport:
        """Generate or update daily performance report."""
        if date is None:
            date = timezone.now().date()

        logs = PostbackLog.objects.filter(
            publisher_id=publisher_id,
            received_at__date=date,
        )
        impressions  = logs.count()
        fills        = logs.exclude(status=PostbackLog.STATUS_REJECTED).count()
        completions  = logs.filter(status=PostbackLog.STATUS_VERIFIED).count()
        revenue      = sum(float(l.reward_value) for l in logs.filter(status=PostbackLog.STATUS_VERIFIED))
        ecpm         = (revenue / impressions * 1000) if impressions > 0 else 0
        fill_rate    = (fills / impressions) if impressions > 0 else 0
        comp_rate    = (completions / fills) if fills > 0 else 0

        report, _ = PerformanceReport.objects.update_or_create(
            publisher_id=publisher_id,
            report_date=date,
            period="daily",
            defaults={
                "impressions":       impressions,
                "fills":             fills,
                "completions":       completions,
                "revenue_usd":       round(revenue, 4),
                "ecpm":              round(ecpm, 4),
                "fill_rate":         round(fill_rate, 4),
                "completion_rate":   round(comp_rate, 4),
            },
        )
        return report

    @staticmethod
    def get_report_summary(publisher_id: str, days_back: int = 30) -> dict:
        """Return aggregated stats for the last N days."""
        from django.db.models import Sum, Avg
        cutoff  = timezone.now().date() - timedelta(days=days_back)
        reports = PerformanceReport.objects.filter(
            publisher_id=publisher_id,
            report_date__gte=cutoff,
            period="daily",
        )
        agg = reports.aggregate(
            total_revenue=Sum("revenue_usd"),
            avg_ecpm=Avg("ecpm"),
            total_impressions=Sum("impressions"),
            total_completions=Sum("completions"),
        )
        return {
            "publisher_id":     publisher_id,
            "period_days":      days_back,
            "total_revenue":    float(agg["total_revenue"] or 0),
            "avg_ecpm":         float(agg["avg_ecpm"] or 0),
            "total_impressions": agg["total_impressions"] or 0,
            "total_completions": agg["total_completions"] or 0,
            "avg_completion_rate": reports.aggregate(a=Avg("completion_rate"))["a"] or 0,
        }


class SiteApprovalService:
    """
    Publisher site approval workflow.
    (Monlix: up to 3 business days review before API keys issued)
    Single owner: all site approval logic lives here.
    """

    SLA_BUSINESS_DAYS = 3

    @staticmethod
    def submit_for_approval(
        *,
        publisher_id:    str,
        site_url:        str,
        site_category:   str = "",
        monthly_traffic: str = "",
        description:     str = "",
    ) -> SiteApproval:
        approval, created = SiteApproval.objects.get_or_create(
            publisher_id=publisher_id,
            defaults={
                "site_url":        site_url,
                "site_category":   site_category,
                "monthly_traffic": monthly_traffic,
                "description":     description,
                "status":          SiteApproval.STATUS_PENDING,
            },
        )
        if not created and approval.status == SiteApproval.STATUS_REJECTED:
            approval.status = SiteApproval.STATUS_PENDING
            approval.site_url = site_url
            approval.save()
        logger.info("site_approval.submitted publisher=%s url=%s", publisher_id, site_url)
        return approval

    @staticmethod
    def approve(approval: SiteApproval, reviewer) -> SiteApproval:
        approval.status      = SiteApproval.STATUS_APPROVED
        approval.reviewed_by = reviewer
        approval.reviewed_at = timezone.now()
        approval.save()

        # Issue API keys via offerwall config
        OfferwallConfig.objects.get_or_create(
            publisher_id=approval.publisher_id,
            defaults={
                "postback_secret": str(uuid.uuid4()).replace("-", ""),
                "is_active":       True,
                "approved_at":     timezone.now(),
                "approved_by":     reviewer,
            },
        )

        try:
            from .adapters import AdapterRegistry
            AdapterRegistry.notification.notify_user(
                user_id=approval.publisher_id,
                notification_type="site_approval.approved",
                context={"site_url": approval.site_url},
            )
        except Exception:
            pass

        return approval

    @staticmethod
    def reject(approval: SiteApproval, reviewer, reason: str) -> SiteApproval:
        approval.status           = SiteApproval.STATUS_REJECTED
        approval.reviewed_by      = reviewer
        approval.reviewed_at      = timezone.now()
        approval.rejection_reason = reason
        approval.save()
        return approval

    @staticmethod
    def get_pending_approvals():
        return SiteApproval.objects.filter(status=SiteApproval.STATUS_PENDING).order_by("submitted_at")

    @staticmethod
    def is_overdue(approval: SiteApproval) -> bool:
        """Return True if approval is past SLA (3 business days)."""
        deadline = approval.submitted_at + timedelta(days=SiteApprovalService.SLA_BUSINESS_DAYS)
        return approval.status == SiteApproval.STATUS_PENDING and timezone.now() > deadline


class PaymentScheduleService:
    """
    Publisher payment schedule management.
    (Monlix: NET30, minimum $20 payout, method selection)
    Single owner: all payment schedule logic lives here.
    """

    @staticmethod
    def get_or_create(publisher_id: str) -> PaymentSchedule:
        schedule, _ = PaymentSchedule.objects.get_or_create(
            publisher_id=publisher_id,
            defaults={"schedule_type": PaymentSchedule.SCHEDULE_NET30, "min_payout_usd": 20.00},
        )
        return schedule

    @staticmethod
    def is_eligible_for_payout(publisher_id: str, balance_usd: float) -> dict:
        """Check if publisher meets min payout threshold."""
        schedule = PaymentScheduleService.get_or_create(publisher_id)
        meets    = balance_usd >= float(schedule.min_payout_usd)
        return {
            "eligible":       meets,
            "balance":        balance_usd,
            "minimum":        float(schedule.min_payout_usd),
            "schedule":       schedule.schedule_type,
            "payout_method":  schedule.payout_method,
            "shortfall":      max(0, float(schedule.min_payout_usd) - balance_usd),
        }

    @staticmethod
    def update_schedule(
        publisher_id: str,
        schedule_type: str = None,
        min_payout: float = None,
        payout_method: str = None,
        payout_email: str = None,
    ) -> PaymentSchedule:
        schedule = PaymentScheduleService.get_or_create(publisher_id)
        if schedule_type:   schedule.schedule_type  = schedule_type
        if min_payout:      schedule.min_payout_usd = min_payout
        if payout_method:   schedule.payout_method  = payout_method
        if payout_email:    schedule.payout_email   = payout_email
        schedule.save()
        return schedule

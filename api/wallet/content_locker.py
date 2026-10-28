# api/wallet/content_locker.py
"""
ContentLocker — CPALead-style content locking.

Publisher places a "locker" on premium content.
Visitor must complete an offer to unlock access.
On completion → publisher earns CPL/CPA commission.

Flow:
  1. Publisher creates ContentLocker (content_url, payout_rate)
  2. Visitor visits locked content → redirected to offer wall
  3. Visitor completes offer → OfferConversion recorded
  4. ContentLocker.unlock(visitor_token) → returns access_token
  5. Publisher credited via CPALeadService.record_conversion()
"""
import hashlib
import hmac
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger("wallet.content_locker")

_SECRET = None


def _get_secret() -> bytes:
    global _SECRET
    if _SECRET is None:
        raw = getattr(settings, "WALLET_INTEGRITY_SECRET", "wallet-content-locker-secret")
        _SECRET = raw.encode() if isinstance(raw, str) else raw
    return _SECRET


# ════════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════════

class ContentLocker(models.Model):
    """
    A publisher-created lock on a piece of content.
    Visitors must complete an offer to gain access.
    """

    STATUS_ACTIVE   = "active"
    STATUS_PAUSED   = "paused"
    STATUS_EXPIRED  = "expired"
    STATUS_CHOICES  = [
        (STATUS_ACTIVE,  "Active"),
        (STATUS_PAUSED,  "Paused"),
        (STATUS_EXPIRED, "Expired"),
    ]

    LOCKER_TYPE_DOWNLOAD = "download"
    LOCKER_TYPE_VIDEO    = "video"
    LOCKER_TYPE_ARTICLE  = "article"
    LOCKER_TYPE_LINK     = "link"
    LOCKER_TYPE_CHOICES  = [
        (LOCKER_TYPE_DOWNLOAD, "Download"),
        (LOCKER_TYPE_VIDEO,    "Video"),
        (LOCKER_TYPE_ARTICLE,  "Article"),
        (LOCKER_TYPE_LINK,     "Link"),
    ]

    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="content_lockers",
    )
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="content_lockers",
    )
    wallet = models.ForeignKey(
        "wallet.Wallet", on_delete=models.CASCADE,
        related_name="content_lockers",
    )

    # ── Locker definition ─────────────────────────────────────────
    locker_id   = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    locker_type = models.CharField(
        max_length=12, choices=LOCKER_TYPE_CHOICES, default=LOCKER_TYPE_LINK,
    )

    # ── Content (what gets unlocked) ──────────────────────────────
    content_url      = models.URLField(help_text="URL revealed after offer completion")
    thumbnail_url    = models.URLField(blank=True)
    preview_text     = models.TextField(
        blank=True, help_text="Teaser shown before unlock"
    )

    # ── Payout ────────────────────────────────────────────────────
    payout_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal("0.50"),
        help_text="Publisher payout per unlock (BDT)",
    )
    currency    = models.CharField(max_length=10, default="BDT")

    # ── Traffic & completion ──────────────────────────────────────
    total_views       = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    total_earned      = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal("0"),
    )

    # ── Unlock token TTL ─────────────────────────────────────────
    unlock_ttl_hours = models.PositiveSmallIntegerField(
        default=24, help_text="How long unlock access lasts (hours)",
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
        db_table  = "wallet_contentlocker"
        ordering  = ["-created_at"]
        indexes   = [
            models.Index(fields=["publisher", "status"]),
            models.Index(fields=["locker_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} | {self.publisher_id} | {self.payout_rate} {self.currency}"

    @property
    def conversion_rate(self) -> float:
        if not self.total_views:
            return 0.0
        return round(self.total_completions / self.total_views * 100, 2)

    @property
    def is_active(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class ContentLockerUnlock(models.Model):
    """
    Records a visitor's completed unlock. Stores signed access_token
    so the content URL is not exposed until the offer is verified.
    """

    locker      = models.ForeignKey(
        ContentLocker, on_delete=models.CASCADE, related_name="unlocks",
    )
    visitor_id  = models.CharField(max_length=128, db_index=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    access_token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at  = models.DateTimeField()
    click_id    = models.CharField(max_length=128, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_contentlockerunlock"
        indexes   = [
            models.Index(fields=["visitor_id", "locker"]),
            models.Index(fields=["expires_at"]),
        ]

    @property
    def is_valid(self) -> bool:
        return self.expires_at > timezone.now()


# ════════════════════════════════════════════════════════════════
# SERVICE
# ════════════════════════════════════════════════════════════════

class ContentLockerService:
    """
    Business logic for content lockers.
    No external module calls — purely internal.
    """

    @staticmethod
    def create(
        publisher,
        wallet,
        title: str,
        content_url: str,
        payout_rate: Decimal,
        locker_type: str = ContentLocker.LOCKER_TYPE_LINK,
        preview_text: str = "",
        unlock_ttl_hours: int = 24,
    ) -> ContentLocker:
        """Create a new content locker for a publisher."""
        return ContentLocker.objects.create(
            publisher=publisher,
            wallet=wallet,
            title=title,
            content_url=content_url,
            payout_rate=Decimal(str(payout_rate)),
            locker_type=locker_type,
            preview_text=preview_text,
            unlock_ttl_hours=unlock_ttl_hours,
        )

    @staticmethod
    def record_view(locker_id: str) -> None:
        """Increment view counter (called when visitor hits locker page)."""
        ContentLocker.objects.filter(
            locker_id=locker_id, status=ContentLocker.STATUS_ACTIVE
        ).update(total_views=models.F("total_views") + 1)

    @classmethod
    def unlock(
        cls,
        locker_id: str,
        visitor_id: str,
        click_id: str = "",
        ip_address: str = "",
    ) -> dict:
        """
        Called after offer completion is verified.
        Creates a signed access_token valid for unlock_ttl_hours.
        Credits publisher via CPALeadService.

        Returns:
            {"access_token": str, "content_url": str, "expires_at": str}
        """
        try:
            locker = ContentLocker.objects.select_for_update().get(
                locker_id=locker_id, status=ContentLocker.STATUS_ACTIVE
            )
        except ContentLocker.DoesNotExist:
            raise ValueError(f"ContentLocker {locker_id} not found or inactive")

        with transaction.atomic():
            # Generate access token
            token_raw = f"{locker_id}:{visitor_id}:{click_id}:{uuid.uuid4()}"
            access_token = hmac.new(
                _get_secret(), token_raw.encode(), hashlib.sha256
            ).hexdigest()

            expires_at = timezone.now() + timezone.timedelta(
                hours=locker.unlock_ttl_hours
            )

            unlock = ContentLockerUnlock.objects.create(
                locker=locker,
                visitor_id=visitor_id,
                ip_address=ip_address or None,
                access_token=access_token,
                expires_at=expires_at,
                click_id=click_id,
            )

            # Update locker stats
            ContentLocker.objects.filter(pk=locker.pk).update(
                total_completions=models.F("total_completions") + 1,
                total_earned=models.F("total_earned") + locker.payout_rate,
            )

            # Credit publisher wallet via CPALeadService (lazy import — no circular)
            try:
                from .services.cpalead.CPALeadService import CPALeadService
                CPALeadService.credit_content_lock(
                    wallet=locker.wallet,
                    amount=locker.payout_rate,
                    locker_id=str(locker.locker_id),
                    click_id=click_id,
                    ip_address=ip_address,
                )
            except Exception as e:
                logger.error(f"ContentLocker credit failed locker={locker_id}: {e}")

            logger.info(
                f"ContentLocker unlocked: locker={locker_id} visitor={visitor_id}"
            )

        return {
            "access_token": access_token,
            "content_url":  locker.content_url,
            "expires_at":   expires_at.isoformat(),
        }

    @staticmethod
    def verify_token(access_token: str) -> dict | None:
        """
        Verify an access token and return content_url if valid.
        Returns None if expired or not found.
        """
        try:
            unlock = ContentLockerUnlock.objects.select_related("locker").get(
                access_token=access_token
            )
        except ContentLockerUnlock.DoesNotExist:
            return None

        if not unlock.is_valid:
            return None

        return {
            "content_url": unlock.locker.content_url,
            "locker_id":   str(unlock.locker.locker_id),
            "expires_at":  unlock.expires_at.isoformat(),
        }

    @staticmethod
    def stats(locker_id: str) -> dict:
        """Return performance stats for a locker."""
        try:
            locker = ContentLocker.objects.get(locker_id=locker_id)
        except ContentLocker.DoesNotExist:
            return {}
        return {
            "locker_id":         str(locker.locker_id),
            "title":             locker.title,
            "total_views":       locker.total_views,
            "total_completions": locker.total_completions,
            "conversion_rate":   locker.conversion_rate,
            "total_earned":      str(locker.total_earned),
            "status":            locker.status,
        }

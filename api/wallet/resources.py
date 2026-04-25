# api/wallet/resources.py
"""
Django Import-Export resources for bulk wallet data management.
Also contains Smart Link routing, Sub-ID tracking, Click tracking/deduplication.

pip install django-import-export

Admin usage:
    @admin.register(Wallet)
    class WalletAdmin(ImportExportModelAdmin):
        resource_class = WalletResource

Smart Link usage:
    GET /api/wallet/offers/smart-link/?pub_id=123&sub_id=abc&country=BD&device=mobile
"""
import hashlib
import logging
import uuid
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("wallet.resources")

# ══════════════════════════════════════════════════════════════
# IMPORT-EXPORT RESOURCES
# ══════════════════════════════════════════════════════════════

try:
    from import_export import resources, fields
    from import_export.widgets import DecimalWidget, DateTimeWidget, BooleanWidget

    class WalletResource(resources.ModelResource):
        """Import/export Wallet model for bulk admin operations."""
        username         = fields.Field(column_name="username")
        email            = fields.Field(column_name="email")
        available_balance = fields.Field(column_name="available_balance",
                                         widget=DecimalWidget())

        class Meta:
            try:
                from .models.core import Wallet
                model = Wallet
            except ImportError:
                model = None
            export_order = [
                "id", "username", "email", "current_balance", "pending_balance",
                "frozen_balance", "bonus_balance", "available_balance",
                "total_earned", "total_withdrawn", "is_locked", "currency", "created_at",
            ]
            import_id_fields = ["id"]
            skip_unchanged   = True

        def dehydrate_username(self, wallet):
            return wallet.user.username if wallet.user else ""

        def dehydrate_email(self, wallet):
            return wallet.user.email if wallet.user else ""

        def dehydrate_available_balance(self, wallet):
            return wallet.available_balance

    class WalletTransactionResource(resources.ModelResource):
        """Import/export WalletTransaction for audit/reporting."""
        wallet_user = fields.Field(column_name="user")

        class Meta:
            try:
                from .models.core import WalletTransaction
                model = WalletTransaction
            except ImportError:
                model = None
            export_order = [
                "id", "wallet_user", "type", "amount", "status",
                "balance_before", "balance_after", "description",
                "reference_id", "created_at",
            ]

        def dehydrate_wallet_user(self, txn):
            return txn.wallet.user.username if txn.wallet and txn.wallet.user else ""

    class WithdrawalRequestResource(resources.ModelResource):
        """Import/export WithdrawalRequest for finance team."""
        username = fields.Field(column_name="username")
        gateway  = fields.Field(column_name="gateway")
        account  = fields.Field(column_name="account_number")

        class Meta:
            try:
                from .models.withdrawal import WithdrawalRequest
                model = WithdrawalRequest
            except ImportError:
                model = None
            export_order = [
                "id", "username", "amount", "fee", "net_amount",
                "gateway", "account", "status", "gateway_reference", "created_at",
            ]

        def dehydrate_username(self, wr):
            return wr.user.username if wr.user else ""

        def dehydrate_gateway(self, wr):
            return wr.payment_method.method_type if wr.payment_method else ""

        def dehydrate_account(self, wr):
            return wr.payment_method.account_number if wr.payment_method else ""

    class EarningRecordResource(resources.ModelResource):
        """Import/export EarningRecord for affiliate reporting."""
        username = fields.Field(column_name="username")

        class Meta:
            try:
                from .models.earning import EarningRecord
                model = EarningRecord
            except ImportError:
                model = None
            export_order = [
                "id", "username", "source_type", "amount",
                "original_amount", "country_code", "earned_at",
            ]

        def dehydrate_username(self, rec):
            return rec.wallet.user.username if rec.wallet and rec.wallet.user else ""

except ImportError:
    # django-import-export not installed — stub classes
    class WalletResource: pass
    class WalletTransactionResource: pass
    class WithdrawalRequestResource: pass
    class EarningRecordResource: pass


# ══════════════════════════════════════════════════════════════
# SMART LINK ROUTING (CPAlead feature)
# ══════════════════════════════════════════════════════════════

class SmartLinkRouter:
    """
    CPAlead-style Smart Link — routes publisher traffic to best offer.
    Factors: GEO, device type, publisher level, offer caps, A/B test.

    GET /offers/smart-link/?pub_id=123&sub_id=abc&country=BD&device=mobile
    → Returns best matching offer URL for the user
    """

    @staticmethod
    def route(publisher_id: int, country_code: str = "BD",
              device_type: str = "desktop", sub_id: str = "",
              category: str = "") -> dict:
        """
        Route publisher to best available offer.
        Returns offer details + tracking URL.
        """
        try:
            from .models_cpalead_extra import EarningOffer
            from .services.cpalead.CPALeadService import CPALeadService

            # Get available offers
            offers = EarningOffer.objects.filter(
                is_active=True,
                countries__contains=[country_code.upper()],
            ).exclude(
                # Exclude capped offers
                conversions_today__gte=models_F("daily_cap"),
            ).order_by("-payout")[:10]

            if not offers.exists():
                # Fallback: any active offer
                offers = EarningOffer.objects.filter(is_active=True).order_by("-payout")[:5]

            if not offers.exists():
                return {"success": False, "error": "No offers available"}

            # Select best offer (highest payout for this geo)
            geo_mult = CPALeadService.get_geo_rate(country_code)
            best_offer = None
            best_payout = Decimal("0")

            for offer in offers:
                effective_payout = offer.payout * geo_mult
                if effective_payout > best_payout:
                    best_payout = effective_payout
                    best_offer  = offer

            if not best_offer:
                best_offer = offers[0]

            # Generate click tracking URL
            click_id = SmartLinkRouter._generate_click_id(
                publisher_id, best_offer.id, sub_id, country_code, device_type
            )

            # Build tracking URL
            tracking_url = SmartLinkRouter._build_tracking_url(
                best_offer, click_id, publisher_id, sub_id
            )

            return {
                "success":     True,
                "offer_id":    best_offer.id,
                "offer_title": best_offer.title,
                "offer_type":  best_offer.offer_type,
                "payout":      float(best_offer.payout),
                "geo_payout":  float(best_payout),
                "click_id":    click_id,
                "redirect_url":tracking_url,
            }

        except Exception as e:
            logger.error(f"SmartLink routing error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def _generate_click_id(pub_id: int, offer_id: int, sub_id: str,
                            country: str, device: str) -> str:
        """Generate unique click ID for tracking."""
        data = f"{pub_id}:{offer_id}:{sub_id}:{country}:{device}:{uuid.uuid4().hex}"
        return hashlib.md5(data.encode()).hexdigest()

    @staticmethod
    def _build_tracking_url(offer, click_id: str, pub_id: int, sub_id: str) -> str:
        """Build offer URL with tracking parameters."""
        from django.conf import settings
        base_url = getattr(settings, "OFFER_TRACKING_BASE_URL", "https://track.platform.com")
        return (
            f"{base_url}/click"
            f"?offer_id={offer.id}"
            f"&click_id={click_id}"
            f"&pub_id={pub_id}"
            f"&sub_id={sub_id}"
            f"&o={offer.offer_id}"
        )


# ══════════════════════════════════════════════════════════════
# CLICK TRACKING + DEDUPLICATION (CPAlead feature)
# ══════════════════════════════════════════════════════════════

class ClickTracker:
    """
    Track offer clicks with deduplication.
    Prevents double-conversion fraud (same click → two conversions).

    Redis-based: click_id stored for 24h window.
    """

    CLICK_TTL = 86400  # 24 hours

    @staticmethod
    def record_click(click_id: str, offer_id: int, publisher_id: int,
                     ip_address: str = "", sub_id: str = "",
                     country_code: str = "", device_type: str = "desktop") -> bool:
        """
        Record a click. Returns True if new, False if duplicate.
        """
        cache_key = f"click:{click_id}"

        # Check for duplicate
        if cache.get(cache_key):
            logger.warning(f"Duplicate click detected: click_id={click_id} offer={offer_id}")
            return False

        # Store click data
        click_data = {
            "click_id":    click_id,
            "offer_id":    offer_id,
            "publisher_id":publisher_id,
            "ip_address":  ip_address,
            "sub_id":      sub_id,
            "country_code":country_code,
            "device_type": device_type,
            "clicked_at":  timezone.now().isoformat(),
            "converted":   False,
        }
        cache.set(cache_key, click_data, ClickTracker.CLICK_TTL)

        # IP-based dedup within 60 seconds (same IP + same offer)
        ip_key = f"click_ip:{ip_address}:{offer_id}"
        if cache.get(ip_key):
            logger.warning(f"Same IP rapid click: ip={ip_address} offer={offer_id}")
            cache.delete(cache_key)
            return False
        cache.set(ip_key, "1", 60)

        logger.debug(f"Click recorded: {click_id} offer={offer_id} pub={publisher_id}")
        return True

    @staticmethod
    def get_click(click_id: str) -> dict:
        """Retrieve click data."""
        return cache.get(f"click:{click_id}") or {}

    @staticmethod
    def mark_converted(click_id: str) -> bool:
        """Mark a click as converted (prevents double conversion)."""
        cache_key = f"click:{click_id}"
        click_data = cache.get(cache_key)
        if not click_data:
            return False

        if click_data.get("converted"):
            logger.warning(f"Already converted click: {click_id}")
            return False

        click_data["converted"]    = True
        click_data["converted_at"] = timezone.now().isoformat()
        cache.set(cache_key, click_data, ClickTracker.CLICK_TTL)
        return True

    @staticmethod
    def is_duplicate_conversion(click_id: str) -> bool:
        """Check if this click was already converted."""
        data = cache.get(f"click:{click_id}")
        return bool(data and data.get("converted"))

    @staticmethod
    def get_publisher_stats(publisher_id: int, date_from=None, date_to=None) -> dict:
        """Get click stats for a publisher (from database)."""
        try:
            from .models_cpalead_extra import OfferConversion
            from django.db.models import Sum, Count
            qs = OfferConversion.objects.filter(user_id=publisher_id)
            if date_from:
                qs = qs.filter(created_at__date__gte=date_from)
            if date_to:
                qs = qs.filter(created_at__date__lte=date_to)
            return qs.aggregate(
                total_conversions=Count("id"),
                total_payout=Sum("payout"),
                approved=Count("id", filter=models_Q(status="approved")),
                rejected=Count("id", filter=models_Q(status="rejected")),
            )
        except Exception as e:
            logger.error(f"Publisher stats error: {e}")
            return {}


# ══════════════════════════════════════════════════════════════
# SUB-ID TRACKING (CPAlead feature)
# ══════════════════════════════════════════════════════════════

class SubIDTracker:
    """
    Track Sub-ID performance for publishers.
    Sub-ID = publisher's own campaign/placement identifier.
    e.g. ?sub_id=facebook_ad_123 or ?sub_id=email_campaign_5
    """

    @staticmethod
    def record(publisher_id: int, sub_id: str, offer_id: int,
               country_code: str = "", device_type: str = "") -> None:
        """Store sub-ID impression for analytics."""
        if not sub_id:
            return
        cache_key = f"subid:{publisher_id}:{sub_id}:impressions"
        try:
            cache.incr(cache_key)
        except Exception:
            cache.set(cache_key, 1, 86400 * 30)

    @staticmethod
    def get_report(publisher_id: int) -> list:
        """Get Sub-ID performance report from DB."""
        try:
            from .models_cpalead_extra import OfferConversion
            from django.db.models import Sum, Count
            return list(
                OfferConversion.objects.filter(
                    user_id=publisher_id,
                    status="approved",
                ).values("sub_id").annotate(
                    conversions=Count("id"),
                    total_payout=Sum("payout"),
                ).order_by("-total_payout")
            )
        except Exception:
            return []

    @staticmethod
    def get_best_sub_ids(publisher_id: int, limit: int = 10) -> list:
        """Get top performing sub-IDs."""
        report = SubIDTracker.get_report(publisher_id)
        return report[:limit]


# ══════════════════════════════════════════════════════════════
# OFFER ROTATION / A-B TESTING (CPAlead feature)
# ══════════════════════════════════════════════════════════════

class OfferRotator:
    """
    Rotate offers for A/B testing and cap management.
    Distributes traffic across multiple offers for a publisher.
    """

    @staticmethod
    def get_offers_for_ab_test(publisher_id: int, country_code: str = "BD",
                                limit: int = 3) -> list:
        """
        Get a set of offers for A/B testing.
        Returns top N offers by payout for the given GEO.
        """
        try:
            from .models_cpalead_extra import EarningOffer
            offers = EarningOffer.objects.filter(
                is_active=True,
            ).order_by("-payout")[:limit * 3]

            # Filter by daily cap
            available = []
            for offer in offers:
                if not offer.is_capped():
                    available.append({
                        "offer_id":    offer.id,
                        "title":       offer.title,
                        "type":        offer.offer_type,
                        "payout":      float(offer.payout),
                        "conversions": offer.conversions_today,
                        "daily_cap":   offer.daily_cap,
                    })
                if len(available) >= limit:
                    break

            return available
        except Exception as e:
            logger.error(f"OfferRotator error: {e}")
            return []

    @staticmethod
    def pick_offer(publisher_id: int, country_code: str = "BD",
                   rotation_method: str = "highest_payout") -> dict:
        """
        Pick single offer using rotation strategy.
        rotation_method: highest_payout | round_robin | random | weighted
        """
        offers = OfferRotator.get_offers_for_ab_test(publisher_id, country_code)
        if not offers:
            return {}

        if rotation_method == "highest_payout":
            return offers[0]
        elif rotation_method == "random":
            import random
            return random.choice(offers)
        elif rotation_method == "round_robin":
            # Use Redis counter for round-robin
            key = f"rotator:{publisher_id}:idx"
            idx = cache.incr(key) % len(offers)
            return offers[idx]
        else:
            return offers[0]

    @staticmethod
    def track_ab_result(offer_id: int, pub_id: int, converted: bool) -> None:
        """Record A/B test result for analytics."""
        key = f"ab:{offer_id}:{pub_id}:{'conv' if converted else 'noconv'}"
        try:
            cache.incr(key)
        except Exception:
            cache.set(key, 1, 86400 * 7)

    @staticmethod
    def get_ab_stats(offer_id: int, pub_id: int) -> dict:
        """Get A/B test stats for an offer."""
        conversions   = cache.get(f"ab:{offer_id}:{pub_id}:conv") or 0
        no_conversions= cache.get(f"ab:{offer_id}:{pub_id}:noconv") or 0
        total         = conversions + no_conversions
        return {
            "offer_id":       offer_id,
            "publisher_id":   pub_id,
            "total_clicks":   total,
            "conversions":    conversions,
            "no_conversions": no_conversions,
            "cvr":            round(conversions / total * 100, 2) if total > 0 else 0,
        }


# ══════════════════════════════════════════════════════════════
# POSTBACK / S2S TRACKING (CPAlead feature)
# ══════════════════════════════════════════════════════════════

class PostbackService:
    """
    Server-to-Server postback for conversion tracking.
    Fires an HTTP request to publisher's postback URL on conversion.
    e.g. https://tracker.publisher.com/conv?click_id={click_id}&payout={payout}
    """

    @staticmethod
    def fire(publisher_id: int, click_id: str, payout: Decimal,
             sub_id: str = "", status: str = "approved") -> dict:
        """Fire postback to publisher's configured URL."""
        import requests
        from django.conf import settings

        try:
            # Get publisher postback URL
            postback_url = PostbackService._get_postback_url(publisher_id)
            if not postback_url:
                return {"fired": False, "reason": "No postback URL configured"}

            # Build URL with macros
            url = postback_url.replace("{click_id}", click_id)
            url = url.replace("{payout}",   str(payout))
            url = url.replace("{sub_id}",   sub_id)
            url = url.replace("{status}",   status)
            url = url.replace("{currency}", "BDT")

            resp = requests.get(url, timeout=10)
            logger.info(f"Postback fired: pub={publisher_id} url={url[:80]} status={resp.status_code}")
            return {"fired": True, "status_code": resp.status_code, "url": url}

        except Exception as e:
            logger.error(f"Postback fire error: {e}")
            return {"fired": False, "error": str(e)}

    @staticmethod
    def _get_postback_url(publisher_id: int) -> str:
        """Get publisher's configured postback URL."""
        try:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(id=publisher_id)
            return getattr(user, "postback_url", "") or ""
        except Exception:
            return ""


# ── Import helpers for clean use in views ─────────────────────
try:
    from django.db.models import Q as models_Q, F as models_F
except ImportError:
    models_Q = None
    models_F = None

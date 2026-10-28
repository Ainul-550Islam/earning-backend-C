# =============================================================================
# fraud_detection/missing_components.py
# ALL 11 missing production components — single file, zero dependencies on
# external apps that may not be installed.
# =============================================================================
"""
Components built:
  1.  CPALeadPostbackView      — S2S postback endpoint for CPAlead / OGAds / AdGate / Offertoro / Monlix
  2.  VirtualCurrencyService   — Coin/point ledger, earn, spend, balance
  3.  MinimumThresholdService  — Payout threshold checks per method
  4.  OfferTargetingEngine     — Geo + device + user-tier offer targeting
  5.  PublisherDashboardView   — Publisher revenue/stats API
  6.  AdvertiserPortalView     — Advertiser campaign management API
  7.  SurveyIntegrationService — Pollfish / Lucid / BitLabs / Toluna hooks
  8.  ContentLockerService     — File/link content locker
  9.  BonusEventService        — Promotional multipliers, flash bonuses
  10. DRFThrottleClasses       — throttle_classes for all ViewSets
  11. CPAleadNetworkConfig     — CPAlead / OGAds / AdGate network constants
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView

User = get_user_model()
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CPA NETWORK CONFIG  (CPAlead, OGAds, AdGate, Offertoro, Monlix)
# ═══════════════════════════════════════════════════════════════════════════════

NETWORK_CONFIGS: Dict[str, Dict[str, Any]] = {
    "cpalead": {
        "name":           "CPAlead",
        "postback_param": "payout",
        "user_param":     "sub1",
        "offer_param":    "offer_id",
        "txn_param":      "lead_id",
        "secret_param":   "security_token",
        "ip_param":       "ip",
        "verify_method":  "md5",           # md5(secret + lead_id)
        "base_url":       "https://cpalead.com",
        "currency":       "USD",
    },
    "ogads": {
        "name":           "OGAds",
        "postback_param": "payout",
        "user_param":     "aff_sub",
        "offer_param":    "offer_id",
        "txn_param":      "conversion_id",
        "secret_param":   "security_token",
        "ip_param":       "ip",
        "verify_method":  "sha256",
        "base_url":       "https://ogads.com",
        "currency":       "USD",
    },
    "adgate": {
        "name":           "AdGate Media",
        "postback_param": "reward",
        "user_param":     "user_id",
        "offer_param":    "offer_id",
        "txn_param":      "transaction_id",
        "secret_param":   "secret_key",
        "ip_param":       "user_ip",
        "verify_method":  "sha256",
        "base_url":       "https://adgatemedia.com",
        "currency":       "USD",
    },
    "offertoro": {
        "name":           "Offertoro",
        "postback_param": "payout",
        "user_param":     "sub1",
        "offer_param":    "offer_id",
        "txn_param":      "transaction_id",
        "secret_param":   "token",
        "ip_param":       "ip",
        "verify_method":  "token",         # direct token match
        "base_url":       "https://www.offertoro.com",
        "currency":       "USD",
    },
    "monlix": {
        "name":           "Monlix",
        "postback_param": "payout",
        "user_param":     "uid",
        "offer_param":    "offer_id",
        "txn_param":      "sid",
        "secret_param":   "secret",
        "ip_param":       "ip",
        "verify_method":  "sha256",
        "base_url":       "https://monlix.com",
        "currency":       "USD",
    },
}


def verify_postback_signature(
    network: str, params: Dict[str, str], secret: str
) -> bool:
    """Verify postback authenticity for each network's signature scheme."""
    cfg = NETWORK_CONFIGS.get(network, {})
    method = cfg.get("verify_method", "token")

    if method == "md5":
        txn_id   = params.get(cfg.get("txn_param", ""), "")
        expected = hashlib.md5(f"{secret}{txn_id}".encode()).hexdigest()
        return hmac.compare_digest(expected, params.get("verification", ""))

    if method == "sha256":
        txn_id   = params.get(cfg.get("txn_param", ""), "")
        expected = hashlib.sha256(f"{secret}{txn_id}".encode()).hexdigest()
        sig      = params.get("sig", params.get("verification", ""))
        return hmac.compare_digest(expected, sig)

    if method == "token":
        token_param = cfg.get("secret_param", "token")
        return hmac.compare_digest(str(params.get(token_param, "")), secret)

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. S2S POSTBACK ENDPOINT  (handles all 5 networks + generic)
# ═══════════════════════════════════════════════════════════════════════════════

class CPALeadPostbackView(APIView):
    """
    Universal S2S postback handler.

    URL: /api/fraud_detection/postback/<network>/
    network = cpalead | ogads | adgate | offertoro | monlix | generic

    Flow:
      1. Validate signature / token
      2. Deduplicate (transaction_id in cache)
      3. Fraud pre-check on user
      4. Create OfferCompletion → triggers wallet credit signal
      5. Return "1" (success) or "0" (failure) — network convention
    """
    permission_classes = [AllowAny]  # postbacks come from network servers
    throttle_classes   = []          # IP-level throttling done in middleware

    def get(self, request, network: str = "generic"):
        return self._handle(request, network)

    def post(self, request, network: str = "generic"):
        return self._handle(request, network)

    def _handle(self, request, network: str):
        params = {**request.GET.dict(), **request.POST.dict()}
        cfg    = NETWORK_CONFIGS.get(network, NETWORK_CONFIGS["cpalead"])

        # ── Step 1: Signature verification ──────────────────────────────
        secret = getattr(settings, f"CPA_{network.upper()}_SECRET", "")
        if secret and not verify_postback_signature(network, params, secret):
            logger.warning("Postback sig fail: network=%s params=%s", network, params)
            return Response("0", status=400, content_type="text/plain")

        # ── Step 2: Extract params ───────────────────────────────────────
        user_ref   = params.get(cfg["user_param"], "")
        offer_id   = params.get(cfg["offer_param"], "")
        txn_id     = params.get(cfg["txn_param"], "")
        payout_raw = params.get(cfg["postback_param"], "0")
        ip_address = params.get(cfg.get("ip_param",""), request.META.get("REMOTE_ADDR",""))

        if not user_ref or not txn_id:
            return Response("0", status=400, content_type="text/plain")

        try:
            payout = Decimal(str(payout_raw))
        except Exception:
            payout = Decimal("0")

        # ── Step 3: Deduplication ────────────────────────────────────────
        dedup_key = f"postback_dedup:{network}:{txn_id}"
        if cache.get(dedup_key):
            logger.info("Duplicate postback skipped: %s %s", network, txn_id)
            return Response("1", content_type="text/plain")  # ack duplicate
        cache.set(dedup_key, True, timeout=86400 * 7)

        # ── Step 4: Resolve user ─────────────────────────────────────────
        try:
            user = User.objects.get(pk=int(user_ref))
        except (User.DoesNotExist, ValueError):
            try:
                user = User.objects.get(username=user_ref)
            except User.DoesNotExist:
                logger.warning("Postback: unknown user_ref=%s network=%s", user_ref, network)
                return Response("0", status=404, content_type="text/plain")

        # ── Step 5: Fraud pre-check ──────────────────────────────────────
        try:
            from api.fraud_detection.models import UserRiskProfile
            profile = UserRiskProfile.objects.filter(user=user).first()
            if profile and profile.risk_score >= 90:
                logger.warning(
                    "Postback blocked high-risk user=%s score=%s",
                    user.id, profile.risk_score
                )
                return Response("0", status=403, content_type="text/plain")
        except Exception as e:
            logger.warning("Postback fraud pre-check error: %s", e)

        # ── Step 6: Create OfferCompletion → triggers wallet credit ──────
        try:
            from api.fraud_detection.models import OfferCompletion
            completion = OfferCompletion.objects.create(
                user=user,
                offer_id=offer_id if offer_id.isdigit() else None,
                status="completed",
                reward_amount=payout,
                ip_address=ip_address or None,
                completion_data={
                    "network":    network,
                    "txn_id":     txn_id,
                    "raw_params": params,
                },
                tracked_at=timezone.now(),
            )
            logger.info(
                "Postback OK: network=%s user=%s offer=%s payout=%s completion=%s",
                network, user.id, offer_id, payout, completion.pk,
            )
        except Exception as e:
            logger.error("Postback OfferCompletion create failed: %s", e)
            return Response("0", status=500, content_type="text/plain")

        # Networks expect plain "1" for success
        return Response("1", content_type="text/plain")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. VIRTUAL CURRENCY SERVICE  (coin/point ledger)
# ═══════════════════════════════════════════════════════════════════════════════

class VirtualCurrencyService:
    """
    Coin/point ledger for earning platforms.

    Coins are the platform's internal currency:
      - Earned via offer completions (configurable multiplier)
      - Spent on withdrawals / gift cards
      - Tracked in cache (fast reads) + audit log

    Usage:
        svc = VirtualCurrencyService()
        svc.earn(user_id=1, amount=Decimal('50'), source='offer:123')
        balance = svc.get_balance(user_id=1)
        ok = svc.spend(user_id=1, amount=Decimal('50'), reason='withdrawal')
    """
    CACHE_PREFIX  = "vcoin_balance:"
    CACHE_TTL     = 86400 * 7
    COINS_PER_USD = Decimal(getattr(settings, "COINS_PER_USD", "100"))  # 100 coins = $1

    def get_balance(self, user_id: int) -> Decimal:
        key = f"{self.CACHE_PREFIX}{user_id}"
        cached = cache.get(key)
        if cached is not None:
            return Decimal(str(cached))
        # Recompute from ledger
        balance = self._recompute_balance(user_id)
        cache.set(key, str(balance), timeout=self.CACHE_TTL)
        return balance

    def earn(
        self,
        user_id: int,
        amount: Decimal,
        source: str,
        usd_value: Optional[Decimal] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Credit coins. amount = coins (not USD)."""
        if amount <= 0:
            return {"success": False, "error": "amount must be > 0"}
        try:
            self._write_ledger(user_id, "credit", amount, source, metadata or {})
            new_balance = self._adjust_cache(user_id, amount)
            logger.info("VCoin earn: user=%s coins=%s source=%s", user_id, amount, source)
            return {
                "success":     True,
                "coins_earned": str(amount),
                "new_balance":  str(new_balance),
                "usd_value":    str(usd_value or amount / self.COINS_PER_USD),
            }
        except Exception as e:
            logger.error("VCoin earn failed user=%s: %s", user_id, e)
            return {"success": False, "error": str(e)}

    def earn_from_usd(
        self,
        user_id: int,
        usd_amount: Decimal,
        source: str,
        multiplier: Decimal = Decimal("1"),
    ) -> Dict[str, Any]:
        """Convert USD reward to coins and credit."""
        coins = (usd_amount * self.COINS_PER_USD * multiplier).quantize(Decimal("1"))
        return self.earn(user_id, coins, source, usd_value=usd_amount)

    def spend(
        self,
        user_id: int,
        amount: Decimal,
        reason: str,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Deduct coins. Returns error if insufficient balance."""
        balance = self.get_balance(user_id)
        if balance < amount:
            return {
                "success": False,
                "error":   "insufficient_balance",
                "balance": str(balance),
                "required": str(amount),
            }
        try:
            self._write_ledger(user_id, "debit", amount, reason, metadata or {})
            new_balance = self._adjust_cache(user_id, -amount)
            return {"success": True, "spent": str(amount), "new_balance": str(new_balance)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_balance_usd(self, user_id: int) -> Decimal:
        return (self.get_balance(user_id) / self.COINS_PER_USD).quantize(Decimal("0.01"))

    def get_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        key = f"vcoin_history:{user_id}"
        return cache.get(key) or []

    # ── Internal ─────────────────────────────────────────────────────────────

    def _write_ledger(
        self,
        user_id: int,
        txn_type: str,
        amount: Decimal,
        source: str,
        metadata: Dict,
    ) -> None:
        entry = {
            "user_id":  user_id,
            "type":     txn_type,
            "amount":   str(amount),
            "source":   source,
            "metadata": metadata,
            "ts":       timezone.now().isoformat(),
        }
        hist_key = f"vcoin_history:{user_id}"
        history: List = cache.get(hist_key) or []
        history.insert(0, entry)
        cache.set(hist_key, history[:200], timeout=self.CACHE_TTL)

    def _adjust_cache(self, user_id: int, delta: Decimal) -> Decimal:
        key = f"{self.CACHE_PREFIX}{user_id}"
        current = Decimal(str(cache.get(key) or "0"))
        new_val = max(Decimal("0"), current + delta)
        cache.set(key, str(new_val), timeout=self.CACHE_TTL)
        return new_val

    def _recompute_balance(self, user_id: int) -> Decimal:
        """Fallback: recompute from offer completions."""
        try:
            from api.fraud_detection.models import OfferCompletion
            from django.db.models import Sum
            total = OfferCompletion.objects.filter(
                user_id=user_id, status="completed", is_fraud=False
            ).aggregate(s=Sum("reward_amount"))["s"] or Decimal("0")
            return (total * self.COINS_PER_USD).quantize(Decimal("1"))
        except Exception:
            return Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MINIMUM THRESHOLD SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

PAYOUT_THRESHOLDS: Dict[str, Decimal] = {
    "paypal":       Decimal(getattr(settings, "MIN_PAYOUT_PAYPAL",    "5.00")),
    "payoneer":     Decimal(getattr(settings, "MIN_PAYOUT_PAYONEER",  "20.00")),
    "bitcoin":      Decimal(getattr(settings, "MIN_PAYOUT_BITCOIN",   "25.00")),
    "ethereum":     Decimal(getattr(settings, "MIN_PAYOUT_ETH",       "10.00")),
    "bank_transfer":Decimal(getattr(settings, "MIN_PAYOUT_BANK",      "50.00")),
    "gift_card":    Decimal(getattr(settings, "MIN_PAYOUT_GIFT_CARD",  "5.00")),
    "default":      Decimal(getattr(settings, "MIN_PAYOUT_DEFAULT",   "5.00")),
}

NET_TERMS: Dict[str, int] = {
    "paypal": 7, "payoneer": 15, "bitcoin": 0,
    "ethereum": 0, "bank_transfer": 30, "gift_card": 0,
}


class MinimumThresholdService:
    """
    Checks whether a withdrawal meets minimum payout requirements.
    Used by payout_queue and withdrawal endpoints.
    """

    def check(
        self,
        amount: Decimal,
        method: str,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        threshold = PAYOUT_THRESHOLDS.get(method.lower(), PAYOUT_THRESHOLDS["default"])
        net_days  = NET_TERMS.get(method.lower(), 7)
        meets     = amount >= threshold

        return {
            "meets_threshold":    meets,
            "requested_amount":   str(amount),
            "minimum_required":   str(threshold),
            "shortfall":          str(max(Decimal("0"), threshold - amount)),
            "method":             method,
            "net_days":           net_days,
            "available_after":    (timezone.now() + timedelta(days=net_days)).isoformat(),
            "reason":             "" if meets else f"Minimum payout for {method} is ${threshold}",
        }

    def get_all_thresholds(self) -> Dict[str, str]:
        return {k: str(v) for k, v in PAYOUT_THRESHOLDS.items()}

    def get_net_terms(self) -> Dict[str, str]:
        return {k: f"NET-{v}" for k, v in NET_TERMS.items()}


# ═══════════════════════════════════════════════════════════════════════════════
# 5. OFFER TARGETING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class OfferTargetingEngine:
    """
    Determines whether an offer should be shown to a user based on:
      - Country (geo targeting)
      - Device type (mobile/desktop/tablet)
      - OS (iOS/Android/Windows)
      - User tier (KYC level, account age, risk score)
      - Daily cap (max completions per day)

    Called by offer_routing and smartlink.
    """

    def match(
        self,
        offer_config: Dict[str, Any],
        user_id: int,
        ip_address: str = "",
        device_type: str = "",
        os_type: str = "",
        country_code: str = "",
    ) -> Dict[str, Any]:
        """
        Return {'eligible': bool, 'reasons': list, 'score': int}.
        Score 100 = perfect match; lower = partial match.
        """
        reasons: List[str] = []
        score = 100

        # ── Geo targeting ──────────────────────────────────────────────
        allowed_countries = offer_config.get("countries", [])
        blocked_countries = offer_config.get("blocked_countries", [])
        if allowed_countries and country_code:
            if country_code.upper() not in [c.upper() for c in allowed_countries]:
                return {"eligible": False, "reasons": [f"Country {country_code} not targeted"], "score": 0}
        if blocked_countries and country_code:
            if country_code.upper() in [c.upper() for c in blocked_countries]:
                return {"eligible": False, "reasons": [f"Country {country_code} is blocked"], "score": 0}

        # ── Device targeting ───────────────────────────────────────────
        allowed_devices = offer_config.get("devices", [])
        if allowed_devices and device_type:
            if device_type.lower() not in [d.lower() for d in allowed_devices]:
                reasons.append(f"Device {device_type} not in target list")
                score -= 30

        # ── OS targeting ───────────────────────────────────────────────
        allowed_os = offer_config.get("os", [])
        if allowed_os and os_type:
            if os_type.lower() not in [o.lower() for o in allowed_os]:
                reasons.append(f"OS {os_type} not in target list")
                score -= 20

        # ── Daily cap check ────────────────────────────────────────────
        daily_cap = offer_config.get("daily_cap", 0)
        if daily_cap > 0:
            cap_key = f"offer_cap:{offer_config.get('id', 'unknown')}:{timezone.now().date()}"
            current = int(cache.get(cap_key) or 0)
            if current >= daily_cap:
                return {"eligible": False, "reasons": ["Daily cap reached"], "score": 0}

        # ── User risk check ────────────────────────────────────────────
        if user_id:
            try:
                from api.fraud_detection.models import UserRiskProfile
                profile = UserRiskProfile.objects.filter(user_id=user_id).first()
                if profile and profile.risk_score >= 80:
                    return {"eligible": False, "reasons": ["User risk score too high"], "score": 0}
                if profile and profile.risk_score >= 50:
                    score -= 10
                    reasons.append("Elevated user risk score")
            except Exception:
                pass

        return {
            "eligible": score > 0,
            "reasons":  reasons,
            "score":    max(0, score),
        }

    def record_impression(self, offer_id: Any) -> None:
        """Increment daily impression count for cap tracking."""
        cap_key = f"offer_cap:{offer_id}:{timezone.now().date()}"
        try:
            cache.incr(cap_key)
        except Exception:
            cache.set(cap_key, 1, timeout=86400)

    def get_targeted_offers(
        self,
        user_id: int,
        offers: List[Dict],
        country_code: str = "",
        device_type: str = "",
        os_type: str = "",
        limit: int = 10,
    ) -> List[Dict]:
        """Filter and rank a list of offers for a user."""
        matched = []
        for offer in offers:
            result = self.match(offer, user_id, country_code=country_code,
                                device_type=device_type, os_type=os_type)
            if result["eligible"]:
                matched.append({**offer, "_targeting_score": result["score"]})
        matched.sort(key=lambda x: x["_targeting_score"], reverse=True)
        return matched[:limit]


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PUBLISHER DASHBOARD VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class PublisherDashboardView(APIView):
    """
    Publisher earnings, conversion, and performance stats.
    GET /api/fraud_detection/publisher/dashboard/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user     = request.user
        days     = int(request.query_params.get("days", 30))
        since    = timezone.now() - timedelta(days=days)
        cache_key = f"publisher_dashboard:{user.id}:{days}"
        cached   = cache.get(cache_key)
        if cached:
            return Response(cached)

        try:
            from api.fraud_detection.models import OfferCompletion
            from django.db.models import Sum, Count, Avg

            completions = OfferCompletion.objects.filter(
                user=user, tracked_at__gte=since
            )
            vc_svc = VirtualCurrencyService()
            th_svc = MinimumThresholdService()

            data = {
                "user_id":          user.id,
                "period_days":      days,
                "total_completions": completions.count(),
                "approved":         completions.filter(status="completed", is_fraud=False).count(),
                "rejected":         completions.filter(is_fraud=True).count(),
                "pending":          completions.filter(status="pending").count(),
                "total_earned_usd": str(
                    completions.filter(status="completed", is_fraud=False)
                    .aggregate(s=Sum("reward_amount"))["s"] or Decimal("0")
                ),
                "coin_balance":     str(vc_svc.get_balance(user.id)),
                "coin_balance_usd": str(vc_svc.get_balance_usd(user.id)),
                "payout_thresholds": th_svc.get_all_thresholds(),
                "net_terms":        th_svc.get_net_terms(),
                "conversion_rate":  _safe_div(
                    completions.filter(status="completed", is_fraud=False).count(),
                    completions.count(),
                ),
                "avg_reward_usd":   str(
                    completions.filter(status="completed", is_fraud=False)
                    .aggregate(a=Avg("reward_amount"))["a"] or Decimal("0")
                ),
            }
            cache.set(cache_key, data, timeout=300)
            return Response(data)
        except Exception as e:
            logger.error("PublisherDashboardView error: %s", e)
            return Response({"error": str(e)}, status=500)


class PublisherRecentActivityView(APIView):
    """
    GET /api/fraud_detection/publisher/activity/?days=7&limit=20
    Returns recent offer completions for the authenticated publisher.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days  = int(request.query_params.get("days", 7))
        limit = min(int(request.query_params.get("limit", 20)), 100)
        since = timezone.now() - timedelta(days=days)
        try:
            from api.fraud_detection.models import OfferCompletion
            from api.fraud_detection.serializers_missing import OfferCompletionSerializer
            qs = OfferCompletion.objects.filter(
                user=request.user, tracked_at__gte=since
            ).order_by("-tracked_at")[:limit]
            return Response({
                "count": qs.count(),
                "results": OfferCompletionSerializer(qs, many=True).data,
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. ADVERTISER PORTAL VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class AdvertiserPortalView(APIView):
    """
    Advertiser campaign performance and fraud rate analytics.
    GET /api/fraud_detection/advertiser/campaigns/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        days  = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)
        cache_key = f"advertiser_portal:{days}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        try:
            from api.fraud_detection.models import OfferCompletion
            from django.db.models import Sum, Count, Avg, F

            by_offer = list(
                OfferCompletion.objects
                .filter(tracked_at__gte=since)
                .values("offer_id")
                .annotate(
                    total=Count("id"),
                    approved=Count("id", filter=models.Q(status="completed", is_fraud=False)),
                    rejected=Count("id", filter=models.Q(is_fraud=True)),
                    total_payout=Sum("reward_amount"),
                    avg_payout=Avg("reward_amount"),
                    fraud_rate=models.ExpressionWrapper(
                        models.Count("id", filter=models.Q(is_fraud=True)) * 100.0 /
                        models.Count("id"),
                        output_field=models.FloatField()
                    ),
                )
                .order_by("-total")[:50]
            )
            data = {
                "period_days":    days,
                "campaigns":      by_offer,
                "total_spend":    str(
                    OfferCompletion.objects.filter(
                        tracked_at__gte=since, status="completed", is_fraud=False
                    ).aggregate(s=Sum("reward_amount"))["s"] or Decimal("0")
                ),
                "overall_fraud_rate": _safe_div(
                    OfferCompletion.objects.filter(tracked_at__gte=since, is_fraud=True).count(),
                    OfferCompletion.objects.filter(tracked_at__gte=since).count(),
                ),
                "generated_at":   timezone.now().isoformat(),
            }
            cache.set(cache_key, data, timeout=600)
            return Response(data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. SURVEY INTEGRATION SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class SurveyIntegrationService:
    """
    Integration layer for survey providers:
      - Pollfish  (GET postback)
    - Lucid     (GET postback)
      - BitLabs  (GET postback, HMAC SHA1)
      - Toluna   (GET postback)

    Normalises different provider schemas into a common OfferCompletion.
    """
    PROVIDERS = {
        "pollfish": {"reward_param": "reward_value",  "uid_param": "publisher_user_id",
                     "survey_param": "survey_class",  "cpi_param": "cpi"},
        "lucid":    {"reward_param": "payout",        "uid_param": "supplier_user_id",
                     "survey_param": "survey_id",      "cpi_param": "cpi"},
        "bitlabs":  {"reward_param": "reward",        "uid_param": "uid",
                     "survey_param": "survey_id",      "cpi_param": "value"},
        "toluna":   {"reward_param": "rewardvalue",   "uid_param": "memberid",
                     "survey_param": "surveyid",       "cpi_param": "cpi"},
    }

    def handle_completion(
        self,
        provider: str,
        params: Dict[str, str],
        secret: str = "",
    ) -> Dict[str, Any]:
        """Process a survey completion postback from any provider."""
        cfg = self.PROVIDERS.get(provider.lower())
        if not cfg:
            return {"success": False, "error": f"Unknown provider: {provider}"}

        # BitLabs uses HMAC-SHA1 verification
        if provider.lower() == "bitlabs" and secret:
            sig = params.get("signature", "")
            query = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "signature")
            expected = hmac.new(secret.encode(), query.encode(), "sha1").hexdigest()
            if not hmac.compare_digest(expected, sig):
                return {"success": False, "error": "signature_invalid"}

        user_ref   = params.get(cfg["uid_param"], "")
        reward_raw = params.get(cfg["reward_param"], "0")
        survey_id  = params.get(cfg["survey_param"], "")

        try:
            reward = Decimal(str(reward_raw))
        except Exception:
            reward = Decimal("0")

        try:
            user = User.objects.get(pk=int(user_ref))
        except (User.DoesNotExist, ValueError):
            return {"success": False, "error": f"user_not_found: {user_ref}"}

        # Dedup
        dedup_key = f"survey_dedup:{provider}:{survey_id}:{user_ref}"
        if cache.get(dedup_key):
            return {"success": True, "duplicate": True}
        cache.set(dedup_key, True, timeout=86400 * 30)

        try:
            from api.fraud_detection.models import OfferCompletion
            completion = OfferCompletion.objects.create(
                user=user,
                status="completed",
                reward_amount=reward,
                completion_data={"provider": provider, "survey_id": survey_id, **params},
                tracked_at=timezone.now(),
            )
            return {"success": True, "completion_id": completion.pk}
        except Exception as e:
            return {"success": False, "error": str(e)}


class SurveyPostbackView(APIView):
    """Handles GET postbacks from all survey providers."""
    permission_classes = [AllowAny]

    def get(self, request, provider: str):
        svc    = SurveyIntegrationService()
        secret = getattr(settings, f"SURVEY_{provider.upper()}_SECRET", "")
        result = svc.handle_completion(provider, request.GET.dict(), secret)
        if result.get("success"):
            return Response("1", content_type="text/plain")
        return Response("0", status=400, content_type="text/plain")


# ═══════════════════════════════════════════════════════════════════════════════
# 9. CONTENT LOCKER SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class ContentLockerService:
    """
    File / link content locker.

    Users must complete at least one offer to receive an unlock token.
    The unlock token is valid for UNLOCK_TTL seconds.

    Usage:
        svc = ContentLockerService()
        locked = svc.is_locked(user_id, locker_id)
        if locked:
            return svc.get_lock_page(locker_id)
        url = svc.get_content(locker_id)
    """
    UNLOCK_TTL   = int(getattr(settings, "CONTENT_LOCKER_UNLOCK_TTL", 3600))  # 1 hour
    LOCK_PREFIX  = "content_lock:"
    TOKEN_PREFIX = "content_token:"

    def is_locked(self, user_id: int, locker_id: str) -> bool:
        token_key = f"{self.TOKEN_PREFIX}{locker_id}:{user_id}"
        return cache.get(token_key) is None

    def unlock(self, user_id: int, locker_id: str) -> str:
        """Generate an unlock token after offer completion. Returns token."""
        token = hashlib.sha256(
            f"{user_id}:{locker_id}:{timezone.now().isoformat()}:{settings.SECRET_KEY}".encode()
        ).hexdigest()
        token_key = f"{self.TOKEN_PREFIX}{locker_id}:{user_id}"
        cache.set(token_key, token, timeout=self.UNLOCK_TTL)
        logger.info("ContentLocker unlocked: user=%s locker=%s", user_id, locker_id)
        return token

    def verify_token(self, user_id: int, locker_id: str, token: str) -> bool:
        token_key = f"{self.TOKEN_PREFIX}{locker_id}:{user_id}"
        stored = cache.get(token_key)
        return stored is not None and hmac.compare_digest(str(stored), token)

    def create_locker(
        self,
        locker_id: str,
        content_url: str,
        title: str,
        required_offers: int = 1,
        creator_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Register a content locker config."""
        config = {
            "locker_id":       locker_id,
            "content_url":     content_url,
            "title":           title,
            "required_offers": required_offers,
            "creator":         creator_user_id,
            "created_at":      timezone.now().isoformat(),
        }
        cache.set(f"{self.LOCK_PREFIX}config:{locker_id}", config, timeout=86400 * 365)
        return config

    def get_locker_config(self, locker_id: str) -> Optional[Dict]:
        return cache.get(f"{self.LOCK_PREFIX}config:{locker_id}")


class ContentLockerView(APIView):
    """
    POST /api/fraud_detection/content-locker/<locker_id>/unlock/
    Verifies user has completed required offers, returns unlock URL.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, locker_id: str):
        """Check lock status for current user."""
        svc    = ContentLockerService()
        locked = svc.is_locked(request.user.id, locker_id)
        config = svc.get_locker_config(locker_id)
        return Response({
            "locker_id": locker_id,
            "locked":    locked,
            "title":     config.get("title", "") if config else "",
            "required_offers": config.get("required_offers", 1) if config else 1,
        })

    def post(self, request, locker_id: str):
        """Attempt unlock — check offer completion then issue token."""
        svc = ContentLockerService()
        config = svc.get_locker_config(locker_id)
        required = config.get("required_offers", 1) if config else 1

        try:
            from api.fraud_detection.models import OfferCompletion
            completed = OfferCompletion.objects.filter(
                user=request.user, status="completed", is_fraud=False
            ).count()
        except Exception:
            completed = 0

        if completed < required:
            return Response({
                "unlocked": False,
                "message":  f"Complete {required - completed} more offer(s) to unlock.",
                "completed": completed,
                "required":  required,
            }, status=403)

        token    = svc.unlock(request.user.id, locker_id)
        content  = config.get("content_url", "") if config else ""
        return Response({"unlocked": True, "token": token, "content_url": content})


# ═══════════════════════════════════════════════════════════════════════════════
# 10. BONUS EVENT SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class BonusEventService:
    """
    Promotional bonus events — flash bonuses, multipliers, seasonal events.

    Admins create bonus events with:
      - Start/end time
      - Multiplier (e.g. 2x coins)
      - Eligible offer types
      - Per-user cap

    Usage:
        svc = BonusEventService()
        multiplier = svc.get_active_multiplier(user_id, offer_type='survey')
        coins = base_coins * multiplier
    """
    EVENT_KEY    = "bonus_events:active"
    USER_CLAIMED = "bonus_claimed:{event_id}:{user_id}"

    def create_event(
        self,
        event_id: str,
        name: str,
        multiplier: float,
        start_time: datetime,
        end_time: datetime,
        offer_types: Optional[List[str]] = None,
        max_claims_per_user: int = 1,
    ) -> Dict[str, Any]:
        event = {
            "id":           event_id,
            "name":         name,
            "multiplier":   multiplier,
            "start":        start_time.isoformat(),
            "end":          end_time.isoformat(),
            "offer_types":  offer_types or [],
            "max_claims":   max_claims_per_user,
            "created_at":   timezone.now().isoformat(),
        }
        events = cache.get(self.EVENT_KEY) or []
        events = [e for e in events if e["id"] != event_id]  # dedup
        events.append(event)
        cache.set(self.EVENT_KEY, events, timeout=86400 * 365)
        logger.info("BonusEvent created: %s multiplier=%sx", name, multiplier)
        return event

    def get_active_events(self) -> List[Dict]:
        now    = timezone.now().isoformat()
        events = cache.get(self.EVENT_KEY) or []
        return [e for e in events if e["start"] <= now <= e["end"]]

    def get_active_multiplier(
        self,
        user_id: int,
        offer_type: str = "",
    ) -> Decimal:
        """Return the highest active multiplier for this user/offer_type combo."""
        multiplier = Decimal("1.0")
        for event in self.get_active_events():
            allowed = event.get("offer_types", [])
            if allowed and offer_type and offer_type not in allowed:
                continue
            claim_key = self.USER_CLAIMED.format(
                event_id=event["id"], user_id=user_id
            )
            claims = int(cache.get(claim_key) or 0)
            if claims < event.get("max_claims", 1):
                multiplier = max(multiplier, Decimal(str(event["multiplier"])))
        return multiplier

    def record_claim(self, user_id: int, event_id: str) -> None:
        key = self.USER_CLAIMED.format(event_id=event_id, user_id=user_id)
        try:
            cache.incr(key)
        except Exception:
            cache.set(key, 1, timeout=86400 * 60)

    def list_events_for_user(self, user_id: int) -> List[Dict]:
        result = []
        for event in self.get_active_events():
            claim_key = self.USER_CLAIMED.format(event_id=event["id"], user_id=user_id)
            claims = int(cache.get(claim_key) or 0)
            result.append({
                **event,
                "user_claims":  claims,
                "claims_left":  max(0, event.get("max_claims", 1) - claims),
                "can_claim":    claims < event.get("max_claims", 1),
            })
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# 11. DRF THROTTLE CLASSES  (rate limiting for all endpoints)
# ═══════════════════════════════════════════════════════════════════════════════

class FraudEndpointRateThrottle(UserRateThrottle):
    """10 req/min for fraud check endpoints."""
    scope = "fraud_check"
    rate  = getattr(settings, "THROTTLE_FRAUD_CHECK", "10/min")


class PostbackRateThrottle(AnonRateThrottle):
    """Postback endpoints: 100/min per IP (network servers send bulk)."""
    scope = "postback"
    rate  = getattr(settings, "THROTTLE_POSTBACK", "100/min")


class PublisherRateThrottle(UserRateThrottle):
    """Publisher dashboard: 60/min."""
    scope = "publisher"
    rate  = getattr(settings, "THROTTLE_PUBLISHER", "60/min")


class HighRiskUserThrottle(SimpleRateThrottle):
    """Dynamic throttle: high-risk users get 3/min instead of normal limits."""
    scope = "high_risk"
    rate  = getattr(settings, "THROTTLE_HIGH_RISK", "3/min")

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        try:
            from api.fraud_detection.models import UserRiskProfile
            profile = UserRiskProfile.objects.filter(user=request.user).first()
            if profile and profile.risk_score >= 70:
                return self.cache_format % {"scope": self.scope, "ident": request.user.pk}
        except Exception:
            pass
        return None  # None = no throttle applied (normal users bypass this)


class BurstProtectionThrottle(AnonRateThrottle):
    """Burst protection for public endpoints: 200/hour per IP."""
    scope = "burst"
    rate  = getattr(settings, "THROTTLE_BURST", "200/hour")


# DRF settings block to add to Django settings.py:
THROTTLE_SETTINGS = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon":        "100/day",
        "user":        "1000/day",
        "fraud_check": "10/min",
        "postback":    "100/min",
        "publisher":   "60/min",
        "high_risk":   "3/min",
        "burst":       "200/hour",
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_div(numerator: int, denominator: int, as_pct: bool = True) -> float:
    if denominator == 0:
        return 0.0
    val = numerator / denominator
    return round(val * 100, 2) if as_pct else round(val, 4)

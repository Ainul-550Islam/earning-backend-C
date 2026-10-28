"""
viewsets_new.py — ViewSets for all newly added earning-platform components.

Registered in urls.py under /api/postback/:
  offers/           OfferViewSet
  offer-clicks/     OfferClickViewSet
  completions/      UserOfferCompletionViewSet
  payment-methods/  PaymentMethodViewSet
  withdrawals/      WithdrawalRequestViewSet
  referral-programs/ ReferralProgramViewSet
  referrals/        UserReferralViewSet
  tiers/            UserTierViewSet
  tier-membership/  UserTierMembershipViewSet
  daily-bonus/      DailyBonusViewSet
  leaderboard/      LeaderboardViewSet
  geo-rules/        GeoTargetingRuleViewSet
  survey-routers/   SurveyRouterViewSet
  sdk-configs/      OfferwallSDKConfigViewSet
"""
from rest_framework import serializers
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .permissions import IsPostbackAdmin
from .models import (
    Offer, OfferCategory, OfferClick, UserOfferCompletion,
    PaymentMethod, WithdrawalRequest,
    ReferralProgram, UserReferral, ReferralCommission,
    UserTier, UserTierMembership,
    DailyBonusConfig, UserLoginStreak,
    LeaderboardEntry,
    GeoTargetingRule,
    SurveyRouter,
    OfferwallSDKConfig,
)
from .serializers import (
    OfferCategorySerializer,
    OfferListSerializer, OfferDetailSerializer,
    OfferClickSerializer,
    UserOfferCompletionSerializer,
    PaymentMethodSerializer, PaymentMethodReadSerializer,
    WithdrawalRequestSerializer, WithdrawalRequestCreateSerializer,
    ReferralProgramSerializer, UserReferralSerializer, ReferralCommissionSerializer,
    UserTierSerializer, UserTierMembershipSerializer,
    DailyBonusConfigSerializer, UserLoginStreakSerializer,
    LeaderboardEntrySerializer,
    GeoTargetingRuleSerializer,
    SurveyRouterSerializer,
    OfferwallSDKConfigSerializer, OfferwallEmbedURLSerializer,
)

logger = logging.getLogger(__name__)


# ── Offers ────────────────────────────────────────────────────────────────────

class OfferCategoryViewSet(viewsets.ModelViewSet):
    queryset = OfferCategory.objects.filter(is_active=True)
    serializer_class = OfferCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["sort_order", "name"]
    ordering = ["sort_order"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsPostbackAdmin()]
        return [IsAuthenticated()]


class OfferViewSet(viewsets.ModelViewSet):
    queryset = Offer.objects.select_related("network", "category").filter(is_active=True)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["network", "category", "difficulty", "device_target", "is_featured"]
    search_fields = ["name", "description", "external_offer_id"]
    ordering_fields = ["points_reward", "payout_usd", "created_at"]
    ordering = ["-is_featured", "-points_reward"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return OfferDetailSerializer
        return OfferListSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsPostbackAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        country = self.request.query_params.get("country")
        if country:
            # Exclude offers that block this country
            from django.db.models import Q
            qs = qs.exclude(countries_blocked__contains=country)
            # If offer has country restrictions, only show matching ones
            qs = qs.filter(
                Q(countries_allowed=[]) | Q(countries_allowed__contains=country)
            )
        return qs

    @action(detail=True, methods=["post"], url_path="click")
    def record_click(self, request, pk=None):
        """Record a user click and return the network redirect URL with click_id."""
        import uuid as _uuid
        offer = self.get_object()
        click_id = str(_uuid.uuid4()).replace("-", "")[:20]
        # Check per-user daily cap before recording click
        from .models import OfferDailyCapCounter
        allowed, cap_reason = OfferDailyCapCounter.check_and_increment(offer, request.user)
        if not allowed:
            return Response({"detail": cap_reason}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        OfferClick.objects.create(
            offer=offer,
            user=request.user,
            click_id=click_id,
            source_ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            country_code=request.data.get("country_code", ""),
            device_type=request.data.get("device_type", "all"),
            idfa=request.data.get("idfa", ""),
            gaid=request.data.get("gaid", ""),
        )
        redirect_url = (offer.offer_url or "").replace("{click_id}", click_id)
        logger.info("Offer click: user=%s offer=%s click_id=%s", request.user.pk, pk, click_id)
        return Response({"click_id": click_id, "redirect_url": redirect_url})

    @action(detail=False, methods=["get"], url_path="featured")
    def featured(self, request):
        """Return featured offers — used for homepage/dashboard highlights."""
        qs = self.get_queryset().filter(is_featured=True)[:20]
        return Response(OfferListSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="by-category/(?P<slug>[^/.]+)")
    def by_category(self, request, slug=None):
        """Return offers for a specific category slug."""
        qs = self.get_queryset().filter(category__slug=slug)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(OfferListSerializer(page, many=True).data)
        return Response(OfferListSerializer(qs, many=True).data)


class OfferClickViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OfferClickSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["offer", "converted", "country_code", "device_type"]
    ordering = ["-clicked_at"]

    def get_queryset(self):
        if getattr(self.request.user, "is_staff", False):
            return OfferClick.objects.select_related("offer").all()
        return OfferClick.objects.select_related("offer").filter(user=self.request.user)


class UserOfferCompletionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserOfferCompletionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["offer", "is_reversed"]
    ordering = ["-completed_at"]

    def get_queryset(self):
        if getattr(self.request.user, "is_staff", False):
            return UserOfferCompletion.objects.select_related("offer").all()
        return UserOfferCompletion.objects.select_related("offer").filter(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """User's earning summary: total completions, total points, by category."""
        from django.db.models import Sum, Count
        qs = self.get_queryset().filter(is_reversed=False)
        agg = qs.aggregate(
            total_completions=Count("id"),
            total_points=Sum("points_awarded"),
        )
        by_category = list(
            qs.values("offer__category__name")
            .annotate(completions=Count("id"), points=Sum("points_awarded"))
            .order_by("-points")
        )
        agg["by_category"] = by_category
        return Response(agg)


# ── Withdrawal ────────────────────────────────────────────────────────────────

class PaymentMethodViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PaymentMethodSerializer
        return PaymentMethodReadSerializer

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Ensure only one default per user
        if serializer.validated_data.get("is_default"):
            PaymentMethod.objects.filter(user=self.request.user).update(is_default=False)
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        method = self.get_object()
        PaymentMethod.objects.filter(user=request.user).update(is_default=False)
        method.is_default = True
        method.save(update_fields=["is_default"])
        return Response({"status": "default updated"})


class WithdrawalRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "payment_method"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return WithdrawalRequestCreateSerializer
        return WithdrawalRequestSerializer

    def get_queryset(self):
        if getattr(self.request.user, "is_staff", False):
            return WithdrawalRequest.objects.select_related("payment_method", "user").all()
        return WithdrawalRequest.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        from decimal import Decimal
        from .models import SiteConfig
        from .utils.fraud_detector import full_fraud_check_on_withdrawal
        from rest_framework.exceptions import PermissionDenied

        cfg = SiteConfig.get()
        points = serializer.validated_data["points_requested"]

        # SiteConfig min withdrawal
        if points < cfg.min_withdrawal_points:
            raise serializers.ValidationError(
                f"Minimum withdrawal is {cfg.min_withdrawal_points} points."
            )

        # Pre-flight fraud check
        fraud = full_fraud_check_on_withdrawal(str(self.request.user.pk))
        if not fraud["passed"]:
            raise PermissionDenied(
                f"Withdrawal blocked (risk score {fraud['risk_score']}). "
                "Contact support if you believe this is an error."
            )

        rate = cfg.points_to_bdt_rate
        amount_bdt = (Decimal(str(points)) * rate).quantize(Decimal("0.01"))
        serializer.save(user=self.request.user, amount_bdt=amount_bdt)

    @action(detail=True, methods=["post"], url_path="approve", permission_classes=[IsPostbackAdmin])
    def approve(self, request, pk=None):
        w = self.get_object()
        if w.status != "pending":
            return Response({"detail": "Only pending requests can be approved."}, status=400)
        from django.utils import timezone as tz
        w.status = "approved"
        w.processed_at = tz.now()
        w.processed_by = request.user
        w.admin_note = request.data.get("admin_note", "")
        w.save(update_fields=["status", "processed_at", "processed_by", "admin_note"])
        logger.info("Withdrawal %s approved by %s", pk, request.user.pk)
        return Response(WithdrawalRequestSerializer(w).data)

    @action(detail=True, methods=["post"], url_path="reject", permission_classes=[IsPostbackAdmin])
    def reject(self, request, pk=None):
        w = self.get_object()
        if w.status not in ("pending", "approved"):
            return Response({"detail": "Cannot reject in current status."}, status=400)
        from django.utils import timezone as tz
        w.status = "rejected"
        w.processed_at = tz.now()
        w.processed_by = request.user
        w.rejection_reason = request.data.get("rejection_reason", "")
        w.save(update_fields=["status", "processed_at", "processed_by", "rejection_reason"])
        return Response(WithdrawalRequestSerializer(w).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        w = self.get_object()
        if w.user != request.user:
            return Response({"detail": "Forbidden."}, status=403)
        if w.status != "pending":
            return Response({"detail": "Only pending requests can be cancelled."}, status=400)
        w.status = "cancelled"
        w.save(update_fields=["status"])
        return Response({"status": "cancelled"})

    @action(detail=False, methods=["get"], url_path="stats", permission_classes=[IsPostbackAdmin])
    def stats(self, request):
        """Admin: aggregated withdrawal stats by status."""
        from django.db.models import Sum, Count
        data = (
            WithdrawalRequest.objects.values("status")
            .annotate(count=Count("id"), total_bdt=Sum("amount_bdt"))
            .order_by("status")
        )
        return Response(list(data))


# ── Referral ──────────────────────────────────────────────────────────────────

class ReferralProgramViewSet(viewsets.ModelViewSet):
    queryset = ReferralProgram.objects.filter(is_active=True)
    serializer_class = ReferralProgramSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsPostbackAdmin()]
        return [IsAuthenticated()]


class UserReferralViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserReferralSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserReferral.objects.filter(referrer=self.request.user).select_related(
            "program", "referee"
        )

    @action(detail=False, methods=["get"], url_path="my-code")
    def my_code(self, request):
        """Return the user's own referral code (or generate one)."""
        import hashlib
        code = hashlib.md5(f"ref_{request.user.pk}".encode()).hexdigest()[:8].upper()
        return Response({"referral_code": code, "referral_url": f"/join/?ref={code}"})

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Summary of a user's referral earnings."""
        from django.db.models import Sum, Count
        qs = UserReferral.objects.filter(referrer=request.user)
        agg = qs.aggregate(
            total_referrals=Count("id"),
            active_referrals=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(is_active=True)),
            total_commission=Sum("total_commission_earned"),
        )
        return Response(agg)


# ── User Tier ─────────────────────────────────────────────────────────────────

class UserTierViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserTier.objects.all()
    serializer_class = UserTierSerializer
    permission_classes = [IsAuthenticated]
    ordering = ["sort_order"]


class UserTierMembershipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserTierMembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self.request.user, "is_staff", False):
            return UserTierMembership.objects.select_related("tier").all()
        return UserTierMembership.objects.filter(user=self.request.user).select_related("tier")

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """Return the authenticated user's current tier and progress."""
        membership, _ = UserTierMembership.objects.get_or_create(
            user=request.user,
            defaults={"tier": UserTier.objects.order_by("sort_order").first()},
        )
        next_tier = (
            UserTier.objects.filter(
                min_lifetime_points__gt=membership.lifetime_points
            ).order_by("min_lifetime_points").first()
        )
        data = UserTierMembershipSerializer(membership).data
        data["next_tier"] = UserTierSerializer(next_tier).data if next_tier else None
        if next_tier:
            needed = next_tier.min_lifetime_points - membership.lifetime_points
            data["points_to_next_tier"] = needed
        return Response(data)


# ── Daily Bonus ───────────────────────────────────────────────────────────────

class DailyBonusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyBonusConfig.objects.all()
    serializer_class = DailyBonusConfigSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="streak")
    def streak(self, request):
        """Return the authenticated user's current streak status."""
        streak, _ = UserLoginStreak.objects.get_or_create(user=request.user)
        return Response(UserLoginStreakSerializer(streak).data)

    @action(detail=False, methods=["post"], url_path="claim")
    def claim(self, request):
        """Claim today's daily login bonus."""
        streak, _ = UserLoginStreak.objects.get_or_create(user=request.user)
        points = streak.claim_daily_bonus()
        if points == 0:
            return Response(
                {"detail": "Already claimed today.", "claimed": False, "points": 0},
                status=status.HTTP_200_OK,
            )
        logger.info("Daily bonus claimed: user=%s points=%d streak=%d",
                    request.user.pk, points, streak.current_streak)
        return Response({
            "claimed": True,
            "points": points,
            "current_streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
        })


# ── Leaderboard ───────────────────────────────────────────────────────────────

class LeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaderboardEntrySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["period"]

    def get_queryset(self):
        from django.db.models import Max
        period = self.request.query_params.get("period", "weekly")
        latest = LeaderboardEntry.objects.filter(period=period).aggregate(
            latest=Max("period_start")
        )["latest"]
        if not latest:
            return LeaderboardEntry.objects.none()
        return LeaderboardEntry.objects.filter(
            period=period, period_start=latest
        ).order_by("rank")[:100]

    @action(detail=False, methods=["get"], url_path="my-rank")
    def my_rank(self, request):
        """Return the authenticated user's rank in the current period."""
        period = request.query_params.get("period", "weekly")
        from django.db.models import Max
        latest = LeaderboardEntry.objects.filter(period=period).aggregate(
            latest=Max("period_start")
        )["latest"]
        entry = LeaderboardEntry.objects.filter(
            user=request.user, period=period, period_start=latest
        ).first()
        if not entry:
            return Response({"rank": None, "message": "Not yet ranked."})
        return Response(LeaderboardEntrySerializer(entry).data)


# ── Geo Targeting ─────────────────────────────────────────────────────────────

class GeoTargetingRuleViewSet(viewsets.ModelViewSet):
    queryset = GeoTargetingRule.objects.select_related("network").all()
    serializer_class = GeoTargetingRuleSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["network", "country_code", "action", "is_active"]

    @action(detail=False, methods=["post"], url_path="check")
    def check(self, request):
        """Check if a country_code is allowed for a given network."""
        network_id = request.data.get("network")
        country_code = request.data.get("country_code", "")
        rules = GeoTargetingRule.objects.filter(
            network_id=network_id, is_active=True
        ).order_by("-priority")
        action_result = "allow"
        multiplier = 1.0
        for rule in rules:
            if rule.country_code == country_code or rule.country_code == "*":
                action_result = rule.action
                multiplier = float(rule.payout_multiplier)
                break
        return Response({
            "country_code": country_code,
            "action": action_result,
            "payout_multiplier": multiplier,
            "is_allowed": action_result != "block",
        })


# ── Survey Router ─────────────────────────────────────────────────────────────

class SurveyRouterViewSet(viewsets.ModelViewSet):
    queryset = SurveyRouter.objects.select_related("network").filter(is_active=True)
    serializer_class = SurveyRouterSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsPostbackAdmin()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"], url_path="route")
    def route(self, request):
        """
        Return the best survey provider URL for this user's country + device.
        Waterfalls through providers in priority order.
        """
        country = request.query_params.get("country_code", "")
        device = request.query_params.get("device_type", "all")
        user_id = str(request.user.pk)
        sub_id1 = request.query_params.get("sub_id1", "")

        available = [
            r for r in self.get_queryset()
            if r.is_available_for(country, device)
        ]
        if not available:
            return Response(
                {"detail": "No surveys available for your country/device."},
                status=status.HTTP_404_NOT_FOUND,
            )
        chosen = available[0]
        redirect_url = chosen.build_redirect_url(user_id, country, device, sub_id1)
        return Response({
            "provider_key": chosen.provider_key,
            "redirect_url": redirect_url,
            "min_cpi_usd": chosen.min_cpi_usd,
        })


# ── Offerwall SDK ─────────────────────────────────────────────────────────────

class OfferwallSDKConfigViewSet(viewsets.ModelViewSet):
    queryset = OfferwallSDKConfig.objects.select_related("network").filter(is_active=True)
    serializer_class = OfferwallSDKConfigSerializer
    permission_classes = [IsPostbackAdmin]

    @action(detail=True, methods=["post"], url_path="embed-url")
    def embed_url(self, request, pk=None):
        """Generate a signed iframe embed URL for this SDK config."""
        sdk_config = self.get_object()
        serializer = OfferwallEmbedURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        url = sdk_config.generate_embed_url(
            user_id=serializer.validated_data["user_id"],
            country_code=serializer.validated_data.get("country_code", ""),
            device_type=serializer.validated_data.get("device_type", "all"),
            sub_id1=serializer.validated_data.get("sub_id1", ""),
        )
        return Response({"embed_url": url, "expires_in": sdk_config.session_ttl_seconds})

    @action(detail=False, methods=["post"], url_path="generate-key", permission_classes=[IsPostbackAdmin])
    def generate_key(self, request):
        """Generate a new sdk_key + sdk_secret pair."""
        import secrets
        sdk_key = secrets.token_urlsafe(16)
        sdk_secret = secrets.token_urlsafe(32)
        return Response({"sdk_key": sdk_key, "sdk_secret": sdk_secret})


# ══════════════════════════════════════════════════════════════════════════════
# ROUND-2 VIEWSETS — SiteConfig, CurrencyRate, ManualPointAdjustment,
#                    FCMDevice, OfferImpression, OfferwallImpression
# ══════════════════════════════════════════════════════════════════════════════

from .serializers import (
    SiteConfigSerializer, CurrencyRateSerializer,
    ManualPointAdjustmentSerializer, ManualPointAdjustmentCreateSerializer,
    FCMDeviceSerializer, OfferImpressionSerializer,
)
from .models import (
    SiteConfig, CurrencyRate, ManualPointAdjustment,
    FCMDevice, OfferImpression,
)


class SiteConfigViewSet(viewsets.ViewSet):
    """
    Singleton site config — only GET (read) and PATCH (update).
    Only admins can write.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """GET /api/postback/site-config/ — returns current config."""
        cfg = SiteConfig.get()
        return Response(SiteConfigSerializer(cfg).data)

    def partial_update(self, request, pk=None):
        """PATCH /api/postback/site-config/1/ — update settings."""
        if not request.user.is_staff:
            return Response({"detail": "Admin only."}, status=403)
        cfg = SiteConfig.get()
        serializer = SiteConfigSerializer(cfg, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        logger.info("SiteConfig updated by %s: %s", request.user, request.data.keys())
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="public")
    def public(self, request):
        """Return non-sensitive config visible to all authenticated users."""
        cfg = SiteConfig.get()
        return Response({
            "points_to_bdt_rate": str(cfg.points_to_bdt_rate),
            "min_withdrawal_points": cfg.min_withdrawal_points,
            "maintenance_mode": cfg.maintenance_mode,
            "features": {
                "referral": cfg.referral_program_enabled,
                "daily_bonus": cfg.daily_bonus_enabled,
                "leaderboard": cfg.leaderboard_enabled,
                "survey_router": cfg.survey_router_enabled,
                "offerwall": cfg.offerwall_enabled,
            },
        })


class CurrencyRateViewSet(viewsets.ModelViewSet):
    """
    Historical points↔BDT rate log.
    Admins POST a new row to change the rate (old rows kept for audit).
    """
    queryset = CurrencyRate.objects.all()
    serializer_class = CurrencyRateSerializer
    permission_classes = [IsPostbackAdmin]
    ordering = ["-effective_from"]

    def perform_create(self, serializer):
        instance = serializer.save(set_by=self.request.user)
        # Sync new rate into SiteConfig singleton
        cfg = SiteConfig.get()
        cfg.points_to_bdt_rate = instance.points_to_bdt
        cfg.points_to_usd_rate = instance.points_to_usd
        cfg.updated_by = self.request.user
        cfg.save(update_fields=["points_to_bdt_rate", "points_to_usd_rate", "updated_by", "updated_at"])
        logger.info("Currency rate updated by %s: 1pt = %s BDT", self.request.user, instance.points_to_bdt)

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        """Return the most recently active rate."""
        latest = CurrencyRate.objects.order_by("-effective_from").first()
        if not latest:
            cfg = SiteConfig.get()
            return Response({
                "points_to_bdt": str(cfg.points_to_bdt_rate),
                "points_to_usd": str(cfg.points_to_usd_rate),
                "source": "site_config_default",
            })
        return Response(CurrencyRateSerializer(latest).data)


class ManualPointAdjustmentViewSet(viewsets.ModelViewSet):
    """
    Admin-only manual credit / debit of user points.
    Creates a ManualPointAdjustment record and fires the wallet signal.
    """
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["user", "adjustment_type", "reason"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return ManualPointAdjustmentCreateSerializer
        return ManualPointAdjustmentSerializer

    def get_queryset(self):
        return ManualPointAdjustment.objects.select_related("user", "performed_by").all()

    def perform_create(self, serializer):
        instance = serializer.save(performed_by=self.request.user)
        # Fire wallet credit/debit signal
        try:
            from .adapters.wallet_bridge import credit_wallet_for_postback
            from .signals import postback_manual_adjustment
            postback_manual_adjustment.send(
                sender=ManualPointAdjustment,
                instance=instance,
            )
        except Exception as exc:
            logger.error("ManualPointAdjustment wallet signal failed: %s", exc)
        logger.info(
            "Manual point adjustment: admin=%s user=%s type=%s points=%d",
            self.request.user.pk, instance.user_id,
            instance.adjustment_type, instance.points,
        )

    @action(detail=False, methods=["get"], url_path="user-history/(?P<user_id>[^/.]+)")
    def user_history(self, request, user_id=None):
        """List all manual adjustments for a specific user."""
        qs = self.get_queryset().filter(user_id=user_id)
        from django.db.models import Sum
        total_credited = qs.filter(adjustment_type="credit").aggregate(
            total=Sum("points")
        )["total"] or 0
        total_debited = qs.filter(adjustment_type="debit").aggregate(
            total=Sum("points")
        )["total"] or 0
        return Response({
            "user_id": user_id,
            "total_credited": total_credited,
            "total_debited": total_debited,
            "net_adjustment": total_credited - total_debited,
            "adjustments": ManualPointAdjustmentSerializer(qs, many=True).data,
        })


class FCMDeviceViewSet(viewsets.ModelViewSet):
    """
    FCM push token registration. Users register their devices here.
    Supports Android (FCM), iOS (APNs via FCM), and Web Push.
    """
    serializer_class = FCMDeviceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["platform", "is_active"]

    def get_queryset(self):
        return FCMDevice.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()  # Upsert handled in serializer.create()

    @action(detail=False, methods=["post"], url_path="deactivate-all")
    def deactivate_all(self, request):
        """Deactivate all devices for logout / account-switch."""
        updated = FCMDevice.objects.filter(user=request.user, is_active=True).update(
            is_active=False
        )
        return Response({"deactivated": updated})

    @action(detail=True, methods=["post"], url_path="test-push", permission_classes=[IsPostbackAdmin])
    def test_push(self, request, pk=None):
        """Admin: send a test push notification to this device."""
        device = self.get_object()
        return Response({
            "message": "Test push queued.",
            "device_id": str(device.id),
            "platform": device.platform,
        })


class OfferImpressionViewSet(viewsets.ModelViewSet):
    """
    Records offer impressions (shown in wall). Used for CTR analytics.
    POST: record impression. GET: admin analytics view.
    """
    serializer_class = OfferImpressionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["offer", "country_code", "device_type"]
    ordering = ["-shown_at"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsPostbackAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if getattr(self.request.user, "is_staff", False):
            return OfferImpression.objects.select_related("offer").all()
        return OfferImpression.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            country_code=self.request.data.get("country_code", ""),
            device_type=self.request.data.get("device_type", ""),
        )

    @action(detail=False, methods=["get"], url_path="ctr-stats", permission_classes=[IsPostbackAdmin])
    def ctr_stats(self, request):
        """CTR (click-through-rate) per offer: impressions / clicks."""
        from django.db.models import Count, F
        from django.db.models.functions import Round
        stats = (
            OfferImpression.objects
            .values("offer__name", "offer_id")
            .annotate(
                impressions=Count("id"),
                clicks=Count("offer__clicks"),
            )
            .order_by("-impressions")[:50]
        )
        return Response(list(stats))

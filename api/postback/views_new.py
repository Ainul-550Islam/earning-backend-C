"""
views_new.py — Utility views for new earning-platform features.

  GET  /api/postback/postback-url-builder/   → PostbackURLBuilderView
  GET  /api/postback/offerwall/embed/        → OfferwallEmbedView
  GET  /api/postback/daily-bonus/schedule/   → DailyBonusScheduleView
  GET  /api/postback/survey/redirect/        → SurveyRouterRedirectView
"""
import logging
from django.http import JsonResponse, HttpResponseRedirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .permissions import IsPostbackAdmin

logger = logging.getLogger(__name__)


class PostbackURLBuilderView(APIView):
    """
    Generate a ready-to-paste postback URL for a given NetworkPostbackConfig.

    CPAlead, Offertoro, and AdGate all provide this in their publisher dashboard.
    Mirrors NetworkPostbackConfig.field_mapping + callback_url macros.

    GET /api/postback/postback-url-builder/?network_key=cpalead
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import NetworkPostbackConfig
        network_key = request.query_params.get("network_key")
        if not network_key:
            return Response({"detail": "network_key is required."}, status=400)
        try:
            network = NetworkPostbackConfig.objects.get(network_key=network_key)
        except NetworkPostbackConfig.DoesNotExist:
            return Response({"detail": f"Network '{network_key}' not found."}, status=404)

        base_url = request.build_absolute_uri(
            f"/api/postback/receive/{network_key}/"
        )
        # Build macro params from field_mapping
        mapping = network.field_mapping or {}
        macro_map = {
            "lead_id": mapping.get("lead_id", "lead_id"),
            "offer_id": mapping.get("offer_id", "offer_id"),
            "user_id": mapping.get("user_id", "user_id"),
            "payout": mapping.get("payout", "payout"),
            "currency": mapping.get("currency", "currency"),
            "transaction_id": mapping.get("transaction_id", "transaction_id"),
            "goal_id": mapping.get("goal_id", "goal_id"),
            "sub_id1": mapping.get("sub_id1", "aff_sub1"),
            "sub_id2": mapping.get("sub_id2", "aff_sub2"),
            "sub_id3": mapping.get("sub_id3", "aff_sub3"),
            "country_code": mapping.get("country_code", "country"),
        }
        # Build the GET postback URL with macro placeholders
        params = "&".join(
            f"{field}={{{macro}}}"
            for field, macro in macro_map.items()
        )
        get_url = f"{base_url}?{params}"
        # Also include the signature param if HMAC is configured
        if network.signature_algorithm != "none":
            get_url += "&sig={signature}"

        # POST variant instructions
        post_url = base_url

        # S2S outbound template (if configured)
        s2s_template = network.callback_url or ""

        return Response({
            "network_key": network_key,
            "network_name": network.name,
            "signature_algorithm": network.signature_algorithm,
            "postback_urls": {
                "GET": get_url,
                "POST": post_url,
            },
            "s2s_callback_template": s2s_template,
            "macro_reference": {
                "{lead_id}": "Unique conversion ID from the network",
                "{offer_id}": "Offer / task ID",
                "{user_id}": "Your user's ID (sub_id1 in most networks)",
                "{payout}": "Commission in USD",
                "{currency}": "Payout currency code",
                "{transaction_id}": "Network-side transaction ID",
                "{goal_id}": "Conversion goal / event type",
                "{sub_id1}–{sub_id3}": "Pass-through tracking params",
                "{country_code}": "User's country ISO-2",
                "{signature}": "HMAC-SHA256 signature (auto-verified)",
            },
            "required_fields": network.required_fields or [],
            "ip_whitelist": network.ip_whitelist or [],
        })


class OfferwallEmbedView(APIView):
    """
    Return the signed iframe embed URL for a given SDK config + user.

    OGAds, AdGate, Offertoro, and Monlix all provide an iframe embed.

    GET /api/postback/offerwall/embed/?sdk_key=XYZ&user_id=123&country=BD&device=mobile
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import OfferwallSDKConfig
        sdk_key = request.query_params.get("sdk_key")
        if not sdk_key:
            return Response({"detail": "sdk_key is required."}, status=400)
        try:
            sdk = OfferwallSDKConfig.objects.select_related("network").get(
                sdk_key=sdk_key, is_active=True
            )
        except OfferwallSDKConfig.DoesNotExist:
            return Response({"detail": "SDK config not found or inactive."}, status=404)

        user_id = request.query_params.get("user_id", str(request.user.pk))
        country_code = request.query_params.get("country", "")
        device_type = request.query_params.get("device", "all")
        sub_id1 = request.query_params.get("sub_id1", "")

        # Check domain is allowed
        referer = request.META.get("HTTP_REFERER", "")
        if sdk.allowed_domains:
            import urllib.parse
            referer_domain = urllib.parse.urlparse(referer).netloc
            if referer_domain and referer_domain not in sdk.allowed_domains:
                logger.warning("Offerwall embed blocked for domain: %s", referer_domain)
                return Response({"detail": "Domain not authorised."}, status=403)

        embed_url = sdk.generate_embed_url(user_id, country_code, device_type, sub_id1)

        return Response({
            "embed_url": request.build_absolute_uri(embed_url),
            "sdk_key": sdk_key,
            "theme": sdk.theme,
            "primary_color": sdk.primary_color,
            "show_search": sdk.show_search,
            "show_categories": sdk.show_categories,
            "session_ttl_seconds": sdk.session_ttl_seconds,
            "iframe_html": (
                f'<iframe src="{request.build_absolute_uri(embed_url)}" '
                f'width="100%" height="600" frameborder="0" '
                f'style="border:none;overflow:hidden" scrolling="no"></iframe>'
            ),
        })


class DailyBonusScheduleView(APIView):
    """
    Return the full daily bonus schedule so the frontend can render
    the streak reward calendar (day 1 → N, day 7 → milestone, etc.).

    GET /api/postback/daily-bonus/schedule/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import DailyBonusConfig, UserLoginStreak
        from .serializers import DailyBonusConfigSerializer, UserLoginStreakSerializer

        schedule = DailyBonusConfig.objects.all().order_by("day_number")
        streak, _ = UserLoginStreak.objects.get_or_create(user=request.user)
        from django.utils.timezone import localdate
        today = localdate()

        return Response({
            "schedule": DailyBonusConfigSerializer(schedule, many=True).data,
            "user_streak": UserLoginStreakSerializer(streak).data,
            "can_claim_today": streak.last_claim_date != today,
            "today": today.isoformat(),
        })


class SurveyRouterRedirectView(APIView):
    """
    Find the best survey provider for this user and redirect them.

    Mirrors AdGate and Offertoro survey routing.

    GET /api/postback/survey/redirect/?country=BD&device=mobile&sub_id1=USER123
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import SurveyRouter
        country = request.query_params.get("country_code", "")
        device = request.query_params.get("device_type", "all")
        sub_id1 = request.query_params.get("sub_id1", str(request.user.pk))
        user_id = str(request.user.pk)

        available = [
            r for r in SurveyRouter.objects.filter(is_active=True).order_by("-priority")
            if r.is_available_for(country, device)
        ]

        if not available:
            return Response(
                {"detail": "No surveys available for your country or device type."},
                status=404,
            )

        chosen = available[0]
        redirect_url = chosen.build_redirect_url(user_id, country, device, sub_id1)
        logger.info(
            "Survey redirect: user=%s provider=%s country=%s device=%s",
            request.user.pk, chosen.provider_key, country, device,
        )
        return HttpResponseRedirect(redirect_url)

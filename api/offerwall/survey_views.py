"""
api/offerwall/survey_views.py

Survey Provider API — exposes SurveyProviderService (CPX Research,
BitLabs, Pollfish) which had FULL logic but ZERO API exposure.

Endpoints:
  GET  /api/offerwall/surveys/                  → list surveys for user
  GET  /api/offerwall/surveys/providers/        → list available survey providers
  GET  /api/offerwall/surveys/config/           → JS SDK config per provider
  POST /api/offerwall/surveys/webhooks/cpx/     → CPX Research postback
  POST /api/offerwall/surveys/webhooks/bitlabs/ → BitLabs postback
  POST /api/offerwall/surveys/webhooks/pollfish/→ Pollfish postback
"""
import logging
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: resolve OfferProvider by provider_type
# ─────────────────────────────────────────────────────────────────────────────

def _get_provider(provider_type: str):
    """Return active OfferProvider for survey type or None."""
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.filter(
        provider_type=provider_type, status="active"
    ).first()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Survey List — fetch from all connected survey providers
# ─────────────────────────────────────────────────────────────────────────────

class SurveyListView(APIView):
    """
    GET /api/offerwall/surveys/
        ?provider=cpx            filter by provider (cpx|bitlabs|pollfish)
        ?country=BD              ISO 2-letter country code
        ?language=en

    Fetches surveys from all active survey providers and returns a merged list.
    Calls SurveyProviderService.fetch_surveys(user, country, language).

    Returns::
        {
          "count": 12,
          "providers_queried": ["cpx", "bitlabs"],
          "results": [
            {
              "id": "...", "title": "...", "loi": 5,
              "payout": "0.35", "reward": "0.25",
              "currency": "Points", "ir": 65.0, "provider": "cpx",
              "click_url": "https://..."
            }
          ]
        }
    """
    permission_classes = [IsAuthenticated]

    SURVEY_PROVIDERS = ["cpx", "bitlabs", "pollfish"]

    def get(self, request):
        # B2B plan gate: allow_survey_offers must be True
        if hasattr(request.user, 'b2b_client'):
            client = request.user.b2b_client
            if not client.has_feature('survey_offers'):
                return Response(
                    {'error': 'plan_limit',
                     'detail': 'Survey offers require Pro plan or above.',
                     'upgrade_url': '/api/offerwall/b2b/upgrade/'},
                    status=status.HTTP_403_FORBIDDEN)

        from api.offerwall.services.survey.SurveyProviderService import (
            SurveyProviderFactory,
        )

        provider_filter = request.query_params.get("provider")
        country         = request.query_params.get("country", "US").upper()
        language        = request.query_params.get("language", "en").lower()

        provider_types = (
            [provider_filter] if provider_filter else self.SURVEY_PROVIDERS
        )
        provider_types = [p for p in provider_types
                          if SurveyProviderFactory.is_supported(p)]

        all_surveys      = []
        providers_queried = []
        errors           = {}

        for ptype in provider_types:
            provider_obj = _get_provider(ptype)
            if not provider_obj:
                continue

            try:
                svc = SurveyProviderFactory.create(provider_obj)
                surveys = svc.fetch_surveys(
                    user=request.user,
                    country=country,
                    language=language,
                )

                # Add click_url to each survey
                for s in surveys:
                    try:
                        s["click_url"] = svc.build_survey_url(s, request.user)
                    except Exception:
                        s["click_url"] = ""
                    # Serialise Decimal → str
                    for key in ("payout", "reward"):
                        if key in s and isinstance(s[key], Decimal):
                            s[key] = str(s[key])

                all_surveys.extend(surveys)
                providers_queried.append(ptype)

            except Exception as e:
                logger.error(f"[SurveyList] {ptype} fetch failed: {e}")
                errors[ptype] = str(e)

        # Sort by payout descending
        try:
            all_surveys.sort(
                key=lambda x: float(x.get("payout", 0) or 0),
                reverse=True,
            )
        except Exception:
            pass

        response_data = {
            "count":             len(all_surveys),
            "providers_queried": providers_queried,
            "results":           all_surveys,
        }
        if errors:
            response_data["provider_errors"] = errors

        return Response(response_data)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Survey Provider List — which providers are connected
# ─────────────────────────────────────────────────────────────────────────────

class SurveyProviderListView(APIView):
    """
    GET /api/offerwall/surveys/providers/

    Lists which survey providers are connected (have an active OfferProvider row).
    Exposes SurveyProviderFactory.supported_types().
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.offerwall.services.survey.SurveyProviderService import (
            SurveyProviderFactory,
        )
        from api.offerwall.models import OfferProvider

        supported = SurveyProviderFactory.supported_types()
        results   = []

        for ptype in supported:
            provider_obj = _get_provider(ptype)
            results.append({
                "provider_type": ptype,
                "is_connected":  provider_obj is not None,
                "provider_id":   str(provider_obj.id) if provider_obj else None,
                "provider_name": provider_obj.name if provider_obj else None,
                "status":        provider_obj.status if provider_obj else "not_configured",
            })

        return Response({
            "supported_types": supported,
            "providers":       results,
        })


# ─────────────────────────────────────────────────────────────────────────────
# 3. Survey SDK Config — JS SDK configuration per provider
# ─────────────────────────────────────────────────────────────────────────────

class SurveySDKConfigView(APIView):
    """
    GET /api/offerwall/surveys/config/?provider=pollfish

    Returns SDK configuration JSON for embedding surveys in the frontend.
    Uses SurveyProviderService.fetch_surveys() and build_survey_url().

    Particularly useful for Pollfish which is SDK-driven.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from api.offerwall.services.survey.SurveyProviderService import (
            SurveyProviderFactory,
        )

        provider_type = request.query_params.get("provider", "pollfish")

        if not SurveyProviderFactory.is_supported(provider_type):
            return Response(
                {
                    "error": "unsupported_provider",
                    "valid": SurveyProviderFactory.supported_types(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider_obj = _get_provider(provider_type)
        if not provider_obj:
            return Response(
                {"error": "provider_not_configured",
                 "detail": f"No active OfferProvider found for type '{provider_type}'"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            svc = SurveyProviderFactory.create(provider_obj)
            surveys = svc.fetch_surveys(
                user=request.user,
                country=request.query_params.get("country", "US"),
                language=request.query_params.get("language", "en"),
            )

            # Build SDK config from first survey (SDK-type providers like Pollfish
            # embed their config in the survey object)
            sdk_config = {}
            if surveys and surveys[0].get("sdk_config"):
                sdk_config = surveys[0]["sdk_config"]

            return Response({
                "provider":   provider_type,
                "sdk_config": sdk_config,
                "surveys":    [
                    {
                        "id":       s.get("id"),
                        "title":    s.get("title"),
                        "loi":      s.get("loi"),
                        "payout":   str(s.get("payout", "0")),
                        "reward":   str(s.get("reward", "0")),
                        "currency": s.get("currency", "Points"),
                        "click_url": svc.build_survey_url(s, request.user),
                    }
                    for s in surveys[:20]
                ],
            })

        except Exception as e:
            logger.error(f"[SurveySDK] {provider_type} config failed: {e}")
            return Response(
                {"error": "provider_error", "detail": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Survey Webhooks — one per provider
#    SurveyProviderService.verify_postback() + parse_postback()
#    → OfferwallIntegrationService.process_conversion()
# ─────────────────────────────────────────────────────────────────────────────

class BaseSurveyWebhookView(View):
    """
    Base class for survey provider postback webhooks.
    Each subclass sets provider_type and is registered at its own URL.

    Flow:
      1. verify_postback(data)    → raises or returns True
      2. parse_postback(data)     → { user_id, survey_id, payout, status, tx_id }
      3. OfferwallIntegrationService.process_conversion(...)
      4. Return provider-expected response string
    """
    provider_type = "unknown"
    success_body  = "1"
    error_body    = "0"

    def get_or_post(self, request):
        from api.offerwall.services.survey.SurveyProviderService import (
            SurveyProviderFactory,
        )
        from api.offerwall.services.OfferwallIntegrationService import (
            OfferwallIntegrationService,
        )
        from api.offerwall.utils.RewardCalculator import RewardCalculator
        from django.contrib.auth import get_user_model

        User = get_user_model()

        provider_obj = _get_provider(self.provider_type)
        if not provider_obj:
            logger.error(f"[SurveyWebhook] provider not found: {self.provider_type}")
            return HttpResponse(self.error_body, status=400)

        try:
            svc = SurveyProviderFactory.create(provider_obj)

            # Merge GET + POST params
            data = {**request.GET.dict(), **request.POST.dict()}

            # Verify signature
            try:
                svc.verify_postback(dict(data))  # pass copy (verify may pop keys)
            except Exception as e:
                logger.warning(f"[SurveyWebhook:{self.provider_type}] sig fail: {e}")
                return HttpResponse(self.error_body, status=401)

            # Parse to canonical dict
            parsed = svc.parse_postback(data)
            user_id   = parsed.get("user_id")
            payout    = parsed.get("payout", Decimal("0"))
            cb_status = parsed.get("status", "pending")
            tx_id     = parsed.get("tx_id", "")
            survey_id = parsed.get("survey_id", "")

            if not user_id:
                return HttpResponse(self.error_body, status=400)

            try:
                user = User.objects.get(id=int(user_id))
            except (User.DoesNotExist, ValueError):
                logger.warning(f"[SurveyWebhook] user not found: {user_id}")
                return HttpResponse(self.error_body, status=400)

            # Try to find an Offer matching the survey (best-effort)
            offer = self._find_offer(provider_obj, survey_id)

            # Calculate reward
            reward = Decimal("0")
            if offer:
                calc = RewardCalculator(offer=offer, provider=provider_obj)
                reward = calc.calculate_user_reward(payout)
            else:
                # No matching offer → use provider revenue_share directly
                revenue_share = provider_obj.revenue_share / Decimal("100")
                reward = (Decimal(str(payout)) * revenue_share).quantize(
                    Decimal("0.000001")
                )

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                payout_amount=Decimal(str(payout)),
                reward_amount=reward,
                external_tx_id=tx_id,
                conversion_id=f"{self.provider_type}_{tx_id or survey_id}_{user_id}",
                postback_data=data,
                auto_approve=(cb_status == "approved"),
            )

            logger.info(
                f"[SurveyWebhook:{self.provider_type}] "
                f"user={user_id} tx={tx_id} created={result.get('created')}"
            )
            return HttpResponse(self.success_body, status=200)

        except Exception as e:
            logger.exception(f"[SurveyWebhook:{self.provider_type}] error: {e}")
            return HttpResponse(self.error_body, status=400)

    def _find_offer(self, provider_obj, survey_id: str):
        """Try to match survey_id to an Offer.external_offer_id."""
        if not survey_id:
            return None
        from api.offerwall.models import Offer
        return Offer.objects.filter(
            provider=provider_obj,
            external_offer_id=str(survey_id),
        ).first()

    def get(self, request):
        return self.get_or_post(request)

    def post(self, request):
        return self.get_or_post(request)


@method_decorator(csrf_exempt, name="dispatch")
class CPXResearchWebhookView(BaseSurveyWebhookView):
    """
    GET /api/offerwall/surveys/webhooks/cpx/

    CPX Research sends GET postbacks.
    Signature: MD5(app_id + subid + secret)
    """
    provider_type = "cpx"
    success_body  = "OK"
    error_body    = "ERROR"


@method_decorator(csrf_exempt, name="dispatch")
class BitLabsWebhookView(BaseSurveyWebhookView):
    """
    POST /api/offerwall/surveys/webhooks/bitlabs/

    BitLabs sends POST postbacks with HMAC-SHA256 signature.
    """
    provider_type = "bitlabs"
    success_body  = "1"
    error_body    = "0"


@method_decorator(csrf_exempt, name="dispatch")
class PollfishWebhookView(BaseSurveyWebhookView):
    """
    GET /api/offerwall/surveys/webhooks/pollfish/

    Pollfish sends GET postbacks with HMAC-SHA1 signature.
    """
    provider_type = "pollfish"
    success_body  = "1"
    error_body    = "0"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Survey Analytics (admin) — how surveys are performing
# ─────────────────────────────────────────────────────────────────────────────

class SurveyAnalyticsView(APIView):
    """
    GET /api/offerwall/admin/surveys/analytics/?provider=cpx

    Admin endpoint — survey conversion stats per provider.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"error": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        from api.offerwall.models import OfferConversion
        from django.db.models import Sum, Count, Avg

        provider_type = request.query_params.get("provider")

        qs = OfferConversion.objects.filter(
            offer__offer_type="survey"
        ).select_related("offer", "offer__provider")

        if provider_type:
            qs = qs.filter(offer__provider__provider_type=provider_type)

        agg = qs.aggregate(
            total=Count("id"),
            approved=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(status="approved")),
            total_payout=Sum("payout_amount"),
            total_reward=Sum("reward_amount"),
        )

        by_provider = (
            qs.values("offer__provider__provider_type", "offer__provider__name")
            .annotate(count=Count("id"), revenue=Sum("payout_amount"))
            .order_by("-count")
        )

        return Response({
            "totals":      agg,
            "by_provider": list(by_provider),
        })

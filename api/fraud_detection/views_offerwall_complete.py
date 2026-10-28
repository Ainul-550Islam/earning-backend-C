# =============================================================================
# fraud_detection/views_offerwall_complete.py  — NEWLY CONNECTED
#
# Exposes all offerwall/revenue/campaign logic from missing_components_v2.py
# via proper DRF APIViews. WAS FLOATING: 18 classes with zero URL routing.
#
# URL routes are in urls_offerwall.py (included by master urls.py).
# =============================================================================
from __future__ import annotations
import logging
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

logger = logging.getLogger(__name__)

def _ok(data, http_status=status.HTTP_200_OK):
    return Response({"success": True, "data": data}, status=http_status)

def _err(msg, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "error": msg}, status=http_status)


# ── OFFERWALL EMBED ──────────────────────────────────────────────────────────
class OfferwallEmbedAPIView(APIView):
    """GET /offerwall/embed/ — render the offerwall embed HTML."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .missing_components_v2 import OfferwallEmbedView
            view = OfferwallEmbedView()
            return view.get(request)
        except Exception as exc:
            return _err(str(exc))


class OfferFeedAPIView(APIView):
    """GET /offerwall/feed/ — paginated list of available offers."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .missing_components_v2 import OfferFeedAPIView as _Inner
            return _Inner().get(request)
        except Exception as exc:
            return _err(str(exc))


# ── OFFER CATALOG ────────────────────────────────────────────────────────────
class OfferCatalogAPIView(APIView):
    """GET/POST /offerwall/catalog/ — browse and filter the offer catalog."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .missing_components_v2 import OfferCatalogService
            svc = OfferCatalogService()
            return _ok(svc.get_catalog(
                category=request.query_params.get("category"),
                page=int(request.query_params.get("page", 1)),
                limit=int(request.query_params.get("limit", 20)),
            ))
        except Exception as exc:
            return _err(str(exc))


# ── TRAFFIC QUALITY ───────────────────────────────────────────────────────────
class TrafficQualityAPIView(APIView):
    """POST /offerwall/traffic-quality/ — score incoming traffic."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from .missing_components_v2 import TrafficQualityService
            result = TrafficQualityService().score(request.data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


# ── CONVERSION PIXEL ──────────────────────────────────────────────────────────
class ConversionPixelAPIView(APIView):
    """GET /offerwall/pixel/<conversion_id>/ — fire conversion pixel."""
    permission_classes = []  # public endpoint (pixel fire)

    def get(self, request, conversion_id: str = ""):
        try:
            from .missing_components_v2 import ConversionPixelView
            return ConversionPixelView().get(request, conversion_id=conversion_id)
        except Exception as exc:
            return _err(str(exc))


# ── AUTO PAYOUT ───────────────────────────────────────────────────────────────
class AutoPayoutTriggerAPIView(APIView):
    """POST /offerwall/payout/trigger/ — manually trigger auto-payout."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .missing_components_v2 import AutoPayoutScheduler
            result = AutoPayoutScheduler().run()
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


class AutoPayoutStatusAPIView(APIView):
    """GET /offerwall/payout/status/ — current payout queue status."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .missing_components_v2 import AutoPayoutScheduler
            return _ok(AutoPayoutScheduler().get_status())
        except Exception as exc:
            return _err(str(exc))


# ── REVENUE REPORTS ───────────────────────────────────────────────────────────
class RevenueReportAPIView(APIView):
    """GET /offerwall/revenue/report/ — revenue summary for a period."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .missing_components_v2 import RevenueReportService
            return _ok(RevenueReportService().generate(
                period=request.query_params.get("period", "monthly"),
                start=request.query_params.get("start"),
                end=request.query_params.get("end"),
            ))
        except Exception as exc:
            return _err(str(exc))


class RevenueReportExportAPIView(APIView):
    """GET /offerwall/revenue/export/ — download revenue CSV/XLSX."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .missing_components_v2 import RevenueReportExportView
            return RevenueReportExportView().get(request)
        except Exception as exc:
            return _err(str(exc))


# ── OFFER TYPE POSTBACKS ───────────────────────────────────────────────────────
class PINSubmitPostbackAPIView(APIView):
    """POST /offerwall/offers/pin-submit/postback/ — PIN-submit offer postback."""
    permission_classes = []  # postback = no auth

    def post(self, request):
        try:
            from .missing_components_v2 import PINSubmitOfferView
            return PINSubmitOfferView().post(request)
        except Exception as exc:
            return _err(str(exc))


class EmailSubmitOfferAPIView(APIView):
    """POST /offerwall/offers/email-submit/ — email-submit offer action."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from .missing_components_v2 import EmailSubmitOfferService
            result = EmailSubmitOfferService().process(request.data, user=request.user)
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            return _err(str(exc))


class VideoOfferPostbackAPIView(APIView):
    """POST /offerwall/offers/video/postback/ — video-offer completion postback."""
    permission_classes = []  # postback = no auth

    def post(self, request):
        try:
            from .missing_components_v2 import VideoOfferPostbackView
            return VideoOfferPostbackView().post(request)
        except Exception as exc:
            return _err(str(exc))


class TrialOfferPostbackAPIView(APIView):
    """POST /offerwall/offers/trial/postback/ — trial-offer completion postback."""
    permission_classes = []  # postback = no auth

    def post(self, request):
        try:
            from .missing_components_v2 import TrialOfferPostbackView
            return TrialOfferPostbackView().post(request)
        except Exception as exc:
            return _err(str(exc))


# ── ADVERTISER BILLING ────────────────────────────────────────────────────────
class AdvertiserBillingAPIView(APIView):
    """GET/POST /offerwall/advertiser/billing/ — billing records for advertisers."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .missing_components_v2 import AdvertiserBillingService
            return _ok(AdvertiserBillingService().get_billing_summary(
                advertiser_id=request.query_params.get("advertiser_id"),
                period=request.query_params.get("period", "monthly"),
            ))
        except Exception as exc:
            return _err(str(exc))

    def post(self, request):
        try:
            from .missing_components_v2 import AdvertiserBillingView
            return AdvertiserBillingView().post(request)
        except Exception as exc:
            return _err(str(exc))


# ── CAMPAIGN MANAGER ──────────────────────────────────────────────────────────
class CampaignListAPIView(APIView):
    """GET /offerwall/campaigns/ — list all fraud-monitored campaigns."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .missing_components_v2 import CampaignManager
            return _ok({"campaigns": CampaignManager().list_campaigns(
                status=request.query_params.get("status"),
                page=int(request.query_params.get("page", 1)),
            )})
        except Exception as exc:
            return _err(str(exc))


class CampaignFraudCheckAPIView(APIView):
    """POST /offerwall/campaigns/<id>/fraud-check/ — run fraud check on campaign."""
    permission_classes = [IsAdminUser]

    def post(self, request, campaign_id: str):
        try:
            from .missing_components_v2 import CampaignManager
            result = CampaignManager().run_fraud_check(campaign_id, request.data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


class CampaignPauseAPIView(APIView):
    """POST /offerwall/campaigns/<id>/pause/ — pause a campaign on fraud detection."""
    permission_classes = [IsAdminUser]

    def post(self, request, campaign_id: str):
        try:
            from .missing_components_v2 import CampaignManager
            result = CampaignManager().pause_campaign(campaign_id, reason=request.data.get("reason"))
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))

# =============================================================================
# fraud_detection/views_offerwall_v2.py
# =============================================================================
"""
Offerwall v2 business views — all previously floating.

Re-exports the 8 APIViews from missing_components_v2.py and adds
service-layer endpoints for the 4 services that had no direct view:

  OfferwallEmbedView          → /fraud/offerwall/embed/
  OfferFeedAPIView            → /fraud/offerwall/feed/
  ConversionPixelView         → /fraud/offerwall/pixel/
  RevenueReportExportView     → /fraud/offerwall/revenue/export/
  PINSubmitOfferView          → /fraud/offerwall/pin-submit/
  VideoOfferPostbackView      → /fraud/offerwall/video/postback/
  TrialOfferPostbackView      → /fraud/offerwall/trial/postback/
  AdvertiserBillingView       → /fraud/offerwall/billing/

  OfferCatalogService API     → /fraud/offerwall/catalog/*
  TrafficQualityService API   → /fraud/offerwall/traffic/*
  AutoPayoutScheduler API     → /fraud/offerwall/autopayout/*
  RevenueReportService API    → /fraud/offerwall/revenue/*
  PINSubmitOfferService API   → /fraud/offerwall/pin/*
  EmailSubmitOfferService API → /fraud/offerwall/email-submit/*
  VideoOfferService API       → /fraud/offerwall/video/*
  TrialOfferService API       → /fraud/offerwall/trial/*
  AdvertiserBillingService API→ /fraud/offerwall/advertiser/*
  CampaignManager API         → /fraud/offerwall/campaigns/*
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
)

logger = logging.getLogger(__name__)


def _ok(data, code=status.HTTP_200_OK):
    return Response(data, status=code)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


def _svc(class_name: str):
    """Lazy-import a class from missing_components_v2."""
    from api.fraud_detection import missing_components_v2 as _m
    return getattr(_m, class_name)


# =============================================================================
# DIRECT VIEW RE-EXPORTS
# These classes already exist in missing_components_v2.py as APIViews.
# We import them here so urls_offerwall.py only needs to import from one place.
# =============================================================================

def _get_v2_view(name: str):
    try:
        from api.fraud_detection import missing_components_v2 as m
        return getattr(m, name, None)
    except ImportError:
        return None


# ─── Expose existing APIViews as module-level names ──────────────────────────

class OfferwallEmbedView(APIView):
    """
    GET  /fraud/offerwall/embed/?user_id=X&placement=sidebar
    POST /fraud/offerwall/embed/

    Wrapper that delegates to missing_components_v2.OfferwallEmbedView.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        cls = _get_v2_view('OfferwallEmbedView')
        if cls:
            return cls().get(request)
        return _err('OfferwallEmbedView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)

    def post(self, request):
        cls = _get_v2_view('OfferwallEmbedView')
        if cls:
            return cls().post(request)
        return _err('OfferwallEmbedView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)


class OfferFeedAPIView(APIView):
    """
    GET /fraud/offerwall/feed/?user_id=X&category=survey&limit=20

    Wrapper that delegates to missing_components_v2.OfferFeedAPIView.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        cls = _get_v2_view('OfferFeedAPIView')
        if cls:
            return cls().get(request)
        return _err('OfferFeedAPIView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)


class ConversionPixelView(APIView):
    """
    GET /fraud/offerwall/pixel/?offer_id=X&user_id=Y&transaction_id=Z

    Conversion pixel tracking endpoint.
    Delegates to missing_components_v2.ConversionPixelView.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        cls = _get_v2_view('ConversionPixelView')
        if cls:
            return cls().get(request)
        return _err('ConversionPixelView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)


class RevenueReportExportView(APIView):
    """
    GET  /fraud/offerwall/revenue/export/?period=2025-05&format=csv
    POST /fraud/offerwall/revenue/export/

    Delegates to missing_components_v2.RevenueReportExportView.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        cls = _get_v2_view('RevenueReportExportView')
        if cls:
            return cls().get(request)
        return _err('RevenueReportExportView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)

    def post(self, request):
        cls = _get_v2_view('RevenueReportExportView')
        if cls:
            return cls().post(request)
        return _err('RevenueReportExportView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)


class PINSubmitOfferView(APIView):
    """
    POST /fraud/offerwall/pin-submit/
    Body: { user_id, offer_id, pin, device_id?, ip_address? }

    Delegates to missing_components_v2.PINSubmitOfferView.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        cls = _get_v2_view('PINSubmitOfferView')
        if cls:
            return cls().post(request)
        return _err('PINSubmitOfferView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)


class VideoOfferPostbackView(APIView):
    """
    POST /fraud/offerwall/video/postback/
    Body: { offer_id, user_id, video_duration_watched, completion_percent, ... }

    Delegates to missing_components_v2.VideoOfferPostbackView.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        cls = _get_v2_view('VideoOfferPostbackView')
        if cls:
            return cls().post(request)
        return _err('VideoOfferPostbackView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)


class TrialOfferPostbackView(APIView):
    """
    POST /fraud/offerwall/trial/postback/
    Body: { offer_id, user_id, trial_status, days_active, ... }

    Delegates to missing_components_v2.TrialOfferPostbackView.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        cls = _get_v2_view('TrialOfferPostbackView')
        if cls:
            return cls().post(request)
        return _err('TrialOfferPostbackView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)


class AdvertiserBillingView(APIView):
    """
    GET  /fraud/offerwall/billing/?advertiser_id=X
    POST /fraud/offerwall/billing/

    Delegates to missing_components_v2.AdvertiserBillingView.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        cls = _get_v2_view('AdvertiserBillingView')
        if cls:
            return cls().get(request)
        return _err('AdvertiserBillingView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)

    def post(self, request):
        cls = _get_v2_view('AdvertiserBillingView')
        if cls:
            return cls().post(request)
        return _err('AdvertiserBillingView not available.', status.HTTP_503_SERVICE_UNAVAILABLE)


# =============================================================================
# SERVICE-LAYER API ENDPOINTS
# =============================================================================

# ─── OfferCatalogService ─────────────────────────────────────────────────────

class OfferCatalogListAPIView(APIView):
    """GET /fraud/offerwall/catalog/?category=X&country=BD&limit=20"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            svc = _svc('OfferCatalogService')()
            result = svc.get_offers(
                category=request.query_params.get('category'),
                country=request.query_params.get('country'),
                platform=request.query_params.get('platform'),
                limit=int(request.query_params.get('limit', 20)),
                user_id=request.query_params.get('user_id'),
            ) if hasattr(svc, 'get_offers') else []
            offers = [o.to_dict() if hasattr(o, 'to_dict') else o for o in (result or [])]
            return _ok({'count': len(offers), 'offers': offers})
        except Exception as exc:
            logger.exception('OfferCatalogListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferCatalogDetailAPIView(APIView):
    """GET /fraud/offerwall/catalog/<offer_id>/"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, offer_id: int):
        try:
            svc   = _svc('OfferCatalogService')()
            offer = svc.get_offer_detail(offer_id=offer_id) if hasattr(svc, 'get_offer_detail') else None
            if not offer:
                return _err('Offer not found.', status.HTTP_404_NOT_FOUND)
            return _ok(offer.to_dict() if hasattr(offer, 'to_dict') else offer)
        except Exception as exc:
            logger.exception('OfferCatalogDetailAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferCatalogStatsAPIView(APIView):
    """GET /fraud/offerwall/catalog/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc   = _svc('OfferCatalogService')()
            stats = svc.get_stats() if hasattr(svc, 'get_stats') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('OfferCatalogStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── TrafficQualityService ───────────────────────────────────────────────────

class TrafficQualityCheckAPIView(APIView):
    """
    POST /fraud/offerwall/traffic/check/
    Body: { user_id, offer_id, ip_address, user_agent, device_id? }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        user_id    = request.data.get('user_id', request.user.id)
        offer_id   = request.data.get('offer_id')
        ip_address = request.data.get('ip_address', '')
        user_agent = request.data.get('user_agent', '')
        if not offer_id:
            return _err('offer_id required.')
        try:
            svc    = _svc('TrafficQualityService')()
            result = svc.check_traffic_quality(
                user_id=user_id, offer_id=offer_id,
                ip_address=ip_address, user_agent=user_agent,
                device_id=request.data.get('device_id', ''),
            ) if hasattr(svc, 'check_traffic_quality') else {'quality': 'unknown'}
            return _ok(result.to_dict() if hasattr(result, 'to_dict') else result)
        except Exception as exc:
            logger.exception('TrafficQualityCheckAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TrafficQualityStatsAPIView(APIView):
    """GET /fraud/offerwall/traffic/stats/?days=30"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc   = _svc('TrafficQualityService')()
            stats = svc.get_statistics(
                days=int(request.query_params.get('days', 30))
            ) if hasattr(svc, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('TrafficQualityStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TrafficQualityReportAPIView(APIView):
    """GET /fraud/offerwall/traffic/report/?offer_id=X"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        offer_id = request.query_params.get('offer_id')
        try:
            svc    = _svc('TrafficQualityService')()
            report = svc.generate_quality_report(offer_id=offer_id) \
                if hasattr(svc, 'generate_quality_report') else {}
            return _ok(report.to_dict() if hasattr(report, 'to_dict') else report)
        except Exception as exc:
            logger.exception('TrafficQualityReportAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── AutoPayoutScheduler ─────────────────────────────────────────────────────

class AutoPayoutRunAPIView(APIView):
    """POST /fraud/offerwall/autopayout/run/ — trigger auto-payout cycle."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        dry_run = bool(request.data.get('dry_run', False))
        try:
            svc    = _svc('AutoPayoutScheduler')()
            result = svc.run(dry_run=dry_run) if hasattr(svc, 'run') else \
                     _svc('run_auto_payout')()
            return _ok(result.to_dict() if hasattr(result, 'to_dict') else
                       result if isinstance(result, dict) else {'ran': True, 'dry_run': dry_run})
        except Exception as exc:
            logger.exception('AutoPayoutRunAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutoPayoutStatusAPIView(APIView):
    """GET /fraud/offerwall/autopayout/status/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc    = _svc('AutoPayoutScheduler')()
            result = svc.get_status() if hasattr(svc, 'get_status') else {}
            return _ok(result.to_dict() if hasattr(result, 'to_dict') else result)
        except Exception as exc:
            logger.exception('AutoPayoutStatusAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutoPayoutConfigAPIView(APIView):
    """
    GET  /fraud/offerwall/autopayout/config/
    POST /fraud/offerwall/autopayout/config/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc    = _svc('AutoPayoutScheduler')()
            config = svc.get_config() if hasattr(svc, 'get_config') else {}
            return _ok(config)
        except Exception as exc:
            logger.exception('AutoPayoutConfigAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            svc    = _svc('AutoPayoutScheduler')()
            result = svc.update_config(request.data) if hasattr(svc, 'update_config') else {}
            return _ok(result.to_dict() if hasattr(result, 'to_dict') else result)
        except Exception as exc:
            logger.exception('AutoPayoutConfigAPIView.post failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── RevenueReportService ────────────────────────────────────────────────────

class RevenueReportAPIView(APIView):
    """GET /fraud/offerwall/revenue/report/?period=2025-05&advertiser_id=X"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        period        = request.query_params.get('period', timezone.now().strftime('%Y-%m'))
        advertiser_id = request.query_params.get('advertiser_id')
        try:
            svc    = _svc('RevenueReportService')()
            report = svc.generate_report(
                period=period,
                advertiser_id=advertiser_id,
            ) if hasattr(svc, 'generate_report') else {}
            return _ok(report.to_dict() if hasattr(report, 'to_dict') else report)
        except Exception as exc:
            logger.exception('RevenueReportAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class RevenueReportSummaryAPIView(APIView):
    """GET /fraud/offerwall/revenue/summary/?days=30"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        try:
            svc     = _svc('RevenueReportService')()
            summary = svc.get_summary(days=days) if hasattr(svc, 'get_summary') else {}
            return _ok(summary.to_dict() if hasattr(summary, 'to_dict') else summary)
        except Exception as exc:
            logger.exception('RevenueReportSummaryAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── PINSubmitOfferService ───────────────────────────────────────────────────

class PINSubmitServiceCheckAPIView(APIView):
    """
    POST /fraud/offerwall/pin/check/
    Body: { offer_id, user_id, pin }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        offer_id = request.data.get('offer_id')
        user_id  = request.data.get('user_id', request.user.id)
        pin      = request.data.get('pin', '').strip()
        if not offer_id or not pin:
            return _err('offer_id and pin required.')
        try:
            svc    = _svc('PINSubmitOfferService')()
            result = svc.verify_pin(
                offer_id=offer_id, user_id=user_id, pin=pin,
            ) if hasattr(svc, 'verify_pin') else {'valid': False}
            return _ok(result.to_dict() if hasattr(result, 'to_dict') else result)
        except Exception as exc:
            logger.exception('PINSubmitServiceCheckAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PINSubmitServiceStatsAPIView(APIView):
    """GET /fraud/offerwall/pin/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc   = _svc('PINSubmitOfferService')()
            stats = svc.get_statistics() if hasattr(svc, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('PINSubmitServiceStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── VideoOfferService ───────────────────────────────────────────────────────

class VideoOfferVerifyAPIView(APIView):
    """
    POST /fraud/offerwall/video/verify/
    Body: { offer_id, user_id, video_id, watch_duration, completion_percent }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        offer_id           = request.data.get('offer_id')
        user_id            = request.data.get('user_id', request.user.id)
        video_id           = request.data.get('video_id', '')
        watch_duration     = request.data.get('watch_duration', 0)
        completion_percent = request.data.get('completion_percent', 0)
        if not offer_id:
            return _err('offer_id required.')
        try:
            svc    = _svc('VideoOfferService')()
            result = svc.verify_completion(
                offer_id=offer_id, user_id=user_id, video_id=video_id,
                watch_duration=watch_duration, completion_percent=completion_percent,
            ) if hasattr(svc, 'verify_completion') else {'verified': False}
            return _ok(result.to_dict() if hasattr(result, 'to_dict') else result)
        except Exception as exc:
            logger.exception('VideoOfferVerifyAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class VideoOfferStatsAPIView(APIView):
    """GET /fraud/offerwall/video/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc   = _svc('VideoOfferService')()
            stats = svc.get_statistics(
                days=int(request.query_params.get('days', 30))
            ) if hasattr(svc, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('VideoOfferStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── TrialOfferService ───────────────────────────────────────────────────────

class TrialOfferVerifyAPIView(APIView):
    """
    POST /fraud/offerwall/trial/verify/
    Body: { offer_id, user_id, trial_status, days_active }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        offer_id     = request.data.get('offer_id')
        user_id      = request.data.get('user_id', request.user.id)
        trial_status = request.data.get('trial_status', '')
        days_active  = int(request.data.get('days_active', 0))
        if not offer_id or not trial_status:
            return _err('offer_id and trial_status required.')
        try:
            svc    = _svc('TrialOfferService')()
            result = svc.verify_trial(
                offer_id=offer_id, user_id=user_id,
                trial_status=trial_status, days_active=days_active,
            ) if hasattr(svc, 'verify_trial') else {'verified': False}
            return _ok(result.to_dict() if hasattr(result, 'to_dict') else result)
        except Exception as exc:
            logger.exception('TrialOfferVerifyAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TrialOfferStatsAPIView(APIView):
    """GET /fraud/offerwall/trial/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc   = _svc('TrialOfferService')()
            stats = svc.get_statistics() if hasattr(svc, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('TrialOfferStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── AdvertiserBillingService ────────────────────────────────────────────────

class AdvertiserBillingInvoiceAPIView(APIView):
    """GET /fraud/offerwall/advertiser/<advertiser_id>/invoices/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, advertiser_id: int):
        try:
            svc      = _svc('AdvertiserBillingService')()
            invoices = svc.get_invoices(advertiser_id=advertiser_id) \
                if hasattr(svc, 'get_invoices') else []
            return _ok({'count': len(invoices),
                        'invoices': [i.to_dict() if hasattr(i, 'to_dict') else i for i in invoices]})
        except Exception as exc:
            logger.exception('AdvertiserBillingInvoiceAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdvertiserBillingStatsAPIView(APIView):
    """GET /fraud/offerwall/advertiser/billing/stats/?days=30"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc   = _svc('AdvertiserBillingService')()
            stats = svc.get_billing_statistics(
                days=int(request.query_params.get('days', 30))
            ) if hasattr(svc, 'get_billing_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('AdvertiserBillingStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── CampaignManager ────────────────────────────────────────────────────────

class CampaignListAPIView(APIView):
    """GET /fraud/offerwall/campaigns/?advertiser_id=X&status=active"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            svc    = _svc('CampaignManager')()
            status_f = request.query_params.get('status')
            adv_id   = request.query_params.get('advertiser_id')
            items  = svc.list_campaigns(
                status=status_f, advertiser_id=adv_id
            ) if hasattr(svc, 'list_campaigns') else []
            return _ok({'count': len(items),
                        'campaigns': [c.to_dict() if hasattr(c, 'to_dict') else c for c in items]})
        except Exception as exc:
            logger.exception('CampaignListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CampaignDetailAPIView(APIView):
    """GET /fraud/offerwall/campaigns/<campaign_id>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, campaign_id: int):
        try:
            svc      = _svc('CampaignManager')()
            campaign = svc.get_campaign(campaign_id=campaign_id) \
                if hasattr(svc, 'get_campaign') else None
            if not campaign:
                return _err('Campaign not found.', status.HTTP_404_NOT_FOUND)
            return _ok(campaign.to_dict() if hasattr(campaign, 'to_dict') else campaign)
        except Exception as exc:
            logger.exception('CampaignDetailAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CampaignStatsAPIView(APIView):
    """GET /fraud/offerwall/campaigns/<campaign_id>/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, campaign_id: int):
        try:
            svc   = _svc('CampaignManager')()
            stats = svc.get_campaign_stats(campaign_id=campaign_id) \
                if hasattr(svc, 'get_campaign_stats') else {}
            return _ok(stats.to_dict() if hasattr(stats, 'to_dict') else stats)
        except Exception as exc:
            logger.exception('CampaignStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── MISSING: Fraud-check views for offerwall ──────────────────────────────────
from rest_framework.views import APIView as _OV
from rest_framework.response import Response as _OR
from rest_framework.permissions import IsAuthenticated as _OA

class OfferwallFraudCheckAPIView(_OV):
    permission_classes = [_OA]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_detection_service
        result = get_fraud_detection_service().check_user(
            request.data.get("user_id"), request.data)
        return _OR({"success": True, "is_fraud": result.get("risk_score", 0) >= 70, "result": result})

class OfferwallBatchCheckAPIView(_OV):
    permission_classes = [_OA]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_detection_service
        svc    = get_fraud_detection_service()
        offers = request.data.get("offers", [])
        results = [{"offer_id": o.get("offer_id"),
                    "result": svc.check_user(o.get("user_id"), o)} for o in offers]
        return _OR({"success": True, "results": results, "total": len(results)})

class OfferwallAnalyticsAPIView(_OV):
    permission_classes = [_OA]
    def get(self, request):
        from api.fraud_detection.analytics import FraudAnalyticsEngine
        return _OR({"success": True, "data": FraudAnalyticsEngine().get_offer_fraud_stats()})

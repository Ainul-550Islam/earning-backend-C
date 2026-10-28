"""
api/offerwall/admin_api_views.py

Exposes all internal utility/service logic as REST API endpoints.

Previously these classes had full logic but zero API exposure:
  - utils/AnalyticsTracker   → get_offer_performance_stats, get_provider_performance,
                                generate_performance_report
  - utils/RewardCalculator   → calculate_conversion_value, calculate_all_bonuses
  - utils/FraudDetector      → comprehensive_fraud_check, analyze_user_behavior
  - services/OfferFactory    → validate_provider_config, get_provider_capabilities,
                                sync_all_providers, get_processor_info
  - services/adapters        → OfferwallAdapterFactory.health_check_all()

All views require IsAuthenticated + IsAdminUser except RewardPreviewView (any auth user).

URL prefix:  /api/offerwall/admin/   (wired in urls.py)
"""
import logging
from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def _require_staff(request):
    """Return 403 Response if not staff, else None."""
    if not request.user.is_staff:
        return Response({"error": "forbidden", "detail": "Admin access required."},
                        status=status.HTTP_403_FORBIDDEN)
    return None


# ═══════════════════════════════════════════════════════════════
# 1.  ANALYTICS ENDPOINTS
#     AnalyticsTracker.get_offer_performance_stats()
#     AnalyticsTracker.get_provider_performance()
#     AnalyticsTracker.generate_performance_report()
# ═══════════════════════════════════════════════════════════════

class OfferPerformanceView(APIView):
    """
    GET /api/offerwall/admin/analytics/offer/{offer_id}/?period=week

    Exposes AnalyticsTracker.get_offer_performance_stats()

    period choices: day | week | month | all  (default: week)

    Returns: views, clicks, conversions, conversion_rate, CTR,
             total_revenue, total_payout, profit,
             device_breakdown, country_breakdown, quality_score
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, offer_id):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.models import Offer
        from api.offerwall.utils.AnalyticsTracker import AnalyticsTracker

        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            return Response({"error": "offer_not_found"}, status=status.HTTP_404_NOT_FOUND)

        period = request.query_params.get("period", "week")
        if period not in ("day", "week", "month", "all"):
            return Response(
                {"error": "invalid_period", "valid": ["day", "week", "month", "all"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tracker = AnalyticsTracker(offer=offer)
        stats = tracker.get_offer_performance_stats(period=period)

        return Response(stats)


class ProviderPerformanceView(APIView):
    """
    GET /api/offerwall/admin/analytics/provider/{provider_id}/

    Exposes AnalyticsTracker.get_provider_performance()

    Returns: total_offers, active_offers, total_views, total_clicks,
             total_conversions, conversion_rate, CTR,
             total_revenue, total_payout, profit,
             avg_completion_rate, avg_quality_score
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, provider_id):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.models import OfferProvider
        from api.offerwall.utils.AnalyticsTracker import AnalyticsTracker

        try:
            provider = OfferProvider.objects.get(id=provider_id)
        except OfferProvider.DoesNotExist:
            return Response({"error": "provider_not_found"}, status=status.HTTP_404_NOT_FOUND)

        tracker = AnalyticsTracker()
        stats = tracker.get_provider_performance(provider)

        return Response(stats)


class PerformanceReportView(APIView):
    """
    GET /api/offerwall/admin/analytics/report/
        ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

    Exposes AnalyticsTracker.generate_performance_report()

    Returns: period summary → offers (total/active/featured),
             engagement (clicks, unique_users, conversions),
             revenue (total, payouts)

    Defaults: last 30 days if dates not supplied.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.utils.AnalyticsTracker import AnalyticsTracker

        start_str = request.query_params.get("start_date")
        end_str   = request.query_params.get("end_date")

        try:
            if start_str:
                start_date = datetime.strptime(start_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.get_current_timezone())
            else:
                start_date = timezone.now() - timedelta(days=30)

            if end_str:
                end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.get_current_timezone())
            else:
                end_date = timezone.now()
        except ValueError:
            return Response(
                {"error": "invalid_date_format", "expected": "YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_date > end_date:
            return Response(
                {"error": "start_date must be before end_date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = AnalyticsTracker.generate_performance_report(start_date, end_date)
        return Response(report)


class UserOfferAnalyticsView(APIView):
    """
    GET /api/offerwall/admin/analytics/user/{user_id}/

    Exposes AnalyticsTracker.get_user_offer_stats() for any user (admin view).
    Regular users can see their own stats via /conversions/stats/.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        err = _require_staff(request)
        if err:
            return err

        from django.contrib.auth import get_user_model
        from api.offerwall.utils.AnalyticsTracker import AnalyticsTracker

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "user_not_found"}, status=status.HTTP_404_NOT_FOUND)

        tracker = AnalyticsTracker(user=user)
        stats = tracker.get_user_offer_stats()
        return Response(stats)


# ═══════════════════════════════════════════════════════════════
# 2.  REWARD CALCULATOR ENDPOINTS
#     RewardCalculator.calculate_conversion_value()
#     RewardCalculator.calculate_all_bonuses()
# ═══════════════════════════════════════════════════════════════

class RewardPreviewView(APIView):
    """
    GET /api/offerwall/offers/{offer_id}/reward-preview/
        ?payout=0.75&user_id=42

    Exposes RewardCalculator.calculate_conversion_value()
    Any authenticated user can preview their reward before clicking.

    Returns: payout, base_reward, bonuses (tier/time/streak/volume/event),
             final_reward, platform_fee, bonus_breakdown
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, offer_id):
        from api.offerwall.models import Offer
        from api.offerwall.utils.RewardCalculator import RewardCalculator
        from decimal import Decimal, InvalidOperation

        try:
            offer = Offer.objects.select_related("provider").get(id=offer_id)
        except Offer.DoesNotExist:
            return Response({"error": "offer_not_found"}, status=status.HTTP_404_NOT_FOUND)

        # Allow custom payout preview or fall back to offer.payout
        payout_str = request.query_params.get("payout", str(offer.payout))
        try:
            payout = Decimal(payout_str)
        except (InvalidOperation, ValueError):
            return Response(
                {"error": "invalid_payout", "value": payout_str},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Optionally calculate bonuses for a specific user
        target_user = request.user
        user_id_param = request.query_params.get("user_id")
        if user_id_param and request.user.is_staff:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                target_user = User.objects.get(id=user_id_param)
            except User.DoesNotExist:
                return Response({"error": "user_not_found"}, status=status.HTTP_404_NOT_FOUND)

        calc = RewardCalculator(offer=offer, provider=offer.provider)
        breakdown = calc.calculate_conversion_value(payout, user=target_user)

        # Convert Decimal to str for JSON
        def _serialize(d):
            if isinstance(d, dict):
                return {k: _serialize(v) for k, v in d.items()}
            from decimal import Decimal as D
            if isinstance(d, D):
                return str(d)
            return d

        return Response(_serialize(breakdown))


class AllBonusesPreviewView(APIView):
    """
    GET /api/offerwall/admin/rewards/bonuses/?user_id=42&offer_id=...

    Exposes RewardCalculator.calculate_all_bonuses()
    Admin endpoint to inspect all bonus multipliers for a user+offer combination.

    Returns: tier, time, streak, volume, event multipliers + total
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_staff(request)
        if err:
            return err

        from django.contrib.auth import get_user_model
        from api.offerwall.models import Offer
        from api.offerwall.utils.RewardCalculator import RewardCalculator
        from decimal import Decimal

        User = get_user_model()
        user_id  = request.query_params.get("user_id")
        offer_id = request.query_params.get("offer_id")

        if not user_id:
            return Response({"error": "user_id required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "user_not_found"}, status=status.HTTP_404_NOT_FOUND)

        offer = None
        if offer_id:
            try:
                offer = Offer.objects.select_related("provider").get(id=offer_id)
            except Offer.DoesNotExist:
                return Response({"error": "offer_not_found"}, status=status.HTTP_404_NOT_FOUND)

        calc = RewardCalculator(offer=offer)
        bonuses = calc.calculate_all_bonuses(user)

        return Response({k: str(v) for k, v in bonuses.items()})


# ═══════════════════════════════════════════════════════════════
# 3.  FRAUD DETECTOR ENDPOINTS
#     FraudDetector.comprehensive_fraud_check()
#     FraudDetector.analyze_user_behavior()
#     FraudDetector.check_ip_reputation()
# ═══════════════════════════════════════════════════════════════

class FraudCheckView(APIView):
    """
    POST /api/offerwall/admin/fraud/check/

    Exposes FraudDetector.comprehensive_fraud_check()

    Body::
        {
          "user_id":  42,
          "offer_id": "uuid...",
          "click_data": {
              "ip_address": "1.2.3.4",
              "user_agent": "Mozilla...",
              "country": "BD"
          },
          "device_data": { "is_vpn": false, "trust_score": 90 }
        }

    Returns: fraud_score, fraud_level, should_block, indicators, analyses, recommendation
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        err = _require_staff(request)
        if err:
            return err

        from django.contrib.auth import get_user_model
        from api.offerwall.models import Offer
        from api.offerwall.utils.FraudDetector import FraudDetector

        User = get_user_model()
        user_id  = request.data.get("user_id")
        offer_id = request.data.get("offer_id")

        if not user_id:
            return Response({"error": "user_id required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "user_not_found"}, status=status.HTTP_404_NOT_FOUND)

        offer = None
        if offer_id:
            try:
                offer = Offer.objects.get(id=offer_id)
            except Offer.DoesNotExist:
                return Response({"error": "offer_not_found"}, status=status.HTTP_404_NOT_FOUND)

        detector = FraudDetector(user=user, offer=offer)
        result = detector.comprehensive_fraud_check(
            click_data=request.data.get("click_data"),
            device_data=request.data.get("device_data"),
            completion_time=request.data.get("completion_time"),
        )

        # Remove non-serializable nested objects if any
        return Response(result)


class UserBehaviorAnalysisView(APIView):
    """
    GET /api/offerwall/admin/fraud/user/{user_id}/behavior/

    Exposes FraudDetector.analyze_user_behavior() + analyze_multi_account()
    + analyze_conversion_patterns() separately for admin review.

    Returns: behavior_analysis, multi_account_analysis, conversion_pattern
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        err = _require_staff(request)
        if err:
            return err

        from django.contrib.auth import get_user_model
        from api.offerwall.utils.FraudDetector import FraudDetector

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "user_not_found"}, status=status.HTTP_404_NOT_FOUND)

        detector = FraudDetector(user=user)
        return Response({
            "user_id":            user_id,
            "behavior":           detector.analyze_user_behavior(),
            "multi_account":      detector.analyze_multi_account(),
            "conversion_pattern": detector.analyze_conversion_patterns(),
        })


class IPReputationView(APIView):
    """
    GET /api/offerwall/admin/fraud/ip/?ip=1.2.3.4

    Exposes FraudDetector.check_ip_reputation()

    Returns: is_blacklisted, fraud_score, spam_score, threat_types
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_staff(request)
        if err:
            return err

        ip = request.query_params.get("ip", "").strip()
        if not ip:
            return Response({"error": "ip parameter required"}, status=status.HTTP_400_BAD_REQUEST)

        from api.offerwall.utils.FraudDetector import FraudDetector
        result = FraudDetector.check_ip_reputation(ip)
        return Response({"ip": ip, **result})


# ═══════════════════════════════════════════════════════════════
# 4.  OFFER FACTORY ENDPOINTS
#     OfferFactory.validate_provider_config()
#     OfferFactory.get_provider_capabilities()
#     OfferFactory.sync_all_providers()
#     OfferFactory.get_processor_info()
# ═══════════════════════════════════════════════════════════════

class ProviderValidateView(APIView):
    """
    POST /api/offerwall/admin/providers/{provider_id}/validate/

    Exposes OfferFactory.validate_provider_config()

    Returns: { is_valid: bool, errors: [...] }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, provider_id):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.models import OfferProvider
        from api.offerwall.services.OfferFactory import OfferFactory

        try:
            provider = OfferProvider.objects.get(id=provider_id)
        except OfferProvider.DoesNotExist:
            return Response({"error": "provider_not_found"}, status=status.HTTP_404_NOT_FOUND)

        is_valid, errors = OfferFactory.validate_provider_config(provider)
        return Response({
            "provider_id":   str(provider.id),
            "provider_name": provider.name,
            "provider_type": provider.provider_type,
            "is_valid":      is_valid,
            "errors":        errors,
        })


class ProviderCapabilitiesView(APIView):
    """
    GET /api/offerwall/admin/providers/{provider_id}/capabilities/

    Exposes OfferFactory.get_provider_capabilities()

    Returns: supports_sync, supports_webhook, supports_targeting,
             supports_categories, supports_video, supports_surveys
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, provider_id):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.models import OfferProvider
        from api.offerwall.services.OfferFactory import OfferFactory

        try:
            provider = OfferProvider.objects.get(id=provider_id)
        except OfferProvider.DoesNotExist:
            return Response({"error": "provider_not_found"}, status=status.HTTP_404_NOT_FOUND)

        capabilities = OfferFactory.get_provider_capabilities(provider.provider_type)
        return Response({
            "provider_id":    str(provider.id),
            "provider_type":  provider.provider_type,
            "capabilities":   capabilities,
        })


class SyncAllProvidersView(APIView):
    """
    POST /api/offerwall/admin/sync-all/

    Exposes OfferFactory.sync_all_providers()

    Body (optional):
        { "provider_ids": ["uuid1", "uuid2"] }  → sync only these providers
        {}                                       → sync all active+auto_sync providers

    Returns: { "provider_name": { synced, created, updated, errors } }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.models import OfferProvider
        from api.offerwall.services.OfferFactory import OfferFactory

        provider_ids = request.data.get("provider_ids")

        if provider_ids:
            providers = OfferProvider.objects.filter(
                id__in=provider_ids, status="active"
            )
        else:
            providers = None  # OfferFactory will pull auto_sync=True ones

        results = OfferFactory.sync_all_providers(providers)

        total_synced  = sum(r.get("synced", 0)  for r in results.values())
        total_created = sum(r.get("created", 0) for r in results.values())
        total_errors  = sum(len(r.get("errors", [])) for r in results.values())

        return Response({
            "summary": {
                "providers_synced": len(results),
                "total_offers_synced": total_synced,
                "total_created": total_created,
                "total_errors": total_errors,
            },
            "results": results,
        })


class ProcessorRegistryView(APIView):
    """
    GET /api/offerwall/admin/processors/

    Exposes OfferFactory.get_processor_info() + OfferProcessorFactory.get_available_processors()

    Returns: { provider_type → processor_class_name }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.services.OfferFactory import OfferFactory
        from api.offerwall.services.OfferProcessor import OfferProcessorFactory

        return Response({
            "factory_registry":    OfferFactory.get_processor_info(),
            "processor_registry":  {t: t for t in OfferProcessorFactory.get_available_processors()},
            "available_providers": OfferFactory.get_available_providers(),
        })


# ═══════════════════════════════════════════════════════════════
# 5.  ADAPTER HEALTH CHECK
#     OfferwallAdapterFactory.health_check_all()
# ═══════════════════════════════════════════════════════════════

class AdapterHealthView(APIView):
    """
    GET /api/offerwall/admin/adapters/health/

    Exposes OfferwallAdapterFactory.health_check_all()

    Returns health status of all 18 adapters:
      wallet, notification, fraud_detection, audit, referral,
      analytics, tasks, postback, postback_engine, gamification,
      loyalty, promotions, alerts, rate_limit, behavior,
      offer_routing, payout_queue, subscription

    Each adapter returns:
      { adapter: name, circuit_open: bool, failure_count: int }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

        health = OfferwallAdapterFactory.health_check_all()

        # Summarise
        total     = len(health)
        degraded  = sum(1 for v in health.values() if v.get("circuit_open"))
        healthy   = total - degraded

        return Response({
            "summary": {
                "total":    total,
                "healthy":  healthy,
                "degraded": degraded,
                "status":   "ok" if not degraded else "degraded",
            },
            "adapters": health,
        })


class AdapterResetView(APIView):
    """
    POST /api/offerwall/admin/adapters/reset/{adapter_name}/

    Reset circuit breaker for a specific adapter.
    Useful after fixing a downstream service outage.

    Body: {} (no body needed)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, adapter_name):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

        try:
            adapter = OfferwallAdapterFactory.get(adapter_name)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Reset circuit breaker state
        adapter._circuit_open   = False
        adapter._failure_count  = 0
        adapter._last_failure   = None

        logger.info(f"[AdapterReset] {adapter_name} circuit reset by {request.user.username}")

        return Response({
            "adapter": adapter_name,
            "reset":   True,
            "health":  adapter.health_check(),
        })


# ═══════════════════════════════════════════════════════════════
# 6.  B2B MIDDLEWARE STATUS ENDPOINT
#     Exposes B2BQuotaMiddleware status check for a publisher key
# ═══════════════════════════════════════════════════════════════

class B2BQuotaStatusView(APIView):
    """
    GET /api/offerwall/admin/b2b/quota/{client_id}/

    Admin: check quota status for any B2B client.
    Returns current usage, limit, quota_pct, can_make_api_call.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, client_id):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.b2b.models import B2BClient

        try:
            client = B2BClient.objects.select_related("plan").get(id=client_id)
        except B2BClient.DoesNotExist:
            return Response({"error": "client_not_found"}, status=status.HTTP_404_NOT_FOUND)

        usage = client.get_current_usage()
        can_call, reason = client.can_make_api_call()

        return Response({
            "client_id":      str(client.id),
            "company_name":   client.company_name,
            "status":         client.status,
            "plan":           client.plan.plan_type if client.plan else None,
            "quota": {
                "api_calls_used":    usage.api_calls,
                "api_calls_limit":   client.plan.monthly_api_calls if client.plan else 0,
                "quota_pct":         usage.quota_pct(),
                "can_make_api_call": can_call,
                "block_reason":      reason,
                "period":            f"{usage.period_year}/{usage.period_month:02d}",
            },
        })


class B2BUsageIncrementView(APIView):
    """
    POST /api/offerwall/admin/b2b/quota/{client_id}/increment/

    Admin: manually increment a usage counter (for testing/backfill).
    Body: { "field": "api_calls", "amount": 1 }

    Valid fields: api_calls, conversions, offer_views, offer_clicks,
                  content_unlocks, webhook_calls
    """
    permission_classes = [IsAuthenticated]

    VALID_FIELDS = {
        "api_calls", "conversions", "offer_views",
        "offer_clicks", "content_unlocks", "webhook_calls",
    }

    def post(self, request, client_id):
        err = _require_staff(request)
        if err:
            return err

        from api.offerwall.b2b.models import B2BClient

        try:
            client = B2BClient.objects.get(id=client_id)
        except B2BClient.DoesNotExist:
            return Response({"error": "client_not_found"}, status=status.HTTP_404_NOT_FOUND)

        field  = request.data.get("field", "api_calls")
        amount = int(request.data.get("amount", 1))

        if field not in self.VALID_FIELDS:
            return Response(
                {"error": "invalid_field", "valid": sorted(self.VALID_FIELDS)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usage = client.get_current_usage()
        usage.increment(field, amount)
        usage.refresh_from_db()

        return Response({
            "client_id": str(client.id),
            "field":     field,
            "amount":    amount,
            "new_value": getattr(usage, field),
            "quota_pct": usage.quota_pct(),
        })

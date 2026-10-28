# =============================================================================
# fraud_detection/views_services.py
#
# API layer that exposes EVERY service method and INTEGRATION_SYSTEM module
# that previously had logic but no HTTP endpoint.
#
# Services wired here:
#   1.  FraudCaseService          → /cases/service/*
#   2.  FraudInsightService       → /insights/*
#   3.  FraudNotificationService  → /notifications/service/*
#   4.  IPReputationService       → /ip-reputation/service/*
#   5.  WhitelistService          → /whitelist/service/*
#   6.  FraudScoreCalculator      → /risk-score/*
#   7.  AutoBanService            → /auto-ban/service/*  (stats + validate-config)
#   8.  ReviewService             → /review/service/*   (already has views but
#                                    batch + stats were missing from service layer)
#   9.  MLFraudScorer             → /ml/*
#
# INTEGRATION_SYSTEM modules wired here:
#   10. HealthCheckManager        → /integration/health/*
#   11. PerformanceMonitor        → /integration/performance/*
#   12. CircuitBreakerRegistry    → /integration/circuit-breaker/*
#   13. EventBus                  → /integration/events/*
#   14. MessageQueueManager       → /integration/queue/*
#   15. AuditLogger               → /integration/audit/*
#   16. SyncManager               → /integration/sync/*
#   17. IntegrationRegistry       → /integration/registry/*
#   18. IntegrationHandler        → /integration/handler/*
#   19. FraudDetectionAdapter     → /integration/adapter/*
# =============================================================================
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
    HighRiskUserThrottle,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine from a sync Django view."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=30)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response(data, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"error": msg}, status=status_code)


# =============================================================================
# 1. FraudCaseService
# =============================================================================

class FraudCaseServiceCreateAPIView(APIView):
    """POST /cases/service/create/  →  FraudCaseService.create_case()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.services.FraudCaseService import FraudCaseService
            svc = FraudCaseService()
            data = request.data
            case = svc.create_case(
                user_id=data.get("user_id"),
                title=data.get("title", ""),
                description=data.get("description", ""),
                risk_score=int(data.get("risk_score", 0)),
                assigned_to_id=data.get("assigned_to_id"),
                metadata=data.get("metadata", {}),
            )
            return _ok(case, status.HTTP_201_CREATED)
        except (TypeError, ValueError) as exc:
            return _err(str(exc))
        except Exception as exc:
            logger.exception("FraudCaseService.create_case failed: %s", exc)
            return _err("Case creation failed.", status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseServiceStatusAPIView(APIView):
    """PATCH /cases/service/<case_id>/status/  →  update_case_status()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def patch(self, request, case_id):
        try:
            from api.fraud_detection.services.FraudCaseService import FraudCaseService
            svc = FraudCaseService()
            result = svc.update_case_status(
                case_id=case_id,
                new_status=request.data.get("status", ""),
                updated_by=request.user,
                notes=request.data.get("notes", ""),
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("update_case_status failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseServiceEvidenceAPIView(APIView):
    """POST /cases/service/<case_id>/evidence/  →  add_evidence()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, case_id):
        try:
            from api.fraud_detection.services.FraudCaseService import FraudCaseService
            svc = FraudCaseService()
            result = svc.add_evidence(
                case_id=case_id,
                evidence_type=request.data.get("evidence_type", ""),
                data=request.data.get("data", {}),
                added_by=request.user,
            )
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("add_evidence failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseServiceActionAPIView(APIView):
    """POST /cases/service/<case_id>/action/  →  create_action()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, case_id):
        try:
            from api.fraud_detection.services.FraudCaseService import FraudCaseService
            svc = FraudCaseService()
            result = svc.create_action(
                case_id=case_id,
                action_type=request.data.get("action_type", ""),
                note=request.data.get("note", ""),
                performed_by=request.user,
            )
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("create_action failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseServiceDetailAPIView(APIView):
    """GET /cases/service/<case_id>/detail/  →  get_case_details()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, case_id):
        try:
            from api.fraud_detection.services.FraudCaseService import FraudCaseService
            svc = FraudCaseService()
            include_evidence = request.query_params.get("include_evidence", "true").lower() == "true"
            include_actions  = request.query_params.get("include_actions", "true").lower() == "true"
            result = svc.get_case_details(
                case_id=case_id,
                include_evidence=include_evidence,
                include_actions=include_actions,
            )
            if not result:
                return _err("Case not found.", status.HTTP_404_NOT_FOUND)
            return _ok(result)
        except Exception as exc:
            logger.exception("get_case_details failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseServiceUserCasesAPIView(APIView):
    """GET /cases/service/user/<user_id>/  →  get_user_cases()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, user_id):
        if not request.user.is_staff and request.user.id != user_id:
            return _err("Permission denied.", status.HTTP_403_FORBIDDEN)
        try:
            from api.fraud_detection.services.FraudCaseService import FraudCaseService
            svc = FraudCaseService()
            result = svc.get_user_cases(
                user_id=user_id,
                status=request.query_params.get("status"),
                limit=int(request.query_params.get("limit", 50)),
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("get_user_cases failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseServiceBulkUpdateAPIView(APIView):
    """POST /cases/service/bulk-update/  →  bulk_update_cases()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        case_ids = request.data.get("case_ids", [])
        updates  = request.data.get("updates", {})
        if not case_ids:
            return _err("case_ids required.")
        if not updates:
            return _err("updates required.")
        try:
            from api.fraud_detection.services.FraudCaseService import FraudCaseService
            svc = FraudCaseService()
            result = svc.bulk_update_cases(case_ids=case_ids, updates=updates)
            return _ok(result)
        except Exception as exc:
            logger.exception("bulk_update_cases failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 2. FraudInsightService
# =============================================================================

class FraudInsightOverviewAPIView(APIView):
    """GET /insights/overview/  →  FraudInsightService.get_fraud_overview()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.FraudInsightService import FraudInsightService
            svc = FraudInsightService()
            days = int(request.query_params.get("days", 30))
            return _ok(svc.get_fraud_overview(days=days))
        except Exception as exc:
            logger.exception("get_fraud_overview failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudInsightTrendsAPIView(APIView):
    """GET /insights/trends/  →  get_fraud_trends()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.FraudInsightService import FraudInsightService
            svc = FraudInsightService()
            return _ok(svc.get_fraud_trends(
                days=int(request.query_params.get("days", 30)),
                granularity=request.query_params.get("granularity", "daily"),
            ))
        except Exception as exc:
            logger.exception("get_fraud_trends failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudInsightRiskFactorsAPIView(APIView):
    """GET /insights/risk-factors/  →  get_top_risk_factors()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.FraudInsightService import FraudInsightService
            svc = FraudInsightService()
            return _ok(svc.get_top_risk_factors(
                days=int(request.query_params.get("days", 30)),
                limit=int(request.query_params.get("limit", 10)),
            ))
        except Exception as exc:
            logger.exception("get_top_risk_factors failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudInsightGeographicAPIView(APIView):
    """GET /insights/geographic/  →  get_geographic_analysis()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.FraudInsightService import FraudInsightService
            svc = FraudInsightService()
            return _ok(svc.get_geographic_analysis(
                days=int(request.query_params.get("days", 30))
            ))
        except Exception as exc:
            logger.exception("get_geographic_analysis failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudInsightPerformanceAPIView(APIView):
    """GET /insights/performance/  →  get_performance_metrics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.FraudInsightService import FraudInsightService
            svc = FraudInsightService()
            return _ok(svc.get_performance_metrics(
                days=int(request.query_params.get("days", 30))
            ))
        except Exception as exc:
            logger.exception("get_performance_metrics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudInsightPredictiveAPIView(APIView):
    """GET /insights/predictive/  →  get_predictive_insights()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.FraudInsightService import FraudInsightService
            svc = FraudInsightService()
            return _ok(svc.get_predictive_insights(
                days=int(request.query_params.get("days", 30))
            ))
        except Exception as exc:
            logger.exception("get_predictive_insights failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudInsightExportAPIView(APIView):
    """GET /insights/export/  →  export_analytics_data()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.FraudInsightService import FraudInsightService
            svc = FraudInsightService()
            result = svc.export_analytics_data(
                format_type=request.query_params.get("format", "json"),
                days=int(request.query_params.get("days", 30)),
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("export_analytics_data failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 3. FraudNotificationService
# =============================================================================

class NotificationServiceCreateAPIView(APIView):
    """POST /notifications/service/create/  →  create_notification()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
            svc = FraudNotificationService()
            result = svc.create_notification(
                user_id=request.data.get("user_id"),
                notification_type=request.data.get("notification_type", ""),
                message=request.data.get("message", ""),
                metadata=request.data.get("metadata", {}),
            )
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("create_notification failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationServiceSendAPIView(APIView):
    """POST /notifications/service/<notification_id>/send/  →  send_notification()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, notification_id):
        try:
            from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
            svc = FraudNotificationService()
            success = svc.send_notification(notification_id=notification_id)
            return _ok({"sent": success, "notification_id": notification_id})
        except Exception as exc:
            logger.exception("send_notification failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationServiceBulkSendAPIView(APIView):
    """POST /notifications/service/bulk-send/  →  send_bulk_notifications()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        notification_type = request.data.get("notification_type", "")
        message           = request.data.get("message", "")
        user_ids          = request.data.get("user_ids", [])
        if not notification_type:
            return _err("notification_type required.")
        if not message:
            return _err("message required.")
        if not user_ids:
            return _err("user_ids required.")
        try:
            from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
            svc = FraudNotificationService()
            result = svc.send_bulk_notifications(
                notification_type=notification_type,
                message=message,
                user_ids=user_ids,
                metadata=request.data.get("metadata", {}),
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("send_bulk_notifications failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationServiceAlertAPIView(APIView):
    """POST /notifications/service/alert/<alert_id>/  →  create_alert_notification()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, alert_id):
        try:
            from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
            svc = FraudNotificationService()
            success = svc.create_alert_notification(alert_id=alert_id)
            return _ok({"created": success, "alert_id": alert_id})
        except Exception as exc:
            logger.exception("create_alert_notification failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationServiceCaseAPIView(APIView):
    """POST /notifications/service/case/<case_id>/  →  create_case_notification()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, case_id):
        try:
            from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
            svc = FraudNotificationService()
            result = svc.create_case_notification(
                case_id=case_id,
                notification_type=request.data.get("notification_type", "case_opened"),
                extra_context=request.data.get("extra_context", {}),
            )
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("create_case_notification failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationServiceStatsAPIView(APIView):
    """GET /notifications/service/stats/  →  get_notification_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
            svc = FraudNotificationService()
            return _ok(svc.get_notification_statistics(
                days=int(request.query_params.get("days", 30))
            ))
        except Exception as exc:
            logger.exception("get_notification_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationServiceRetryAPIView(APIView):
    """POST /notifications/service/retry-failed/  →  retry_failed_notifications()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
            svc = FraudNotificationService()
            result = svc.retry_failed_notifications(
                max_age_hours=int(request.data.get("max_age_hours", 24))
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("retry_failed_notifications failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 4. IPReputationService
# =============================================================================

class IPReputationServiceLookupAPIView(APIView):
    """GET /ip-reputation/service/lookup/?ip=x  →  get_ip_reputation()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        ip = request.query_params.get("ip", "").strip()
        if not ip:
            return _err("ip query param required.")
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            rep = svc.get_ip_reputation(
                ip_address=ip,
                force_refresh=request.query_params.get("force_refresh", "false").lower() == "true",
            )
            from api.fraud_detection.serializers import IPReputationSerializer
            return _ok(IPReputationSerializer(rep).data)
        except Exception as exc:
            logger.exception("get_ip_reputation failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationServiceActivityAPIView(APIView):
    """POST /ip-reputation/service/activity/  →  update_ip_activity()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        ip = request.data.get("ip_address", "").strip()
        if not ip:
            return _err("ip_address required.")
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            result = svc.update_ip_activity(
                ip_address=ip,
                user_id=request.data.get("user_id"),
                is_fraud=bool(request.data.get("is_fraud", False)),
                fraud_score=int(request.data.get("fraud_score", 0)),
            )
            return _ok({"updated": True, "ip_address": ip})
        except Exception as exc:
            logger.exception("update_ip_activity failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationServiceCheckAPIView(APIView):
    """POST /ip-reputation/service/check/  →  check_ip_risk()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        ip = request.data.get("ip_address", "").strip()
        if not ip:
            return _err("ip_address required.")
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            return _ok(svc.check_ip_risk(ip_address=ip))
        except Exception as exc:
            logger.exception("check_ip_risk failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationServiceBulkCheckAPIView(APIView):
    """POST /ip-reputation/service/bulk-check/  →  bulk_check_ip_risk()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        ips = request.data.get("ip_addresses", [])
        if not ips:
            return _err("ip_addresses list required.")
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            return _ok(svc.bulk_check_ip_risk(ip_addresses=ips))
        except Exception as exc:
            logger.exception("bulk_check_ip_risk failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationServiceBlacklistAPIView(APIView):
    """POST /ip-reputation/service/blacklist/  →  blacklist_ip()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        ip     = request.data.get("ip_address", "").strip()
        reason = request.data.get("reason", "").strip()
        if not ip:
            return _err("ip_address required.")
        if not reason:
            return _err("reason required.")
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            result = svc.blacklist_ip(
                ip_address=ip,
                reason=reason,
                blacklisted_by=request.user.id,
                duration_hours=request.data.get("duration_hours"),
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("blacklist_ip failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationServiceWhitelistAPIView(APIView):
    """POST /ip-reputation/service/whitelist/  →  whitelist_ip()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        ip     = request.data.get("ip_address", "").strip()
        reason = request.data.get("reason", "").strip()
        if not ip:
            return _err("ip_address required.")
        if not reason:
            return _err("reason required.")
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            result = svc.whitelist_ip(
                ip_address=ip,
                reason=reason,
                whitelisted_by=request.user.id,
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("whitelist_ip failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationServiceHighRiskAPIView(APIView):
    """GET /ip-reputation/service/high-risk/  →  get_high_risk_ips()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            return _ok(svc.get_high_risk_ips(
                min_score=int(request.query_params.get("min_score", 70)),
                limit=int(request.query_params.get("limit", 100)),
            ))
        except Exception as exc:
            logger.exception("get_high_risk_ips failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationServiceStatsAPIView(APIView):
    """GET /ip-reputation/service/stats/  →  get_ip_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            return _ok(svc.get_ip_statistics(
                days=int(request.query_params.get("days", 30))
            ))
        except Exception as exc:
            logger.exception("get_ip_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationServiceCleanupAPIView(APIView):
    """POST /ip-reputation/service/cleanup/  →  cleanup_old_ip_data()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.services.IPReputationService import IPReputationService
            svc = IPReputationService()
            result = svc.cleanup_old_ip_data(
                days_to_keep=int(request.data.get("days_to_keep", 365))
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("cleanup_old_ip_data failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 5. WhitelistService
# =============================================================================

class WhitelistServiceAddAPIView(APIView):
    """POST /whitelist/service/add/  →  add_to_whitelist()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        entity_type  = request.data.get("entity_type", "").strip()
        entity_value = request.data.get("entity_value", "").strip()
        reason       = request.data.get("reason", "").strip()
        if not all([entity_type, entity_value, reason]):
            return _err("entity_type, entity_value, reason all required.")
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            result = svc.add_to_whitelist(
                entity_type=entity_type,
                entity_value=entity_value,
                reason=reason,
                added_by=request.user.id,
                expires_at=request.data.get("expires_at"),
            )
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("add_to_whitelist failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceAddBlacklistAPIView(APIView):
    """POST /whitelist/service/blacklist/  →  add_to_blacklist()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        entity_type  = request.data.get("entity_type", "").strip()
        entity_value = request.data.get("entity_value", "").strip()
        reason       = request.data.get("reason", "").strip()
        if not all([entity_type, entity_value, reason]):
            return _err("entity_type, entity_value, reason all required.")
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            result = svc.add_to_blacklist(
                entity_type=entity_type,
                entity_value=entity_value,
                reason=reason,
                added_by=request.user.id,
            )
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("add_to_blacklist failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceRemoveAPIView(APIView):
    """DELETE /whitelist/service/remove/  →  remove_from_whitelist()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def delete(self, request):
        entity_type  = request.data.get("entity_type", "").strip()
        entity_value = request.data.get("entity_value", "").strip()
        if not all([entity_type, entity_value]):
            return _err("entity_type and entity_value required.")
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            result = svc.remove_from_whitelist(
                entity_type=entity_type,
                entity_value=entity_value,
                removed_by=request.user.id,
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("remove_from_whitelist failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceRemoveBlacklistAPIView(APIView):
    """DELETE /whitelist/service/remove-blacklist/  →  remove_from_blacklist()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def delete(self, request):
        entity_type  = request.data.get("entity_type", "").strip()
        entity_value = request.data.get("entity_value", "").strip()
        if not all([entity_type, entity_value]):
            return _err("entity_type and entity_value required.")
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            result = svc.remove_from_blacklist(
                entity_type=entity_type,
                entity_value=entity_value,
                removed_by=request.user.id,
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("remove_from_blacklist failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceCheckAPIView(APIView):
    """GET /whitelist/service/check/?entity_type=ip&entity_value=1.2.3.4  →  is_whitelisted()/is_blacklisted()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        entity_type  = request.query_params.get("entity_type", "").strip()
        entity_value = request.query_params.get("entity_value", "").strip()
        if not all([entity_type, entity_value]):
            return _err("entity_type and entity_value query params required.")
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            return _ok({
                "entity_type":    entity_type,
                "entity_value":   entity_value,
                "is_whitelisted": svc.is_whitelisted(entity_type=entity_type, entity_value=entity_value),
                "is_blacklisted": svc.is_blacklisted(entity_type=entity_type, entity_value=entity_value),
            })
        except Exception as exc:
            logger.exception("whitelist check failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceEntriesAPIView(APIView):
    """GET /whitelist/service/entries/  →  get_whitelist_entries()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            result = svc.get_whitelist_entries(
                entity_type=request.query_params.get("entity_type"),
                is_active=request.query_params.get("is_active"),
                limit=int(request.query_params.get("limit", 100)),
            )
            return _ok(result)
        except Exception as exc:
            logger.exception("get_whitelist_entries failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceBulkWhitelistAPIView(APIView):
    """POST /whitelist/service/bulk-whitelist/  →  bulk_whitelist()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        entities = request.data.get("entities", [])
        reason   = request.data.get("reason", "").strip()
        if not entities:
            return _err("entities list required.")
        if not reason:
            return _err("reason required.")
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            pairs = [(e["entity_type"], e["entity_value"]) for e in entities]
            result = svc.bulk_whitelist(entities=pairs, reason=reason, added_by=request.user.id)
            return _ok(result)
        except (KeyError, TypeError) as exc:
            return _err(f"Bad entity format: {exc}")
        except Exception as exc:
            logger.exception("bulk_whitelist failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceBulkBlacklistAPIView(APIView):
    """POST /whitelist/service/bulk-blacklist/  →  bulk_blacklist()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        entities = request.data.get("entities", [])
        reason   = request.data.get("reason", "").strip()
        if not entities:
            return _err("entities list required.")
        if not reason:
            return _err("reason required.")
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            pairs = [(e["entity_type"], e["entity_value"]) for e in entities]
            result = svc.bulk_blacklist(entities=pairs, reason=reason, added_by=request.user.id)
            return _ok(result)
        except (KeyError, TypeError) as exc:
            return _err(f"Bad entity format: {exc}")
        except Exception as exc:
            logger.exception("bulk_blacklist failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceCleanupAPIView(APIView):
    """POST /whitelist/service/cleanup/  →  cleanup_expired_entries()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            return _ok(svc.cleanup_expired_entries())
        except Exception as exc:
            logger.exception("cleanup_expired_entries failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WhitelistServiceStatsAPIView(APIView):
    """GET /whitelist/service/stats/  →  get_whitelist_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.WhitelistService import WhitelistService
            svc = WhitelistService()
            return _ok(svc.get_whitelist_statistics())
        except Exception as exc:
            logger.exception("get_whitelist_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 6. FraudScoreCalculator
# =============================================================================

class RiskScoreCalculateAPIView(APIView):
    """GET /risk-score/<user_id>/  →  FraudScoreCalculator.calculate_overall_risk()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, user_id):
        if not request.user.is_staff and request.user.id != user_id:
            return _err("Permission denied.", status.HTTP_403_FORBIDDEN)
        try:
            from django.contrib.auth import get_user_model
            from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            calc = FraudScoreCalculator(user)
            return _ok({
                "user_id":    user_id,
                "risk_score": calc.calculate_overall_risk(),
            })
        except Exception as exc:
            logger.exception("calculate_overall_risk failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class RiskScoreBreakdownAPIView(APIView):
    """GET /risk-score/<user_id>/breakdown/  →  calculate_risk_breakdown()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, user_id):
        if not request.user.is_staff and request.user.id != user_id:
            return _err("Permission denied.", status.HTTP_403_FORBIDDEN)
        try:
            from django.contrib.auth import get_user_model
            from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            calc = FraudScoreCalculator(user)
            return _ok(calc.calculate_risk_breakdown())
        except Exception as exc:
            logger.exception("calculate_risk_breakdown failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class RiskScoreRecommendationsAPIView(APIView):
    """GET /risk-score/<user_id>/recommendations/  →  get_risk_recommendations()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, user_id):
        if not request.user.is_staff and request.user.id != user_id:
            return _err("Permission denied.", status.HTTP_403_FORBIDDEN)
        try:
            from django.contrib.auth import get_user_model
            from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            calc = FraudScoreCalculator(user)
            return _ok({"user_id": user_id, "recommendations": calc.get_risk_recommendations()})
        except Exception as exc:
            logger.exception("get_risk_recommendations failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class RiskScoreActionRequiredAPIView(APIView):
    """GET /risk-score/<user_id>/action-required/  →  calculate_action_required()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, user_id):
        try:
            from django.contrib.auth import get_user_model
            from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            calc = FraudScoreCalculator(user)
            threshold = int(request.query_params.get("threshold", 70))
            return _ok(calc.calculate_action_required(threshold=threshold))
        except Exception as exc:
            logger.exception("calculate_action_required failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 7. AutoBanService  (stats + validate_config — process/ban are in views.py)
# =============================================================================

class AutoBanServiceStatsAPIView(APIView):
    """GET /auto-ban/service/stats/  →  AutoBanService.get_auto_ban_stats()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.AutoBanService import AutoBanService
            svc = AutoBanService()
            return _ok(svc.get_auto_ban_stats(
                days=int(request.query_params.get("days", 7))
            ))
        except Exception as exc:
            logger.exception("get_auto_ban_stats failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutoBanServiceValidateConfigAPIView(APIView):
    """GET /auto-ban/service/validate-config/  →  AutoBanService.validate_config()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.AutoBanService import AutoBanService
            svc = AutoBanService()
            return _ok(svc.validate_config())
        except Exception as exc:
            logger.exception("validate_config failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutoBanServiceBulkFraudAPIView(APIView):
    """POST /auto-ban/service/process-bulk/  →  process_bulk_fraud()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        attempt_ids = request.data.get("attempt_ids", [])
        if not attempt_ids:
            return _err("attempt_ids required.")
        try:
            from api.fraud_detection.models import FraudAttempt
            from api.fraud_detection.services.AutoBanService import AutoBanService
            attempts = list(FraudAttempt.objects.filter(attempt_id__in=attempt_ids))
            if not attempts:
                return _err("No matching attempts found.", status.HTTP_404_NOT_FOUND)
            svc = AutoBanService()
            return _ok(svc.process_bulk_fraud(fraud_attempts=attempts))
        except Exception as exc:
            logger.exception("process_bulk_fraud failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutoBanServiceUnbanScheduledAPIView(APIView):
    """POST /auto-ban/service/check-unban/  →  check_and_unban_users()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.services.AutoBanService import AutoBanService
            svc = AutoBanService()
            return _ok(svc.check_and_unban_users())
        except Exception as exc:
            logger.exception("check_and_unban_users failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 8. ReviewService (batch + stats service-layer wiring)
# =============================================================================

class ReviewServiceBatchAPIView(APIView):
    """POST /review/service/batch/  →  ReviewService.batch_review_decisions()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        decisions = request.data.get("decisions", [])
        if not decisions:
            return _err("decisions list required.")
        try:
            from api.fraud_detection.services.ReviewService import ReviewService
            svc = ReviewService()
            return _ok(svc.batch_review_decisions(decisions=decisions, reviewer=request.user))
        except Exception as exc:
            logger.exception("batch_review_decisions failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReviewServiceStatsAPIView(APIView):
    """GET /review/service/stats/  →  ReviewService.get_review_stats()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.ReviewService import ReviewService
            svc = ReviewService()
            return _ok(svc.get_review_stats(
                reviewer=request.user if not request.user.is_staff else None,
                days=int(request.query_params.get("days", 30)),
            ))
        except Exception as exc:
            logger.exception("get_review_stats failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 9. MLFraudScorer
# =============================================================================

class MLScorerScoreAPIView(APIView):
    """POST /ml/score/  →  MLFraudScorer.score()"""
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        features = request.data.get("features")
        if not features or not isinstance(features, dict):
            return _err("features dict required.")
        try:
            from api.fraud_detection.services.MLFraudScorer import get_ml_scorer
            scorer = get_ml_scorer()
            explanation = scorer.score(features)
            return _ok(explanation.to_dict() if hasattr(explanation, "to_dict") else explanation)
        except Exception as exc:
            logger.exception("MLFraudScorer.score failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLScorerBatchScoreAPIView(APIView):
    """POST /ml/batch-score/  →  MLFraudScorer.batch_score()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        feature_list = request.data.get("feature_list", [])
        if not feature_list or not isinstance(feature_list, list):
            return _err("feature_list (list of dicts) required.")
        try:
            from api.fraud_detection.services.MLFraudScorer import get_ml_scorer
            scorer = get_ml_scorer()
            results = scorer.batch_score(feature_list)
            return _ok({
                "count":   len(results),
                "results": [r.to_dict() if hasattr(r, "to_dict") else r for r in results],
            })
        except Exception as exc:
            logger.exception("MLFraudScorer.batch_score failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLScorerFitAPIView(APIView):
    """POST /ml/fit/  →  MLFraudScorer.fit()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        historical = request.data.get("historical_features", [])
        if not historical:
            return _err("historical_features list required.")
        try:
            from api.fraud_detection.services.MLFraudScorer import get_ml_scorer
            scorer = get_ml_scorer()
            scorer.fit(historical_features=historical)
            return _ok({"fitted": True, "sample_count": len(historical)})
        except Exception as exc:
            logger.exception("MLFraudScorer.fit failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MLScorerDriftAPIView(APIView):
    """GET /ml/drift/  →  MLFraudScorer.check_drift()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.services.MLFraudScorer import get_ml_scorer
            scorer = get_ml_scorer()
            return _ok(scorer.check_drift())
        except Exception as exc:
            logger.exception("MLFraudScorer.check_drift failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 10. INTEGRATION_SYSTEM — HealthCheckManager
# =============================================================================

class IntegrationHealthRunAPIView(APIView):
    """GET /integration/health/run/  →  run_health_checks()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.health_check import run_health_checks
            checker_names = request.query_params.getlist("checker") or None
            result = _run(run_health_checks(checker_names=checker_names))
            return _ok(result.to_dict() if hasattr(result, "to_dict") else result)
        except Exception as exc:
            logger.exception("run_health_checks failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationHealthStatusAPIView(APIView):
    """GET /integration/health/status/  →  get_system_health_status() (sync)"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.health_check import get_system_health_status
            result = get_system_health_status()
            return _ok(result.to_dict() if hasattr(result, "to_dict") else result)
        except Exception as exc:
            logger.exception("get_system_health_status failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationHealthStatsAPIView(APIView):
    """GET /integration/health/stats/  →  get_health_statistics() (sync)"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.health_check import get_health_statistics
            return _ok(get_health_statistics())
        except Exception as exc:
            logger.exception("get_health_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationHealthCheckAPIView(APIView):
    """GET /integration/health/check/<integration_name>/  →  check_integration_health()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, integration_name):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.health_check import check_integration_health
            result = _run(check_integration_health(integration_name=integration_name))
            return _ok(result.to_dict() if hasattr(result, "to_dict") else result)
        except Exception as exc:
            logger.exception("check_integration_health failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 11. INTEGRATION_SYSTEM — PerformanceMonitor
# =============================================================================

class IntegrationPerformanceMetricsAPIView(APIView):
    """GET /integration/performance/metrics/  →  get_performance_metrics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.performance_monitor import get_performance_metrics
            metric_name = request.query_params.get("metric_name")
            results     = get_performance_metrics(metric_name=metric_name)
            return _ok([m.to_dict() if hasattr(m, "to_dict") else m for m in results])
        except Exception as exc:
            logger.exception("get_performance_metrics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationPerformanceAlertsAPIView(APIView):
    """GET /integration/performance/alerts/  →  get_performance_alerts()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.performance_monitor import get_performance_alerts
            results = get_performance_alerts()
            return _ok([a.to_dict() if hasattr(a, "to_dict") else a for a in results])
        except Exception as exc:
            logger.exception("get_performance_alerts failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationPerformanceStatsAPIView(APIView):
    """GET /integration/performance/stats/  →  get_performance_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.performance_monitor import get_performance_statistics
            return _ok(get_performance_statistics())
        except Exception as exc:
            logger.exception("get_performance_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationPerformanceRecordAPIView(APIView):
    """POST /integration/performance/record/  →  record_request()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        integration_name = request.data.get("integration_name", "")
        response_time    = request.data.get("response_time", 0.0)
        success          = bool(request.data.get("success", True))
        if not integration_name:
            return _err("integration_name required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.performance_monitor import record_request
            record_request(integration_name=integration_name, response_time=float(response_time), success=success)
            return _ok({"recorded": True})
        except Exception as exc:
            logger.exception("record_request failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 12. INTEGRATION_SYSTEM — CircuitBreakerRegistry
# =============================================================================

class CircuitBreakerStatusAPIView(APIView):
    """GET /integration/circuit-breaker/<name>/status/  →  get_circuit_breaker_status()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, name):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.circuit_breaker import get_circuit_breaker_status
            result = get_circuit_breaker_status(name=name)
            if result is None:
                return _err(f"Circuit breaker '{name}' not found.", status.HTTP_404_NOT_FOUND)
            return _ok(result)
        except Exception as exc:
            logger.exception("get_circuit_breaker_status failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CircuitBreakerResetAPIView(APIView):
    """POST /integration/circuit-breaker/<name>/reset/  →  reset_circuit_breaker()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, name):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.circuit_breaker import reset_circuit_breaker
            success = reset_circuit_breaker(name=name)
            return _ok({"reset": success, "name": name})
        except Exception as exc:
            logger.exception("reset_circuit_breaker failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CircuitBreakerAllStatesAPIView(APIView):
    """GET /integration/circuit-breaker/states/  →  get_circuit_breaker_states()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.circuit_breaker import get_circuit_breaker_registry
            registry = get_circuit_breaker_registry()
            return _ok(registry.get_circuit_breaker_states())
        except Exception as exc:
            logger.exception("get_circuit_breaker_states failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CircuitBreakerSystemHealthAPIView(APIView):
    """GET /integration/circuit-breaker/system-health/  →  get_system_health()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.circuit_breaker import get_circuit_breaker_registry
            registry = get_circuit_breaker_registry()
            return _ok(registry.get_system_health())
        except Exception as exc:
            logger.exception("circuit_breaker get_system_health failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 13. INTEGRATION_SYSTEM — EventBus
# =============================================================================

class EventBusPublishAPIView(APIView):
    """POST /integration/events/publish/  →  EventBus.publish()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        event_name = request.data.get("event_name", "").strip()
        payload    = request.data.get("payload", {})
        if not event_name:
            return _err("event_name required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.event_bus import (
                get_event_bus, Event, EventType,
            )
            bus = get_event_bus()
            event = Event(
                name=event_name,
                event_type=EventType(request.data.get("event_type", "integration")),
                payload=payload,
                source=request.data.get("source", "api"),
            )
            event_id = _run(bus.publish(event))
            return _ok({"published": True, "event_id": str(event_id)}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("EventBus.publish failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventBusGetEventsAPIView(APIView):
    """GET /integration/events/  →  EventBus.get_events()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.event_bus import get_event_bus
            bus   = get_event_bus()
            limit = int(request.query_params.get("limit", 100))
            events = _run(bus.get_events(limit=limit))
            return _ok([e.to_dict() if hasattr(e, "to_dict") else e for e in events])
        except Exception as exc:
            logger.exception("EventBus.get_events failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventBusStatsAPIView(APIView):
    """GET /integration/events/stats/  →  EventBus.get_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.event_bus import get_event_bus
            return _ok(_run(get_event_bus().get_statistics()))
        except Exception as exc:
            logger.exception("EventBus.get_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventBusSubscriptionsAPIView(APIView):
    """GET /integration/events/subscriptions/  →  get_subscriptions()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.event_bus import get_event_bus
            pattern = request.query_params.get("pattern")
            subs    = _run(get_event_bus().get_subscriptions(pattern=pattern))
            return _ok(subs)
        except Exception as exc:
            logger.exception("EventBus.get_subscriptions failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 14. INTEGRATION_SYSTEM — MessageQueueManager
# =============================================================================

class MessageQueuePublishAPIView(APIView):
    """POST /integration/queue/<queue_name>/publish/  →  publish_message()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, queue_name):
        payload = request.data.get("payload", {})
        if not payload:
            return _err("payload required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.message_queue import publish_message
            result = _run(publish_message(
                queue_name=queue_name,
                payload=payload,
                priority=int(request.data.get("priority", 5)),
                delay_seconds=int(request.data.get("delay_seconds", 0)),
            ))
            return _ok({"published": bool(result)}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("publish_message failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MessageQueueStatsAPIView(APIView):
    """GET /integration/queue/stats/  →  get_queue_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.message_queue import get_queue_statistics
            return _ok(get_queue_statistics())
        except Exception as exc:
            logger.exception("get_queue_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MessageQueueListAPIView(APIView):
    """GET /integration/queue/list/  →  list_queues()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.message_queue import get_message_queue_manager
            mgr = get_message_queue_manager()
            return _ok({"queues": mgr.list_queues()})
        except Exception as exc:
            logger.exception("list_queues failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MessageQueuePurgeAPIView(APIView):
    """POST /integration/queue/<queue_name>/purge/  →  purge_queue()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, queue_name):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.message_queue import get_message_queue_manager
            mgr   = get_message_queue_manager()
            count = _run(mgr.purge_queue(queue_name=queue_name))
            return _ok({"purged": count, "queue_name": queue_name})
        except Exception as exc:
            logger.exception("purge_queue failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 15. INTEGRATION_SYSTEM — AuditLogger
# =============================================================================

class AuditLogSearchAPIView(APIView):
    """GET /integration/audit/search/  →  AuditLogger.search_logs()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_audit_logs import get_audit_logger
            logger_obj = get_audit_logger()
            filters = {}
            if request.query_params.get("user_id"):
                filters["user_id"] = int(request.query_params["user_id"])
            if request.query_params.get("action_type"):
                filters["action_type"] = request.query_params["action_type"]
            if request.query_params.get("level"):
                filters["level"] = request.query_params["level"]
            limit = int(request.query_params.get("limit", 100))
            logs  = _run(logger_obj.search_logs(filters=filters, limit=limit))
            return _ok([l.to_dict() if hasattr(l, "to_dict") else l for l in logs])
        except Exception as exc:
            logger.exception("AuditLogger.search_logs failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuditLogStatsAPIView(APIView):
    """GET /integration/audit/stats/  →  get_audit_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_audit_logs import get_audit_statistics
            return _ok(get_audit_statistics())
        except Exception as exc:
            logger.exception("get_audit_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuditLogExportAPIView(APIView):
    """GET /integration/audit/export/  →  AuditLogger.export_logs()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_audit_logs import get_audit_logger
            logger_obj = get_audit_logger()
            result = _run(logger_obj.export_logs(
                filters={},
                format_type=request.query_params.get("format", "json"),
            ))
            return _ok(result)
        except Exception as exc:
            logger.exception("AuditLogger.export_logs failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuditLogVerifyIntegrityAPIView(APIView):
    """POST /integration/audit/verify/  →  verify_log_integrity()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        log_id        = request.data.get("log_id", "")
        expected_hash = request.data.get("expected_hash", "")
        if not log_id or not expected_hash:
            return _err("log_id and expected_hash required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_audit_logs import get_audit_logger
            logger_obj = get_audit_logger()
            valid = logger_obj.verify_log_integrity(log_id=log_id, expected_hash=expected_hash)
            return _ok({"log_id": log_id, "valid": valid})
        except Exception as exc:
            logger.exception("verify_log_integrity failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuditLogCleanupAPIView(APIView):
    """POST /integration/audit/cleanup/  →  cleanup_old_logs()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_audit_logs import get_audit_logger
            logger_obj = get_audit_logger()
            deleted = _run(logger_obj.cleanup_old_logs())
            return _ok({"deleted": deleted})
        except Exception as exc:
            logger.exception("cleanup_old_logs failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 16. INTEGRATION_SYSTEM — SyncManager
# =============================================================================

class SyncManagerCreateAPIView(APIView):
    """POST /integration/sync/create/  →  create_sync_operation()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        source = request.data.get("source_system", "").strip()
        target = request.data.get("target_system", "").strip()
        if not source or not target:
            return _err("source_system and target_system required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.sync_manager import create_sync_operation
            result = _run(create_sync_operation(
                source_system=source,
                target_system=target,
                data_records=request.data.get("data_records", []),
            ))
            return _ok(result.to_dict() if hasattr(result, "to_dict") else result,
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("create_sync_operation failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SyncManagerExecuteAPIView(APIView):
    """POST /integration/sync/<sync_id>/execute/  →  execute_sync()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, sync_id):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.sync_manager import execute_sync
            result = _run(execute_sync(
                sync_id=sync_id,
                resolution_strategy=request.data.get("resolution_strategy"),
            ))
            return _ok(result)
        except Exception as exc:
            logger.exception("execute_sync failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SyncManagerStatsAPIView(APIView):
    """GET /integration/sync/stats/  →  get_sync_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.sync_manager import get_sync_statistics
            return _ok(get_sync_statistics())
        except Exception as exc:
            logger.exception("get_sync_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SyncManagerListAPIView(APIView):
    """GET /integration/sync/list/  →  list_sync_operations()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.sync_manager import get_sync_manager
            mgr  = get_sync_manager()
            ops  = _run(mgr.list_sync_operations(
                source_system=request.query_params.get("source_system"),
                target_system=request.query_params.get("target_system"),
            ))
            return _ok([o.to_dict() if hasattr(o, "to_dict") else o for o in ops])
        except Exception as exc:
            logger.exception("list_sync_operations failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SyncManagerCancelAPIView(APIView):
    """POST /integration/sync/<sync_id>/cancel/  →  cancel_sync()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, sync_id):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.sync_manager import get_sync_manager
            mgr     = get_sync_manager()
            success = _run(mgr.cancel_sync(sync_id=sync_id))
            return _ok({"cancelled": success, "sync_id": sync_id})
        except Exception as exc:
            logger.exception("cancel_sync failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 17. INTEGRATION_SYSTEM — IntegrationRegistry
# =============================================================================

class IntegrationRegistryListAPIView(APIView):
    """GET /integration/registry/list/  →  list_integrations()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
            reg = get_integration_registry()
            items = _run(reg.list_integrations())
            return _ok([i.to_dict() if hasattr(i, "to_dict") else i for i in items])
        except Exception as exc:
            logger.exception("list_integrations failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationRegistryHealthAPIView(APIView):
    """GET /integration/registry/health/  →  health_check_all()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
            reg = get_integration_registry()
            return _ok(_run(reg.health_check_all()))
        except Exception as exc:
            logger.exception("registry health_check_all failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationRegistryStatsAPIView(APIView):
    """GET /integration/registry/stats/  →  get_registry_statistics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
            reg = get_integration_registry()
            return _ok(_run(reg.get_registry_statistics()))
        except Exception as exc:
            logger.exception("get_registry_statistics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationRegistryActivateAPIView(APIView):
    """POST /integration/registry/<name>/activate/  →  initialize_integration()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, name):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
            reg     = get_integration_registry()
            success = _run(reg.initialize_integration(name=name))
            return _ok({"activated": success, "name": name})
        except Exception as exc:
            logger.exception("initialize_integration failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationRegistryDeactivateAPIView(APIView):
    """POST /integration/registry/<name>/deactivate/  →  deactivate_integration()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, name):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_registry import get_integration_registry
            reg     = get_integration_registry()
            success = _run(reg.deactivate_integration(name=name))
            return _ok({"deactivated": success, "name": name})
        except Exception as exc:
            logger.exception("deactivate_integration failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 18. INTEGRATION_SYSTEM — IntegrationHandler
# =============================================================================

class IntegrationHandlerStatusAPIView(APIView):
    """GET /integration/handler/<integration_name>/status/  →  get_integration_status()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, integration_name):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_handler import get_integration_handler
            handler = get_integration_handler()
            return _ok(_run(handler.get_integration_status(integration_name=integration_name)))
        except Exception as exc:
            logger.exception("get_integration_status failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationHandlerSystemStatusAPIView(APIView):
    """GET /integration/handler/system-status/  →  get_system_status()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_handler import get_integration_handler
            handler = get_integration_handler()
            return _ok(_run(handler.get_system_status()))
        except Exception as exc:
            logger.exception("get_system_status failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationHandlerExecuteAPIView(APIView):
    """POST /integration/handler/execute/  →  execute_integration()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        integration_name = request.data.get("integration_name", "").strip()
        method           = request.data.get("method", "").strip()
        if not integration_name or not method:
            return _err("integration_name and method required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_handler import execute_integration
            result = _run(execute_integration(
                integration_name=integration_name,
                method=method,
                params=request.data.get("params", {}),
                timeout=request.data.get("timeout"),
            ))
            return _ok(result.to_dict() if hasattr(result, "to_dict") else result)
        except Exception as exc:
            logger.exception("execute_integration failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationHandlerResetBreakerAPIView(APIView):
    """POST /integration/handler/<integration_name>/reset-breaker/  →  reset_circuit_breaker()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, integration_name):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_handler import get_integration_handler
            handler = get_integration_handler()
            handler.reset_circuit_breaker(integration_name=integration_name)
            return _ok({"reset": True, "integration": integration_name})
        except Exception as exc:
            logger.exception("reset_circuit_breaker (handler) failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 19. INTEGRATION_SYSTEM — FraudDetectionAdapter
# =============================================================================

class AdapterIPEnrichAPIView(APIView):
    """GET /integration/adapter/enrich-ip/?ip=x  →  FraudDetectionAdapter.enrich_ip()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        ip = request.query_params.get("ip", "").strip()
        if not ip:
            return _err("ip query param required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            return _ok(adapter.enrich_ip(ip_address=ip))
        except Exception as exc:
            logger.exception("enrich_ip failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterBehaviourSignalsAPIView(APIView):
    """GET /integration/adapter/behaviour/<user_id>/  →  get_behaviour_signals()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, user_id):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            return _ok(adapter.get_behaviour_signals(user_id=user_id))
        except Exception as exc:
            logger.exception("get_behaviour_signals failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterKYCStatusAPIView(APIView):
    """GET /integration/adapter/kyc/<user_id>/  →  get_kyc_status()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request, user_id):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            return _ok(adapter.get_kyc_status(user_id=user_id))
        except Exception as exc:
            logger.exception("get_kyc_status failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterBonusAbuseAPIView(APIView):
    """POST /integration/adapter/bonus-abuse/  →  check_bonus_abuse()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        user_id    = request.data.get("user_id")
        bonus_type = request.data.get("bonus_type", "").strip()
        if not user_id or not bonus_type:
            return _err("user_id and bonus_type required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            return _ok(adapter.check_bonus_abuse(user_id=user_id, bonus_type=bonus_type))
        except Exception as exc:
            logger.exception("check_bonus_abuse failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterMLRiskScoreAPIView(APIView):
    """POST /integration/adapter/ml-risk-score/  →  get_ml_risk_score()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        features = request.data.get("features", {})
        if not features:
            return _err("features dict required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            return _ok(adapter.get_ml_risk_score(features=features))
        except Exception as exc:
            logger.exception("get_ml_risk_score failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterExportMetricsAPIView(APIView):
    """GET /integration/adapter/export-metrics/  →  export_fraud_metrics()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            return _ok(adapter.export_fraud_metrics(
                since_days=int(request.query_params.get("days", 30))
            ))
        except Exception as exc:
            logger.exception("export_fraud_metrics failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterPrePayoutScreenAPIView(APIView):
    """POST /integration/adapter/pre-payout-screen/  →  pre_payout_screen()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        user_id = request.data.get("user_id")
        amount  = request.data.get("amount")
        if not user_id or amount is None:
            return _err("user_id and amount required.")
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            return _ok(adapter.pre_payout_screen(
                user_id=user_id,
                amount=float(amount),
                payout_method=request.data.get("payout_method", ""),
            ))
        except Exception as exc:
            logger.exception("pre_payout_screen failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterHealthCheckAPIView(APIView):
    """GET /integration/adapter/health/  →  FraudDetectionAdapter.health_check()"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            return _ok(adapter.health_check())
        except Exception as exc:
            logger.exception("adapter health_check failed: %s", exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── MISSING: service view aliases & ML scorer / score calculator views ────────
from rest_framework.views import APIView as _SvcView
from rest_framework.response import Response as _SR
from rest_framework.permissions import IsAuthenticated as _Auth, IsAdminUser as _SvcAdmin
from rest_framework import status as _ss


def _svc_ok(data, st=200):  return _SR({"success": True, "data": data}, status=st)
def _svc_err(msg, st=500):  return _SR({"success": False, "error": msg}, status=st)


# ── AutoBan service aliases ───────────────────────────────────────────────────
class AutoBanServiceStatsAPIView(_SvcView):
    permission_classes = [_SvcAdmin]
    def get(self, request):
        from api.fraud_detection.services import get_auto_ban_service
        return _svc_ok(get_auto_ban_service().get_stats())

class AutoBanServiceValidateConfigAPIView(_SvcView):
    permission_classes = [_SvcAdmin]
    def post(self, request):
        from api.fraud_detection.services import get_auto_ban_service
        result = get_auto_ban_service().validate_config(request.data)
        return _svc_ok(result)

class AutoBanServiceBulkFraudAPIView(_SvcView):
    permission_classes = [_SvcAdmin]
    def post(self, request):
        from api.fraud_detection.services import get_auto_ban_service
        result = get_auto_ban_service().process_bulk_fraud(request.data.get("user_ids", []))
        return _svc_ok(result)

class AutoBanServiceUnbanScheduledAPIView(_SvcView):
    permission_classes = [_SvcAdmin]
    def post(self, request):
        from api.fraud_detection.services import get_auto_ban_service
        result = get_auto_ban_service().process_scheduled_unbans()
        return _svc_ok(result)


# ── Review service aliases ────────────────────────────────────────────────────
class ReviewServiceBatchAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_review_service
        result = get_review_service().batch_review(request.data.get("items", []))
        return _svc_ok(result)

class ReviewServiceStatsAPIView(_SvcView):
    permission_classes = [_Auth]
    def get(self, request):
        from api.fraud_detection.services import get_review_service
        return _svc_ok(get_review_service().get_stats())


# ── IP Reputation bulk ────────────────────────────────────────────────────────
class IPReputationServiceCheckAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_ip_reputation_service
        result = get_ip_reputation_service().check(request.data.get("ip_address", ""))
        return _svc_ok(result)

class IPReputationServiceBulkAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_ip_reputation_service
        result = get_ip_reputation_service().bulk_check(request.data.get("ips", []))
        return _svc_ok(result)

class IPReputationServiceStatsAPIView(_SvcView):
    permission_classes = [_Auth]
    def get(self, request):
        from api.fraud_detection.services import get_ip_reputation_service
        return _svc_ok(get_ip_reputation_service().get_stats())


# ── Whitelist service aliases ─────────────────────────────────────────────────
class WhitelistServiceAddAPIView(_SvcView):
    permission_classes = [_SvcAdmin]
    def post(self, request):
        from api.fraud_detection.services import get_whitelist_service
        result = get_whitelist_service().add(request.data)
        return _svc_ok(result, 201)

class WhitelistServiceRemoveAPIView(_SvcView):
    permission_classes = [_SvcAdmin]
    def post(self, request):
        from api.fraud_detection.services import get_whitelist_service
        result = get_whitelist_service().remove(request.data)
        return _svc_ok(result)

class WhitelistServiceCheckAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_whitelist_service
        result = get_whitelist_service().is_whitelisted(request.data)
        return _svc_ok(result)


# ── Notification service aliases ──────────────────────────────────────────────
class NotificationServiceSendAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_notification_service
        result = get_fraud_notification_service().send(request.data)
        return _svc_ok(result)

class NotificationServiceBulkAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_notification_service
        result = get_fraud_notification_service().send_bulk(request.data.get("notifications", []))
        return _svc_ok(result)

class NotificationServiceStatsAPIView(_SvcView):
    permission_classes = [_Auth]
    def get(self, request):
        from api.fraud_detection.services import get_fraud_notification_service
        return _svc_ok(get_fraud_notification_service().get_stats())


# ── ML Fraud Scorer ───────────────────────────────────────────────────────────
class MLFraudScorerPredictAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_ml_fraud_scorer
        result = get_ml_fraud_scorer().predict(request.data)
        return _svc_ok(result)

class MLFraudScorerBatchAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_ml_fraud_scorer
        result = get_ml_fraud_scorer().batch_predict(request.data.get("records", []))
        return _svc_ok(result)

class MLFraudScorerRetrainAPIView(_SvcView):
    permission_classes = [_SvcAdmin]
    def post(self, request):
        from api.fraud_detection.services import get_ml_fraud_scorer
        result = get_ml_fraud_scorer().trigger_retrain(request.data)
        return _svc_ok(result)

class MLFraudScorerStatusAPIView(_SvcView):
    permission_classes = [_Auth]
    def get(self, request):
        from api.fraud_detection.services import get_ml_fraud_scorer
        return _svc_ok(get_ml_fraud_scorer().get_model_status())


# ── Fraud Score Calculator ────────────────────────────────────────────────────
class FraudScoreCalculatorRunAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_score_calculator
        result = get_fraud_score_calculator().calculate(request.data)
        return _svc_ok(result)

class FraudScoreCalculatorBatchAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_score_calculator
        result = get_fraud_score_calculator().batch_calculate(request.data.get("user_ids", []))
        return _svc_ok(result)

class FraudScoreCalculatorExplainAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_score_calculator
        result = get_fraud_score_calculator().explain_score(request.data)
        return _svc_ok(result)


# ── FraudDetectionService (core) ──────────────────────────────────────────────
class FraudDetectionServiceRunAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_detection_service
        result = get_fraud_detection_service().check_user(
            request.data.get("user_id"), request.data)
        return _svc_ok(result)

class FraudDetectionServiceBatchAPIView(_SvcView):
    permission_classes = [_Auth]
    def post(self, request):
        from api.fraud_detection.services import get_fraud_detection_service
        result = get_fraud_detection_service().batch_check(request.data.get("user_ids", []))
        return _svc_ok(result)

class FraudDetectionServiceStatusAPIView(_SvcView):
    permission_classes = [_Auth]
    def get(self, request):
        from api.fraud_detection.services import get_fraud_detection_service
        return _svc_ok(get_fraud_detection_service().get_status())

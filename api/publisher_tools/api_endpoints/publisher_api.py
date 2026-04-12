# api/publisher_tools/api_endpoints/publisher_api.py
"""
Publisher API Endpoints — Additional publisher-specific API views।
Dashboard, stats, analytics-এর specialized endpoints।
"""
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from core.views import BaseViewSet


class PublisherDashboardView(APIView):
    """
    Publisher Dashboard — Complete dashboard data।
    Single API call-এ সব dashboard widgets-এর data।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile found."}, status=404)

        period = request.query_params.get("period", "last_30_days")
        from api.publisher_tools.performance_analytics.publisher_dashboard import get_dashboard_summary, get_performance_alerts
        from api.publisher_tools.performance_analytics.real_time_analytics import get_live_stats

        try:
            dashboard = get_dashboard_summary(publisher, period)
            alerts    = get_performance_alerts(publisher)
            live      = get_live_stats(publisher)
            return Response({
                "success":   True,
                "data": {
                    "publisher_id":  publisher.publisher_id,
                    "display_name":  publisher.display_name,
                    "status":        publisher.status,
                    "tier":          publisher.tier,
                    "kyc_verified":  publisher.is_kyc_verified,
                    "live_stats":    live,
                    "dashboard":     dashboard,
                    "alerts":        alerts,
                    "alert_count":   len([a for a in alerts if a["severity"] in ("critical", "high")]),
                },
            })
        except Exception as e:
            return Response({"success": False, "message": str(e)}, status=500)


class PublisherStatsAPIView(APIView):
    """
    Publisher Stats — Detailed stats for a specific period।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pub_id=None):
        # Admin can view any, publisher only self
        if request.user.is_staff and pub_id:
            from api.publisher_tools.models import Publisher
            try:
                publisher = Publisher.objects.get(publisher_id=pub_id)
            except Publisher.DoesNotExist:
                return Response({"success": False, "message": "Publisher not found."}, status=404)
        else:
            try:
                publisher = request.user.publisher_profile
            except Exception:
                return Response({"success": False, "message": "No publisher profile found."}, status=404)

        period = request.query_params.get("period", "last_30_days")
        from api.publisher_tools.publisher_management.publisher_analytics import (
            get_publisher_overview, get_revenue_breakdown, get_performance_metrics, get_top_earning_content,
        )
        from api.publisher_tools.utils import get_date_range
        start_date, end_date = get_date_range(period)

        return Response({
            "success": True,
            "data": {
                "overview":         get_publisher_overview(publisher, period),
                "performance":      get_performance_metrics(publisher),
                "top_content":      get_top_earning_content(publisher),
                "revenue_breakdown":get_revenue_breakdown(publisher, start_date, end_date),
            },
        })


class PublisherLeaderboardView(APIView):
    """Publisher leaderboard — top earners।"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get("period", "last_30_days")
        limit  = int(request.query_params.get("limit", 10))
        from api.publisher_tools.repository import PublisherRepository
        top = PublisherRepository.get_top_publishers_by_revenue(limit=limit, days=30)
        return Response({"success": True, "data": top})


class PublisherHealthCheckView(APIView):
    """Publisher account health check।"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile found."}, status=404)

        from api.publisher_tools.publisher_management.publisher_profile import (
            get_publisher_profile_completion, calculate_publisher_health_score,
        )
        return Response({
            "success": True,
            "data": {
                "publisher_id":        publisher.publisher_id,
                "health_score":        calculate_publisher_health_score(publisher),
                "profile_completion":  get_publisher_profile_completion(publisher),
                "kyc_status":          publisher.kyc.status if hasattr(publisher, "kyc") else "not_started",
                "active_sites":        publisher.sites.filter(status="active").count(),
                "active_apps":         publisher.apps.filter(status="active").count(),
                "has_verified_payment":publisher.bank_accounts.filter(verification_status="verified").exists(),
                "pending_alerts":      publisher.fraud_alerts.filter(is_resolved=False).count() if hasattr(publisher, "fraud_alerts") else 0,
            },
        })


class PublisherOnboardingView(APIView):
    """Publisher onboarding checklist ও progress।"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile found."}, status=404)

        from api.publisher_tools.models import AdUnit, Site, App
        has_site      = Site.objects.filter(publisher=publisher, status="active").exists()
        has_app       = App.objects.filter(publisher=publisher, status="active").exists()
        has_ad_unit   = AdUnit.objects.filter(publisher=publisher, status="active").exists()
        has_payment   = publisher.bank_accounts.filter(verification_status="verified").exists()

        steps = [
            {"step": 1, "title": "Create Publisher Account",      "completed": True},
            {"step": 2, "title": "Complete Profile",              "completed": bool(publisher.contact_email and publisher.country)},
            {"step": 3, "title": "Verify Email",                  "completed": publisher.is_email_verified},
            {"step": 4, "title": "Register Site or App",          "completed": has_site or has_app},
            {"step": 5, "title": "Verify Domain / Store Listing", "completed": has_site or has_app},
            {"step": 6, "title": "Create Ad Unit",                "completed": has_ad_unit},
            {"step": 7, "title": "Configure Payment Method",      "completed": has_payment},
            {"step": 8, "title": "Complete KYC Verification",     "completed": publisher.is_kyc_verified},
        ]
        completed_count = sum(1 for s in steps if s["completed"])
        next_step = next((s for s in steps if not s["completed"]), None)
        return Response({
            "success": True,
            "data": {
                "completed_steps":  completed_count,
                "total_steps":      len(steps),
                "completion_pct":   round(completed_count / len(steps) * 100),
                "is_onboarded":     completed_count >= 6,
                "next_step":        next_step,
                "steps":            steps,
            },
        })

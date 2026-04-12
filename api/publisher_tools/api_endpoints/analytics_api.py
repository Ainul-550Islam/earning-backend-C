# api/publisher_tools/api_endpoints/analytics_api.py
"""Analytics API — Comprehensive analytics endpoints."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone


class AnalyticsAPIView(APIView):
    """
    Analytics endpoint — multi-dimensional analytics।
    Revenue, traffic, eCPM, CTR data by period।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        metric      = request.query_params.get("metric", "revenue")
        period      = request.query_params.get("period", "last_30_days")
        dimension   = request.query_params.get("dimension", "date")
        granularity = request.query_params.get("granularity", "daily")

        from api.publisher_tools.performance_analytics.publisher_dashboard import get_earnings_chart_data
        from api.publisher_tools.utils import get_date_range
        start_date, end_date = get_date_range(period)

        if dimension == "date":
            data = get_earnings_chart_data(publisher, period, metric)
        elif dimension == "country":
            from api.publisher_tools.performance_analytics.ecpm_analyzer import get_ecpm_by_country
            data = get_ecpm_by_country(publisher, start_date, end_date)
        elif dimension == "ad_unit":
            from api.publisher_tools.performance_analytics.revenue_tracker import get_top_performing_units
            data = get_top_performing_units(publisher)
        elif dimension == "format":
            from api.publisher_tools.performance_analytics.CTR_analyzer import get_ctr_by_format
            data = get_ctr_by_format(publisher)
        else:
            data = get_earnings_chart_data(publisher, period, metric)

        return Response({"success": True, "data": {
            "metric":     metric, "dimension": dimension, "period": period,
            "start_date": str(start_date), "end_date": str(end_date),
            "chart_data": data,
        }})


class ReportAPIView(APIView):
    """Report generation endpoint。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get("type", "daily")
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        if report_type == "daily":
            from api.publisher_tools.performance_analytics.daily_report import generate_daily_report
            from datetime import timedelta
            report_date = timezone.now().date() - timedelta(days=1)
            data = generate_daily_report(publisher, report_date)
        elif report_type == "weekly":
            from api.publisher_tools.performance_analytics.weekly_report import generate_weekly_report
            data = generate_weekly_report(publisher)
        elif report_type == "monthly":
            from api.publisher_tools.performance_analytics.monthly_report import generate_monthly_report
            data = generate_monthly_report(publisher)
        elif report_type == "forecast":
            from api.publisher_tools.performance_analytics.revenue_forecast import forecast_next_month
            data = forecast_next_month(publisher)
        else:
            return Response({"success": False, "message": f"Unknown report type: {report_type}"}, status=400)

        return Response({"success": True, "data": data})


class EarningsSummaryAPIView(APIView):
    """Quick earnings summary for dashboard widgets。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        from api.publisher_tools.models import PublisherEarning
        from django.db.models import Sum
        from datetime import timedelta, date

        today     = timezone.now().date()
        yesterday = today - timedelta(days=1)
        this_month_start = today.replace(day=1)
        last_month_end   = this_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        def get_rev(s, e):
            return float(PublisherEarning.objects.filter(
                publisher=publisher, date__range=[s, e]
            ).aggregate(t=Sum("publisher_revenue")).get("t") or 0)

        return Response({"success": True, "data": {
            "today":           get_rev(today, today),
            "yesterday":       get_rev(yesterday, yesterday),
            "this_month":      get_rev(this_month_start, today),
            "last_month":      get_rev(last_month_start, last_month_end),
            "lifetime":        float(publisher.total_revenue),
            "total_paid_out":  float(publisher.total_paid_out),
            "pending_balance": float(publisher.pending_balance),
            "available":       float(publisher.available_balance),
        }})

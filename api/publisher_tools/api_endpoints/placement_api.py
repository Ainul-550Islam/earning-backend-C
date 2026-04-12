# api/publisher_tools/api_endpoints/placement_api.py
"""Placement API — Bulk operations and placement optimization."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class PlacementBulkAPIView(APIView):
    """Bulk placement operations。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        action        = request.data.get("action", "")
        placement_ids = request.data.get("placement_ids", [])
        if not placement_ids or not action:
            return Response({"success": False, "message": "placement_ids and action required."}, status=400)
        from api.publisher_tools.models import AdPlacement
        from django.db import transaction
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        qs = AdPlacement.objects.filter(id__in=placement_ids, ad_unit__publisher=publisher)
        count = 0
        with transaction.atomic():
            if action == "activate":
                count = qs.update(is_active=True)
            elif action == "deactivate":
                count = qs.update(is_active=False)
            elif action == "enable_refresh":
                interval = int(request.data.get("interval_seconds", 30))
                count = qs.update(refresh_type="time_based", refresh_interval_seconds=interval)
            elif action == "disable_refresh":
                count = qs.update(refresh_type="none")
            elif action == "enable_mobile":
                count = qs.update(show_on_mobile=True)
            elif action == "disable_mobile":
                count = qs.update(show_on_mobile=False)
            elif action == "auto_optimize":
                from api.publisher_tools.optimization_tools.placement_optimizer import auto_optimize_placement
                for p in qs:
                    auto_optimize_placement(p)
                    count += 1
            else:
                return Response({"success": False, "message": f"Unknown action: {action}"}, status=400)
        return Response({"success": True, "data": {"action": action, "affected_count": count}})


class PlacementPerformanceView(APIView):
    """Placement performance report endpoint."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        from api.publisher_tools.ad_placements.placement_reporting import generate_placement_report
        from api.publisher_tools.utils import get_date_range
        period = request.query_params.get("period", "last_30_days")
        start_date, end_date = get_date_range(period)
        report = generate_placement_report(publisher, start_date, end_date)
        return Response({"success": True, "data": report})

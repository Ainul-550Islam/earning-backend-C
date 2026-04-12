# api/publisher_tools/api_endpoints/ad_unit_api.py
"""Ad Unit API — Bulk operations, tag generation, performance."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import transaction


class AdUnitBulkAPIView(APIView):
    """Bulk ad unit operations。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        action   = request.data.get("action", "")
        unit_ids = request.data.get("unit_ids", [])
        if not unit_ids or not action:
            return Response({"success": False, "message": "unit_ids and action required."}, status=400)
        from api.publisher_tools.models import AdUnit
        publisher = request.user.publisher_profile if not request.user.is_staff else None
        qs = AdUnit.objects.filter(unit_id__in=unit_ids)
        if publisher:
            qs = qs.filter(publisher=publisher)
        count = 0
        with transaction.atomic():
            if action == "pause":
                count = qs.filter(status="active").update(status="paused")
            elif action == "activate":
                count = qs.filter(status="paused").update(status="active")
            elif action == "set_test_mode":
                count = qs.update(is_test_mode=True)
            elif action == "unset_test_mode":
                count = qs.update(is_test_mode=False)
            elif action == "update_floor_price":
                new_floor = request.data.get("floor_price")
                if new_floor is None:
                    return Response({"success": False, "message": "floor_price required."}, status=400)
                from decimal import Decimal
                count = qs.update(floor_price=Decimal(str(new_floor)))
            else:
                return Response({"success": False, "message": f"Unknown action: {action}"}, status=400)
        return Response({"success": True, "data": {"action": action, "affected_count": count}})


class AdTagGeneratorView(APIView):
    """Generate ad tags for multiple units at once."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        unit_ids = request.data.get("unit_ids", [])
        tag_type = request.data.get("tag_type", "javascript")
        if not unit_ids:
            return Response({"success": False, "message": "unit_ids required."}, status=400)
        from api.publisher_tools.models import AdUnit
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        units = AdUnit.objects.filter(unit_id__in=unit_ids, publisher=publisher, status="active")
        tags = []
        for unit in units:
            tags.append({
                "unit_id":   unit.unit_id,
                "unit_name": unit.name,
                "format":    unit.format,
                "tag_code":  unit.tag_code,
                "sdk_key":   unit.sdk_key,
            })
        return Response({"success": True, "data": {"tags": tags, "count": len(tags)}})


class AdUnitOptimizationView(APIView):
    """Ad unit optimization suggestions endpoint."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        from api.publisher_tools.optimization_tools.yield_optimizer import (
            optimize_floor_prices, calculate_revenue_opportunity,
        )
        floor_suggestions = optimize_floor_prices(publisher)
        opportunity       = calculate_revenue_opportunity(publisher)
        return Response({"success": True, "data": {
            "floor_price_suggestions": floor_suggestions,
            "revenue_opportunity":     opportunity,
            "optimization_count":      len(floor_suggestions),
        }})

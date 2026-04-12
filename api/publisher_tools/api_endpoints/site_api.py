# api/publisher_tools/api_endpoints/site_api.py
"""Site API — Bulk operations and specialized site endpoints."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import transaction


class SiteBulkAPIView(APIView):
    """Bulk site operations — pause, activate, delete multiple sites。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        action    = request.data.get("action", "")
        site_ids  = request.data.get("site_ids", [])
        if not site_ids or not action:
            return Response({"success": False, "message": "site_ids and action required."}, status=400)
        from api.publisher_tools.models import Site
        publisher = request.user.publisher_profile if not request.user.is_staff else None
        qs = Site.objects.filter(site_id__in=site_ids)
        if publisher:
            qs = qs.filter(publisher=publisher)
        count = 0
        with transaction.atomic():
            if action == "activate":
                count = qs.filter(status__in=["inactive","suspended"]).update(status="active")
            elif action == "deactivate":
                count = qs.filter(status="active").update(status="inactive")
            elif action == "delete":
                count = qs.count()
                qs.delete()
            elif action == "refresh_ads_txt":
                from api.publisher_tools.services import SiteService
                for site in qs:
                    SiteService.refresh_ads_txt(site)
                    count += 1
            else:
                return Response({"success": False, "message": f"Unknown action: {action}"}, status=400)
        return Response({"success": True, "data": {"action": action, "affected_count": count}})


class SiteAdsTextView(APIView):
    """Generate ads.txt content for a publisher。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        ads_txt_line = f"ads.publishertools.io, {publisher.publisher_id}, DIRECT, f08c47fec0942fa0"
        content = f"""# Publisher Tools ads.txt
# Publisher: {publisher.display_name} ({publisher.publisher_id})
# Generated: {__import__("django.utils.timezone", fromlist=["now"]).now().date()}
{ads_txt_line}
"""
        return Response({"success": True, "data": {"ads_txt_content": content, "required_line": ads_txt_line}})


class SiteTrafficAPIView(APIView):
    """Site traffic analytics endpoint."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id=None):
        from api.publisher_tools.models import Site
        from api.publisher_tools.site_management.site_analytics import get_site_performance_summary
        try:
            if request.user.is_staff:
                site = Site.objects.get(site_id=site_id)
            else:
                site = Site.objects.get(site_id=site_id, publisher=request.user.publisher_profile)
        except Site.DoesNotExist:
            return Response({"success": False, "message": "Site not found."}, status=404)
        days = int(request.query_params.get("days", 30))
        summary = get_site_performance_summary(site, days)
        return Response({"success": True, "data": summary})

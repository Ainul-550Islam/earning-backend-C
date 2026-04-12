# api/publisher_tools/api_endpoints/app_api.py
"""App API — Bulk operations and specialized app endpoints."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db import transaction


class AppBulkAPIView(APIView):
    """Bulk app operations。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        action  = request.data.get("action", "")
        app_ids = request.data.get("app_ids", [])
        if not app_ids or not action:
            return Response({"success": False, "message": "app_ids and action required."}, status=400)
        from api.publisher_tools.models import App
        publisher = request.user.publisher_profile if not request.user.is_staff else None
        qs = App.objects.filter(app_id__in=app_ids)
        if publisher:
            qs = qs.filter(publisher=publisher)
        count = 0
        with transaction.atomic():
            if action == "activate":
                count = qs.filter(status="inactive").update(status="active")
            elif action == "deactivate":
                count = qs.filter(status="active").update(status="inactive")
            elif action == "sync_store_metadata":
                from api.publisher_tools.app_management.app_store import AppStoreMetadata
                for app in qs:
                    try:
                        meta, _ = AppStoreMetadata.objects.get_or_create(app=app)
                        meta.sync_from_store()
                        count += 1
                    except Exception:
                        pass
            else:
                return Response({"success": False, "message": f"Unknown action: {action}"}, status=400)
        return Response({"success": True, "data": {"action": action, "affected_count": count}})


class AppSDKIntegrationView(APIView):
    """App SDK integration guide endpoint."""
    permission_classes = [IsAuthenticated]

    def get(self, request, app_id=None):
        from api.publisher_tools.models import App
        try:
            app = App.objects.get(app_id=app_id, publisher=request.user.publisher_profile)
        except App.DoesNotExist:
            return Response({"success": False, "message": "App not found."}, status=404)
        platform = app.platform
        integration_guide = {
            "android": {
                "gradle_dependency": "implementation 'io.publishertools:android-sdk:1.0.0'",
                "init_code": f"PublisherTools.initialize(this, \"{app.sdk_key if hasattr(app, 'sdk_key') else 'YOUR_SDK_KEY'}\");",
                "documentation_url": "https://docs.publishertools.io/android-sdk",
            },
            "ios": {
                "podfile":           "pod 'PublisherToolsSDK'",
                "init_code": f"PublisherTools.initialize(publisherId: \"{app.publisher.publisher_id}\");",
                "documentation_url": "https://docs.publishertools.io/ios-sdk",
            },
        }
        return Response({"success": True, "data": {
            "app_id": app.app_id, "app_name": app.name, "platform": platform,
            "integration": integration_guide.get(platform, integration_guide.get("android")),
        }})

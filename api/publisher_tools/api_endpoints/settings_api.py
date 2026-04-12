# api/publisher_tools/api_endpoints/settings_api.py
"""Settings API — Publisher settings, preferences, notification config。"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser


class PublisherSettingsAPIView(APIView):
    """Publisher settings management。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Publisher-এর current settings।"""
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        settings_data = {
            "publisher_id":          publisher.publisher_id,
            "display_name":          publisher.display_name,
            "contact_email":         publisher.contact_email,
            "contact_phone":         publisher.contact_phone,
            "website":               publisher.website,
            "country":               publisher.country,
            "city":                  publisher.city,
            "address":               publisher.address,
            "revenue_share_pct":     float(publisher.revenue_share_percentage),
            "tier":                  publisher.tier,
            "status":                publisher.status,
            "notification_settings": publisher.metadata.get("notifications", {
                "email_daily_report":    True,
                "email_invoice":         True,
                "email_fraud_alert":     True,
                "email_payout":          True,
                "webhook_enabled":       False,
            }),
            "api_settings": {
                "api_key_visible": False,
                "api_access":      True,
                "rate_limit":      "120/min",
            },
        }
        return Response({"success": True, "data": settings_data})

    def patch(self, request):
        """Publisher settings update করে।"""
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)

        allowed_fields = ["display_name", "contact_phone", "website", "city", "address"]
        updated = False
        for field in allowed_fields:
            if field in request.data:
                setattr(publisher, field, request.data[field])
                updated = True

        if "notification_settings" in request.data:
            if not isinstance(publisher.metadata, dict):
                publisher.metadata = {}
            publisher.metadata["notifications"] = request.data["notification_settings"]
            updated = True

        if updated:
            publisher.save()

        return Response({"success": True, "message": "Settings updated.", "data": {"updated": updated}})


class NotificationSettingsAPIView(APIView):
    """Notification preferences management。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        defaults = {
            "email_daily_report": True,
            "email_weekly_report": True,
            "email_monthly_report": True,
            "email_invoice_created": True,
            "email_invoice_paid": True,
            "email_payout_processed": True,
            "email_fraud_alert": True,
            "email_quality_alert": True,
            "email_kyc_update": True,
            "email_account_status": True,
            "webhook_impressions": False,
            "webhook_clicks": False,
            "webhook_conversions": True,
            "webhook_payments": True,
            "webhook_fraud": True,
        }
        current = publisher.metadata.get("notifications", defaults)
        return Response({"success": True, "data": current})

    def put(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        if not isinstance(publisher.metadata, dict):
            publisher.metadata = {}
        publisher.metadata["notifications"] = request.data
        publisher.save(update_fields=["metadata", "updated_at"])
        return Response({"success": True, "message": "Notification settings saved.", "data": request.data})


class APIKeySettingsView(APIView):
    """API key management endpoint。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        return Response({"success": True, "data": {
            "publisher_id": publisher.publisher_id,
            "api_key":      publisher.api_key,
            "api_key_prefix": publisher.api_key[:8] + "..." if publisher.api_key else "",
            "has_secret":   bool(publisher.api_secret),
        }})

    def post(self, request):
        """API key regenerate করে।"""
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        from api.publisher_tools.services import PublisherService
        publisher = PublisherService.regenerate_api_key(publisher)
        return Response({"success": True, "message": "API key regenerated. Store your new secret securely.", "data": {
            "api_key":    publisher.api_key,
            "api_secret": publisher.api_secret,
            "warning":    "This is the only time you can view your API secret. Store it securely.",
        }})


class PublisherPreferencesAPIView(APIView):
    """Publisher UI preferences — theme, language, timezone。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        prefs = publisher.metadata.get("preferences", {
            "theme": "light",
            "language": "en",
            "timezone": "UTC",
            "date_format": "YYYY-MM-DD",
            "currency_display": "USD",
            "dashboard_period": "last_30_days",
            "items_per_page": 20,
        })
        return Response({"success": True, "data": prefs})

    def put(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        if not isinstance(publisher.metadata, dict):
            publisher.metadata = {}
        allowed_prefs = ["theme", "language", "timezone", "date_format", "currency_display", "dashboard_period", "items_per_page"]
        prefs = {k: v for k, v in request.data.items() if k in allowed_prefs}
        publisher.metadata["preferences"] = prefs
        publisher.save(update_fields=["metadata", "updated_at"])
        return Response({"success": True, "message": "Preferences saved.", "data": prefs})

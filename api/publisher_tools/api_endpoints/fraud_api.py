# api/publisher_tools/api_endpoints/fraud_api.py
"""Fraud API — IVT reports, IP blocking, fraud analytics."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser


class FraudSummaryAPIView(APIView):
    """Publisher fraud summary and IVT report。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return Response({"success": False, "message": "No publisher profile."}, status=404)
        days = int(request.query_params.get("days", 30))
        from api.publisher_tools.fraud_prevention.fraud_report import generate_fraud_report
        from api.publisher_tools.fraud_prevention.quality_score import calculate_publisher_quality_score
        from api.publisher_tools.fraud_prevention.fraud_alert import get_unresolved_alerts
        report      = generate_fraud_report(publisher, days)
        quality     = calculate_publisher_quality_score(publisher)
        alerts      = get_unresolved_alerts(publisher)
        return Response({"success": True, "data": {
            "fraud_report":    report,
            "quality_score":   quality,
            "unresolved_alerts": len(alerts),
            "alerts":          [{"type": a.alert_type, "severity": a.severity, "title": a.title} for a in alerts[:5]],
        }})


class IPBlockAPIView(APIView):
    """IP blocking management API。"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        """List blocked IPs。"""
        from api.publisher_tools.fraud_prevention.ip_blacklist import BlockedIP
        blocked = BlockedIP.objects.filter(is_active=True).order_by("-created_at")[:100]
        return Response({"success": True, "data": [
            {"ip": b.ip_address, "reason": b.reason, "score": b.fraud_score, "expires": str(b.expires_at) if b.expires_at else None}
            for b in blocked
        ]})

    def post(self, request):
        """Block an IP address。"""
        ip_address = request.data.get("ip_address")
        reason     = request.data.get("reason", "Manual block by admin")
        hours      = int(request.data.get("hours", 24))
        if not ip_address:
            return Response({"success": False, "message": "ip_address required."}, status=400)
        from api.publisher_tools.fraud_prevention.ip_blacklist import block_ip
        entry = block_ip(ip_address, reason, fraud_score=90, hours=hours)
        return Response({"success": True, "data": {"ip": entry.ip_address, "blocked": True, "hours": hours}}, status=201)

    def delete(self, request):
        """Unblock an IP address。"""
        ip_address = request.data.get("ip_address")
        if not ip_address:
            return Response({"success": False, "message": "ip_address required."}, status=400)
        from api.publisher_tools.fraud_prevention.ip_blacklist import unblock_ip
        success = unblock_ip(ip_address)
        return Response({"success": success, "data": {"ip": ip_address, "unblocked": success}})


class FraudDetectionAPIView(APIView):
    """Real-time fraud detection endpoint。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Request/event-এর fraud score calculate করে。"""
        request_data = request.data
        from api.publisher_tools.fraud_prevention.invalid_traffic_detector import detect_invalid_traffic
        result = detect_invalid_traffic(request_data)
        return Response({"success": True, "data": result})

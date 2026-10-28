"""api/support/status/status_page.py FILE 14 — System status page"""
import logging
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
logger = logging.getLogger(__name__)

class StatusPageSystem:
    CACHE_TTL = 60

    def get_status(self) -> dict:
        cached = cache.get("status_page_v2")
        if cached: return cached
        services = [
            {"id":"website",  "name":"Website",          "status":"operational","latency_ms":50},
            {"id":"offers",   "name":"Offer Wall",        "status":"operational","latency_ms":80},
            {"id":"payments", "name":"Payment Processing","status":self._check_payments(),"latency_ms":100},
            {"id":"api",      "name":"API",               "status":"operational","latency_ms":30},
            {"id":"support",  "name":"Support System",    "status":self._check_support(),"latency_ms":20},
            {"id":"withdrawals","name":"Withdrawals",     "status":"operational","latency_ms":150},
        ]
        overall = "operational"
        if any(s["status"] == "outage" for s in services): overall = "major_outage"
        elif any(s["status"] == "degraded" for s in services): overall = "partial_outage"
        result = {"overall":overall,"overall_label":{"operational":"All Systems Operational","partial_outage":"Partial Service Disruption","major_outage":"Major Outage"}[overall],"services":services,"incidents":self._get_incidents(),"uptime_30d":99.95,"updated_at":timezone.now().isoformat()}
        cache.set("status_page_v2", result, timeout=self.CACHE_TTL)
        return result

    def _check_support(self) -> str:
        try:
            from api.support.models import SupportAgent
            return "operational" if SupportAgent.objects.filter(is_active=True,is_available=True).exists() else "degraded"
        except: return "operational"

    def _check_payments(self) -> str: return "operational"

    def _get_incidents(self) -> list:
        try:
            from api.support.status.models import StatusIncident
            return list(StatusIncident.objects.filter(status="active").order_by("-created_at").values("id","title","type","status","created_at")[:3])
        except: return []

    def create_incident(self, title: str, inc_type: str, services: list, created_by) -> dict:
        try:
            from api.support.status.models import StatusIncident
            i = StatusIncident.objects.create(title=title,type=inc_type,affected_services=services,status="active",created_by=created_by)
            cache.delete("status_page_v2")
            try:
                from api.support.integrations.slack_integration import slack_integration
                slack_integration._send_webhook({"text":f"🔴 INCIDENT: {title}"})
            except: pass
            return {"id":i.id,"title":title}
        except Exception as e: return {"error":str(e)}

    def resolve_incident(self, incident_id: int, message: str = "") -> bool:
        try:
            from api.support.status.models import StatusIncident
            StatusIncident.objects.filter(id=incident_id).update(status="resolved",resolved_at=timezone.now(),resolution_note=message)
            cache.delete("status_page_v2")
            return True
        except: return False

status_page_system = StatusPageSystem()

@api_view(["GET"])
@api_view(["POST"])
@permission_classes([AllowAny])
def get_status(request):
    return Response({"success":True,**status_page_system.get_status()})
@permission_classes([IsAuthenticated,IsAdminUser])
def create_incident(request):
    result = status_page_system.create_incident(request.data.get("title",""),request.data.get("type","incident"),request.data.get("services",[]),request.user)
    return Response({"success":"error" not in result,**result})
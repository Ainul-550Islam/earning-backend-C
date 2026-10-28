# fraud_detection/views_sla.py — SLA API Views
# DRY: all logic in sla_manager.py
from __future__ import annotations
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status

logger = logging.getLogger(__name__)
def _ok(d, st=200):  return Response({"success": True, "data": d}, status=st)
def _err(m, st=400): return Response({"success": False, "error": str(m)}, status=st)


class SLADashboardAPIView(APIView):
    """GET /sla/dashboard/ — SLA KPIs: open, breached, near-breach."""
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.sla_manager import get_sla_manager
        return _ok(get_sla_manager().get_sla_dashboard())


class SLABreachedCasesAPIView(APIView):
    """GET /sla/breached/ — list all currently breached cases."""
    permission_classes = [IsAuthenticated]
    def get(self, request):
        from api.fraud_detection.sla_manager import get_sla_manager
        breached = get_sla_manager().get_breached_cases()
        return _ok({"cases": [{"case_id": s.case_id, "severity": s.severity,
                                "elapsed_hours": round(s.elapsed_hours, 1),
                                "target_hours": s.target_hours,
                                "breach_pct": s.breach_pct,
                                "escalate_to": s.escalate_to}
                               for s in breached], "total": len(breached)})


class SLACaseStatusAPIView(APIView):
    """GET /sla/cases/<case_id>/ — SLA status for a single case."""
    permission_classes = [IsAuthenticated]
    def get(self, request, case_id):
        from api.fraud_detection.sla_manager import get_sla_manager
        sla = get_sla_manager().get_case_sla_status(case_id)
        if not sla:
            return _err("Case not found or SLA unavailable", 404)
        return _ok({"case_id": sla.case_id, "severity": sla.severity,
                    "target_hours": sla.target_hours,
                    "elapsed_hours": round(sla.elapsed_hours, 1),
                    "is_breached": sla.is_breached,
                    "breach_pct": sla.breach_pct,
                    "escalate_to": sla.escalate_to})


class SLAEscalateAPIView(APIView):
    """POST /sla/cases/<case_id>/escalate/ — manually escalate a case."""
    permission_classes = [IsAdminUser]
    def post(self, request, case_id):
        escalate_to = request.data.get("escalate_to", "senior_analyst")
        reason      = request.data.get("reason", "manual_escalation")
        try:
            from api.fraud_detection.sla_manager import get_sla_manager
            result = get_sla_manager().escalate_case(case_id, escalate_to, reason)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc), 500)


class SLAAutoEscalateAPIView(APIView):
    """POST /sla/auto-escalate/ — trigger auto-escalation of all breached cases."""
    permission_classes = [IsAdminUser]
    def post(self, request):
        try:
            from api.fraud_detection.sla_manager import get_sla_manager
            result = get_sla_manager().auto_escalate_breached()
            return _ok(result)
        except Exception as exc:
            return _err(str(exc), 500)

# api/support/services/agent/AgentService.py  — WORLD #1 COMPLETE
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q
logger = logging.getLogger(__name__)

class AgentService:
    def get_leaderboard(self, days: int = 30, tenant=None) -> list:
        from api.support.models import SupportAgent, SupportTicket, TicketRating
        since = timezone.now() - timedelta(days=days)
        agents = SupportAgent.objects.filter(is_active=True)
        if tenant: agents = agents.filter(tenant=tenant)
        leaderboard = []
        for agent in agents.select_related("user"):
            tickets  = SupportTicket.objects.filter(assigned_to=agent.user, created_at__gte=since)
            resolved = tickets.filter(status="resolved").count()
            total    = tickets.count()
            responded= tickets.filter(admin_responded_at__isnull=False)
            avg_resp = 0
            if responded.exists():
                times = [(t.admin_responded_at - t.created_at).total_seconds()/60 for t in responded]
                avg_resp = round(sum(times)/len(times), 1) if times else 0
            csat = TicketRating.objects.filter(ticket__assigned_to=agent.user, created_at__gte=since).aggregate(avg=Avg("rating"))["avg"] or 0
            score = (resolved/max(total,1))*40 + (csat/5)*40 + max(0,(1-avg_resp/480))*20
            leaderboard.append({
                "rank":0,"username":agent.user.username,"role":agent.role,
                "total_assigned":total,"resolved":resolved,
                "resolution_rate":round(resolved/max(total,1)*100,1),
                "avg_response_min":avg_resp,"csat_score":round(csat,2),
                "performance_score":round(score,1),
                "active_tickets":tickets.filter(status__in=["open","in_progress","waiting_user"]).count(),
            })
        leaderboard.sort(key=lambda x: x["performance_score"], reverse=True)
        for i, e in enumerate(leaderboard): e["rank"] = i+1
        return leaderboard

    def get_agent_metrics(self, agent_user, days: int = 1) -> dict:
        from api.support.models import SupportTicket, TicketRating
        since = timezone.now() - timedelta(days=days)
        tickets = SupportTicket.objects.filter(assigned_to=agent_user, created_at__gte=since)
        total   = tickets.count()
        resolved= tickets.filter(status="resolved").count()
        responded = tickets.filter(admin_responded_at__isnull=False)
        avg_resp = 0
        if responded.exists():
            times = [(t.admin_responded_at-t.created_at).total_seconds()/60 for t in responded]
            avg_resp = round(sum(times)/len(times),1) if times else 0
        csat = TicketRating.objects.filter(ticket__assigned_to=agent_user, created_at__gte=since).aggregate(avg=Avg("rating"))["avg"] or 0
        return {"period_days":days,"total_assigned":total,"resolved":resolved,
                "resolution_rate":round(resolved/max(total,1)*100,1),
                "avg_response_min":avg_resp,"csat_score":round(csat,2),
                "active":tickets.filter(status__in=["open","in_progress","waiting_user"]).count()}

class WorkloadBalancerService:
    def get_workload_report(self) -> list:
        from api.support.models import SupportAgent, SupportTicket
        agents = SupportAgent.objects.filter(is_active=True).annotate(
            active_count=Count("user__assigned_support_tickets",
                filter=Q(user__assigned_support_tickets__status__in=["open","in_progress","waiting_user"]))
        ).select_related("user")
        report = []
        for agent in agents:
            load_pct = round(agent.active_count/max(agent.max_concurrent,1)*100,1)
            report.append({"username":agent.user.username,"role":agent.role,"active":agent.active_count,
                           "max":agent.max_concurrent,"load_pct":load_pct,"available":agent.is_available,
                           "status":"overloaded" if load_pct>=90 else "busy" if load_pct>=60 else "available"})
        return sorted(report, key=lambda x: x["load_pct"], reverse=True)

class AgentPerformanceService:
    def get_metrics(self, agent_user, days: int = 1) -> dict:
        return AgentService().get_agent_metrics(agent_user, days=days)

agent_service     = AgentService()
workload_balancer = WorkloadBalancerService()
performance_service = AgentPerformanceService()
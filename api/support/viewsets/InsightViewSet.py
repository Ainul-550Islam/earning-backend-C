# api/support/viewsets/InsightViewSet.py  — WORLD #1
"""Dashboard charts, CSAT trend, volume analytics."""
import logging
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class InsightViewSet(ViewSet):
    """
    GET /api/support/insights/dashboard/ — full dashboard data
    GET /api/support/insights/csat/      — CSAT trend
    GET /api/support/insights/volume/    — ticket volume chart
    GET /api/support/insights/agents/    — agent leaderboard
    GET /api/support/insights/sla/       — SLA compliance
    GET /api/support/insights/topics/    — topic clusters
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        from api.support.services import ticket_service, sla_service
        from api.support.services.agent.AgentService import agent_service
        stats      = ticket_service.get_stats()
        sla_report = sla_service.get_compliance_report(days=7)
        leaderboard = agent_service.get_leaderboard(days=30)[:5]
        return Response({
            'stats':      stats,
            'sla':        sla_report,
            'top_agents': leaderboard,
            'period':     '7 days',
        })

    @action(detail=False, methods=['get'])
    def csat(self, request):
        from api.support.models import TicketRating
        from django.db.models import Avg, Count
        days  = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        data  = TicketRating.objects.filter(rated_at__gte=since)
        avg   = data.aggregate(avg=Avg('score'))['avg'] or 0
        total = data.count()
        promoters  = data.filter(score=5).count()
        detractors = data.filter(score__lte=2).count()
        nps = round((promoters - detractors) / max(total,1) * 100, 1)
        return Response({'avg_score':round(avg,2),'total':total,'promoters':promoters,'detractors':detractors,'nps':nps,'period_days':days})

    @action(detail=False, methods=['get'])
    def volume(self, request):
        from api.support.models import SupportTicket
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        days  = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        data  = (SupportTicket.objects.filter(created_at__gte=since)
                 .annotate(date=TruncDate('created_at'))
                 .values('date').annotate(count=Count('id')).order_by('date'))
        return Response({'chart': list(data), 'period_days': days})

    @action(detail=False, methods=['get'])
    def agents(self, request):
        from api.support.services.agent.AgentService import agent_service
        days = int(request.query_params.get('days', 30))
        return Response(agent_service.get_leaderboard(days=days))

    @action(detail=False, methods=['get'])
    def sla(self, request):
        from api.support.services import sla_service
        days = int(request.query_params.get('days', 30))
        return Response(sla_service.get_compliance_report(days=days))

    @action(detail=False, methods=['get'])
    def topics(self, request):
        from api.support.models import TopicCluster
        from django.utils import timezone
        today = timezone.now().date()
        clusters = TopicCluster.objects.filter(period=today).order_by('-ticket_count')[:10]
        return Response([{'name':c.name,'volume':c.ticket_count,'trend':c.trend,'keywords':c.keywords} for c in clusters])
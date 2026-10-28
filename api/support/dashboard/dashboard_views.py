"""
api/support/dashboard/dashboard_views.py
FILE 16/70 — Dashboard API Views

REST API endpoints for dashboard data।
Agent/Supervisor/Admin — role-based access।

Endpoints:
    GET /support/dashboard/overview/
    GET /support/dashboard/tickets/
    GET /support/dashboard/agents/
    GET /support/dashboard/sla/
    GET /support/dashboard/chat/
    GET /support/dashboard/charts/
    GET /support/dashboard/alerts/
    POST /support/dashboard/refresh/
"""
import logging
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.support.dashboard.realtime_dashboard import realtime_dashboard
from api.support.permissions import IsSupportAgent, IsSupervisorOrAbove

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# MAIN DASHBOARD
# ══════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_full(request):
    """
    GET /support/dashboard/
    Full dashboard data — one API call।
    """
    try:
        data = realtime_dashboard.get_full_dashboard(user=request.user)
        return Response({'success': True, 'dashboard': data})
    except Exception as e:
        logger.error(f'Dashboard full failed: {e}')
        return Response({'error': str(e)}, status=500)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_overview(request):
    """GET /support/dashboard/overview/ — KPI cards"""
    return Response({
        'success':  True,
        'overview': realtime_dashboard.get_overview(),
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_ticket_queue(request):
    """GET /support/dashboard/tickets/ — live queue"""
    limit = int(request.query_params.get('limit', 20))
    return Response({
        'success': True,
        'queue':   realtime_dashboard.get_ticket_queue(limit=limit),
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_agent_status(request):
    """GET /support/dashboard/agents/ — agent availability"""
    return Response({
        'success': True,
        'agents':  realtime_dashboard.get_agent_status(),
    })
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_sla(request):
    """GET /support/dashboard/sla/ — SLA health"""
    from api.support.sla.advanced_sla_engine import advanced_sla_engine
    return Response({
        'success':    True,
        'sla_status': realtime_dashboard.get_sla_status(),
        'compliance': advanced_sla_engine.get_compliance_report(days=30),
        'breached':   _get_breached_tickets(),
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_chat(request):
    """GET /support/dashboard/chat/ — live chat status"""
    return Response({
        'success':     True,
        'chat_status': realtime_dashboard.get_chat_status(),
        'queue':       _get_chat_queue(),
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_charts(request):
    """GET /support/dashboard/charts/ — chart data"""
    days = int(request.query_params.get('days', 7))
    return Response({
        'success':       True,
        'hourly_volume': realtime_dashboard.get_hourly_volume(),
        'daily_volume':  _get_daily_volume(days),
        'by_category':   realtime_dashboard.get_top_issues(days),
        'by_priority':   _get_by_priority(),
        'csat_trend':    _get_csat_trend(days),
        'resolution_rate':_get_resolution_rate(days),
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_alerts(request):
    """GET /support/dashboard/alerts/ — active alerts"""
    alerts = []

    # Unassigned tickets
    from api.support.models import SupportTicket
    unassigned = SupportTicket.objects.filter(status='open', assigned_to=None).count()
    if unassigned > 0:
        alerts.append({
            'type':     'warning',
            'title':    f'{unassigned} Unassigned Tickets',
            'message':  f'{unassigned} tickets need assignment.',
            'action':   '/support/admin/bulk-assign/',
            'priority': 'high' if unassigned > 5 else 'medium',
        })

    # SLA breaches
    sla_data = realtime_dashboard.get_sla_status()
    breached = sla_data.get('total_breached', 0)
    if breached > 0:
        alerts.append({
            'type':     'error',
            'title':    f'{breached} SLA Breaches',
            'message':  f'{breached} tickets have breached SLA.',
            'action':   '/support/dashboard/sla/',
            'priority': 'urgent',
        })

    # SLA warnings
    fr_warning = sla_data.get('fr_warning', 0)
    if fr_warning > 0:
        alerts.append({
            'type':     'warning',
            'title':    f'{fr_warning} SLA Warnings',
            'message':  f'{fr_warning} tickets approaching SLA deadline.',
            'action':   '/support/dashboard/sla/',
            'priority': 'high',
        })

    # Long chat queue
    chat = realtime_dashboard.get_chat_status()
    if chat.get('waiting', 0) > 3:
        alerts.append({
            'type':     'warning',
            'title':    f'{chat["waiting"]} Users Waiting in Chat',
            'message':  f'Average wait: {chat.get("avg_wait_min", 0):.0f} minutes.',
            'action':   '/support/dashboard/chat/',
            'priority': 'high',
        })

    # All agents offline
    agent_data = realtime_dashboard.get_agent_status()
    online     = sum(1 for a in agent_data if a.get('status') == 'online')
    if online == 0 and agent_data:
        alerts.append({
            'type':     'error',
            'title':    'No Agents Online',
            'message':  'All support agents are currently offline.',
            'action':   '/support/agents/',
            'priority': 'urgent',
        })

    # Sort by priority
    priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
    alerts.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))

    return Response({
        'success':      True,
        'alerts':       alerts,
        'alert_count':  len(alerts),
        'has_critical': any(a['priority'] == 'urgent' for a in alerts),
    })
@permission_classes([IsAuthenticated, IsSupportAgent])
def dashboard_refresh(request):
    """POST /support/dashboard/refresh/ — force cache refresh"""
    realtime_dashboard.invalidate_cache()
    return Response({
        'success':    True,
        'message':    'Dashboard cache cleared.',
        'refreshed_at': timezone.now().isoformat(),
    })


# ══════════════════════════════════════════════════════
# SUPERVISOR / ADMIN ONLY
# ══════════════════════════════════════════════════════

@permission_classes([IsAuthenticated, IsSupervisorOrAbove])
def dashboard_team_performance(request):
    """GET /support/dashboard/team/ — team performance"""
    days = int(request.query_params.get('days', 7))
    from api.support.analytics.agent_heatmap import agent_heatmap
    return Response({
        'success':     True,
        'leaderboard': _get_leaderboard(days),
        'heatmap':     agent_heatmap.get_team_heatmap(days),
        'workload':    _get_workload_distribution(),
    })

@permission_classes([IsAuthenticated, IsSupervisorOrAbove])
def dashboard_forecast(request):
    """GET /support/dashboard/forecast/ — ticket volume forecast"""
    from api.support.analytics.predictive_analytics import predictive_analytics
    return Response({
        'success':  True,
        'forecast': predictive_analytics.forecast_volume(days=7),
        'trends':   predictive_analytics.get_trends(),
    })
@permission_classes([IsAuthenticated, IsSupervisorOrAbove])
def dashboard_churn_risk(request):
    """GET /support/dashboard/churn/ — high risk users"""
    from api.support.ai.ai_churn_predictor import churn_predictor
    return Response({
        'success':    True,
        'high_risk':  churn_predictor.get_high_risk_users(limit=20),
    })


# ══════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════

def _get_breached_tickets() -> list:
    try:
        from api.support.models import SupportTicket
        return list(
            SupportTicket.objects.filter(
                sla__first_response_breached=True,
                status__in=['open','in_progress','waiting_user'],
            ).select_related('user','assigned_to').values(
                'ticket_id','subject','priority','category',
                'assigned_to__username','created_at',
            )[:20]
        )
    except Exception:
        return []


def _get_chat_queue() -> list:
    try:
        from api.support.models import ChatSession
        return list(
            ChatSession.objects.filter(status='waiting')
            .select_related('user')
            .order_by('started_at')
            .values('session_id','user__username','started_at','queue_position')[:10]
        )
    except Exception:
        return []


def _get_daily_volume(days: int) -> list:
    try:
        from api.support.models import SupportTicket
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        return list(
            SupportTicket.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
    except Exception:
        return []


def _get_by_priority() -> dict:
    try:
        from api.support.models import SupportTicket
        from django.db.models import Count
        result = {}
        for p in ['urgent','high','medium','low']:
            result[p] = SupportTicket.objects.filter(
                status__in=['open','in_progress','waiting_user'],
                priority=p,
            ).count()
        return result
    except Exception:
        return {}


def _get_csat_trend(days: int) -> list:
    try:
        from api.support.models import TicketRating
        from django.db.models import Avg
        from django.db.models.functions import TruncDate
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        return list(
            TicketRating.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(avg=Avg('rating'))
            .order_by('date')
        )
    except Exception:
        return []


def _get_resolution_rate(days: int) -> list:
    try:
        from api.support.models import SupportTicket
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        return list(
            SupportTicket.objects.filter(
                resolved_at__gte=since
            ).annotate(date=TruncDate('resolved_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
    except Exception:
        return []


def _get_leaderboard(days: int) -> list:
    try:
        from api.support.models import SupportAgent
        from api.support.services.agent.AgentService import agent_service
        return agent_service.get_leaderboard(days=days)
    except Exception:
        return []


def _get_workload_distribution() -> list:
    try:
        from api.support.services.agent.WorkloadBalancerService import workload_balancer
        if hasattr(workload_balancer, "get_workload_report"):
            return workload_balancer.get_workload_report()
        # Fallback: build basic report
        from api.support.models import SupportAgent, SupportTicket
        from django.db.models import Count, Q
        agents = SupportAgent.objects.filter(is_active=True).annotate(
            active_count=Count("user__assigned_tickets",
                filter=Q(user__assigned_tickets__status__in=["open","in_progress","waiting_user"]))
        )
        return [{"username": a.user.username, "active": a.active_count,
                 "max": a.max_concurrent, "load_pct": round(a.active_count/a.max_concurrent*100) if a.max_concurrent else 0}
                for a in agents]
    except Exception:
        return []
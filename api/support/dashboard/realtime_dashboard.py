"""
api/support/dashboard/realtime_dashboard.py
FILE 14/70 — Real-time Support Dashboard

WebSocket-powered live admin dashboard।
প্রতি 30 সেকেন্ডে auto-refresh।
Agent-এর সামনে সব data live দেখাবে।

Metrics:
- Live ticket queue
- Agent availability
- SLA status
- Chat queue
- Today's performance
- Real-time charts
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_TTL = 15  # 15 seconds cache


class RealtimeDashboard:
    """
    Real-time dashboard data provider।
    WebSocket consumer এই class-এর data push করবে।
    """

    # ──────────────────────────────────────────
    # MAIN DASHBOARD DATA
    # ──────────────────────────────────────────
    def get_full_dashboard(self, user=None) -> dict:
        """
        Complete dashboard data এক call-এ।
        Agent/Supervisor/Admin — role-based data।
        """
        cached = cache.get('dashboard:full')
        if cached and not user:
            return cached

        data = {
            'overview':       self.get_overview(),
            'ticket_queue':   self.get_ticket_queue(),
            'agent_status':   self.get_agent_status(),
            'sla_status':     self.get_sla_status(),
            'chat_status':    self.get_chat_status(),
            'today_metrics':  self.get_today_metrics(),
            'hourly_volume':  self.get_hourly_volume(),
            'top_issues':     self.get_top_issues(),
            'generated_at':   timezone.now().isoformat(),
        }

        cache.set('dashboard:full', data, timeout=CACHE_TTL)
        return data

    # ──────────────────────────────────────────
    # OVERVIEW CARDS
    # ──────────────────────────────────────────
    def get_overview(self) -> dict:
        """Top-level KPI cards"""
        cached = cache.get('dashboard:overview')
        if cached:
            return cached

        try:
            from api.support.models import (
                SupportTicket, SupportAgent,
                ChatSession, TicketRating,
            )
            from django.db.models import Avg, Count

            today     = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tickets   = SupportTicket.objects

            # Previous period for trend calculation
            yesterday = today - timedelta(days=1)

            # Today
            created_today   = tickets.filter(created_at__gte=today).count()
            resolved_today  = tickets.filter(resolved_at__gte=today).count()
            created_yest    = tickets.filter(created_at__gte=yesterday, created_at__lt=today).count()
            resolved_yest   = tickets.filter(resolved_at__gte=yesterday, resolved_at__lt=today).count()

            # Current state
            open_count    = tickets.filter(status__in=['open', 'in_progress', 'waiting_user']).count()
            unassigned    = tickets.filter(status='open', assigned_to=None).count()
            escalated     = tickets.filter(escalated=True, status__in=['open','in_progress']).count()
            breach_count  = tickets.filter(sla__first_response_breached=True).count() + \
                           tickets.filter(sla__resolution_breached=True).count()

            # Agent stats
            total_agents  = SupportAgent.objects.filter(is_active=True).count()
            online_agents = SupportAgent.objects.filter(is_active=True, is_available=True).count()

            # Chat
            waiting_chats = ChatSession.objects.filter(status='waiting').count()
            active_chats  = ChatSession.objects.filter(status='active').count()

            # CSAT
            csat = TicketRating.objects.filter(
                created_at__gte=today
            ).aggregate(avg=Avg('rating'))['avg'] or 0

            data = {
                'open_tickets':    {'value': open_count,      'trend': self._trend(open_count, 0)},
                'created_today':   {'value': created_today,   'trend': self._trend(created_today, created_yest)},
                'resolved_today':  {'value': resolved_today,  'trend': self._trend(resolved_today, resolved_yest)},
                'unassigned':      {'value': unassigned,       'alert': unassigned > 5},
                'escalated':       {'value': escalated,        'alert': escalated > 0},
                'sla_breaches':    {'value': breach_count,     'alert': breach_count > 0},
                'agents_online':   {'value': online_agents,    'total': total_agents},
                'waiting_chats':   {'value': waiting_chats,    'alert': waiting_chats > 3},
                'active_chats':    {'value': active_chats},
                'csat_score':      {'value': round(csat, 1),   'max': 5},
            }

            cache.set('dashboard:overview', data, timeout=CACHE_TTL)
            return data

        except Exception as e:
            logger.error(f'Dashboard overview failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # TICKET QUEUE (Live)
    # ──────────────────────────────────────────
    def get_ticket_queue(self, limit: int = 20) -> list:
        """Live ticket queue — সবচেয়ে urgent আগে"""
        try:
            from api.support.models import SupportTicket
            from django.db.models import Q

            tickets = SupportTicket.objects.filter(
                status__in=['open', 'in_progress', 'waiting_user']
            ).select_related(
                'user', 'assigned_to', 'sla'
            ).order_by(
                '-escalated',
                'priority_order',
                'created_at',
            )

            queue = []
            priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}

            for ticket in tickets[:limit]:
                sla_info = {}
                try:
                    sla = ticket.sla
                    now = timezone.now()
                    if sla.first_response_due and not sla.first_response_at:
                        remaining_min = (sla.first_response_due - now).total_seconds() / 60
                        sla_info = {
                            'remaining_min': round(remaining_min, 1),
                            'is_breached':   remaining_min < 0,
                            'is_warning':    0 <= remaining_min < 60,
                        }
                except Exception:
                    pass

                queue.append({
                    'ticket_id':   ticket.ticket_id,
                    'subject':     ticket.subject[:60],
                    'user':        ticket.user.username,
                    'status':      ticket.status,
                    'priority':    ticket.priority,
                    'category':    ticket.category,
                    'channel':     getattr(ticket, 'channel', 'web'),
                    'assigned_to': ticket.assigned_to.username if ticket.assigned_to else None,
                    'escalated':   ticket.escalated,
                    'wait_minutes':round((timezone.now() - ticket.created_at).total_seconds() / 60, 0),
                    'sla':         sla_info,
                    'created_at':  ticket.created_at.isoformat(),
                })

            return queue

        except Exception as e:
            logger.error(f'Ticket queue failed: {e}')
            return []

    # ──────────────────────────────────────────
    # AGENT STATUS (Live)
    # ──────────────────────────────────────────
    def get_agent_status(self) -> list:
        """All agents-এর real-time status"""
        try:
            from api.support.models import SupportAgent, SupportTicket
            from django.db.models import Count, Q

            agents = SupportAgent.objects.filter(
                is_active=True
            ).select_related(
                'user', 'status', 'department'
            ).annotate(
                active_tickets=Count(
                    'user__assigned_tickets',
                    filter=Q(user__assigned_tickets__status__in=['open','in_progress','waiting_user'])
                )
            )

            result = []
            for agent in agents:
                status = 'offline'
                try:
                    status = agent.status.status
                except Exception:
                    pass

                result.append({
                    'username':      agent.user.username,
                    'role':          agent.role,
                    'department':    agent.department.name if agent.department else None,
                    'status':        status,
                    'is_available':  agent.is_available,
                    'active_tickets':agent.active_tickets,
                    'max_tickets':   agent.max_concurrent,
                    'load_pct':      round(agent.active_tickets / agent.max_concurrent * 100, 0) if agent.max_concurrent else 0,
                })

            return sorted(result, key=lambda x: (x['status'] != 'online', -x['active_tickets']))

        except Exception as e:
            logger.error(f'Agent status failed: {e}')
            return []

    # ──────────────────────────────────────────
    # SLA STATUS
    # ──────────────────────────────────────────
    def get_sla_status(self) -> dict:
        """Real-time SLA health"""
        try:
            from api.support.models import TicketSLA, SupportTicket

            active_slas = TicketSLA.objects.filter(
                ticket__status__in=['open','in_progress','waiting_user'],
            )

            total     = active_slas.count()
            fr_breach = active_slas.filter(first_response_breached=True).count()
            res_breach= active_slas.filter(resolution_breached=True).count()

            # Warning zone (< 1 hour)
            now        = timezone.now()
            fr_warning = 0
            for sla in active_slas.filter(first_response_breached=False,
                                           first_response_at__isnull=True):
                if sla.first_response_due:
                    remaining = (sla.first_response_due - now).total_seconds() / 3600
                    if 0 < remaining < 1:
                        fr_warning += 1

            return {
                'total_active':        total,
                'fr_breached':         fr_breach,
                'res_breached':        res_breach,
                'total_breached':      fr_breach + res_breach,
                'fr_warning':          fr_warning,
                'compliance_rate':     round((total - fr_breach - res_breach) / total * 100, 1) if total else 100,
                'health':              'critical' if (fr_breach + res_breach) > 0 else 'ok',
            }

        except Exception as e:
            logger.error(f'SLA status failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # CHAT STATUS
    # ──────────────────────────────────────────
    def get_chat_status(self) -> dict:
        """Live chat queue status"""
        try:
            from api.support.models import ChatSession
            now = timezone.now()

            waiting = ChatSession.objects.filter(status='waiting')
            active  = ChatSession.objects.filter(status='active')

            avg_wait = 0
            if waiting.exists():
                wait_times = [
                    (now - s.started_at).total_seconds() / 60
                    for s in waiting
                ]
                avg_wait = round(sum(wait_times) / len(wait_times), 1)

            return {
                'waiting':           waiting.count(),
                'active':            active.count(),
                'avg_wait_min':      avg_wait,
                'is_overloaded':     waiting.count() > 5,
            }
        except Exception as e:
            logger.error(f'Chat status failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # TODAY METRICS
    # ──────────────────────────────────────────
    def get_today_metrics(self) -> dict:
        """Today-এর detailed metrics"""
        try:
            from api.support.models import SupportTicket, TicketRating
            from django.db.models import Avg, Count
            from django.utils import timezone

            today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

            tickets_today = SupportTicket.objects.filter(created_at__gte=today)

            # Response time average
            responded = tickets_today.filter(admin_responded_at__isnull=False)
            avg_resp  = 0
            if responded.exists():
                times = []
                for t in responded:
                    diff = (t.admin_responded_at - t.created_at).total_seconds() / 60
                    times.append(diff)
                avg_resp = round(sum(times) / len(times), 1)

            # By category
            by_cat = list(
                tickets_today.values('category')
                .annotate(count=Count('id'))
                .order_by('-count')[:5]
            )

            # By channel
            by_channel = list(
                tickets_today.values('channel')
                .annotate(count=Count('id'))
                .order_by('-count')
            ) if hasattr(SupportTicket, 'channel') else []

            return {
                'total_created':      tickets_today.count(),
                'total_resolved':     tickets_today.filter(status='resolved').count(),
                'avg_response_min':   avg_resp,
                'by_category':        by_cat,
                'by_channel':         by_channel,
                'csat':               round(
                    TicketRating.objects.filter(
                        created_at__gte=today
                    ).aggregate(avg=Avg('rating'))['avg'] or 0, 1
                ),
            }

        except Exception as e:
            logger.error(f'Today metrics failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # HOURLY VOLUME CHART
    # ──────────────────────────────────────────
    def get_hourly_volume(self) -> list:
        """Last 24 hours-এর hourly ticket volume (chart data)"""
        try:
            from api.support.models import SupportTicket
            from django.db.models.functions import TruncHour
            from django.db.models import Count

            since = timezone.now() - timedelta(hours=24)
            data  = list(
                SupportTicket.objects.filter(created_at__gte=since)
                .annotate(hour=TruncHour('created_at'))
                .values('hour')
                .annotate(count=Count('id'))
                .order_by('hour')
            )

            return [
                {
                    'hour':  item['hour'].strftime('%H:00'),
                    'count': item['count'],
                }
                for item in data
            ]

        except Exception as e:
            logger.error(f'Hourly volume failed: {e}')
            return []

    # ──────────────────────────────────────────
    # TOP ISSUES
    # ──────────────────────────────────────────
    def get_top_issues(self, days: int = 7) -> list:
        """Most common issues — knowledge base suggest করতে পারবে"""
        try:
            from api.support.models import SupportTicket
            from django.db.models import Count
            since = timezone.now() - timedelta(days=days)
            return list(
                SupportTicket.objects.filter(created_at__gte=since)
                .values('category')
                .annotate(count=Count('id'))
                .order_by('-count')[:8]
            )
        except Exception:
            return []

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────
    def _trend(self, current: int, previous: int) -> str:
        if previous == 0:
            return 'neutral'
        diff = current - previous
        if diff > 0:
            return 'up'
        if diff < 0:
            return 'down'
        return 'neutral'

    def invalidate_cache(self) -> None:
        """Cache clear করো (ticket update হলে)"""
        for key in ['dashboard:full', 'dashboard:overview']:
            cache.delete(key)


# Singleton
realtime_dashboard = RealtimeDashboard()
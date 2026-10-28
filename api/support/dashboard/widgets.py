"""
api/support/dashboard/widgets.py
FILE 17/70 — Dashboard Reusable Widgets

Modular dashboard components।
Frontend-এ এই widgets render হবে।
WebSocket থেকে auto-update হবে।

Widget Types:
- KPICard: Single metric display
- TicketQueue: Live ticket list
- AgentGrid: Agent status grid
- SLAGauge: SLA compliance gauge
- VolumeChart: Ticket volume over time
- CSATMeter: Customer satisfaction
- AlertBanner: Active alerts
- ChatQueue: Live chat queue
"""
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class DashboardWidgetBuilder:
    """
    Dashboard widgets data builder।
    প্রতিটি widget-এর জন্য structured data return করে।
    """

    # ──────────────────────────────────────────
    # KPI CARDS
    # ──────────────────────────────────────────
    def build_kpi_cards(self) -> list:
        """Top KPI cards — dashboard header"""
        try:
            from api.support.models import (
                SupportTicket, SupportAgent, TicketRating
            )
            from django.db.models import Avg, Count
            from django.utils import timezone

            today    = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday= today - timedelta(days=1)

            # Ticket metrics
            open_now      = SupportTicket.objects.filter(status__in=['open','in_progress','waiting_user']).count()
            created_today = SupportTicket.objects.filter(created_at__gte=today).count()
            resolved_today= SupportTicket.objects.filter(resolved_at__gte=today).count()
            created_yest  = SupportTicket.objects.filter(created_at__gte=yesterday, created_at__lt=today).count()

            # CSAT
            csat_today = TicketRating.objects.filter(
                created_at__gte=today
            ).aggregate(avg=Avg('rating'))['avg'] or 0

            # Agents
            online = SupportAgent.objects.filter(is_active=True, is_available=True).count()
            total  = SupportAgent.objects.filter(is_active=True).count()

            # Avg response time today
            responded = SupportTicket.objects.filter(
                created_at__gte=today,
                admin_responded_at__isnull=False,
            )
            avg_resp = 0
            if responded.exists():
                times = [
                    (t.admin_responded_at - t.created_at).total_seconds() / 60
                    for t in responded
                ]
                avg_resp = round(sum(times) / len(times), 0)

            return [
                {
                    'id':      'open_tickets',
                    'title':   'Open Tickets',
                    'value':   open_now,
                    'icon':    '🎫',
                    'color':   '#6366f1',
                    'trend':   None,
                    'link':    '/support/tickets/?status=open',
                },
                {
                    'id':      'created_today',
                    'title':   'Created Today',
                    'value':   created_today,
                    'icon':    '📥',
                    'color':   '#0ea5e9',
                    'trend':   self._calc_trend(created_today, created_yest),
                    'sub':     f'vs {created_yest} yesterday',
                },
                {
                    'id':      'resolved_today',
                    'title':   'Resolved Today',
                    'value':   resolved_today,
                    'icon':    '✅',
                    'color':   '#16a34a',
                    'trend':   None,
                },
                {
                    'id':      'avg_response',
                    'title':   'Avg Response',
                    'value':   f'{int(avg_resp)}m',
                    'icon':    '⏱️',
                    'color':   '#ca8a04',
                    'trend':   None,
                    'unit':    'minutes',
                },
                {
                    'id':      'csat_score',
                    'title':   'CSAT Score',
                    'value':   round(csat_today, 1),
                    'icon':    '⭐',
                    'color':   '#f59e0b',
                    'max':     5,
                    'sub':     f'{round(csat_today/5*100,0):.0f}% satisfaction',
                },
                {
                    'id':      'agents_online',
                    'title':   'Agents Online',
                    'value':   online,
                    'icon':    '👤',
                    'color':   '#16a34a' if online > 0 else '#dc2626',
                    'sub':     f'{online}/{total} available',
                },
            ]
        except Exception as e:
            logger.error(f'KPI cards failed: {e}')
            return []

    # ──────────────────────────────────────────
    # TICKET QUEUE WIDGET
    # ──────────────────────────────────────────
    def build_ticket_queue_widget(self, agent_user=None, limit: int = 10) -> dict:
        """Live ticket queue widget data"""
        try:
            from api.support.models import SupportTicket
            from django.db.models import Q

            qs = SupportTicket.objects.filter(
                status__in=['open','in_progress','waiting_user']
            ).select_related('user','assigned_to','sla')

            # Agent sees own tickets first
            if agent_user and not agent_user.is_staff:
                qs = qs.filter(
                    Q(assigned_to=agent_user) | Q(assigned_to=None)
                )

            qs = qs.order_by('-escalated', 'created_at')[:limit]

            items = []
            for ticket in qs:
                sla_color = '#16a34a'  # green
                sla_text  = ''
                try:
                    sla   = ticket.sla
                    now   = timezone.now()
                    if sla.first_response_due and not sla.first_response_at:
                        rem = (sla.first_response_due - now).total_seconds() / 60
                        if rem < 0:
                            sla_color = '#dc2626'  # red
                            sla_text  = f'OVERDUE {abs(int(rem))}m'
                        elif rem < 60:
                            sla_color = '#ea580c'  # orange
                            sla_text  = f'{int(rem)}m left'
                        else:
                            sla_color = '#16a34a'  # green
                            sla_text  = f'{int(rem/60)}h left'
                except Exception:
                    pass

                wait_min = int((timezone.now() - ticket.created_at).total_seconds() / 60)

                items.append({
                    'ticket_id':  ticket.ticket_id,
                    'subject':    ticket.subject[:50],
                    'user':       ticket.user.username,
                    'priority':   ticket.priority,
                    'status':     ticket.status,
                    'category':   ticket.category,
                    'agent':      ticket.assigned_to.username if ticket.assigned_to else None,
                    'escalated':  ticket.escalated,
                    'wait_min':   wait_min,
                    'sla_text':   sla_text,
                    'sla_color':  sla_color,
                })

            return {
                'widget':   'ticket_queue',
                'title':    'Ticket Queue',
                'count':    qs.count(),
                'items':    items,
                'refresh':  30,  # seconds
            }
        except Exception as e:
            logger.error(f'Ticket queue widget failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # AGENT GRID WIDGET
    # ──────────────────────────────────────────
    def build_agent_grid_widget(self) -> dict:
        """Agent availability grid"""
        try:
            from api.support.models import SupportAgent, SupportTicket
            from django.db.models import Count, Q

            agents = SupportAgent.objects.filter(
                is_active=True
            ).select_related('user','status','department').annotate(
                active=Count(
                    'user__assigned_tickets',
                    filter=Q(user__assigned_tickets__status__in=['open','in_progress','waiting_user'])
                )
            )

            status_colors = {
                'online':  '#16a34a',
                'busy':    '#ca8a04',
                'away':    '#6366f1',
                'offline': '#9ca3af',
            }

            items = []
            for agent in agents:
                ag_status = 'offline'
                try:
                    ag_status = agent.status.status
                except Exception:
                    pass

                load_pct = round(agent.active / agent.max_concurrent * 100) if agent.max_concurrent else 0

                items.append({
                    'username':   agent.user.username,
                    'role':       agent.role,
                    'department': agent.department.name if agent.department else 'General',
                    'status':     ag_status,
                    'color':      status_colors.get(ag_status, '#9ca3af'),
                    'active':     agent.active,
                    'max':        agent.max_concurrent,
                    'load_pct':   load_pct,
                    'load_color': '#dc2626' if load_pct >= 90 else '#ca8a04' if load_pct >= 70 else '#16a34a',
                })

            items.sort(key=lambda x: (x['status'] != 'online', -x['active']))

            return {
                'widget':  'agent_grid',
                'title':   'Agent Status',
                'agents':  items,
                'online':  sum(1 for a in items if a['status'] == 'online'),
                'total':   len(items),
                'refresh': 10,
            }
        except Exception as e:
            logger.error(f'Agent grid widget failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # SLA GAUGE WIDGET
    # ──────────────────────────────────────────
    def build_sla_gauge_widget(self) -> dict:
        """SLA compliance gauge"""
        try:
            from api.support.models import TicketSLA
            from datetime import timedelta

            since = timezone.now() - timedelta(days=7)
            slas  = TicketSLA.objects.filter(created_at__gte=since)
            total = slas.count()

            if not total:
                return {'widget': 'sla_gauge', 'compliance': 100, 'total': 0}

            breached = slas.filter(
                first_response_breached=True
            ).count() + slas.filter(
                resolution_breached=True,
                first_response_breached=False,
            ).count()

            rate  = round((total - breached) / total * 100, 1)
            color = '#16a34a' if rate >= 90 else '#ca8a04' if rate >= 75 else '#dc2626'

            return {
                'widget':         'sla_gauge',
                'title':          'SLA Compliance (7d)',
                'compliance':     rate,
                'total':          total,
                'breached':       breached,
                'color':          color,
                'status':         'good' if rate >= 90 else 'warning' if rate >= 75 else 'critical',
                'by_priority':    self._sla_by_priority(since),
            }
        except Exception as e:
            logger.error(f'SLA gauge widget failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # CHAT QUEUE WIDGET
    # ──────────────────────────────────────────
    def build_chat_queue_widget(self) -> dict:
        """Live chat queue widget"""
        try:
            from api.support.models import LiveChatSession as ChatSession

            waiting = ChatSession.objects.filter(status='waiting').select_related('user').order_by('started_at')
            active  = ChatSession.objects.filter(status='active').count()
            now     = timezone.now()

            queue_items = []
            for session in waiting[:10]:
                wait_sec = (now - session.started_at).total_seconds()
                queue_items.append({
                    'session_id':    str(session.session_id)[:8],
                    'user':          session.user.username,
                    'wait_min':      round(wait_sec / 60, 1),
                    'queue_position':session.queue_position,
                    'is_long_wait':  wait_sec > 300,  # > 5 min
                })

            avg_wait = 0
            if queue_items:
                avg_wait = sum(q['wait_min'] for q in queue_items) / len(queue_items)

            return {
                'widget':       'chat_queue',
                'title':        'Live Chat Queue',
                'waiting':      waiting.count(),
                'active':       active,
                'avg_wait_min': round(avg_wait, 1),
                'queue':        queue_items,
                'alert':        waiting.count() > 3,
                'refresh':      10,
            }
        except Exception as e:
            logger.error(f'Chat queue widget failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # VOLUME CHART WIDGET
    # ──────────────────────────────────────────
    def build_volume_chart_widget(self, hours: int = 24) -> dict:
        """Ticket volume bar chart"""
        try:
            from api.support.models import SupportTicket
            from django.db.models import Count
            from django.db.models.functions import TruncHour

            since = timezone.now() - timedelta(hours=hours)
            data  = list(
                SupportTicket.objects.filter(created_at__gte=since)
                .annotate(hour=TruncHour('created_at'))
                .values('hour')
                .annotate(
                    created=Count('id'),
                )
                .order_by('hour')
            )

            resolved_data = list(
                SupportTicket.objects.filter(
                    resolved_at__gte=since,
                    resolved_at__isnull=False,
                ).annotate(hour=TruncHour('resolved_at'))
                .values('hour')
                .annotate(resolved=Count('id'))
                .order_by('hour')
            )

            resolved_map = {str(r['hour']): r['resolved'] for r in resolved_data}

            chart_data = []
            for item in data:
                hour_str = item['hour'].strftime('%H:00')
                chart_data.append({
                    'hour':     hour_str,
                    'created':  item['created'],
                    'resolved': resolved_map.get(str(item['hour']), 0),
                })

            return {
                'widget':  'volume_chart',
                'title':   f'Ticket Volume (last {hours}h)',
                'data':    chart_data,
                'refresh': 300,  # 5 min
            }
        except Exception as e:
            logger.error(f'Volume chart widget failed: {e}')
            return {}

    # ──────────────────────────────────────────
    # ALERT BANNER WIDGET
    # ──────────────────────────────────────────
    def build_alert_banner_widget(self) -> dict:
        """Critical alerts banner"""
        alerts = []
        try:
            from api.support.models import SupportTicket

            # Unassigned urgent
            urgent_unassigned = SupportTicket.objects.filter(
                status='open', priority='urgent', assigned_to=None
            ).count()
            if urgent_unassigned:
                alerts.append({
                    'severity': 'critical',
                    'message':  f'🚨 {urgent_unassigned} URGENT unassigned tickets!',
                    'action':   'Assign immediately',
                })

            # SLA breaches
            from api.support.models import TicketSLA
            breached = TicketSLA.objects.filter(
                first_response_breached=True,
                ticket__status__in=['open','in_progress'],
            ).count()
            if breached:
                alerts.append({
                    'severity': 'error',
                    'message':  f'⛔ {breached} tickets have breached first response SLA',
                    'action':   'Respond now',
                })

            # High churn risk
            try:
                from api.support.ai.ai_churn_predictor import churn_predictor
                high_risk = churn_predictor.get_high_risk_users(limit=5)
                critical  = [u for u in high_risk if u['risk_level'] == 'critical']
                if critical:
                    alerts.append({
                        'severity': 'warning',
                        'message':  f'⚠️ {len(critical)} users at critical churn risk',
                        'action':   'Prioritize support',
                    })
            except Exception:
                pass

        except Exception as e:
            logger.error(f'Alert banner widget failed: {e}')

        return {
            'widget':         'alert_banner',
            'alerts':         alerts,
            'has_critical':   any(a['severity'] == 'critical' for a in alerts),
            'count':          len(alerts),
        }

    # ──────────────────────────────────────────
    # ALL WIDGETS BUNDLE
    # ──────────────────────────────────────────
    def build_all_widgets(self, user=None) -> dict:
        """All widgets in one call"""
        return {
            'kpi_cards':    self.build_kpi_cards(),
            'ticket_queue': self.build_ticket_queue_widget(agent_user=user),
            'agent_grid':   self.build_agent_grid_widget(),
            'sla_gauge':    self.build_sla_gauge_widget(),
            'chat_queue':   self.build_chat_queue_widget(),
            'volume_chart': self.build_volume_chart_widget(),
            'alert_banner': self.build_alert_banner_widget(),
            'generated_at': timezone.now().isoformat(),
        }

    # ──────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────
    def _calc_trend(self, current: int, previous: int) -> dict:
        if previous == 0:
            return {'direction': 'neutral', 'pct': 0}
        diff = current - previous
        pct  = round(abs(diff) / previous * 100, 1)
        return {
            'direction': 'up' if diff > 0 else 'down' if diff < 0 else 'neutral',
            'pct':       pct,
            'diff':      diff,
        }

    def _sla_by_priority(self, since) -> dict:
        from api.support.models import TicketSLA
        result = {}
        for p in ['urgent','high','medium','low']:
            p_slas   = TicketSLA.objects.filter(
                created_at__gte=since, ticket__priority=p
            )
            p_total  = p_slas.count()
            p_breach = p_slas.filter(first_response_breached=True).count()
            if p_total:
                result[p] = {
                    'total':      p_total,
                    'compliance': round((p_total - p_breach) / p_total * 100, 1),
                }
        return result


# Singleton
widget_builder = DashboardWidgetBuilder()
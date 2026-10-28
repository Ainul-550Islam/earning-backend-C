"""
api/support/portal/portal_widgets.py
FILE 40/70 — Customer Portal UI Widgets

Portal frontend-এর data providers।
React/Vue component-এর জন্য structured data।
"""
import logging
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PortalWidgetBuilder:
    """Customer portal widget data builder"""

    # ──────────────────────────────────────────
    # TICKET STATUS WIDGET
    # ──────────────────────────────────────────
    def build_ticket_status_widget(self, user) -> dict:
        """User-এর ticket status summary"""
        from api.support.models import SupportTicket
        from django.db.models import Count

        tickets  = SupportTicket.objects.filter(user=user)
        by_status= {
            s: tickets.filter(status=s).count()
            for s in ['open','in_progress','waiting_user','resolved','closed']
        }

        active_count  = by_status['open'] + by_status['in_progress'] + by_status['waiting_user']
        needs_action  = by_status['waiting_user']

        return {
            'widget':       'ticket_status',
            'active':       active_count,
            'needs_action': needs_action,
            'resolved':     by_status['resolved'],
            'by_status':    by_status,
            'alert':        needs_action > 0,
            'alert_msg':    f'You have {needs_action} ticket(s) waiting for your reply!' if needs_action else None,
        }

    # ──────────────────────────────────────────
    # QUICK ACTIONS WIDGET
    # ──────────────────────────────────────────
    def build_quick_actions_widget(self, user) -> dict:
        """Quick action buttons for portal"""
        actions = [
            {
                'id':    'create_ticket',
                'label': '🎫 Create Support Ticket',
                'url':   '/support/portal/tickets/',
                'method':'POST',
                'color': '#6366f1',
            },
            {
                'id':    'search_kb',
                'label': '📚 Search Knowledge Base',
                'url':   '/support/portal/kb/search/',
                'color': '#0ea5e9',
            },
            {
                'id':    'live_chat',
                'label': '💬 Start Live Chat',
                'url':   '/support/widget/chat/start/',
                'color': '#16a34a',
            },
            {
                'id':    'my_tickets',
                'label': '📋 View My Tickets',
                'url':   '/support/portal/tickets/',
                'color': '#ca8a04',
            },
        ]

        # Add "reply needed" if applicable
        from api.support.models import SupportTicket
        waiting = SupportTicket.objects.filter(user=user, status='waiting_user').first()
        if waiting:
            actions.insert(0, {
                'id':    'reply_needed',
                'label': f'💬 Reply to #{waiting.ticket_id}',
                'url':   f'/support/portal/tickets/{waiting.ticket_id}/',
                'color': '#dc2626',
                'urgent': True,
            })

        return {
            'widget':  'quick_actions',
            'actions': actions,
        }

    # ──────────────────────────────────────────
    # RECENT ACTIVITY WIDGET
    # ──────────────────────────────────────────
    def build_recent_activity_widget(self, user, limit: int = 5) -> dict:
        """Recent support activity feed"""
        from api.support.models import SupportTicket, TicketMessage

        activities = []

        # Recent messages on user's tickets
        recent_msgs = TicketMessage.objects.filter(
            ticket__user = user,
            is_agent     = True,
            is_internal  = False,
        ).select_related('ticket').order_by('-created_at')[:limit]

        for msg in recent_msgs:
            diff = (timezone.now() - msg.created_at).total_seconds()
            if diff < 3600:
                time_str = f'{int(diff/60)}m ago'
            elif diff < 86400:
                time_str = f'{int(diff/3600)}h ago'
            else:
                time_str = msg.created_at.strftime('%d %b')

            activities.append({
                'type':      'agent_reply',
                'icon':      '💬',
                'title':     f'Reply on #{msg.ticket.ticket_id}',
                'preview':   msg.content[:80],
                'time':      time_str,
                'ticket_id': msg.ticket.ticket_id,
                'status':    msg.ticket.status,
            })

        # Recent status changes
        recent_resolved = SupportTicket.objects.filter(
            user=user,
            status='resolved',
            resolved_at__isnull=False,
        ).order_by('-resolved_at')[:3]

        for ticket in recent_resolved:
            diff = (timezone.now() - ticket.resolved_at).total_seconds()
            time_str = f'{int(diff/3600)}h ago' if diff < 86400 else ticket.resolved_at.strftime('%d %b')
            activities.append({
                'type':      'resolved',
                'icon':      '✅',
                'title':     f'Ticket #{ticket.ticket_id} Resolved',
                'preview':   ticket.subject[:60],
                'time':      time_str,
                'ticket_id': ticket.ticket_id,
                'status':    'resolved',
                'can_rate':  not ticket.satisfaction_rating,
            })

        activities.sort(key=lambda x: x['time'], reverse=False)
        return {
            'widget':     'recent_activity',
            'activities': activities[:limit],
            'has_more':   len(activities) > limit,
        }

    # ──────────────────────────────────────────
    # CSAT PROMPT WIDGET
    # ──────────────────────────────────────────
    def build_csat_prompt_widget(self, user) -> dict | None:
        """Show CSAT rating prompt for recently resolved tickets"""
        from api.support.models import SupportTicket
        from datetime import timedelta

        since  = timezone.now() - timedelta(days=7)
        ticket = SupportTicket.objects.filter(
            user                = user,
            status              = 'resolved',
            resolved_at__gte    = since,
            satisfaction_rating__isnull = True,
        ).order_by('-resolved_at').first()

        if not ticket:
            return None

        return {
            'widget':    'csat_prompt',
            'ticket_id': ticket.ticket_id,
            'subject':   ticket.subject[:60],
            'message':   f'How was our support for ticket #{ticket.ticket_id}?',
            'rate_url':  f'/support/portal/tickets/{ticket.ticket_id}/rate/',
            'show':      True,
        }

    # ──────────────────────────────────────────
    # SUPPORT HOURS WIDGET
    # ──────────────────────────────────────────
    def build_support_hours_widget(self) -> dict:
        """Current support availability"""
        from api.support.models import SupportSettings, SupportAgent

        obj    = SupportSettings.objects.filter(id=1).first()
        online = SupportAgent.objects.filter(is_active=True, is_available=True).count()

        now       = timezone.localtime().time()
        in_hours  = True
        if obj:
            in_hours = obj.support_hours_start <= now <= obj.support_hours_end

        return {
            'widget':       'support_hours',
            'is_online':    in_hours and online > 0 and (not obj or not obj.maintenance_mode),
            'agents_online':online,
            'hours_start':  str(obj.support_hours_start) if obj else '09:00',
            'hours_end':    str(obj.support_hours_end)   if obj else '18:00',
            'message':      'We\'re online! Chat with us.' if (in_hours and online > 0) else 'We\'re offline. Leave a ticket.',
        }

    # ──────────────────────────────────────────
    # ALL WIDGETS
    # ──────────────────────────────────────────
    def build_portal_home_widgets(self, user) -> dict:
        """Portal home-এর সব widgets এক call-এ"""
        return {
            'ticket_status':   self.build_ticket_status_widget(user),
            'quick_actions':   self.build_quick_actions_widget(user),
            'recent_activity': self.build_recent_activity_widget(user),
            'csat_prompt':     self.build_csat_prompt_widget(user),
            'support_hours':   self.build_support_hours_widget(),
            'generated_at':    timezone.now().isoformat(),
        }


portal_widget_builder = PortalWidgetBuilder()
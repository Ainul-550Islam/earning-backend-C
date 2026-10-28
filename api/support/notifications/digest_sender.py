"""
api/support/notifications/digest_sender.py
FILE 31/70 — Daily/Weekly Digest Sender

Admin-দের daily + weekly summary পাঠাও।
Celery beat-এ schedule করো।
"""
import logging
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)
ADMIN_EMAIL = getattr(settings, 'SUPPORT_ADMIN_EMAIL', '')


class DigestSender:
    """Automated digest email + Slack/Telegram sender"""

    def send_daily_digest(self) -> dict:
        """Daily digest — midnight-এ run করো"""
        stats = self._get_daily_stats()

        # Email
        email_sent = False
        if ADMIN_EMAIL:
            from api.support.notifications.email_notifier import email_notifier
            email_sent = email_notifier.daily_digest(ADMIN_EMAIL, stats)

        # Slack
        slack_sent = False
        try:
            from api.support.integrations.slack_integration import slack_integration
            slack_sent = slack_integration.send_daily_digest()
        except Exception:
            pass

        logger.info(f'Daily digest sent: email={email_sent}, slack={slack_sent}')
        return {'email': email_sent, 'slack': slack_sent, 'stats': stats}

    def send_weekly_digest(self) -> dict:
        """Weekly digest — Monday morning-এ run করো"""
        try:
            from api.support.integrations.slack_integration import slack_integration
            slack_integration.send_weekly_report()
        except Exception:
            pass
        return {'sent': True}

    def send_agent_daily_summary(self) -> int:
        """প্রতিটি agent-কে তাদের daily performance summary পাঠাও"""
        from api.support.models import SupportAgent
        from api.support.services.agent.AgentPerformanceService import performance_service
        from api.support.notifications.email_notifier import email_notifier

        sent = 0
        for agent in SupportAgent.objects.filter(is_active=True).select_related('user'):
            try:
                metrics = performance_service.get_metrics(agent.user, days=1)
                subject = f'Your Daily Performance Summary — {timezone.now().strftime("%d %b %Y")}'
                body    = (
                    f'Hello {agent.user.username},\n\n'
                    f'Your performance today:\n\n'
                    f'Tickets Assigned: {metrics.get("total_assigned", 0)}\n'
                    f'Tickets Resolved: {metrics.get("resolved", 0)}\n'
                    f'Resolution Rate: {metrics.get("resolution_rate", 0)}%\n'
                    f'Avg Response: {metrics.get("avg_response_min", 0):.0f} minutes\n'
                    f'CSAT Score: {metrics.get("csat_score", 0)}/5.0\n\n'
                    f'Keep up the great work!\n'
                    f'Support Team'
                )
                email_notifier._send(agent.user.email, subject, body)
                sent += 1
            except Exception as e:
                logger.warning(f'Agent digest failed for {agent.user.username}: {e}')

        return sent

    def _get_daily_stats(self) -> dict:
        try:
            from api.support.models import SupportTicket, TicketRating, SupportAgent
            from django.db.models import Avg, Count
            from django.utils import timezone

            today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

            created  = SupportTicket.objects.filter(created_at__gte=today).count()
            resolved = SupportTicket.objects.filter(resolved_at__gte=today).count()
            open_ct  = SupportTicket.objects.filter(status__in=['open','in_progress','waiting_user']).count()
            csat     = TicketRating.objects.filter(created_at__gte=today).aggregate(avg=Avg('rating'))['avg'] or 0
            agents   = SupportAgent.objects.filter(is_active=True, is_available=True).count()
            breached = SupportTicket.objects.filter(
                sla__first_response_breached=True, created_at__gte=today
            ).count()

            return {
                'created':   created,
                'resolved':  resolved,
                'open':      open_ct,
                'csat':      round(csat, 1),
                'agents':    agents,
                'breached':  breached,
                'sla_rate':  round((created - breached) / created * 100, 1) if created else 100,
                'date':      today.strftime('%d %b %Y'),
            }
        except Exception as e:
            logger.error(f'Get daily stats failed: {e}')
            return {}


digest_sender = DigestSender()
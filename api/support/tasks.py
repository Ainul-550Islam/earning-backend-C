# api/support/tasks.py
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(bind=True, name='support.tasks.check_sla_breaches', max_retries=3)
    def check_sla_breaches(self):
        from api.support.services import sla_service
        result = sla_service.check_breaches()
        logger.info(f'SLA check: {result}')
        return result

    @shared_task(bind=True, name='support.tasks.auto_close_stale_tickets', max_retries=2)
    def auto_close_stale_tickets(self, waiting_days=7, resolved_days=30):
        from api.support.models import SupportTicket
        from datetime import timedelta
        now = timezone.now()
        c1 = SupportTicket.objects.filter(status='waiting_user', updated_at__lte=now-timedelta(days=waiting_days)).count()
        SupportTicket.objects.filter(status='waiting_user', updated_at__lte=now-timedelta(days=waiting_days)).update(status='closed')
        c2 = SupportTicket.objects.filter(status='resolved', resolved_at__lte=now-timedelta(days=resolved_days)).count()
        SupportTicket.objects.filter(status='resolved', resolved_at__lte=now-timedelta(days=resolved_days)).update(status='closed')
        return {'closed': c1+c2}

    @shared_task(bind=True, name='support.tasks.send_csat_request', max_retries=2)
    def send_csat_request(self, ticket_id: int):
        try:
            from api.support.models import SupportTicket
            ticket = SupportTicket.objects.get(id=ticket_id)
            if not ticket.satisfaction_rating:
                from api.support.services import notification_service
                notification_service.notify_ticket_resolved(ticket)
        except Exception as exc:
            raise self.retry(exc=exc, countdown=3600)

    @shared_task(bind=True, name='support.tasks.send_daily_digest', max_retries=2)
    def send_daily_digest(self):
        from api.support.services import ticket_service
        from api.support.models import SupportSettings
        stats = ticket_service.get_stats()
        obj = SupportSettings.objects.filter(id=1).first()
        if obj and obj.support_admin_email:
            from api.support.services import notification_service
            notification_service._email(
                obj.support_admin_email,
                f'Daily Report - {timezone.now().strftime("%d %b %Y")}',
                f'Open:{stats.get("open",0)} Resolved:{stats.get("resolved",0)} Today:{stats.get("today",0)}'
            )
        return stats

    @shared_task(bind=True, name='support.tasks.assign_unassigned_tickets', max_retries=2)
    def assign_unassigned_tickets(self):
        from api.support.models import SupportTicket
        from api.support.services import ticket_service
        tickets = SupportTicket.objects.filter(assigned_to__isnull=True, status__in=['open','in_progress'])[:20]
        assigned = 0
        for ticket in tickets:
            ticket_service._auto_assign(ticket)
            if ticket.assigned_to:
                assigned += 1
        return {'assigned': assigned}

    @shared_task(bind=True, name='support.tasks.process_integration_event', max_retries=3)
    def process_integration_event(self, event_type: str, data: dict):
        from api.support.integrations.event_bus import event_bus
        event_bus._publish_sync(event_type, data)

    @shared_task(bind=True, name='support.tasks.suggest_kb_for_new_tickets', max_retries=1)
    def suggest_kb_for_new_tickets(self):
        from api.support.models import SupportTicket, TicketMessage
        from api.support.services import kb_service
        from django.contrib.auth import get_user_model
        from datetime import timedelta
        tickets = SupportTicket.objects.filter(
            status='open', message_count=0,
            created_at__gte=timezone.now()-timedelta(minutes=10)
        )[:20]
        bot = get_user_model().objects.filter(is_superuser=True).first()
        for ticket in tickets:
            try:
                articles = kb_service.search(f'{ticket.subject} {ticket.category}', limit=3)
                if articles and bot:
                    suggestions = chr(10).join(f'- {a["title"]}' for a in articles)
                    TicketMessage.objects.create(
                        ticket=ticket, sender=bot, is_agent=True, is_internal=True,
                        content=f'KB Suggestions:{chr(10)}{suggestions}'
                    )
            except Exception:
                pass

except ImportError:
    logger.warning('Celery not installed')
# api/support/signals/ticket_signals.py  — WORLD #1
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
logger = logging.getLogger(__name__)

@receiver(post_save, sender='support.SupportTicket')
def on_ticket_post_save(sender, instance, created, **kwargs):
    if created:
        # 1. Setup SLA
        try:
            from api.support.services import ticket_service
            ticket_service._setup_sla(instance)
        except Exception as e:
            logger.warning(f"SLA setup failed for {instance.ticket_id}: {e}")
        # 2. Auto-assign agent
        try:
            from api.support.services import ticket_service
            ticket_service._auto_assign(instance)
        except Exception as e:
            logger.warning(f"Auto-assign failed for {instance.ticket_id}: {e}")
        # 3. Send KB suggestions (background)
        try:
            from api.support.tasks.kb_tasks import suggest_kb_for_new_tickets
            suggest_kb_for_new_tickets.apply_async(countdown=5)
        except Exception:
            pass
        # 4. Trigger automation
        try:
            from api.support.automation.trigger_engine import trigger_engine
            trigger_engine.fire("ticket_created", ticket=instance)
        except Exception as e:
            logger.debug(f"Automation trigger failed: {e}")
    else:
        # Status change → trigger automation
        try:
            from api.support.automation.trigger_engine import trigger_engine
            trigger_engine.fire("ticket_status_changed", ticket=instance)
        except Exception:
            pass

        # Status → resolved: schedule CSAT
        if instance.status == "resolved":
            try:
                from api.support.tasks.csat_tasks import send_single_csat_request
                send_single_csat_request.apply_async(args=[instance.id], countdown=24*3600)
            except Exception:
                pass
# api/support/tasks/kb_tasks.py  — WORLD #1 COMPLETE
"""Knowledge base maintenance tasks."""
import logging
from celery import shared_task
logger = logging.getLogger(__name__)

@shared_task(name="support.tasks.kb_tasks.update_kb_category_counts")
def update_kb_category_counts():
    """Every 6 hours — update article counts per category."""
    from api.support.models import KBCategory, KBArticle
    from django.db.models import Count
    updated = 0
    for cat in KBCategory.objects.filter(is_active=True):
        count = KBArticle.objects.filter(category=cat, status="published").count()
        updated += 1
    logger.info(f"KB category counts updated: {updated} categories")
    return {"updated": updated}

@shared_task(name="support.tasks.kb_tasks.suggest_kb_for_new_tickets")
def suggest_kb_for_new_tickets():
    """Check recent open tickets and suggest KB articles as internal notes."""
    from api.support.models import SupportTicket, TicketMessage
    from api.support.services.knowledge_base.KBRecommendService import kb_recommend_service
    from django.utils import timezone
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    recent = SupportTicket.objects.filter(
        status="open",
        created_at__gte=timezone.now() - timedelta(hours=1),
        message_count=0,
    ).select_related("user")[:20]
    suggested = 0
    for ticket in recent:
        suggestions = kb_recommend_service.suggest_for_ticket(ticket.subject or "", ticket.category or "other")
        if suggestions:
            bot = get_user_model().objects.filter(is_superuser=True).first()
            if bot:
                content = "📚 KB Suggestions:\n" + "\n".join(f"• {s["title"]}" for s in suggestions[:3])
                TicketMessage.objects.get_or_create(
                    ticket=ticket, content=content, is_agent=True, is_internal=True,
                    defaults={"sender": bot}
                )
                suggested += 1
    return {"kb_suggested_for": suggested}
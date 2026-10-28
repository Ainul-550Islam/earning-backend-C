# api/support/dependencies.py
from rest_framework.exceptions import NotFound, PermissionDenied
from django.core.cache import cache


def get_ticket_or_404(ticket_id, user=None):
    from api.support.models import SupportTicket
    try:
        ticket = (SupportTicket.objects.get(ticket_id=ticket_id)
                  if str(ticket_id).startswith('TKT')
                  else SupportTicket.objects.get(id=ticket_id))
    except SupportTicket.DoesNotExist:
        raise NotFound(f'Ticket {ticket_id} not found.')
    if user and not user.is_staff and ticket.user != user:
        raise PermissionDenied('Not your ticket.')
    return ticket


def get_support_settings():
    from api.support.models import SupportSettings
    key = 'support:settings:singleton'
    obj = cache.get(key)
    if not obj:
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        cache.set(key, obj, timeout=300)
    return obj


def get_faq_or_404(faq_id):
    from api.support.models import FAQ
    try:
        return FAQ.objects.get(id=faq_id)
    except FAQ.DoesNotExist:
        raise NotFound(f'FAQ {faq_id} not found.')


def get_kb_article_or_404(slug):
    from api.support.models import KBArticle
    try:
        return KBArticle.objects.get(slug=slug, status='published', is_public=True)
    except KBArticle.DoesNotExist:
        raise NotFound(f'Article {slug} not found.')
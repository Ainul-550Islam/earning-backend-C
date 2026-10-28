# api/support/search.py
"""
Full-text search for support system.
Searches across tickets, KB articles, FAQs.
Uses Django ORM with Q objects (no Elasticsearch required).
"""
import logging
from typing import Optional

from django.db.models import Q

logger = logging.getLogger(__name__)


class SupportSearch:
    """Full-text search across support content."""

    # ── Ticket Search ─────────────────────────────────────────
    def search_tickets(self, query: str, user=None, limit: int = 20) -> list:
        """
        Search tickets by ticket_id, subject, description, user.
        If user is given and non-staff, only searches their own tickets.
        """
        if not query or len(query.strip()) < 2:
            return []
        from api.support.models import SupportTicket
        q  = query.strip()
        qs = SupportTicket.objects.select_related('user', 'assigned_to')
        if user and not user.is_staff:
            qs = qs.filter(user=user)
        qs = qs.filter(
            Q(ticket_id__icontains=q) |
            Q(subject__icontains=q) |
            Q(description__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(admin_response__icontains=q)
        ).distinct().order_by('-created_at')[:limit]
        return list(qs)

    # ── KB Article Search ─────────────────────────────────────
    def search_kb(self, query: str, limit: int = 10, published_only: bool = True) -> list:
        """Search KB articles by title, body, summary, tags."""
        if not query or len(query.strip()) < 2:
            return []
        from api.support.models import KBArticle
        q  = query.strip()
        qs = KBArticle.objects.select_related('category')
        if published_only:
            qs = qs.filter(status='published', is_public=True)
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(body__icontains=q) |
            Q(summary__icontains=q)
        ).distinct().order_by('-views_count')[:limit]
        return list(qs)

    # ── FAQ Search ────────────────────────────────────────────
    def search_faq(self, query: str, limit: int = 10) -> list:
        """Search FAQs by question and answer."""
        if not query or len(query.strip()) < 2:
            return []
        from api.support.models import FAQ
        q  = query.strip()
        qs = FAQ.objects.filter(
            is_active=True
        ).filter(
            Q(question__icontains=q) | Q(answer__icontains=q)
        ).order_by('-view_count')[:limit]
        return list(qs)

    # ── Unified Search ────────────────────────────────────────
    def search_all(self, query: str, user=None, limit_each: int = 5) -> dict:
        """
        Search across all content types.
        Returns dict: {tickets, kb_articles, faqs, total}
        """
        if not query or len(query.strip()) < 2:
            return {'tickets': [], 'kb_articles': [], 'faqs': [], 'total': 0}

        tickets     = self.search_tickets(query, user=user, limit=limit_each)
        kb_articles = self.search_kb(query, limit=limit_each)
        faqs        = self.search_faq(query, limit=limit_each)

        return {
            'tickets':     tickets,
            'kb_articles': kb_articles,
            'faqs':        faqs,
            'total':       len(tickets) + len(kb_articles) + len(faqs),
            'query':       query,
        }

    # ── Suggest KB for Ticket ─────────────────────────────────
    def suggest_kb_for_ticket(self, ticket, limit: int = 3) -> list:
        """
        Suggest relevant KB articles for a ticket.
        Uses subject + category to find matching articles.
        """
        search_terms = []
        if ticket.subject:
            # Extract key words (remove common words)
            words = ticket.subject.lower().split()
            stop  = {'the','a','an','is','my','i','not','and','or','in','to','for','of','was'}
            key_words = [w for w in words if len(w) > 3 and w not in stop]
            search_terms.extend(key_words[:3])

        if ticket.category:
            search_terms.append(ticket.category)

        if not search_terms:
            return []

        query   = ' '.join(search_terms)
        results = self.search_kb(query, limit=limit)
        return [
            {
                'id':      a.id,
                'title':   a.title,
                'slug':    a.slug,
                'summary': a.summary or a.body[:100],
                'category':a.category.name if a.category else '',
            }
            for a in results
        ]

    # ── Canned Response Search ────────────────────────────────
    def search_canned_responses(self, query: str, limit: int = 10) -> list:
        """Search canned responses by shortcut, title, content."""
        if not query:
            return []
        from api.support.models import CannedResponse
        q  = query.strip()
        qs = CannedResponse.objects.filter(
            is_active=True
        ).filter(
            Q(shortcut__icontains=q) |
            Q(title__icontains=q) |
            Q(content__icontains=q)
        ).order_by('shortcut')[:limit]
        return list(qs)


support_search = SupportSearch()
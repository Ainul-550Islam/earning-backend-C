# api/support/querysets.py
"""
Custom QuerySet classes for support models.
Full code — no summarizing.
These extend managers.py with additional query methods.
"""
from django.db import models
from django.utils import timezone
from django.db.models import Q, Count, Avg, F


class SupportTicketQuerySet(models.QuerySet):
    """Full-featured QuerySet for SupportTicket model."""

    # ── Status filters ────────────────────────────────────────
    def open(self):
        return self.filter(status='open')

    def in_progress(self):
        return self.filter(status='in_progress')

    def waiting(self):
        return self.filter(status='waiting_user')

    def active(self):
        """All non-closed, non-spam tickets."""
        return self.filter(status__in=['open', 'in_progress', 'waiting_user'])

    def resolved(self):
        return self.filter(status='resolved')

    def closed(self):
        return self.filter(status='closed')

    def spam(self):
        return self.filter(status='spam')

    # ── Priority filters ──────────────────────────────────────
    def urgent(self):
        return self.filter(priority='urgent')

    def high_priority(self):
        return self.filter(priority__in=['urgent', 'high'])

    def needs_attention(self):
        """Urgent + high priority that are still open."""
        return self.filter(priority__in=['urgent', 'high'], status__in=['open', 'in_progress', 'waiting_user'])

    # ── Assignment filters ────────────────────────────────────
    def unassigned(self):
        return self.filter(assigned_to__isnull=True)

    def assigned_to_agent(self, agent_user):
        return self.filter(assigned_to=agent_user)

    def assigned(self):
        return self.filter(assigned_to__isnull=False)

    # ── Response filters ──────────────────────────────────────
    def unanswered(self):
        return self.filter(Q(admin_response='') | Q(admin_response__isnull=True))

    def answered(self):
        return self.exclude(Q(admin_response='') | Q(admin_response__isnull=True))

    # ── Escalation filters ────────────────────────────────────
    def escalated(self):
        return self.filter(escalated=True)

    def not_escalated(self):
        return self.filter(escalated=False)

    # ── Time-based filters ────────────────────────────────────
    def created_today(self):
        return self.filter(created_at__date=timezone.now().date())

    def created_this_week(self):
        from datetime import timedelta
        return self.filter(created_at__gte=timezone.now() - timedelta(days=7))

    def created_this_month(self):
        from datetime import timedelta
        return self.filter(created_at__gte=timezone.now() - timedelta(days=30))

    def old_waiting(self, days=7):
        """Tickets waiting for user response for X days."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(status='waiting_user', updated_at__lte=cutoff)

    # ── SLA filters ───────────────────────────────────────────
    def sla_breached(self):
        return self.filter(
            Q(sla__first_response_breached=True) | Q(sla__resolution_breached=True)
        )

    def sla_at_risk(self):
        """Tickets where SLA deadline is within 1 hour."""
        from datetime import timedelta
        soon = timezone.now() + timedelta(hours=1)
        return self.filter(
            status__in=['open', 'in_progress', 'waiting_user'],
            sla__first_response_due__lte=soon,
            sla__first_response_at__isnull=True,
        )

    # ── Category filters ──────────────────────────────────────
    def for_category(self, category: str):
        return self.filter(category=category)

    def for_channel(self, channel: str):
        return self.filter(channel=channel)

    # ── Tenant ────────────────────────────────────────────────
    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def for_user(self, user):
        return self.filter(user=user)

    # ── Annotations ───────────────────────────────────────────
    def with_message_count(self):
        return self.annotate(msg_count=Count('messages'))

    def with_avg_rating(self):
        return self.annotate(avg_rating=Avg('ticket_rating__score'))

    # ── Search ────────────────────────────────────────────────
    def search(self, q: str):
        if not q or len(q.strip()) < 2:
            return self
        return self.filter(
            Q(ticket_id__icontains=q) |
            Q(subject__icontains=q) |
            Q(description__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q)
        )

    # ── Prefetch helpers ──────────────────────────────────────
    def with_full_detail(self):
        return self.select_related(
            'user', 'assigned_to', 'sla', 'tenant'
        ).prefetch_related(
            'messages', 'ticket_tags__tag', 'attachments', 'notification_logs'
        )

    def with_user(self):
        return self.select_related('user')

    def with_agent(self):
        return self.select_related('assigned_to')

    # ── Statistics ────────────────────────────────────────────
    def resolution_time_stats(self):
        """Get average resolution time in hours."""
        resolved = self.filter(status__in=['resolved', 'closed'], resolved_at__isnull=False)
        if not resolved.exists():
            return {'avg_hours': 0, 'count': 0}
        times = [
            (t.resolved_at - t.created_at).total_seconds() / 3600
            for t in resolved
            if t.resolved_at and t.created_at
        ]
        return {
            'avg_hours': round(sum(times) / len(times), 1) if times else 0,
            'count': len(times),
        }


class FAQQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_category(self, category: str):
        return self.filter(category=category)

    def popular(self, limit: int = 10):
        return self.order_by('-view_count')[:limit]

    def most_helpful(self, limit: int = 10):
        return self.annotate(
            helpful_total=F('helpful_yes') + F('helpful_no')
        ).filter(helpful_total__gt=0).order_by('-helpful_yes')[:limit]

    def search(self, q: str):
        return self.filter(Q(question__icontains=q) | Q(answer__icontains=q))


class KBArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status='published', is_public=True)

    def drafts(self):
        return self.filter(status='draft')

    def for_category(self, category_slug: str):
        return self.filter(category__slug=category_slug)

    def search(self, q: str):
        if not q or len(q.strip()) < 2:
            return self
        return self.filter(
            Q(title__icontains=q) | Q(body__icontains=q) | Q(summary__icontains=q)
        )

    def popular(self, limit: int = 10):
        return self.filter(status='published').order_by('-views_count')[:limit]

    def most_helpful(self, limit: int = 10):
        return self.filter(status='published').order_by('-helpful_yes')[:limit]


class OfferDisputeQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status='pending')

    def investigating(self):
        return self.filter(status='investigating')

    def approved(self):
        return self.filter(status='approved')

    def rejected(self):
        return self.filter(status='rejected')

    def for_user(self, user):
        return self.filter(user=user)

    def high_confidence(self, threshold: float = 0.85):
        return self.filter(confidence_score__gte=threshold)

    def low_confidence(self, threshold: float = 0.5):
        return self.filter(confidence_score__lt=threshold)

    def eligible_for_auto_approval(self):
        return self.filter(status='pending', confidence_score__gte=0.7)

    def with_ticket(self):
        return self.select_related('ticket', 'user')


class ChatSessionQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status='active')

    def waiting(self):
        return self.filter(status='waiting')

    def ended(self):
        return self.filter(status='ended')

    def for_user(self, user):
        return self.filter(user=user)

    def for_agent(self, agent_user):
        return self.filter(agent=agent_user)

    def unassigned(self):
        return self.filter(agent__isnull=True, status='waiting')

    def with_messages(self):
        return self.prefetch_related('messages')
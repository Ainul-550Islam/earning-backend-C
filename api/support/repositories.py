# api/support/repositories.py
"""
Repository pattern — data access layer abstraction.
Wraps Django ORM calls so business logic doesn't touch ORM directly.
Repositories are called by use_cases and services.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TicketRepository:
    """Data access for SupportTicket model."""

    def get_by_ticket_id(self, ticket_id: str):
        from api.support.models import SupportTicket
        try:
            return SupportTicket.objects.select_related(
                'user', 'assigned_to', 'sla', 'tenant'
            ).get(ticket_id=ticket_id)
        except SupportTicket.DoesNotExist:
            return None

    def get_by_id(self, pk: int):
        from api.support.models import SupportTicket
        try:
            return SupportTicket.objects.select_related(
                'user', 'assigned_to', 'sla'
            ).get(id=pk)
        except SupportTicket.DoesNotExist:
            return None

    def create(self, **kwargs):
        from api.support.models import SupportTicket
        return SupportTicket.objects.create(**kwargs)

    def update(self, ticket, **fields):
        for key, val in fields.items():
            setattr(ticket, key, val)
        ticket.save(update_fields=list(fields.keys()))
        return ticket

    def filter_for_user(self, user, **filters):
        from api.support.models import SupportTicket
        return SupportTicket.objects.filter(user=user, **filters).order_by('-created_at')

    def filter_all(self, **filters):
        from api.support.models import SupportTicket
        return SupportTicket.objects.filter(**filters).select_related(
            'user', 'assigned_to'
        ).order_by('-created_at')

    def count_by_status(self, tenant=None) -> dict:
        from api.support.models import SupportTicket
        from django.db.models import Count
        qs = SupportTicket.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)
        rows = qs.values('status').annotate(count=Count('id'))
        return {r['status']: r['count'] for r in rows}

    def bulk_update_status(self, queryset, new_status: str) -> int:
        from django.utils import timezone
        kwargs = {'status': new_status}
        if new_status in ('resolved', 'closed'):
            kwargs['resolved_at'] = timezone.now()
        return queryset.update(**kwargs)


class FAQRepository:
    """Data access for FAQ model."""

    def get_by_id(self, faq_id: int):
        from api.support.models import FAQ
        try:
            return FAQ.objects.get(id=faq_id)
        except FAQ.DoesNotExist:
            return None

    def list_active(self, category: str = None, tenant=None):
        from api.support.models import FAQ
        qs = FAQ.objects.filter(is_active=True)
        if category:
            qs = qs.filter(category=category)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('order', '-created_at')

    def create(self, **kwargs):
        from api.support.models import FAQ
        return FAQ.objects.create(**kwargs)

    def update(self, faq, **fields):
        for key, val in fields.items():
            setattr(faq, key, val)
        faq.save(update_fields=list(fields.keys()))
        return faq

    def increment_view_count(self, faq_id: int) -> None:
        from api.support.models import FAQ
        FAQ.objects.filter(id=faq_id).update(view_count=FAQ._meta.get_field('view_count').default)


class DisputeRepository:
    """Data access for OfferDispute and WithdrawalDispute."""

    def create_offer_dispute(self, **kwargs):
        from api.support.models import OfferDispute
        return OfferDispute.objects.create(**kwargs)

    def get_offer_dispute(self, dispute_id: int):
        from api.support.models import OfferDispute
        try:
            return OfferDispute.objects.select_related('user', 'ticket').get(id=dispute_id)
        except OfferDispute.DoesNotExist:
            return None

    def count_user_disputes_this_week(self, user) -> int:
        from api.support.models import OfferDispute
        from django.utils import timezone
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        return OfferDispute.objects.filter(user=user, created_at__gte=week_ago).count()

    def filter_pending(self, tenant=None):
        from api.support.models import OfferDispute
        qs = OfferDispute.objects.filter(
            status__in=['pending', 'investigating']
        ).select_related('user', 'ticket')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.order_by('-created_at')

    def update_dispute(self, dispute, **fields):
        for key, val in fields.items():
            setattr(dispute, key, val)
        dispute.save(update_fields=list(fields.keys()))
        return dispute


class SLARepository:
    """Data access for TicketSLA."""

    def get_for_ticket(self, ticket):
        try:
            return ticket.sla
        except Exception:
            return None

    def create_for_ticket(self, ticket, first_response_due, resolution_due):
        from api.support.models import TicketSLA
        sla, _ = TicketSLA.objects.get_or_create(
            ticket=ticket,
            defaults={
                'first_response_due': first_response_due,
                'resolution_due':     resolution_due,
            }
        )
        return sla

    def get_breached(self, tenant=None):
        from api.support.models import TicketSLA
        from django.db.models import Q
        qs = TicketSLA.objects.filter(
            Q(first_response_breached=True) | Q(resolution_breached=True)
        ).select_related('ticket')
        return qs

    def get_due_soon(self, hours: int = 1):
        """SLA records that will breach within N hours."""
        from api.support.models import TicketSLA
        from django.utils import timezone
        from datetime import timedelta
        soon = timezone.now() + timedelta(hours=hours)
        from django.db.models import Q
        return TicketSLA.objects.filter(
            Q(first_response_due__lte=soon, first_response_at__isnull=True,
              first_response_breached=False) |
            Q(resolution_due__lte=soon, resolution_at__isnull=True,
              resolution_breached=False)
        ).select_related('ticket')


class AgentRepository:
    """Data access for SupportAgent."""

    def get_available_agents(self, department=None, tenant=None):
        from api.support.models import SupportAgent
        qs = SupportAgent.objects.filter(
            is_active=True, is_available=True
        ).select_related('user', 'status_record')
        if department:
            qs = qs.filter(department=department)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def get_by_user(self, user):
        try:
            return user.support_agent
        except Exception:
            return None

    def set_availability(self, agent, available: bool) -> None:
        from api.support.models import SupportAgent
        SupportAgent.objects.filter(pk=agent.pk).update(is_available=available)


# ── Singleton instances ───────────────────────────────────────
ticket_repo  = TicketRepository()
faq_repo     = FAQRepository()
dispute_repo = DisputeRepository()
sla_repo     = SLARepository()
agent_repo   = AgentRepository()
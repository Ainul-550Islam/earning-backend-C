# api/support/managers.py
from django.db import models
from django.utils import timezone


class SupportTicketQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status__in=['open', 'in_progress', 'waiting_user'])

    def closed(self):
        return self.filter(status__in=['resolved', 'closed', 'spam'])

    def urgent(self):
        return self.filter(priority='urgent', status__in=['open', 'in_progress', 'waiting_user'])

    def unanswered(self):
        from django.db.models import Q
        return self.filter(Q(admin_response='') | Q(admin_response__isnull=True))

    def escalated(self):
        return self.filter(escalated=True)

    def unassigned(self):
        return self.filter(assigned_to__isnull=True, status__in=['open', 'in_progress'])

    def for_agent(self, agent):
        return self.filter(assigned_to=agent)

    def created_today(self):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(created_at__gte=today)

    def full_detail(self):
        return self.select_related(
            'user', 'assigned_to', 'sla', 'tenant'
        ).prefetch_related('messages', 'ticket_tags__tag', 'attachments')


class SupportTicketManager(models.Manager):
    def get_queryset(self):
        return SupportTicketQuerySet(self.model, using=self._db)

    def open(self):
        return self.get_queryset().open()

    def urgent(self):
        return self.get_queryset().urgent()

    def unanswered(self):
        return self.get_queryset().unanswered()

    def for_agent(self, agent):
        return self.get_queryset().for_agent(agent)


class FAQQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def popular(self, limit=10):
        return self.order_by('-view_count')[:limit]


class FAQManager(models.Manager):
    def get_queryset(self):
        return FAQQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()


class OfferDisputeQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status='pending')

    def approved(self):
        return self.filter(status='approved')

    def for_user(self, user):
        return self.filter(user=user)


class OfferDisputeManager(models.Manager):
    def get_queryset(self):
        return OfferDisputeQuerySet(self.model, using=self._db)

    def pending(self):
        return self.get_queryset().pending()
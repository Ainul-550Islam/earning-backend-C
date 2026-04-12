"""
DATABASE_MODELS/user_subscription_model.py
============================================
QuerySet + Manager for SubscriptionPlan, UserSubscription, RecurringBilling.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import timedelta

from django.db import models
from django.db.models import Count, DecimalField, F, Q, Sum
from django.utils import timezone


class SubscriptionPlanQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def popular_first(self):
        return self.order_by('-is_popular', 'sort_order', 'price')

    def by_interval(self, interval: str):
        return self.filter(interval=interval)

    def subscriber_count(self):
        """Annotate each plan with number of active subscribers."""
        return self.annotate(
            subscriber_count=Count(
                'monetization_tools_usersubscription_plan',
                filter=Q(monetization_tools_usersubscription_plan__status__in=['trial', 'active']),
            )
        )


class SubscriptionPlanManager(models.Manager):
    def get_queryset(self):
        return SubscriptionPlanQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def for_tenant(self, tenant):
        return self.get_queryset().active().for_tenant(tenant).popular_first()


class UserSubscriptionQuerySet(models.QuerySet):

    def active(self):
        return self.filter(
            status__in=['trial', 'active'],
            current_period_end__gt=timezone.now(),
        )

    def trial(self):
        return self.filter(status='trial')

    def expiring_within(self, hours: int = 24):
        now    = timezone.now()
        cutoff = now + timedelta(hours=hours)
        return self.filter(
            status__in=['trial', 'active'],
            current_period_end__lte=cutoff,
            current_period_end__gt=now,
        )

    def due_for_renewal(self):
        return self.filter(
            status='active',
            is_auto_renew=True,
            current_period_end__lte=timezone.now() + timedelta(hours=24),
            current_period_end__gt=timezone.now(),
        ).select_related('user', 'plan')

    def cancelled(self):
        return self.filter(status='cancelled')

    def expired(self):
        return self.filter(
            Q(status='expired') |
            Q(status__in=['trial', 'active'], current_period_end__lt=timezone.now())
        )

    def for_user(self, user):
        return self.filter(user=user)

    def for_plan(self, plan_id):
        return self.filter(plan_id=plan_id)

    def revenue_by_plan(self):
        return (
            self.filter(status='active')
                .values('plan__name', 'plan__price', 'plan__currency')
                .annotate(subscriber_count=Count('id'))
                .order_by('-subscriber_count')
        )

    def churn_stats(self, start, end):
        return {
            'new':       self.filter(started_at__date__gte=start, started_at__date__lte=end).count(),
            'cancelled': self.filter(cancelled_at__date__gte=start, cancelled_at__date__lte=end).count(),
            'expired':   self.filter(status='expired', updated_at__date__gte=start).count(),
        }


class UserSubscriptionManager(models.Manager):
    def get_queryset(self):
        return UserSubscriptionQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def get_active_for_user(self, user):
        return self.get_queryset().active().for_user(user).select_related('plan').first()

    def due_for_renewal(self):
        return self.get_queryset().due_for_renewal()

    def expiring_soon(self, hours: int = 24):
        return self.get_queryset().expiring_within(hours)


class RecurringBillingQuerySet(models.QuerySet):

    def scheduled(self):
        return self.filter(status='scheduled')

    def overdue(self):
        return self.filter(
            status='scheduled',
            scheduled_at__lt=timezone.now(),
        )

    def failed_with_retries_left(self):
        return self.filter(
            status='failed',
            attempt_count__lt=F('max_attempts'),
        )

    def due_now(self):
        return self.filter(
            status='scheduled',
            scheduled_at__lte=timezone.now(),
        ).select_related('subscription', 'subscription__user', 'subscription__plan')


class RecurringBillingManager(models.Manager):
    def get_queryset(self):
        return RecurringBillingQuerySet(self.model, using=self._db)

    def due_now(self):
        return self.get_queryset().due_now()

    def overdue(self):
        return self.get_queryset().overdue()

    def retry_queue(self):
        return self.get_queryset().failed_with_retries_left()

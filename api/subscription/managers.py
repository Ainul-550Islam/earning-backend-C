import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── QuerySets ─────────────────────────────────────────────────────────────────

class SubscriptionPlanQuerySet(models.QuerySet):
    def active(self):
        from .choices import PlanStatus
        return self.filter(status=PlanStatus.ACTIVE)

    def inactive(self):
        from .choices import PlanStatus
        return self.filter(status=PlanStatus.INACTIVE)

    def free(self):
        return self.filter(price=0)

    def paid(self):
        return self.filter(price__gt=0)

    def by_interval(self, interval):
        return self.filter(interval=interval)

    def with_benefits(self):
        return self.prefetch_related("benefits")

    def ordered(self):
        return self.order_by("price")


class UserSubscriptionQuerySet(models.QuerySet):
    def active(self):
        from .choices import SubscriptionStatus
        return self.filter(status=SubscriptionStatus.ACTIVE)

    def trialing(self):
        from .choices import SubscriptionStatus
        return self.filter(status=SubscriptionStatus.TRIALING)

    def cancelled(self):
        from .choices import SubscriptionStatus
        return self.filter(status=SubscriptionStatus.CANCELLED)

    def expired(self):
        from .choices import SubscriptionStatus
        return self.filter(status=SubscriptionStatus.EXPIRED)

    def past_due(self):
        from .choices import SubscriptionStatus
        return self.filter(status=SubscriptionStatus.PAST_DUE)

    def active_or_trialing(self):
        from .choices import SubscriptionStatus
        return self.filter(
            status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
        )

    def expiring_soon(self, days=7):
        threshold = timezone.now() + timezone.timedelta(days=days)
        return self.active_or_trialing().filter(current_period_end__lte=threshold)

    def expiring_trials(self, days=3):
        from .choices import SubscriptionStatus
        threshold = timezone.now() + timezone.timedelta(days=days)
        return self.filter(
            status=SubscriptionStatus.TRIALING,
            trial_end__lte=threshold,
            trial_end__gt=timezone.now(),
        )

    def overdue(self):
        from .choices import SubscriptionStatus
        return self.filter(
            status=SubscriptionStatus.PAST_DUE,
            current_period_end__lt=timezone.now(),
        )

    def for_user(self, user):
        return self.filter(user=user)

    def with_plan(self):
        return self.select_related("plan")

    def with_payments(self):
        return self.prefetch_related("payments")


class SubscriptionPaymentQuerySet(models.QuerySet):
    def succeeded(self):
        from .choices import PaymentStatus
        return self.filter(status=PaymentStatus.SUCCEEDED)

    def failed(self):
        from .choices import PaymentStatus
        return self.filter(status=PaymentStatus.FAILED)

    def pending(self):
        from .choices import PaymentStatus
        return self.filter(status=PaymentStatus.PENDING)

    def refunded(self):
        from .choices import PaymentStatus
        return self.filter(status__in=["refunded", "partially_refunded"])

    def for_subscription(self, subscription):
        return self.filter(subscription=subscription)

    def for_user(self, user):
        return self.filter(subscription__user=user)

    def in_date_range(self, start, end):
        return self.filter(created_at__date__range=[start, end])

    def total_revenue(self):
        from django.db.models import Sum
        from .choices import PaymentStatus
        return (
            self.filter(status=PaymentStatus.SUCCEEDED)
            .aggregate(total=Sum("amount"))["total"]
            or 0
        )


# ─── Managers ──────────────────────────────────────────────────────────────────

class SubscriptionPlanManager(models.Manager):
    def get_queryset(self):
        return SubscriptionPlanQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def free(self):
        return self.get_queryset().free()

    def paid(self):
        return self.get_queryset().paid()

    def get_default_plan(self):
        """Return the cheapest active plan (free tier if available)."""
        return self.active().ordered().first()


class UserSubscriptionManager(models.Manager):
    def get_queryset(self):
        return UserSubscriptionQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def active_or_trialing(self):
        return self.get_queryset().active_or_trialing()

    def expiring_soon(self, days=7):
        return self.get_queryset().expiring_soon(days)

    def get_active_for_user(self, user):
        """Get the single active subscription for a user, or None."""
        return self.active_or_trialing().filter(user=user).select_related("plan").first()

    def has_active_subscription(self, user):
        return self.active_or_trialing().filter(user=user).exists()


class SubscriptionPaymentManager(models.Manager):
    def get_queryset(self):
        return SubscriptionPaymentQuerySet(self.model, using=self._db)

    def succeeded(self):
        return self.get_queryset().succeeded()

    def failed(self):
        return self.get_queryset().failed()

    def total_revenue(self):
        return self.get_queryset().total_revenue()
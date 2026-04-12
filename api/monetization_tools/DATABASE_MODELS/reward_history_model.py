"""
DATABASE_MODELS/reward_history_model.py
=========================================
QuerySet + Manager for RewardTransaction, PointLedgerSnapshot, SpinWheelLog.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import date, timedelta

from django.db import models
from django.db.models import Count, DecimalField, F, Q, Sum
from django.utils import timezone


class RewardTransactionQuerySet(models.QuerySet):

    def for_user(self, user):
        return self.filter(user=user)

    def credits(self):
        return self.filter(amount__gt=0)

    def debits(self):
        return self.filter(amount__lt=0)

    def by_type(self, txn_type: str):
        return self.filter(transaction_type=txn_type)

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def in_date_range(self, start: date, end: date):
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def last_n_days(self, n: int = 30):
        return self.filter(created_at__gte=timezone.now() - timedelta(days=n))

    def by_reference(self, reference_id: str):
        return self.filter(reference_id=reference_id).first()

    def total_earned(self, user=None):
        qs = self.credits()
        if user:
            qs = qs.for_user(user)
        return qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    def total_spent(self, user=None):
        qs = self.debits()
        if user:
            qs = qs.for_user(user)
        return abs(qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))

    def breakdown_by_type(self):
        return (
            self.credits()
                .values('transaction_type')
                .annotate(count=Count('id'), total=Sum('amount'))
                .order_by('-total')
        )

    def top_earners(self, limit: int = 20):
        return (
            self.credits()
                .values('user_id', 'user__username')
                .annotate(total=Sum('amount'))
                .order_by('-total')[:limit]
        )

    def daily_issued(self, days: int = 30):
        from django.db.models.functions import TruncDate
        return (
            self.credits()
                .filter(created_at__gte=timezone.now() - timedelta(days=days))
                .annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(count=Count('id'), total=Sum('amount'))
                .order_by('day')
        )


class RewardTransactionManager(models.Manager):
    def get_queryset(self):
        return RewardTransactionQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user).order_by('-created_at')

    def credits_for_user(self, user):
        return self.get_queryset().for_user(user).credits()

    def user_balance_history(self, user, days: int = 30):
        """Return balance_after per day for charting."""
        from django.db.models.functions import TruncDate
        return (
            self.get_queryset()
                .for_user(user)
                .in_date_range(
                    (timezone.now() - timedelta(days=days)).date(),
                    timezone.now().date(),
                )
                .annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(closing_balance=Sum('amount'))
                .order_by('day')
        )


class SpinWheelLogQuerySet(models.QuerySet):

    def for_user(self, user):
        return self.filter(user=user)

    def today_for_user(self, user):
        return self.filter(user=user, played_at__date=timezone.now().date())

    def by_type(self, log_type: str):
        return self.filter(log_type=log_type)

    def wins(self):
        return self.exclude(prize_type='no_prize')

    def uncredited(self):
        return self.filter(is_credited=False).exclude(prize_type='no_prize')

    def prize_distribution(self):
        return (
            self.values('prize_type', 'log_type')
                .annotate(count=Count('id'), total_value=Sum('prize_value'))
                .order_by('-count')
        )

    def daily_count(self, user, log_type: str = 'spin_wheel') -> int:
        return self.filter(
            user=user,
            log_type=log_type,
            played_at__date=timezone.now().date(),
        ).count()


class SpinWheelLogManager(models.Manager):
    def get_queryset(self):
        return SpinWheelLogQuerySet(self.model, using=self._db)

    def today_count(self, user, log_type: str = 'spin_wheel') -> int:
        return self.get_queryset().daily_count(user, log_type)

    def wins_for_user(self, user):
        return self.get_queryset().for_user(user).wins().order_by('-played_at')

    def uncredited(self):
        return self.get_queryset().uncredited().select_related('user')

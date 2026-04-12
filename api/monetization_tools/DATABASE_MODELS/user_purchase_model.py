"""
DATABASE_MODELS/user_purchase_model.py
========================================
QuerySet + Manager for InAppPurchase and PayoutRequest/PayoutMethod.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import date

from django.db import models
from django.db.models import Count, DecimalField, Q, Sum
from django.utils import timezone


class InAppPurchaseQuerySet(models.QuerySet):

    def completed(self):
        return self.filter(status='completed')

    def pending(self):
        return self.filter(status='pending')

    def failed(self):
        return self.filter(status='failed')

    def refunded(self):
        return self.filter(status='refunded')

    def for_user(self, user):
        return self.filter(user=user)

    def for_product(self, product_id: str):
        return self.filter(product_id=product_id)

    def today(self):
        return self.filter(purchased_at__date=timezone.now().date())

    def in_date_range(self, start: date, end: date):
        return self.filter(purchased_at__date__gte=start, purchased_at__date__lte=end)

    def revenue_aggregate(self):
        return self.completed().aggregate(
            total_revenue=Sum('amount'),
            total_purchases=Count('id'),
            total_coins=Sum('coins_granted'),
        )

    def revenue_by_product(self):
        return (
            self.completed()
                .values('product_id', 'product_name', 'currency')
                .annotate(
                    count=Count('id'),
                    total=Sum('amount'),
                    coins=Sum('coins_granted'),
                )
                .order_by('-total')
        )

    def by_gateway(self):
        return (
            self.completed()
                .values('gateway')
                .annotate(count=Count('id'), revenue=Sum('amount'))
                .order_by('-revenue')
        )


class InAppPurchaseManager(models.Manager):
    def get_queryset(self):
        return InAppPurchaseQuerySet(self.model, using=self._db)

    def completed(self):
        return self.get_queryset().completed()

    def pending(self):
        return self.get_queryset().pending()

    def revenue_today(self):
        return self.get_queryset().today().revenue_aggregate()

    def revenue_in_range(self, start: date, end: date):
        return self.get_queryset().in_date_range(start, end).revenue_aggregate()


class PayoutRequestQuerySet(models.QuerySet):

    def pending(self):
        return self.filter(status='pending')

    def approved(self):
        return self.filter(status='approved')

    def paid(self):
        return self.filter(status='paid')

    def rejected(self):
        return self.filter(status='rejected')

    def for_user(self, user):
        return self.filter(user=user)

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def in_date_range(self, start: date, end: date):
        return self.filter(created_at__date__gte=start, created_at__date__lte=end)

    def amount_aggregate(self):
        return self.aggregate(
            total_requests=Count('id'),
            total_coins=Sum('coins_deducted'),
            total_amount_local=Sum('amount_local'),
            total_net=Sum('net_amount'),
        )

    def by_payout_method(self):
        return (
            self.paid()
                .values('payout_method__method_type')
                .annotate(count=Count('id'), total=Sum('net_amount'))
                .order_by('-total')
        )

    def pending_value(self):
        return self.pending().aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')


class PayoutRequestManager(models.Manager):
    def get_queryset(self):
        return PayoutRequestQuerySet(self.model, using=self._db)

    def pending(self):
        return self.get_queryset().pending().select_related('user', 'payout_method')

    def for_user(self, user):
        return self.get_queryset().for_user(user).select_related('payout_method')

    def pending_total(self):
        return self.get_queryset().pending_value()

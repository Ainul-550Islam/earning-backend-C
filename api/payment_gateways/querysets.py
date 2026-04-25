# api/payment_gateways/querysets.py
from django.db import models
from django.utils import timezone
from decimal import Decimal


class TransactionQuerySet(models.QuerySet):
    def completed(self):
        return self.filter(status='completed')

    def pending(self):
        return self.filter(status__in=('pending', 'processing'))

    def failed(self):
        return self.filter(status='failed')

    def for_user(self, user):
        return self.filter(user=user)

    def for_gateway(self, gateway):
        return self.filter(gateway=gateway)

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def total_amount(self):
        from django.db.models import Sum
        return self.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    def success_rate(self):
        total     = self.count()
        completed = self.completed().count()
        return round(completed / total * 100, 2) if total else 0.0


class DepositQuerySet(models.QuerySet):
    def completed(self): return self.filter(status='completed')
    def pending(self):   return self.filter(status__in=('initiated','pending'))
    def expired(self):   return self.filter(status='expired')
    def today(self):     return self.filter(initiated_at__date=timezone.now().date())


class ConversionQuerySet(models.QuerySet):
    def approved(self):  return self.filter(status='approved')
    def pending(self):   return self.filter(status='pending')
    def for_publisher(self, pub): return self.filter(publisher=pub)
    def for_offer(self, offer):   return self.filter(offer=offer)
    def today(self):     return self.filter(created_at__date=timezone.now().date())

    def total_payout(self):
        from django.db.models import Sum
        return self.aggregate(t=Sum('payout'))['t'] or Decimal('0')

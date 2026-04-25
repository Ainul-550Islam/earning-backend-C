# api/payment_gateways/managers.py
from django.db import models
from django.utils import timezone


class ActiveGatewayManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='active')


class CompletedTransactionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='completed')

    def today(self):
        return self.get_queryset().filter(created_at__date=timezone.now().date())

    def this_month(self):
        now = timezone.now()
        return self.get_queryset().filter(created_at__year=now.year, created_at__month=now.month)


class PendingManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status__in=('pending', 'processing'))


class ActiveOfferManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='active')

    def for_publisher(self, publisher):
        from django.db.models import Q
        return self.get_queryset().filter(
            Q(is_public=True) | Q(allowed_publishers=publisher)
        ).exclude(blocked_publishers=publisher)

    def for_country(self, country_code):
        from django.db.models import Q
        qs = self.get_queryset()
        if country_code:
            qs = qs.filter(
                Q(target_countries=[]) | Q(target_countries__contains=[country_code])
            ).exclude(blocked_countries__contains=[country_code])
        return qs

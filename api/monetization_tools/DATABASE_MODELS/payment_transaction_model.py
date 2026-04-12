"""
DATABASE_MODELS/payment_transaction_model.py
=============================================
QuerySet + Manager for PaymentTransaction, PostbackLog, FraudAlert.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import date, timedelta

from django.db import models
from django.db.models import Count, DecimalField, Q, Sum
from django.utils import timezone


class PaymentTransactionQuerySet(models.QuerySet):

    def success(self):
        return self.filter(status='success')

    def failed(self):
        return self.filter(status='failed')

    def pending(self):
        return self.filter(status__in=['initiated', 'pending'])

    def for_user(self, user):
        return self.filter(user=user)

    def by_gateway(self, gateway: str):
        return self.filter(gateway=gateway)

    def by_purpose(self, purpose: str):
        return self.filter(purpose=purpose)

    def today(self):
        return self.filter(initiated_at__date=timezone.now().date())

    def in_date_range(self, start: date, end: date):
        return self.filter(initiated_at__date__gte=start, initiated_at__date__lte=end)

    def revenue_aggregate(self):
        return self.success().aggregate(
            total_transactions=Count('id'),
            total_revenue=Sum('amount'),
        )

    def by_gateway_breakdown(self):
        return (
            self.success()
                .values('gateway', 'currency')
                .annotate(count=Count('id'), revenue=Sum('amount'))
                .order_by('-revenue')
        )

    def disputed(self):
        return self.filter(status='disputed')

    def refunded(self):
        return self.filter(status='refunded')

    def get_by_gateway_ref(self, gateway: str, gateway_txn_id: str):
        return self.filter(gateway=gateway, gateway_txn_id=gateway_txn_id).first()


class PaymentTransactionManager(models.Manager):
    def get_queryset(self):
        return PaymentTransactionQuerySet(self.model, using=self._db)

    def success(self):
        return self.get_queryset().success()

    def pending(self):
        return self.get_queryset().pending()

    def for_user(self, user):
        return self.get_queryset().for_user(user).order_by('-initiated_at')

    def today_revenue(self) -> dict:
        return self.get_queryset().today().revenue_aggregate()

    def in_range_revenue(self, start: date, end: date) -> dict:
        return self.get_queryset().in_date_range(start, end).revenue_aggregate()

    def get_by_gateway_ref(self, gateway: str, gateway_txn_id: str):
        return self.get_queryset().get_by_gateway_ref(gateway, gateway_txn_id)


class PostbackLogQuerySet(models.QuerySet):

    def received(self):
        return self.filter(status='received')

    def accepted(self):
        return self.filter(status='accepted')

    def rejected(self):
        return self.filter(status__in=['rejected', 'fraud', 'duplicate'])

    def unprocessed(self):
        return self.filter(status='received')

    def for_network(self, network_id):
        return self.filter(ad_network_id=network_id)

    def from_ip(self, ip: str):
        return self.filter(source_ip=ip)

    def signature_invalid(self):
        return self.filter(signature_valid=False)

    def today(self):
        return self.filter(received_at__date=timezone.now().date())

    def in_date_range(self, start: date, end: date):
        return self.filter(received_at__date__gte=start, received_at__date__lte=end)

    def fraud_ips(self, threshold: int = 10):
        """IPs sending many invalid/fraud postbacks."""
        return (
            self.rejected()
                .values('source_ip')
                .annotate(count=Count('id'))
                .filter(count__gte=threshold)
                .order_by('-count')
        )

    def status_summary(self):
        return (
            self.values('status')
                .annotate(count=Count('id'))
                .order_by('-count')
        )


class PostbackLogManager(models.Manager):
    def get_queryset(self):
        return PostbackLogQuerySet(self.model, using=self._db)

    def unprocessed(self):
        return self.get_queryset().unprocessed().select_related('ad_network').order_by('received_at')

    def suspicious_ips(self, threshold: int = 10):
        return self.get_queryset().fraud_ips(threshold)

    def today_summary(self):
        return self.get_queryset().today().status_summary()


class FraudAlertQuerySet(models.QuerySet):

    def open(self):
        return self.filter(resolution='open')

    def critical(self):
        return self.filter(severity='critical')

    def for_user(self, user):
        return self.filter(user=user)

    def by_type(self, alert_type: str):
        return self.filter(alert_type=alert_type)

    def unresolved(self):
        return self.filter(resolution__in=['open', 'reviewing'])

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def severity_summary(self):
        return (
            self.unresolved()
                .values('severity')
                .annotate(count=Count('id'))
                .order_by('-count')
        )

    def type_summary(self):
        return (
            self.values('alert_type')
                .annotate(count=Count('id'))
                .order_by('-count')
        )


class FraudAlertManager(models.Manager):
    def get_queryset(self):
        return FraudAlertQuerySet(self.model, using=self._db)

    def open_critical(self):
        return self.get_queryset().open().critical().select_related('user').order_by('-created_at')

    def for_user(self, user):
        return self.get_queryset().for_user(user).order_by('-created_at')

    def dashboard_summary(self):
        return {
            'open':     self.get_queryset().open().count(),
            'critical': self.get_queryset().critical().open().count(),
            'today':    self.get_queryset().today().count(),
            'by_type':  list(self.get_queryset().type_summary()),
        }

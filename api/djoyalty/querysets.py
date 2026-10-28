# api/djoyalty/querysets.py
"""
Djoyalty Custom QuerySets -- Reusable queryset logic।
Provides chainable query methods for complex loyalty queries।
"""
from django.db import models
from django.utils import timezone


class CustomerQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def verified(self):
        return self.filter(is_verified=True)

    def with_tier(self, tier_name: str):
        return self.filter(user_tiers__tier__name__iexact=tier_name, user_tiers__is_current=True)

    def at_risk_of_churn(self):
        from django.db.models import F
        try:
            return self.filter(ai_profile__churn_risk__in=['high', 'critical'])
        except Exception:
            return self.none()

    def with_balance_gte(self, min_balance):
        from decimal import Decimal
        return self.filter(loyalty_points__balance__gte=Decimal(str(min_balance)))

    def opted_in_sms(self):
        return self.filter(sms_opt_in=True)

    def opted_in_push(self):
        return self.filter(push_opt_in=True)

    def birthday_this_month(self):
        return self.filter(date_of_birth__month=timezone.now().month)

    def rfm_segment(self, segment: str):
        try:
            return self.filter(ai_profile__rfm_segment__iexact=segment)
        except Exception:
            return self.none()


class PointsLedgerQuerySet(models.QuerySet):
    def credits(self):
        return self.filter(txn_type='credit')

    def debits(self):
        return self.filter(txn_type='debit')

    def from_source(self, source: str):
        return self.filter(source=source)

    def this_month(self):
        now = timezone.now()
        return self.filter(created_at__year=now.year, created_at__month=now.month)

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

    def not_reversed(self):
        return self.filter(is_reversed=False)

    def total_credits(self):
        from django.db.models import Sum
        result = self.credits().not_reversed().aggregate(total=Sum('points'))
        return result['total'] or 0

    def total_debits(self):
        from django.db.models import Sum
        result = self.debits().not_reversed().aggregate(total=Sum('points'))
        return result['total'] or 0


class OfferCompletionQuerySet(models.QuerySet):
    def verified(self):
        return self.filter(status='verified')

    def points_awarded(self):
        return self.filter(status='points_awarded')

    def pending(self):
        return self.filter(status='pending')

    def fraudulent(self):
        return self.filter(is_flagged=True)

    def from_provider(self, provider_name: str):
        return self.filter(offer_wall__provider=provider_name)

    def today(self):
        return self.filter(completed_at__date=timezone.now().date())


class CashoutQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status='pending')

    def approved(self):
        return self.filter(status='approved')

    def completed(self):
        return self.filter(status='completed')

    def by_method(self, method: str):
        return self.filter(cashout_method=method)

    def this_month(self):
        now = timezone.now()
        return self.filter(created_at__year=now.year, created_at__month=now.month)


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(is_read=False)

    def read(self):
        return self.filter(is_read=True)

    def by_type(self, notif_type: str):
        return self.filter(notification_type=notif_type)

    def high_priority(self):
        return self.filter(priority__in=['high', 'critical'])

    def today(self):
        return self.filter(created_at__date=timezone.now().date())

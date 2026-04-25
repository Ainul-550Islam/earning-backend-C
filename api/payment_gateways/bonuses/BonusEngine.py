# api/payment_gateways/bonuses/BonusEngine.py
from decimal import Decimal
import logging
logger = logging.getLogger(__name__)


class BonusEngine:
    """Calculates and awards performance bonuses."""

    def calculate_monthly_bonus(self, publisher, year: int, month: int) -> Decimal:
        """Calculate bonus for a publisher's monthly earnings."""
        from .models import PerformanceTier
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum

        earnings = Conversion.objects.filter(
            publisher=publisher, status='approved',
            created_at__year=year, created_at__month=month,
        ).aggregate(t=Sum('payout'))['t'] or Decimal('0')

        tier = PerformanceTier.objects.filter(
            min_monthly_earnings__lte=earnings
        ).order_by('-min_monthly_earnings').first()

        if not tier or tier.bonus_percent <= 0:
            return Decimal('0')

        bonus = (earnings * tier.bonus_percent) / 100
        return bonus

    def award_monthly_bonuses(self, year: int, month: int) -> dict:
        """Award monthly performance bonuses to all qualifying publishers."""
        from .models import PublisherBonus
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        User    = get_user_model()
        awarded = 0

        for publisher in User.objects.filter(is_active=True):
            bonus_amount = self.calculate_monthly_bonus(publisher, year, month)
            if bonus_amount <= 0:
                continue

            period = f'{year}-{month:02d}'
            # Skip if already awarded this period
            if PublisherBonus.objects.filter(publisher=publisher, period=period,
                                              bonus_type='monthly_performance').exists():
                continue

            bonus = PublisherBonus.objects.create(
                publisher=publisher,
                bonus_type='monthly_performance',
                amount=bonus_amount,
                period=period,
                description=f'Monthly performance bonus for {period}',
            )

            # Auto-credit balance
            if hasattr(publisher, 'balance'):
                publisher.balance = (publisher.balance or Decimal('0')) + bonus_amount
                publisher.save(update_fields=['balance'])
                bonus.status = 'paid'
                bonus.paid_at = timezone.now()
                bonus.save()

            awarded += 1
            logger.info(f'Bonus awarded: {publisher.username} ${bonus_amount} for {period}')

        return {'awarded': awarded}

    def get_publisher_tier(self, publisher) -> 'PerformanceTier':
        """Get publisher's current tier based on last 30 days earnings."""
        from .models import PerformanceTier
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta

        since    = timezone.now() - timedelta(days=30)
        earnings = Conversion.objects.filter(
            publisher=publisher, status='approved', created_at__gte=since
        ).aggregate(t=Sum('payout'))['t'] or Decimal('0')

        return PerformanceTier.objects.filter(
            min_monthly_earnings__lte=earnings
        ).order_by('-min_monthly_earnings').first()

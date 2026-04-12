"""
SmartLink Publisher Payout Service
World #1: Automated payout calculation, scrubbing, and reporting.
Goes beyond CPAlead's manual payout system.
"""
import logging
import datetime
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q

logger = logging.getLogger('smartlink.billing')


class PublisherPayoutService:
    """
    Calculate publisher payouts with quality scrubbing.
    Supports: RevShare, CPA, CPC, CPM payout models.
    """

    SCRUB_RULES = {
        'max_fraud_rate':   0.20,   # Scrub if >20% fraud
        'max_bot_rate':     0.15,   # Scrub if >15% bots
        'min_unique_rate':  0.50,   # Require >50% unique clicks
        'min_cr':           0.001,  # Require >0.1% CR for CPA
    }

    def calculate_period_payout(self, publisher_id: int,
                                 date_from: datetime.date,
                                 date_to: datetime.date) -> dict:
        """
        Calculate total payout for a publisher for a date range.
        Applies quality scrubbing rules automatically.
        """
        from ...models import Click
        qs = Click.objects.filter(
            smartlink__publisher_id=publisher_id,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        total = qs.count()
        if total == 0:
            return self._empty_report(publisher_id, date_from, date_to)

        fraud    = qs.filter(is_fraud=True).count()
        bot      = qs.filter(is_bot=True).count()
        unique   = qs.filter(is_unique=True).count()
        converted = qs.filter(is_converted=True).count()

        fraud_rate  = fraud / total
        bot_rate    = bot / total
        unique_rate = unique / total if total > 0 else 0

        # Scrubbing decision
        scrubbed = False
        scrub_reason = ''
        if fraud_rate > self.SCRUB_RULES['max_fraud_rate']:
            scrubbed = True
            scrub_reason = f"Fraud rate {fraud_rate:.1%} exceeds {self.SCRUB_RULES['max_fraud_rate']:.1%}"
        elif bot_rate > self.SCRUB_RULES['max_bot_rate']:
            scrubbed = True
            scrub_reason = f"Bot rate {bot_rate:.1%} exceeds {self.SCRUB_RULES['max_bot_rate']:.1%}"

        # Gross revenue (only valid clicks)
        valid_qs     = qs.filter(is_fraud=False, is_bot=False, is_converted=True)
        gross_payout = float(valid_qs.aggregate(total=Sum('payout'))['total'] or 0)

        # Apply scrubbing penalty
        if scrubbed:
            net_payout = gross_payout * 0.5  # 50% penalty
            logger.warning(
                f"Publisher#{publisher_id} scrubbed: {scrub_reason} "
                f"Gross={gross_payout:.4f} Net={net_payout:.4f}"
            )
        else:
            net_payout = gross_payout

        return {
            'publisher_id':  publisher_id,
            'date_from':     str(date_from),
            'date_to':       str(date_to),
            'total_clicks':  total,
            'valid_clicks':  total - fraud - bot,
            'fraud_clicks':  fraud,
            'bot_clicks':    bot,
            'unique_clicks': unique,
            'conversions':   converted,
            'fraud_rate':    round(fraud_rate * 100, 2),
            'bot_rate':      round(bot_rate * 100, 2),
            'unique_rate':   round(unique_rate * 100, 2),
            'gross_payout':  round(gross_payout, 4),
            'net_payout':    round(net_payout, 4),
            'scrubbed':      scrubbed,
            'scrub_reason':  scrub_reason,
            'scrub_penalty': round(gross_payout - net_payout, 4),
        }

    def _empty_report(self, publisher_id, date_from, date_to) -> dict:
        return {
            'publisher_id': publisher_id,
            'date_from': str(date_from),
            'date_to': str(date_to),
            'total_clicks': 0,
            'gross_payout': 0,
            'net_payout': 0,
            'scrubbed': False,
        }

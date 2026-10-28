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
        from api.smartlink.models import Click
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

        # ── RevShare auto-calculation ──────────────────────────────────────────
        # For links using default_payout_model='revshare', add revenue-share
        # earnings on top of CPA payouts. Previously revshare_percent existed
        # on the model but was never used in payout calculation.
        from api.smartlink.models import SmartLink
        revshare_extra = self._calculate_revshare_earnings(
            publisher_id=publisher_id,
            date_from=date_from,
            date_to=date_to,
        )
        gross_payout += revshare_extra

        # Apply scrubbing penalty
        if scrubbed:
            net_payout = gross_payout * 0.5  # 50% penalty
            logger.warning(
                f"Publisher#{publisher_id} scrubbed: {scrub_reason} "
                f"Gross={gross_payout:.4f} Net={net_payout:.4f}"
            )
        else:
            net_payout = gross_payout

        # ── Publisher tier bonus ───────────────────────────────────────────────
        bonus_pct = self._get_tier_bonus_pct(publisher_id)
        if bonus_pct > 0:
            tier_bonus = net_payout * (bonus_pct / 100)
            net_payout += tier_bonus
            logger.info(
                f"Publisher#{publisher_id} tier bonus: +{bonus_pct}% = +{tier_bonus:.4f}"
            )
        else:
            tier_bonus = 0.0

        return {
            'publisher_id':    publisher_id,
            'date_from':       str(date_from),
            'date_to':         str(date_to),
            'total_clicks':    total,
            'valid_clicks':    total - fraud - bot,
            'fraud_clicks':    fraud,
            'bot_clicks':      bot,
            'unique_clicks':   unique,
            'conversions':     converted,
            'fraud_rate':      round(fraud_rate * 100, 2),
            'bot_rate':        round(bot_rate * 100, 2),
            'unique_rate':     round(unique_rate * 100, 2),
            'gross_payout_usd':round(gross_payout, 4),
            'gross_payout':    round(gross_payout, 4),
            'revshare_extra':  round(revshare_extra, 4),
            'tier_bonus':      round(tier_bonus, 4),
            'net_payout_usd':  round(net_payout, 4),
            'net_payout':      round(net_payout, 4),
            'scrubbed':        scrubbed,
            'scrub_reason':    scrub_reason,
            'scrub_rate':      round(0.5 if scrubbed else 0.0, 4),
            'scrub_deduction_usd': round(gross_payout - (gross_payout * 0.5 if scrubbed else gross_payout), 4),
            'scrub_penalty':   round(gross_payout - net_payout + tier_bonus, 4),
        }

    def _calculate_revshare_earnings(self, publisher_id: int,
                                     date_from, date_to) -> float:
        """
        Calculate additional RevShare earnings for SmartLinks configured with
        default_payout_model='revshare'. Multiplies the raw click revenue by
        the SmartLink's revshare_percent.

        Example: SmartLink has revshare_percent=30, offer earned $100 in revenue
        → publisher gets $30 regardless of individual click payouts.
        """
        from api.smartlink.models import SmartLink, Click
        revshare_total = 0.0
        revshare_links = SmartLink.objects.filter(
            publisher_id=publisher_id,
            default_payout_model='revshare',
            revshare_percent__gt=0,
        )
        for sl in revshare_links:
            period_revenue = float(
                Click.objects.filter(
                    smartlink=sl,
                    is_converted=True,
                    is_fraud=False,
                    is_bot=False,
                    created_at__date__gte=date_from,
                    created_at__date__lte=date_to,
                ).aggregate(total=Sum('payout'))['total'] or 0
            )
            if period_revenue > 0:
                share = period_revenue * float(sl.revshare_percent) / 100
                revshare_total += share
                logger.debug(
                    f"RevShare: sl=[{sl.slug}] revenue={period_revenue:.4f} "
                    f"rate={sl.revshare_percent}% share={share:.4f}"
                )
        return revshare_total

    def _get_tier_bonus_pct(self, publisher_id: int) -> float:
        """Return the publisher's tier bonus percentage (0 if no tier record)."""
        try:
            from api.smartlink.models.extensions.smartlink_schedule import PublisherTier
            tier = PublisherTier.objects.get(publisher_id=publisher_id)
            return float(tier.payout_bonus_percent or 0)
        except Exception:
            return 0.0

    def check_traffic_quality_auto_pause(self, publisher_id: int,
                                         hours: int = 1) -> dict:
        """
        Traffic source auto-pause check.
        If a publisher's traffic quality drops below threshold in the last N hours,
        suggest pausing or flag for review. Called by hourly_fraud_scan task.

        Returns: {should_pause: bool, reason: str, metrics: dict}
        """
        from api.smartlink.models import Click
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        recent = Click.objects.filter(
            smartlink__publisher_id=publisher_id,
            created_at__gte=cutoff,
        )
        total = recent.count()
        if total < 50:
            return {'should_pause': False, 'reason': 'Insufficient data', 'metrics': {}}

        fraud_count = recent.filter(is_fraud=True).count()
        bot_count   = recent.filter(is_bot=True).count()
        fraud_rate  = fraud_count / total
        bot_rate    = bot_count / total

        if fraud_rate > 0.40:
            return {
                'should_pause': True,
                'reason': f'Fraud rate {fraud_rate:.1%} exceeds 40% threshold in last {hours}h',
                'metrics': {'total': total, 'fraud_rate': fraud_rate, 'bot_rate': bot_rate},
            }
        if bot_rate > 0.50:
            return {
                'should_pause': True,
                'reason': f'Bot rate {bot_rate:.1%} exceeds 50% threshold in last {hours}h',
                'metrics': {'total': total, 'fraud_rate': fraud_rate, 'bot_rate': bot_rate},
            }
        return {
            'should_pause': False,
            'reason': 'Traffic quality within acceptable limits',
            'metrics': {'total': total, 'fraud_rate': fraud_rate, 'bot_rate': bot_rate},
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
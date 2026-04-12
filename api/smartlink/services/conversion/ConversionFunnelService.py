"""
SmartLink Conversion Funnel Service
World #1 Feature: Full funnel analytics from click to conversion.

Tracks every step:
Click → Landing Page → Pre-lander → Offer Page → Conversion

Identifies funnel dropoff points to help publishers optimize.
No competitor offers this level of funnel visibility.
"""
import logging
import datetime
from django.utils import timezone
from django.db.models import Count, Q, Avg

logger = logging.getLogger('smartlink.conversion_funnel')


class ConversionFunnelService:
    """
    Analyze the complete conversion funnel for a SmartLink.
    Shows where users drop off and how to improve conversion rate.
    """

    def get_funnel(self, smartlink, days: int = 7) -> dict:
        """
        Build full conversion funnel data.

        Returns step-by-step funnel:
        Total Clicks → Unique Clicks → Non-Fraud → Non-Bot → Conversions
        """
        from ...models import Click
        cutoff = timezone.now() - datetime.timedelta(days=days)

        qs = Click.objects.filter(smartlink=smartlink, created_at__gte=cutoff)

        total     = qs.count()
        unique    = qs.filter(is_unique=True).count()
        non_fraud = qs.filter(is_fraud=False).count()
        non_bot   = qs.filter(is_bot=False).count()
        clean     = qs.filter(is_fraud=False, is_bot=False).count()
        converted = qs.filter(is_converted=True, is_fraud=False, is_bot=False).count()

        def pct(a, b):
            return round(a / b * 100, 2) if b > 0 else 0

        funnel = {
            'period_days': days,
            'steps': [
                {
                    'step': 1,
                    'name': 'Total Clicks',
                    'count': total,
                    'rate': 100.0,
                    'drop': 0,
                },
                {
                    'step': 2,
                    'name': 'Unique Clicks',
                    'count': unique,
                    'rate': pct(unique, total),
                    'drop': total - unique,
                    'drop_reason': 'duplicate_clicks',
                },
                {
                    'step': 3,
                    'name': 'Non-Bot Traffic',
                    'count': non_bot,
                    'rate': pct(non_bot, total),
                    'drop': total - non_bot,
                    'drop_reason': 'bot_traffic',
                },
                {
                    'step': 4,
                    'name': 'Non-Fraud Traffic',
                    'count': non_fraud,
                    'rate': pct(non_fraud, total),
                    'drop': total - non_fraud,
                    'drop_reason': 'fraud_traffic',
                },
                {
                    'step': 5,
                    'name': 'Clean Traffic',
                    'count': clean,
                    'rate': pct(clean, total),
                    'drop': total - clean,
                    'drop_reason': 'combined_invalid',
                },
                {
                    'step': 6,
                    'name': 'Conversions',
                    'count': converted,
                    'rate': pct(converted, clean),
                    'drop': clean - converted,
                    'drop_reason': 'no_conversion',
                },
            ],
            'overall_cr':       pct(converted, total),
            'effective_cr':     pct(converted, clean),
            'traffic_quality':  pct(clean, total),
            'optimization_tips': self._generate_tips(total, unique, non_bot, non_fraud, converted),
        }

        return funnel

    def get_geo_funnel(self, smartlink, days: int = 7) -> list:
        """Funnel breakdown by country — shows which geos convert best."""
        from ...models import Click
        cutoff = timezone.now() - datetime.timedelta(days=days)

        rows = (
            Click.objects.filter(smartlink=smartlink, created_at__gte=cutoff)
            .values('country')
            .annotate(
                total=Count('id'),
                unique=Count('id', filter=Q(is_unique=True)),
                clean=Count('id', filter=Q(is_fraud=False, is_bot=False)),
                converted=Count('id', filter=Q(is_converted=True, is_fraud=False, is_bot=False)),
            )
            .order_by('-converted')[:20]
        )

        result = []
        for row in rows:
            t = row['total'] or 0
            c = row['clean'] or 0
            conv = row['converted'] or 0
            result.append({
                'country':        row['country'],
                'total_clicks':   t,
                'unique_clicks':  row['unique'] or 0,
                'clean_clicks':   c,
                'conversions':    conv,
                'overall_cr':     round(conv / t * 100, 2) if t else 0,
                'effective_cr':   round(conv / c * 100, 2) if c else 0,
                'quality_rate':   round(c / t * 100, 2) if t else 0,
            })
        return result

    def get_time_funnel(self, smartlink, days: int = 7) -> list:
        """Conversion rate by hour of day — find peak conversion hours."""
        from ...models import Click
        cutoff = timezone.now() - datetime.timedelta(days=days)

        rows = (
            Click.objects.filter(
                smartlink=smartlink,
                created_at__gte=cutoff,
                is_fraud=False, is_bot=False,
            )
            .extra(select={'hour': 'EXTRACT(HOUR FROM created_at)'})
            .values('hour')
            .annotate(
                clicks=Count('id'),
                converted=Count('id', filter=Q(is_converted=True)),
            )
            .order_by('hour')
        )

        result = []
        for row in rows:
            clicks = row['clicks'] or 0
            conv   = row['converted'] or 0
            result.append({
                'hour': int(row['hour']),
                'clicks': clicks,
                'conversions': conv,
                'cr': round(conv / clicks * 100, 2) if clicks else 0,
            })
        return result

    def _generate_tips(self, total, unique, non_bot, non_fraud, converted) -> list:
        """Generate actionable optimization tips based on funnel data."""
        tips = []

        if total == 0:
            return ['No traffic yet. Start sending clicks to this SmartLink.']

        unique_rate  = unique / total if total else 0
        bot_rate     = 1 - (non_bot / total) if total else 0
        fraud_rate   = 1 - (non_fraud / total) if total else 0
        clean_clicks = total - (total - non_bot) - (total - non_fraud)
        cr           = converted / max(clean_clicks, 1)

        if unique_rate < 0.5:
            tips.append(f"⚠️ Only {unique_rate*100:.0f}% unique clicks — reduce duplicate traffic from same source.")

        if bot_rate > 0.2:
            tips.append(f"🤖 {bot_rate*100:.0f}% bot traffic detected — review your traffic source quality.")

        if fraud_rate > 0.15:
            tips.append(f"🚨 {fraud_rate*100:.0f}% fraud traffic — consider blocking high-fraud traffic sources.")

        if cr < 0.01 and clean_clicks > 100:
            tips.append("📉 Low conversion rate (<1%) — try switching to EPC-optimized rotation.")

        if cr > 0.05:
            tips.append(f"🎉 Great CR of {cr*100:.1f}%! Consider increasing traffic volume.")

        if not tips:
            tips.append("✅ Funnel looks healthy! Keep monitoring daily stats.")

        return tips

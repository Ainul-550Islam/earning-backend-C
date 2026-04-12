"""
SmartLink Publisher Report Service
World #1 Feature: Advanced, drill-down performance reports.
Comparable to Everflow's reporting but with more dimensions.

Report types:
- Performance by date range
- Drill-down by geo, device, OS, browser, hour
- Offer-level breakdown
- Quality metrics (fraud rate, unique rate)
- Revenue trend analysis
- Top/bottom performer identification
"""
import logging
import datetime
from django.db.models import Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField
from django.utils import timezone

logger = logging.getLogger('smartlink.reports')


class PublisherReportService:
    """
    Generate comprehensive performance reports for publishers.
    All reports are queryable with flexible date ranges and dimensions.
    """

    DIMENSIONS = ['country', 'device_type', 'os', 'browser', 'offer', 'hour', 'date']

    def performance_report(self, publisher_id: int, params: dict) -> dict:
        """
        Main performance report.

        Params:
            date_from:   YYYY-MM-DD
            date_to:     YYYY-MM-DD
            smartlink:   slug (optional filter)
            group_by:    'date' | 'country' | 'device_type' | 'offer' | 'hour'
            include_fraud: bool (default False)
        """
        from ..models import Click, SmartLink

        date_from = params.get('date_from')
        date_to   = params.get('date_to')
        group_by  = params.get('group_by', 'date')
        sl_slug   = params.get('smartlink')
        include_fraud = params.get('include_fraud', False)

        # Base queryset
        qs = Click.objects.filter(
            smartlink__publisher_id=publisher_id
        )

        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if sl_slug:
            qs = qs.filter(smartlink__slug=sl_slug)
        if not include_fraud:
            qs = qs.filter(is_fraud=False, is_bot=False)

        # Group by dimension
        if group_by == 'date':
            rows = (
                qs.extra(select={'dim': "DATE(created_at)"})
                .values('dim')
                .annotate(**self._agg_fields())
                .order_by('dim')
            )
        elif group_by == 'country':
            rows = qs.values('country').annotate(**self._agg_fields()).order_by('-revenue')
        elif group_by == 'device_type':
            rows = qs.values('device_type').annotate(**self._agg_fields()).order_by('-clicks')
        elif group_by == 'offer':
            rows = qs.values('offer__id', 'offer__name').annotate(**self._agg_fields()).order_by('-revenue')
        elif group_by == 'hour':
            rows = (
                qs.extra(select={'dim': "EXTRACT(HOUR FROM created_at)"})
                .values('dim')
                .annotate(**self._agg_fields())
                .order_by('dim')
            )
        else:
            rows = qs.values(group_by).annotate(**self._agg_fields()).order_by('-clicks')

        # Compute totals
        totals = qs.aggregate(**self._agg_fields())
        formatted_rows = [self._format_row(r) for r in rows]

        return {
            'group_by':    group_by,
            'date_from':   str(date_from) if date_from else None,
            'date_to':     str(date_to) if date_to else None,
            'total_rows':  len(formatted_rows),
            'totals':      self._format_row(totals),
            'rows':        formatted_rows,
        }

    def top_performers(self, publisher_id: int, days: int = 7, limit: int = 10) -> dict:
        """Identify top-performing SmartLinks by EPC and revenue."""
        from ..models import SmartLink, Click
        cutoff = timezone.now() - datetime.timedelta(days=days)

        links = (
            Click.objects.filter(
                smartlink__publisher_id=publisher_id,
                created_at__gte=cutoff,
                is_fraud=False, is_bot=False,
            )
            .values('smartlink__slug', 'smartlink__name')
            .annotate(**self._agg_fields())
            .order_by('-epc')[:limit]
        )

        return {
            'period_days': days,
            'top_by_epc':     list(links.order_by('-epc')[:limit]),
            'top_by_revenue': list(links.order_by('-revenue')[:limit]),
            'top_by_clicks':  list(links.order_by('-clicks')[:limit]),
        }

    def hourly_heatmap(self, publisher_id: int, days: int = 7) -> list:
        """
        Generate 7×24 heatmap data (day of week × hour of day).
        Shows when traffic is highest quality.
        """
        from ..models import Click
        cutoff = timezone.now() - datetime.timedelta(days=days)

        rows = (
            Click.objects.filter(
                smartlink__publisher_id=publisher_id,
                created_at__gte=cutoff,
                is_fraud=False, is_bot=False,
            )
            .extra(select={
                'dow':  "EXTRACT(DOW FROM created_at)",
                'hour': "EXTRACT(HOUR FROM created_at)",
            })
            .values('dow', 'hour')
            .annotate(
                clicks=Count('id'),
                conversions=Count('id', filter=Q(is_converted=True)),
                revenue=Sum('payout'),
            )
            .order_by('dow', 'hour')
        )

        # Format as 7×24 matrix
        matrix = {}
        for row in rows:
            key = f"{int(row['dow'])}:{int(row['hour'])}"
            matrix[key] = {
                'dow':         int(row['dow']),
                'hour':        int(row['hour']),
                'clicks':      row['clicks'],
                'conversions': row['conversions'],
                'revenue':     float(row['revenue'] or 0),
            }

        return list(matrix.values())

    def quality_report(self, publisher_id: int, days: int = 30) -> dict:
        """Publisher traffic quality breakdown."""
        from ..models import Click
        cutoff = timezone.now() - datetime.timedelta(days=days)

        qs = Click.objects.filter(
            smartlink__publisher_id=publisher_id,
            created_at__gte=cutoff,
        )
        total = qs.count()
        if total == 0:
            return {'total': 0, 'quality_rate': 100}

        fraud    = qs.filter(is_fraud=True).count()
        bot      = qs.filter(is_bot=True).count()
        unique   = qs.filter(is_unique=True).count()
        converted = qs.filter(is_converted=True).count()
        valid    = total - fraud - bot

        return {
            'period_days':     days,
            'total_clicks':    total,
            'valid_clicks':    valid,
            'fraud_clicks':    fraud,
            'bot_clicks':      bot,
            'unique_clicks':   unique,
            'conversions':     converted,
            'quality_rate':    round(valid / total * 100, 2) if total else 0,
            'fraud_rate':      round(fraud / total * 100, 2) if total else 0,
            'bot_rate':        round(bot / total * 100, 2) if total else 0,
            'unique_rate':     round(unique / valid * 100, 2) if valid else 0,
            'conversion_rate': round(converted / valid * 100, 2) if valid else 0,
        }

    # ── Private ─────────────────────────────────────────────────────

    def _agg_fields(self) -> dict:
        return {
            'clicks':      Count('id'),
            'unique_clicks': Count('id', filter=Q(is_unique=True)),
            'conversions': Count('id', filter=Q(is_converted=True)),
            'revenue':     Sum('payout'),
        }

    def _format_row(self, row: dict) -> dict:
        clicks     = row.get('clicks', 0) or 0
        revenue    = float(row.get('revenue', 0) or 0)
        conversions = row.get('conversions', 0) or 0
        return {
            **row,
            'revenue':         round(revenue, 4),
            'epc':             round(revenue / clicks, 4) if clicks > 0 else 0,
            'conversion_rate': round(conversions / clicks * 100, 2) if clicks > 0 else 0,
        }

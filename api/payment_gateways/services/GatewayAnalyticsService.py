# api/payment_gateways/services/GatewayAnalyticsService.py
# Analytics aggregation for gateway performance

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class GatewayAnalyticsService:
    """Aggregates gateway analytics and updates PaymentAnalytics model."""

    def aggregate_daily(self, date=None) -> dict:
        """Aggregate analytics for all gateways for a given date."""
        from api.payment_gateways.models import (
            GatewayTransaction, PaymentGateway, PaymentAnalytics
        )
        from django.db.models import Sum, Count, Avg, Max, Min

        target = date or (timezone.now() - timedelta(days=1)).date()
        results = {}

        for gw in PaymentGateway.objects.all():
            for txn_type in ['deposit', 'withdrawal']:
                qs = GatewayTransaction.objects.filter(
                    gateway=gw.name,
                    transaction_type=txn_type,
                    created_at__date=target,
                )
                agg = qs.aggregate(
                    success_count=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='completed')),
                    failed_count =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='failed')),
                    pending_count=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status__in=['pending','processing'])),
                    total_amount =Sum('amount'),
                    total_fees   =Sum('fee'),
                    avg_amount   =Avg('amount'),
                    max_amount   =Max('amount'),
                    min_amount   =Min('amount'),
                )

                total = (agg['success_count'] or 0) + (agg['failed_count'] or 0) + (agg['pending_count'] or 0)

                analytics, _ = PaymentAnalytics.objects.update_or_create(
                    date=target, gateway=gw, transaction_type=txn_type, currency='BDT',
                    defaults={
                        'success_count': agg['success_count'] or 0,
                        'failed_count':  agg['failed_count']  or 0,
                        'pending_count': agg['pending_count'] or 0,
                        'total_count':   total,
                        'total_amount':  agg['total_amount']  or Decimal('0'),
                        'total_fees':    agg['total_fees']    or Decimal('0'),
                        'avg_amount':    agg['avg_amount']    or Decimal('0'),
                        'max_amount':    agg['max_amount']    or Decimal('0'),
                        'min_amount':    agg['min_amount']    or Decimal('0'),
                        'success_rate':  Decimal(str(round((agg['success_count'] or 0) / max(total,1), 4))),
                        'failure_rate':  Decimal(str(round((agg['failed_count']  or 0) / max(total,1), 4))),
                    }
                )

                # Update cache for success rate
                from django.core.cache import cache
                rate = float(analytics.success_rate)
                cache.set(f'gw_success_rate:{gw.name}', rate, 3600)

                results[f'{gw.name}_{txn_type}'] = {'total': total, 'success': agg['success_count'] or 0}

        logger.info(f'Analytics aggregated for {target}: {len(results)} combinations')
        return results

    def get_gateway_summary(self, days: int = 7) -> list:
        """Get summary stats per gateway for last N days."""
        from api.payment_gateways.models import PaymentAnalytics, PaymentGateway
        from django.db.models import Sum
        from django.utils import timezone

        since   = timezone.now().date() - timedelta(days=days)
        summary = []

        for gw in PaymentGateway.objects.all().order_by('sort_order'):
            qs  = PaymentAnalytics.objects.filter(gateway=gw, date__gte=since)
            agg = qs.aggregate(
                total_vol=Sum('total_amount'),
                total_txn=Sum('total_count'),
                success  =Sum('success_count'),
            )
            summary.append({
                'gateway':      gw.name,
                'display_name': gw.display_name,
                'status':       gw.health_status,
                'total_volume': float(agg['total_vol'] or 0),
                'total_txns':   agg['total_txn'] or 0,
                'success_count':agg['success'] or 0,
                'success_rate': round((agg['success'] or 0) / max(agg['total_txn'] or 1, 1) * 100, 1),
            })

        return summary

# api/publisher_tools/repository.py
"""Publisher Tools — Repository Pattern. DB query layer separated from services."""
from decimal import Decimal
from datetime import date, timedelta
from typing import Optional, List, Dict
from django.db.models import Sum, Avg, Count, Q, F, Max, Min
from django.utils import timezone
from django.core.cache import cache
from .models import (
    Publisher, Site, App, AdUnit, AdPlacement,
    MediationGroup, WaterfallItem, HeaderBiddingConfig,
    PublisherEarning, PayoutThreshold, PublisherInvoice,
    TrafficSafetyLog, SiteQualityMetric, InventoryVerification,
)
from .constants import CACHE_TTL_MEDIUM, CACHE_TTL_LONG
from .utils import build_cache_key


class PublisherRepository:
    """Publisher DB query methods."""

    @staticmethod
    def get_by_id(publisher_id: str) -> Optional[Publisher]:
        try:
            return Publisher.objects.select_related('user').get(publisher_id=publisher_id)
        except Publisher.DoesNotExist:
            return None

    @staticmethod
    def get_by_user(user) -> Optional[Publisher]:
        try:
            return user.publisher_profile
        except Exception:
            return None

    @staticmethod
    def get_by_api_key(api_key: str) -> Optional[Publisher]:
        cache_key = build_cache_key('pub_by_api_key', api_key[:8])
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            pub = Publisher.objects.get(api_key=api_key, status='active')
            cache.set(cache_key, pub, CACHE_TTL_LONG)
            return pub
        except Publisher.DoesNotExist:
            return None

    @staticmethod
    def get_active_publishers(tenant=None) -> List[Publisher]:
        qs = Publisher.objects.filter(status='active').select_related('user')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs)

    @staticmethod
    def get_publishers_needing_invoice(year: int, month: int) -> List[Publisher]:
        from .models import PublisherInvoice
        already_invoiced = PublisherInvoice.objects.filter(
            period_start__year=year, period_start__month=month,
        ).values_list('publisher_id', flat=True)
        return list(
            Publisher.objects.filter(
                status='active',
                is_kyc_verified=True,
            ).exclude(id__in=already_invoiced)
        )

    @staticmethod
    def update_revenue_totals(publisher: Publisher) -> Publisher:
        agg = PublisherEarning.objects.filter(
            publisher=publisher, status__in=['confirmed', 'finalized'],
        ).aggregate(total=Sum('publisher_revenue'))
        publisher.total_revenue = agg.get('total') or Decimal('0')
        publisher.save(update_fields=['total_revenue', 'updated_at'])
        return publisher

    @staticmethod
    def get_top_publishers_by_revenue(limit: int = 10, days: int = 30) -> List[Dict]:
        start = timezone.now().date() - timedelta(days=days)
        return list(
            PublisherEarning.objects.filter(date__gte=start)
            .values('publisher__publisher_id', 'publisher__display_name')
            .annotate(revenue=Sum('publisher_revenue'))
            .order_by('-revenue')[:limit]
        )


class SiteRepository:
    """Site DB query methods."""

    @staticmethod
    def get_by_site_id(site_id: str) -> Optional[Site]:
        try:
            return Site.objects.select_related('publisher').get(site_id=site_id)
        except Site.DoesNotExist:
            return None

    @staticmethod
    def get_by_domain(domain: str) -> Optional[Site]:
        try:
            return Site.objects.get(domain=domain.lower())
        except Site.DoesNotExist:
            return None

    @staticmethod
    def get_active_sites(publisher: Publisher) -> List[Site]:
        return list(Site.objects.filter(publisher=publisher, status='active'))

    @staticmethod
    def get_sites_needing_ads_txt_check() -> List[Site]:
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=24)
        return list(
            Site.objects.filter(status='active').filter(
                Q(ads_txt_verified=False) |
                Q(updated_at__lt=cutoff)
            ).select_related('publisher')
        )

    @staticmethod
    def get_sites_with_quality_alerts() -> List[Site]:
        today = timezone.now().date()
        alerted_site_ids = SiteQualityMetric.objects.filter(
            date=today, has_alerts=True
        ).values_list('site_id', flat=True)
        return list(Site.objects.filter(id__in=alerted_site_ids).select_related('publisher'))


class AdUnitRepository:
    """Ad Unit DB query methods."""

    @staticmethod
    def get_by_unit_id(unit_id: str) -> Optional[AdUnit]:
        cache_key = build_cache_key('ad_unit', unit_id)
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            unit = AdUnit.objects.select_related('publisher', 'site', 'app').get(unit_id=unit_id)
            cache.set(cache_key, unit, CACHE_TTL_MEDIUM)
            return unit
        except AdUnit.DoesNotExist:
            return None

    @staticmethod
    def get_active_units_for_site(site: Site) -> List[AdUnit]:
        return list(AdUnit.objects.filter(site=site, status='active').prefetch_related('targeting', 'mediation_group'))

    @staticmethod
    def get_active_units_for_app(app: App) -> List[AdUnit]:
        return list(AdUnit.objects.filter(app=app, status='active').prefetch_related('targeting', 'mediation_group'))

    @staticmethod
    def get_top_performing_units(publisher: Publisher, days: int = 30, limit: int = 10) -> List[Dict]:
        start = timezone.now().date() - timedelta(days=days)
        return list(
            PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
            .values('ad_unit__unit_id', 'ad_unit__name', 'ad_unit__format')
            .annotate(revenue=Sum('publisher_revenue'), impressions=Sum('impressions'))
            .order_by('-revenue')[:limit]
        )


class EarningRepository:
    """Earning DB query methods."""

    @staticmethod
    def get_period_summary(publisher: Publisher, start_date: date, end_date: date) -> Dict:
        return PublisherEarning.objects.filter(
            publisher=publisher, date__range=[start_date, end_date],
        ).aggregate(
            total_gross=Sum('gross_revenue'),
            total_publisher=Sum('publisher_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_requests=Sum('ad_requests'),
            avg_ecpm=Avg('ecpm'),
            avg_fill_rate=Avg('fill_rate'),
            avg_ctr=Avg('ctr'),
            ivt_deduction=Sum('invalid_traffic_deduction'),
        )

    @staticmethod
    def get_daily_chart_data(publisher: Publisher, start_date: date, end_date: date) -> List[Dict]:
        return list(
            PublisherEarning.objects.filter(
                publisher=publisher, date__range=[start_date, end_date], granularity='daily',
            ).values('date').annotate(
                revenue=Sum('publisher_revenue'),
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
                ecpm=Avg('ecpm'),
            ).order_by('date')
        )

    @staticmethod
    def get_by_country(publisher: Publisher, start_date: date, end_date: date) -> List[Dict]:
        return list(
            PublisherEarning.objects.filter(
                publisher=publisher, date__range=[start_date, end_date],
            ).values('country', 'country_name').annotate(
                revenue=Sum('publisher_revenue'),
                impressions=Sum('impressions'),
            ).order_by('-revenue')[:20]
        )

    @staticmethod
    def get_unfinalized_earnings(publisher: Publisher, year: int, month: int) -> List[PublisherEarning]:
        from calendar import monthrange
        last_day = monthrange(year, month)[1]
        start = date(year, month, 1)
        end   = date(year, month, last_day)
        return list(
            PublisherEarning.objects.filter(
                publisher=publisher, date__range=[start, end], status='estimated',
            )
        )


class FraudRepository:
    """Fraud & IVT DB query methods."""

    @staticmethod
    def get_pending_review(publisher: Publisher = None) -> List[TrafficSafetyLog]:
        qs = TrafficSafetyLog.objects.filter(action_taken='pending', is_false_positive=False)
        if publisher:
            qs = qs.filter(publisher=publisher)
        return list(qs.select_related('publisher', 'site', 'app').order_by('-fraud_score')[:100])

    @staticmethod
    def get_blocked_ips(publisher: Publisher = None) -> List[str]:
        qs = TrafficSafetyLog.objects.filter(action_taken='blocked', ip_address__isnull=False)
        if publisher:
            qs = qs.filter(publisher=publisher)
        return list(qs.values_list('ip_address', flat=True).distinct())

    @staticmethod
    def get_ivt_summary_by_type(publisher: Publisher, days: int = 30) -> List[Dict]:
        start = timezone.now().date() - timedelta(days=days)
        return list(
            TrafficSafetyLog.objects.filter(
                publisher=publisher, detected_at__date__gte=start, is_false_positive=False,
            ).values('traffic_type').annotate(
                count=Count('id'),
                revenue_at_risk=Sum('revenue_at_risk'),
                revenue_deducted=Sum('revenue_deducted'),
            ).order_by('-count')
        )

    @staticmethod
    def get_high_risk_publishers(min_fraud_score: int = 70, days: int = 7) -> List[Dict]:
        start = timezone.now() - timedelta(days=days)
        return list(
            TrafficSafetyLog.objects.filter(
                detected_at__gte=start, fraud_score__gte=min_fraud_score, is_false_positive=False,
            ).values('publisher__publisher_id', 'publisher__display_name').annotate(
                ivt_count=Count('id'),
                max_score=Max('fraud_score'),
            ).order_by('-ivt_count')
        )


class InvoiceRepository:
    """Invoice DB query methods."""

    @staticmethod
    def get_overdue_invoices() -> List[PublisherInvoice]:
        today = timezone.now().date()
        return list(
            PublisherInvoice.objects.filter(
                status='issued', due_date__lt=today,
            ).select_related('publisher', 'payout_threshold')
        )

    @staticmethod
    def get_publisher_invoice_history(publisher: Publisher, limit: int = 12) -> List[PublisherInvoice]:
        return list(
            PublisherInvoice.objects.filter(publisher=publisher)
            .order_by('-period_end')[:limit]
        )

    @staticmethod
    def get_pending_payment_total() -> Decimal:
        agg = PublisherInvoice.objects.filter(
            status='issued',
        ).aggregate(total=Sum('net_payable'))
        return agg.get('total') or Decimal('0')

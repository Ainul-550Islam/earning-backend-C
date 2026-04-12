# api/publisher_tools/services.py
"""
Publisher Tools — Business Logic / Service Layer।
View থেকে business logic আলাদা রাখা হয়েছে।
"""
import uuid
from decimal import Decimal
from datetime import date, timedelta
from typing import Optional, Dict, List, Any

from django.db import transaction
from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .models import (
    Publisher, Site, App, InventoryVerification,
    AdUnit, AdPlacement, AdUnitTargeting,
    MediationGroup, WaterfallItem, HeaderBiddingConfig,
    PublisherEarning, PayoutThreshold, PublisherInvoice,
    TrafficSafetyLog, SiteQualityMetric,
)
from .utils import (
    generate_publisher_id, generate_site_id, generate_app_id,
    generate_unit_id, generate_invoice_number, generate_api_key,
    generate_api_secret, generate_verification_token,
    calculate_ecpm, calculate_ctr, calculate_fill_rate,
    calculate_publisher_revenue, calculate_processing_fee,
    calculate_withholding_tax, calculate_net_payable,
    calculate_quality_score, get_date_range, build_cache_key,
    build_ads_txt_url, build_verification_meta_tag,
)
from .constants import (
    CACHE_TTL_MEDIUM, CACHE_TTL_LONG,
    FRAUD_SCORE_BLOCKED, MAX_IVT_PERCENTAGE,
    CRITICAL_IVT_THRESHOLD, ADS_TXT_CHECK_INTERVAL,
    WATERFALL_OPTIMIZE_INTERVAL,
)
from .exceptions import (
    PublisherNotFound, PublisherNotActive, PublisherAlreadyExists,
    SiteNotFound, SiteNotActive, DomainAlreadyExists,
    AppNotFound, PackageNameAlreadyExists,
    AdUnitNotFound, WaterfallLimitExceeded, PriorityConflict,
    InsufficientBalance, BelowPayoutThreshold,
    SiteVerificationFailed,
)

User = get_user_model()


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class PublisherService:
    """Publisher lifecycle management service"""

    @staticmethod
    @transaction.atomic
    def create_publisher(user: User, data: dict) -> Publisher:
        """
        নতুন Publisher profile তৈরি করে।
        - ID auto-generate
        - API key/secret generate
        - Welcome notification trigger
        """
        if hasattr(user, 'publisher_profile'):
            raise PublisherAlreadyExists()

        count = Publisher.objects.count() + 1
        publisher = Publisher.objects.create(
            user=user,
            publisher_id=generate_publisher_id(count),
            api_key=generate_api_key(),
            api_secret=generate_api_secret(),
            **data
        )

        # Trigger welcome notification (async)
        try:
            from .tasks import send_publisher_welcome_notification
            send_publisher_welcome_notification.delay(str(publisher.id))
        except Exception:
            pass

        return publisher

    @staticmethod
    def get_publisher(publisher_id: str) -> Publisher:
        """Publisher ID দিয়ে Publisher খোঁজে"""
        try:
            return Publisher.objects.select_related('user').get(publisher_id=publisher_id)
        except Publisher.DoesNotExist:
            raise PublisherNotFound()

    @staticmethod
    def get_publisher_by_user(user: User) -> Publisher:
        """User থেকে Publisher খোঁজে"""
        try:
            return user.publisher_profile
        except Exception:
            raise PublisherNotFound()

    @staticmethod
    @transaction.atomic
    def approve_publisher(publisher: Publisher, approved_by=None) -> Publisher:
        """Publisher approve করে"""
        publisher.status = 'active'
        publisher.save(update_fields=['status', 'updated_at'])

        try:
            from .tasks import send_publisher_approved_notification
            send_publisher_approved_notification.delay(str(publisher.id))
        except Exception:
            pass

        return publisher

    @staticmethod
    @transaction.atomic
    def suspend_publisher(publisher: Publisher, reason: str = '') -> Publisher:
        """Publisher suspend করে — সব site ও app suspend"""
        publisher.status = 'suspended'
        publisher.internal_notes = f"{publisher.internal_notes}\n[Suspended] {reason}"
        publisher.save(update_fields=['status', 'internal_notes', 'updated_at'])

        # Suspend all active sites and apps
        publisher.sites.filter(status='active').update(status='suspended')
        publisher.apps.filter(status='active').update(status='suspended')
        publisher.ad_units.filter(status='active').update(status='paused')

        return publisher

    @staticmethod
    def regenerate_api_key(publisher: Publisher) -> Publisher:
        """API key regenerate করে"""
        publisher.api_key = generate_api_key()
        publisher.api_secret = generate_api_secret()
        publisher.save(update_fields=['api_key', 'api_secret', 'updated_at'])
        return publisher

    @staticmethod
    def get_publisher_dashboard_stats(publisher: Publisher, period: str = 'last_30_days') -> dict:
        """Publisher dashboard-এর জন্য stats calculate করে"""
        cache_key = build_cache_key('publisher_dashboard', str(publisher.id), period)
        cached = cache.get(cache_key)
        if cached:
            return cached

        start_date, end_date = get_date_range(period)

        earnings = PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
        ).aggregate(
            total_gross=Sum('gross_revenue'),
            total_publisher=Sum('publisher_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_requests=Sum('ad_requests'),
        )

        period_revenue     = earnings.get('total_publisher') or Decimal('0')
        period_impressions = earnings.get('total_impressions') or 0
        period_clicks      = earnings.get('total_clicks') or 0
        period_requests    = earnings.get('total_requests') or 0
        period_ecpm        = calculate_ecpm(period_revenue, period_impressions)

        stats = {
            'publisher_id':    publisher.publisher_id,
            'display_name':    publisher.display_name,
            'total_revenue':   publisher.total_revenue,
            'total_paid_out':  publisher.total_paid_out,
            'pending_balance': publisher.pending_balance,
            'available_balance': publisher.available_balance,
            'active_sites':    publisher.active_sites_count,
            'active_apps':     publisher.active_apps_count,
            'total_ad_units':  publisher.ad_units.filter(status='active').count(),
            'period_revenue':    period_revenue,
            'period_impressions': period_impressions,
            'period_clicks':     period_clicks,
            'period_ecpm':       period_ecpm,
        }

        cache.set(cache_key, stats, CACHE_TTL_MEDIUM)
        return stats


# ──────────────────────────────────────────────────────────────────────────────
# SITE SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class SiteService:
    """Site management service"""

    @staticmethod
    @transaction.atomic
    def register_site(publisher: Publisher, data: dict) -> Site:
        """নতুন Site register করে"""
        domain = data.get('domain', '')
        from .validators import validate_domain
        domain = validate_domain(domain)
        data['domain'] = domain

        if Site.objects.filter(domain=domain).exists():
            raise DomainAlreadyExists()

        count = Site.objects.count() + 1
        site = Site.objects.create(
            publisher=publisher,
            site_id=generate_site_id(count),
            **data
        )

        # Auto-create verification record
        SiteService._create_verification_record(site, publisher)

        return site

    @staticmethod
    def _create_verification_record(site: Site, publisher: Publisher) -> InventoryVerification:
        """Site-এর জন্য verification record তৈরি করে"""
        from datetime import timedelta
        return InventoryVerification.objects.create(
            publisher=publisher,
            inventory_type='site',
            site=site,
            method='ads_txt',
            verification_token=generate_verification_token(),
            expires_at=timezone.now() + timedelta(days=7),
        )

    @staticmethod
    def verify_site(site: Site, method: str = 'ads_txt') -> dict:
        """
        Site ownership verify করার চেষ্টা করে।
        Returns: {'success': bool, 'message': str}
        """
        verification = InventoryVerification.objects.filter(
            site=site,
            method=method,
            status__in=['pending', 'failed'],
        ).first()

        if not verification:
            # নতুন verification record তৈরি
            verification = SiteService._create_verification_record(site, site.publisher)

        verification.attempt_count += 1

        # Actual verification logic (simplified — production-এ HTTP request করতে হবে)
        is_verified = SiteService._check_verification(site, method, verification.verification_token)

        if is_verified:
            verification.status = 'verified'
            verification.verified_at = timezone.now()
            site.ads_txt_verified = True
            site.status = 'active'
            site.approved_at = timezone.now()
            site.save(update_fields=['ads_txt_verified', 'status', 'approved_at', 'updated_at'])
        else:
            verification.status = 'failed'
            verification.failure_reason = f'Verification failed for method: {method}'

        verification.last_checked_at = timezone.now()
        verification.save()

        return {
            'success': is_verified,
            'message': 'Site verified successfully.' if is_verified else verification.failure_reason,
            'verification': verification,
        }

    @staticmethod
    def _check_verification(site: Site, method: str, token: str) -> bool:
        """
        Verification check করে।
        Production-এ এখানে actual HTTP request / DNS query হবে।
        """
        import requests
        try:
            if method == 'ads_txt':
                url = build_ads_txt_url(site.domain)
                response = requests.get(url, timeout=10)
                return site.publisher.publisher_id in response.text
            elif method == 'meta_tag':
                response = requests.get(site.url, timeout=10)
                return token in response.text
        except Exception:
            pass
        return False

    @staticmethod
    def approve_site(site: Site, approved_by=None) -> Site:
        """Site approve করে"""
        site.status = 'active'
        site.approved_at = timezone.now()
        site.approved_by = approved_by
        site.save(update_fields=['status', 'approved_at', 'approved_by', 'updated_at'])
        return site

    @staticmethod
    def reject_site(site: Site, reason: str) -> Site:
        """Site reject করে"""
        site.status = 'rejected'
        site.rejection_reason = reason
        site.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return site

    @staticmethod
    def refresh_ads_txt(site: Site) -> bool:
        """ads.txt সাইট থেকে re-fetch করে update করে"""
        try:
            import requests
            url = build_ads_txt_url(site.domain)
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                site.ads_txt_content = response.text
                site.ads_txt_verified = True
                site.save(update_fields=['ads_txt_content', 'ads_txt_verified', 'updated_at'])
                return True
        except Exception:
            pass
        site.ads_txt_verified = False
        site.save(update_fields=['ads_txt_verified', 'updated_at'])
        return False

    @staticmethod
    def get_site_analytics(site: Site, start_date: date, end_date: date) -> dict:
        """Site-এর analytics data aggregate করে"""
        earnings = PublisherEarning.objects.filter(
            site=site,
            date__range=[start_date, end_date],
        ).aggregate(
            total_revenue=Sum('publisher_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_requests=Sum('ad_requests'),
        )

        revenue     = earnings.get('total_revenue') or Decimal('0')
        impressions = earnings.get('total_impressions') or 0
        clicks      = earnings.get('total_clicks') or 0
        requests    = earnings.get('total_requests') or 0

        return {
            'site_id':    site.site_id,
            'domain':     site.domain,
            'period':     {'start': str(start_date), 'end': str(end_date)},
            'revenue':    float(revenue),
            'impressions': impressions,
            'clicks':     clicks,
            'ecpm':       float(calculate_ecpm(revenue, impressions)),
            'ctr':        float(calculate_ctr(clicks, impressions)),
            'fill_rate':  float(calculate_fill_rate(impressions, requests)),
        }


# ──────────────────────────────────────────────────────────────────────────────
# APP SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class AppService:
    """App management service"""

    @staticmethod
    @transaction.atomic
    def register_app(publisher: Publisher, data: dict) -> App:
        """নতুন App register করে"""
        package_name = data.get('package_name', '')
        if App.objects.filter(package_name=package_name).exists():
            raise PackageNameAlreadyExists()

        count = App.objects.count() + 1
        app = App.objects.create(
            publisher=publisher,
            app_id=generate_app_id(count),
            **data
        )
        return app

    @staticmethod
    def approve_app(app: App, approved_by=None) -> App:
        app.status = 'active'
        app.approved_at = timezone.now()
        app.approved_by = approved_by
        app.save(update_fields=['status', 'approved_at', 'approved_by', 'updated_at'])
        return app

    @staticmethod
    def reject_app(app: App, reason: str) -> App:
        app.status = 'rejected'
        app.rejection_reason = reason
        app.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return app

    @staticmethod
    def update_store_stats(app: App) -> App:
        """
        Play Store / App Store থেকে stats update করে।
        Production-এ এখানে store API call হবে।
        """
        # Placeholder — production-এ actual store API call
        app.save(update_fields=['updated_at'])
        return app


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class AdUnitService:
    """Ad Unit management service"""

    @staticmethod
    @transaction.atomic
    def create_ad_unit(publisher: Publisher, data: dict) -> AdUnit:
        """নতুন Ad Unit তৈরি করে"""
        count = AdUnit.objects.count() + 1
        ad_unit = AdUnit.objects.create(
            publisher=publisher,
            unit_id=generate_unit_id(count),
            **data
        )

        # Auto-generate ad tag code
        ad_unit.tag_code = AdUnitService._generate_tag_code(ad_unit)
        ad_unit.save(update_fields=['tag_code', 'updated_at'])

        return ad_unit

    @staticmethod
    def _generate_tag_code(ad_unit: AdUnit) -> str:
        """JavaScript ad tag code generate করে"""
        return f'''<!-- Publisher Tools Ad Tag | Unit: {ad_unit.unit_id} | Format: {ad_unit.format} -->
<div id="pt-ad-{ad_unit.unit_id}"></div>
<script>
(function(pt) {{
    pt.cmd = pt.cmd || [];
    pt.cmd.push(function() {{
        pt.display('{ad_unit.unit_id}');
    }});
}})(window.publisherTools = window.publisherTools || {{}});
</script>
<script async src="https://cdn.publishertools.io/pt.js?pub={ad_unit.publisher.publisher_id}"></script>'''

    @staticmethod
    def pause_ad_unit(ad_unit: AdUnit) -> AdUnit:
        ad_unit.status = 'paused'
        ad_unit.save(update_fields=['status', 'updated_at'])
        return ad_unit

    @staticmethod
    def activate_ad_unit(ad_unit: AdUnit) -> AdUnit:
        ad_unit.status = 'active'
        ad_unit.save(update_fields=['status', 'updated_at'])
        return ad_unit

    @staticmethod
    def update_performance_stats(ad_unit_id: str, stats: dict) -> None:
        """Ad Unit-এর performance stats update করে (from tracking callback)"""
        try:
            ad_unit = AdUnit.objects.get(id=ad_unit_id)
            ad_unit.total_impressions = F('total_impressions') + stats.get('impressions', 0)
            ad_unit.total_clicks = F('total_clicks') + stats.get('clicks', 0)
            ad_unit.total_revenue = F('total_revenue') + Decimal(str(stats.get('revenue', 0)))
            ad_unit.save(update_fields=['total_impressions', 'total_clicks', 'total_revenue', 'updated_at'])
        except AdUnit.DoesNotExist:
            raise AdUnitNotFound()


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class MediationService:
    """Mediation & Waterfall management service"""

    @staticmethod
    @transaction.atomic
    def create_mediation_group(ad_unit: AdUnit, data: dict) -> MediationGroup:
        """AdUnit-এর জন্য Mediation Group তৈরি করে"""
        group = MediationGroup.objects.create(ad_unit=ad_unit, **data)
        return group

    @staticmethod
    @transaction.atomic
    def add_waterfall_item(group: MediationGroup, data: dict) -> WaterfallItem:
        """Waterfall-এ নতুন network যোগ করে"""
        existing_count = group.waterfall_items.filter(status__in=['active', 'paused']).count()
        if existing_count >= 20:
            raise WaterfallLimitExceeded()

        priority = data.get('priority')
        if WaterfallItem.objects.filter(mediation_group=group, priority=priority).exists():
            raise PriorityConflict()

        item = WaterfallItem.objects.create(mediation_group=group, **data)
        return item

    @staticmethod
    @transaction.atomic
    def reorder_waterfall(group: MediationGroup, items: list) -> List[WaterfallItem]:
        """
        Waterfall priority reorder করে।
        items: [{'id': uuid, 'priority': int}, ...]
        """
        updated = []
        for item_data in items:
            try:
                item = WaterfallItem.objects.get(
                    id=item_data['id'],
                    mediation_group=group,
                )
                item.priority = item_data['priority']
                item.save(update_fields=['priority', 'updated_at'])
                updated.append(item)
            except WaterfallItem.DoesNotExist:
                continue
        return updated

    @staticmethod
    def optimize_waterfall(group: MediationGroup) -> MediationGroup:
        """
        eCPM-based waterfall optimization।
        সবচেয়ে বেশি eCPM-এর network সবার আগে যাবে।
        """
        items = group.waterfall_items.filter(status='active').order_by('-avg_ecpm')

        with transaction.atomic():
            for priority, item in enumerate(items, start=1):
                item.priority = priority
                item.save(update_fields=['priority', 'updated_at'])

        group.last_optimized_at = timezone.now()
        group.save(update_fields=['last_optimized_at', 'updated_at'])

        # Invalidate cache
        cache.delete(build_cache_key('waterfall', str(group.id)))

        return group

    @staticmethod
    def get_active_waterfall(group: MediationGroup) -> List[WaterfallItem]:
        """Active waterfall items priority অনুযায়ী sorted list return করে"""
        cache_key = build_cache_key('waterfall', str(group.id))
        cached = cache.get(cache_key)
        if cached:
            return cached

        items = list(
            group.waterfall_items
            .filter(status='active')
            .select_related('network')
            .order_by('priority')
        )
        cache.set(cache_key, items, CACHE_TTL_MEDIUM)
        return items


# ──────────────────────────────────────────────────────────────────────────────
# EARNING SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class EarningService:
    """Publisher earnings management service"""

    @staticmethod
    @transaction.atomic
    def record_earning(publisher: Publisher, data: dict) -> PublisherEarning:
        """
        Earning record তৈরি বা update করে।
        একই period + unit + country-র জন্য update করে, নতুন record তৈরি করে না।
        """
        # Calculate derived metrics
        gross     = Decimal(str(data.get('gross_revenue', 0)))
        rev_share = publisher.revenue_share_percentage
        publisher_rev = calculate_publisher_revenue(gross, rev_share)

        impressions = data.get('impressions', 0)
        clicks      = data.get('clicks', 0)
        requests    = data.get('ad_requests', 0)

        data['publisher_revenue'] = publisher_rev
        data['ecpm']      = calculate_ecpm(publisher_rev, impressions)
        data['ctr']       = calculate_ctr(clicks, impressions)
        data['fill_rate'] = calculate_fill_rate(impressions, requests)

        earning, created = PublisherEarning.objects.get_or_create(
            publisher=publisher,
            ad_unit=data.get('ad_unit'),
            date=data.get('date'),
            hour=data.get('hour'),
            country=data.get('country', ''),
            earning_type=data.get('earning_type', 'display'),
            defaults=data,
        )

        if not created:
            # Update existing record
            for field, value in data.items():
                setattr(earning, field, value)
            earning.save()

        # Update publisher totals
        EarningService._update_publisher_totals(publisher)

        return earning

    @staticmethod
    def _update_publisher_totals(publisher: Publisher) -> None:
        """Publisher-এর aggregate revenue totals update করে"""
        totals = PublisherEarning.objects.filter(
            publisher=publisher,
            status__in=['confirmed', 'finalized'],
        ).aggregate(
            total=Sum('publisher_revenue'),
        )
        publisher.total_revenue = totals.get('total') or Decimal('0')
        publisher.save(update_fields=['total_revenue', 'updated_at'])

    @staticmethod
    def get_earnings_report(
        publisher: Publisher,
        start_date: date,
        end_date: date,
        granularity: str = 'daily',
        group_by: Optional[list] = None,
    ) -> Dict:
        """
        Earnings report generate করে।
        granularity: 'hourly', 'daily', 'weekly', 'monthly'
        group_by: ['country', 'ad_unit', 'earning_type', 'network']
        """
        qs = PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
            granularity=granularity,
        )

        if group_by:
            qs = qs.values(*group_by).annotate(
                total_revenue=Sum('publisher_revenue'),
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_requests=Sum('ad_requests'),
            ).order_by(*group_by)
        else:
            qs = qs.values('date').annotate(
                total_revenue=Sum('publisher_revenue'),
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
            ).order_by('date')

        data = list(qs)

        # Overall summary
        summary = PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
        ).aggregate(
            total_gross=Sum('gross_revenue'),
            total_publisher=Sum('publisher_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_requests=Sum('ad_requests'),
        )

        return {
            'summary': summary,
            'data': data,
            'period': {'start': str(start_date), 'end': str(end_date)},
            'granularity': granularity,
        }

    @staticmethod
    def finalize_monthly_earnings(publisher: Publisher, year: int, month: int) -> None:
        """Monthly earnings finalize করে — status 'estimated' → 'finalized'"""
        from calendar import monthrange
        last_day = monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date   = date(year, month, last_day)

        PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
            status='confirmed',
        ).update(status='finalized')


# ──────────────────────────────────────────────────────────────────────────────
# INVOICE SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class InvoiceService:
    """Publisher invoice management service"""

    @staticmethod
    @transaction.atomic
    def generate_monthly_invoice(
        publisher: Publisher,
        year: int,
        month: int,
    ) -> PublisherInvoice:
        """
        Monthly invoice generate করে।
        সব finalized earnings aggregate করে একটি invoice তৈরি করে।
        """
        from calendar import monthrange
        last_day   = monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date   = date(year, month, last_day)

        # Earnings aggregate
        earnings = PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
            status='finalized',
        ).aggregate(
            gross=Sum('gross_revenue'),
            publisher_share=Sum('publisher_revenue'),
            ivt=Sum('invalid_traffic_deduction'),
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
            requests=Sum('ad_requests'),
        )

        gross_revenue   = earnings.get('gross') or Decimal('0')
        publisher_share = earnings.get('publisher_share') or Decimal('0')
        ivt_deduction   = earnings.get('ivt') or Decimal('0')

        # Get primary payment method
        payout_threshold = PayoutThreshold.objects.filter(
            publisher=publisher,
            is_primary=True,
            is_verified=True,
        ).first()

        # Calculate fees
        processing_fee = Decimal('0')
        withholding_tax = Decimal('0')
        if payout_threshold:
            processing_fee = calculate_processing_fee(
                publisher_share,
                payout_threshold.processing_fee_flat,
                payout_threshold.processing_fee_percentage,
            )
            withholding_tax = calculate_withholding_tax(
                publisher_share,
                payout_threshold.withholding_tax_percentage,
            )

        net_payable = calculate_net_payable(
            publisher_share, ivt_deduction, Decimal('0'),
            processing_fee, withholding_tax,
        )

        # Invoice number
        count = PublisherInvoice.objects.filter(
            period_start__year=year,
            period_start__month=month,
        ).count() + 1

        invoice = PublisherInvoice.objects.create(
            publisher=publisher,
            invoice_number=generate_invoice_number(year, month, count),
            invoice_type='regular',
            period_start=start_date,
            period_end=end_date,
            gross_revenue=gross_revenue,
            publisher_share=publisher_share,
            ivt_deduction=ivt_deduction,
            processing_fee=processing_fee,
            withholding_tax=withholding_tax,
            net_payable=net_payable,
            payout_threshold=payout_threshold,
            status='draft',
            due_date=end_date + timedelta(days=30),
            total_impressions=earnings.get('impressions') or 0,
            total_clicks=earnings.get('clicks') or 0,
            total_ad_requests=earnings.get('requests') or 0,
        )

        return invoice

    @staticmethod
    @transaction.atomic
    def issue_invoice(invoice: PublisherInvoice, issued_by=None) -> PublisherInvoice:
        """Invoice issue করে (Draft → Issued)"""
        invoice.status = 'issued'
        invoice.issued_at = timezone.now()
        invoice.processed_by = issued_by
        invoice.save(update_fields=['status', 'issued_at', 'processed_by', 'updated_at'])

        # Publisher pending balance update
        publisher = invoice.publisher
        publisher.pending_balance = F('pending_balance') + invoice.net_payable
        publisher.save(update_fields=['pending_balance', 'updated_at'])

        return invoice

    @staticmethod
    @transaction.atomic
    def mark_as_paid(invoice: PublisherInvoice, payment_reference: str, processed_by=None) -> PublisherInvoice:
        """Invoice paid করা হয়েছে mark করে"""
        invoice.status = 'paid'
        invoice.paid_at = timezone.now()
        invoice.payment_reference = payment_reference
        invoice.processed_by = processed_by
        invoice.save(update_fields=['status', 'paid_at', 'payment_reference', 'processed_by', 'updated_at'])

        # Publisher balance update
        publisher = invoice.publisher
        publisher.total_paid_out = F('total_paid_out') + invoice.net_payable
        publisher.pending_balance = F('pending_balance') - invoice.net_payable
        publisher.save(update_fields=['total_paid_out', 'pending_balance', 'updated_at'])

        return invoice

    @staticmethod
    def check_payout_eligibility(publisher: Publisher) -> dict:
        """Publisher payout-এর জন্য eligible কিনা চেক করে"""
        threshold = PayoutThreshold.objects.filter(
            publisher=publisher,
            is_primary=True,
            is_verified=True,
        ).first()

        if not threshold:
            return {
                'eligible': False,
                'reason': 'No verified payment method configured.',
            }

        available = publisher.available_balance
        if available < threshold.minimum_threshold:
            return {
                'eligible': False,
                'reason': f'Balance ${float(available):.2f} is below minimum threshold ${float(threshold.minimum_threshold):.2f}.',
                'current_balance': float(available),
                'required': float(threshold.minimum_threshold),
            }

        return {
            'eligible': True,
            'available_balance': float(available),
            'payment_method': threshold.payment_method,
            'estimated_net': float(
                calculate_net_payable(
                    available, Decimal('0'), Decimal('0'),
                    threshold.processing_fee_flat,
                    calculate_withholding_tax(available, threshold.withholding_tax_percentage),
                )
            ),
        }


# ──────────────────────────────────────────────────────────────────────────────
# FRAUD DETECTION SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class FraudDetectionService:
    """Traffic quality & fraud detection service"""

    @staticmethod
    @transaction.atomic
    def log_ivt_event(publisher: Publisher, event_data: dict) -> TrafficSafetyLog:
        """IVT event log করে এবং action নেয়"""
        log = TrafficSafetyLog.objects.create(
            publisher=publisher,
            **event_data,
        )

        # Auto-action based on fraud score
        if log.fraud_score >= FRAUD_SCORE_BLOCKED:
            FraudDetectionService.auto_block(log)

        # Update site/app IVT stats
        if log.site:
            FraudDetectionService._update_site_ivt_stats(log.site)

        return log

    @staticmethod
    def auto_block(log: TrafficSafetyLog) -> None:
        """High fraud score হলে auto-block করে"""
        log.action_taken = 'blocked'
        log.action_taken_at = timezone.now()
        log.save(update_fields=['action_taken', 'action_taken_at', 'updated_at'])

        # Block IP if available
        if log.ip_address:
            from django.core.cache import cache
            cache.set(f'blocked_ip:{log.ip_address}', True, 86400)  # 24 hours

    @staticmethod
    def _update_site_ivt_stats(site: Site) -> None:
        """Site-এর IVT stats update করে quality metric-এ"""
        today = timezone.now().date()
        quality_metric, _ = SiteQualityMetric.objects.get_or_create(
            site=site,
            date=today,
            defaults={'overall_quality_score': site.quality_score},
        )

        ivt_count = TrafficSafetyLog.objects.filter(
            site=site,
            detected_at__date=today,
        ).count()

        # Simplified IVT percentage (production-এ impression count-এর সাথে compare করতে হবে)
        quality_metric.has_alerts = ivt_count > 0
        quality_metric.save(update_fields=['has_alerts', 'updated_at'])

    @staticmethod
    def take_action(log: TrafficSafetyLog, action: str, taken_by=None, notes: str = '') -> TrafficSafetyLog:
        """Fraud log-এ action নেয়"""
        log.action_taken = action
        log.action_taken_at = timezone.now()
        log.action_taken_by = taken_by
        if notes:
            log.notes = notes
        log.save(update_fields=['action_taken', 'action_taken_at', 'action_taken_by', 'notes', 'updated_at'])

        if action == 'suspended':
            PublisherService.suspend_publisher(log.publisher, f'IVT fraud detected: {log.traffic_type}')

        return log

    @staticmethod
    def calculate_publisher_ivt_rate(publisher: Publisher, days: int = 30) -> float:
        """Publisher-এর IVT rate calculate করে"""
        start_date = timezone.now().date() - timedelta(days=days)

        ivt_logs = TrafficSafetyLog.objects.filter(
            publisher=publisher,
            detected_at__date__gte=start_date,
            is_false_positive=False,
        )

        total_affected_impressions = ivt_logs.aggregate(
            total=Sum('affected_impressions')
        ).get('total') or 0

        earnings = PublisherEarning.objects.filter(
            publisher=publisher,
            date__gte=start_date,
        ).aggregate(total=Sum('impressions')).get('total') or 0

        if earnings == 0:
            return 0.0

        return round((total_affected_impressions / earnings) * 100, 2)


# ──────────────────────────────────────────────────────────────────────────────
# QUALITY METRIC SERVICE
# ──────────────────────────────────────────────────────────────────────────────

class QualityMetricService:
    """Site quality metric service"""

    @staticmethod
    @transaction.atomic
    def update_daily_metrics(site: Site, metrics_data: dict) -> SiteQualityMetric:
        """Site-এর daily quality metrics update করে"""
        today = timezone.now().date()

        metric, created = SiteQualityMetric.objects.update_or_create(
            site=site,
            date=today,
            defaults=metrics_data,
        )

        # Calculate composite score
        score = calculate_quality_score(
            viewability_rate=float(metric.viewability_rate),
            content_score=metric.content_score,
            invalid_traffic_percentage=float(metric.invalid_traffic_percentage),
            page_speed_score=metric.page_speed_score or 50,
        )

        # Score change from yesterday
        yesterday = today - timedelta(days=1)
        prev_metric = SiteQualityMetric.objects.filter(
            site=site, date=yesterday
        ).first()

        prev_score = prev_metric.overall_quality_score if prev_metric else score
        metric.score_change = score - prev_score
        metric.overall_quality_score = score

        # Check alerts
        alerts = []
        if metric.malware_detected:
            alerts.append({'type': 'malware', 'severity': 'critical'})
        if metric.adult_content_detected:
            alerts.append({'type': 'adult_content', 'severity': 'high'})
        if float(metric.invalid_traffic_percentage) > MAX_IVT_PERCENTAGE:
            alerts.append({'type': 'high_ivt', 'severity': 'high', 'rate': float(metric.invalid_traffic_percentage)})
        if score < 40:
            alerts.append({'type': 'low_quality_score', 'severity': 'medium', 'score': score})

        metric.has_alerts = len(alerts) > 0
        metric.alert_details = alerts
        metric.save()

        # Update site quality score
        site.quality_score = score
        site.save(update_fields=['quality_score', 'updated_at'])

        return metric

    @staticmethod
    def get_quality_trend(site: Site, days: int = 30) -> List[dict]:
        """Site-এর quality score trend data return করে"""
        start_date = timezone.now().date() - timedelta(days=days)
        return list(
            SiteQualityMetric.objects.filter(
                site=site,
                date__gte=start_date,
            ).values(
                'date', 'overall_quality_score',
                'viewability_rate', 'invalid_traffic_percentage',
                'content_quality',
            ).order_by('date')
        )

# publisher_tools/tests/test_services.py
"""
High-priority service-layer tests.

Tests the core business-logic methods directly (no HTTP overhead):
  PublisherService, SiteService, AppService, AdUnitService,
  MediationService, EarningService, InvoiceService,
  FraudDetectionService, QualityMetricService

Run:
    pytest publisher_tools/tests/test_services.py -v
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone

from publisher_tools.services import (
    PublisherService, SiteService, AppService, AdUnitService,
    MediationService, EarningService, InvoiceService,
    FraudDetectionService, QualityMetricService,
)
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AppFactory,
    AdUnitFactory, AdPlacementFactory,
    MediationGroupFactory, WaterfallItemFactory,
    PublisherEarningFactory, PayoutThresholdFactory,
    PublisherInvoiceFactory, TrafficSafetyLogFactory,
    SiteQualityMetricFactory, UserFactory,
)


# ==============================================================================
# PublisherService
# ==============================================================================

@pytest.mark.django_db
class TestPublisherService:

    def test_create_publisher_generates_publisher_id(self):
        user = UserFactory()
        pub = PublisherService.create_publisher(user, {
            'display_name': 'Test Co',
            'business_type': 'company',
            'contact_email': 'test@test.com',
            'country': 'Bangladesh',
            'city': 'Dhaka',
        })
        assert pub.publisher_id.startswith('PUB')

    def test_create_publisher_assigns_user(self):
        user = UserFactory()
        pub = PublisherService.create_publisher(user, {
            'display_name': 'Test Co',
            'business_type': 'company',
            'contact_email': 'test@test.com',
            'country': 'Bangladesh',
            'city': 'Dhaka',
        })
        assert pub.user == user

    def test_approve_publisher_sets_status_active(self):
        admin = UserFactory(is_staff=True)
        pub   = PublisherFactory(status='pending')
        result = PublisherService.approve_publisher(pub, approved_by=admin)
        assert result.status == 'active'

    def test_approve_publisher_sets_approved_by(self):
        admin = UserFactory(is_staff=True)
        pub   = PublisherFactory(status='pending')
        result = PublisherService.approve_publisher(pub, approved_by=admin)
        assert result.approved_by == admin

    def test_suspend_publisher_sets_status_suspended(self):
        pub = PublisherFactory(status='active')
        result = PublisherService.suspend_publisher(pub, reason='Policy violation')
        assert result.status == 'suspended'

    def test_suspend_publisher_stores_reason(self):
        pub = PublisherFactory(status='active')
        result = PublisherService.suspend_publisher(pub, reason='Spam')
        assert 'Spam' in (result.suspension_reason or '')

    def test_regenerate_api_key_changes_key(self):
        pub     = PublisherFactory()
        old_key = pub.api_key
        result  = PublisherService.regenerate_api_key(pub)
        assert result.api_key != old_key

    def test_regenerate_api_key_generates_new_secret(self):
        pub        = PublisherFactory()
        old_secret = pub.api_secret
        result     = PublisherService.regenerate_api_key(pub)
        assert result.api_secret != old_secret

    def test_get_dashboard_stats_returns_dict(self):
        pub   = PublisherFactory(status='active')
        stats = PublisherService.get_publisher_dashboard_stats(pub, 'last_30_days')
        assert isinstance(stats, dict)

    def test_get_dashboard_stats_has_expected_keys(self):
        pub   = PublisherFactory(status='active')
        stats = PublisherService.get_publisher_dashboard_stats(pub, 'last_30_days')
        for key in ('total_revenue', 'total_impressions', 'active_sites', 'active_apps'):
            assert key in stats


# ==============================================================================
# SiteService
# ==============================================================================

@pytest.mark.django_db
class TestSiteService:

    def test_register_site_generates_site_id(self):
        pub  = PublisherFactory(status='active')
        site = SiteService.register_site(pub, {
            'name': 'Test Site',
            'domain': 'testsite.com',
            'url': 'https://testsite.com',
            'category': 'news',
        })
        assert site.site_id.startswith('SITE')

    def test_register_site_assigns_publisher(self):
        pub  = PublisherFactory(status='active')
        site = SiteService.register_site(pub, {
            'name': 'Test', 'domain': 'test.com',
            'url': 'https://test.com', 'category': 'news',
        })
        assert site.publisher == pub

    def test_register_site_sets_pending_status(self):
        pub  = PublisherFactory(status='active')
        site = SiteService.register_site(pub, {
            'name': 'Test', 'domain': 'test.com',
            'url': 'https://test.com', 'category': 'news',
        })
        assert site.status == 'pending'

    def test_approve_site_sets_status_active(self):
        admin = UserFactory(is_staff=True)
        site  = SiteFactory(status='pending')
        result = SiteService.approve_site(site, approved_by=admin)
        assert result.status == 'active'

    def test_reject_site_sets_status_rejected(self):
        site   = SiteFactory(status='pending')
        result = SiteService.reject_site(site, reason='Spam site')
        assert result.status == 'rejected'

    def test_get_site_analytics_returns_dict(self):
        site   = SiteFactory(status='active')
        result = SiteService.get_site_analytics(
            site,
            date.today() - timedelta(days=30),
            date.today(),
        )
        assert isinstance(result, dict)


# ==============================================================================
# AppService
# ==============================================================================

@pytest.mark.django_db
class TestAppService:

    def test_register_app_generates_app_id(self):
        pub = PublisherFactory(status='active')
        app = AppService.register_app(pub, {
            'name': 'TestApp',
            'platform': 'android',
            'package_name': 'com.test.app',
            'category': 'games',
        })
        assert app.app_id.startswith('APP')

    def test_approve_app_sets_status_active(self):
        admin = UserFactory(is_staff=True)
        app   = AppFactory(status='pending')
        result = AppService.approve_app(app, approved_by=admin)
        assert result.status == 'active'

    def test_reject_app_sets_status_rejected(self):
        app    = AppFactory(status='pending')
        result = AppService.reject_app(app, reason='Policy violation')
        assert result.status == 'rejected'


# ==============================================================================
# AdUnitService
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitService:

    def test_create_ad_unit_generates_unit_id(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        unit = AdUnitService.create_ad_unit(pub, {
            'name': 'Banner 300x250',
            'format': 'banner',
            'inventory_type': 'web',
            'floor_price': Decimal('0.50'),
            'site': site,
        })
        assert unit.unit_id is not None

    def test_create_ad_unit_generates_tag_code(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub, status='active')
        unit = AdUnitService.create_ad_unit(pub, {
            'name': 'Banner 300x250',
            'format': 'banner',
            'inventory_type': 'web',
            'floor_price': Decimal('0.50'),
            'site': site,
        })
        assert unit.tag_code is not None
        assert len(unit.tag_code) > 10

    def test_pause_ad_unit_sets_paused_status(self):
        unit   = AdUnitFactory(status='active')
        result = AdUnitService.pause_ad_unit(unit)
        assert result.status == 'paused'

    def test_activate_ad_unit_sets_active_status(self):
        unit   = AdUnitFactory(status='paused')
        result = AdUnitService.activate_ad_unit(unit)
        assert result.status == 'active'


# ==============================================================================
# MediationService
# ==============================================================================

@pytest.mark.django_db
class TestMediationService:

    def test_create_mediation_group_returns_group(self):
        unit  = AdUnitFactory()
        group = MediationService.create_mediation_group(unit, {
            'name': 'Test Group',
            'strategy': 'waterfall',
            'floor_price': Decimal('0.25'),
        })
        assert group.ad_unit == unit

    def test_add_waterfall_item_increases_count(self):
        group = MediationGroupFactory()
        MediationService.add_waterfall_item(group, {
            'mediation_group': group,
            'network_name': 'AdMob',
            'priority': 1,
            'floor_price': Decimal('0.10'),
            'timeout_ms': 3000,
        })
        from publisher_tools.models import WaterfallItem
        count = WaterfallItem.objects.filter(mediation_group=group).count()
        assert count == 1

    def test_get_active_waterfall_returns_active_only(self):
        group = MediationGroupFactory()
        WaterfallItemFactory(mediation_group=group, priority=1, status='active')
        WaterfallItemFactory(mediation_group=group, priority=2, status='paused')
        items = MediationService.get_active_waterfall(group)
        assert all(item.status == 'active' for item in items)

    def test_get_active_waterfall_ordered_by_priority(self):
        group = MediationGroupFactory()
        WaterfallItemFactory(mediation_group=group, priority=3, status='active')
        WaterfallItemFactory(mediation_group=group, priority=1, status='active')
        WaterfallItemFactory(mediation_group=group, priority=2, status='active')
        items = MediationService.get_active_waterfall(group)
        priorities = [i.priority for i in items]
        assert priorities == sorted(priorities)

    def test_reorder_waterfall_assigns_new_priorities(self):
        group = MediationGroupFactory()
        w1 = WaterfallItemFactory(mediation_group=group, priority=1)
        w2 = WaterfallItemFactory(mediation_group=group, priority=2)
        MediationService.reorder_waterfall(group, [str(w2.pk), str(w1.pk)])
        w1.refresh_from_db()
        w2.refresh_from_db()
        assert w2.priority < w1.priority

    def test_optimize_waterfall_returns_group(self):
        group = MediationGroupFactory()
        WaterfallItemFactory(mediation_group=group, avg_ecpm=Decimal('2.00'))
        WaterfallItemFactory(mediation_group=group, avg_ecpm=Decimal('1.00'))
        result = MediationService.optimize_waterfall(group)
        assert result == group


# ==============================================================================
# EarningService
# ==============================================================================

@pytest.mark.django_db
class TestEarningService:

    def test_get_earnings_report_returns_dict(self):
        pub  = PublisherFactory(status='active')
        site = SiteFactory(publisher=pub)
        unit = AdUnitFactory(publisher=pub, site=site)
        PublisherEarningFactory(publisher=pub, site=site, ad_unit=unit)
        report = EarningService.get_earnings_report(
            pub,
            date.today() - timedelta(days=30),
            date.today(),
        )
        assert isinstance(report, dict)

    def test_get_earnings_report_has_revenue_key(self):
        pub    = PublisherFactory(status='active')
        report = EarningService.get_earnings_report(
            pub,
            date.today() - timedelta(days=30),
            date.today(),
        )
        assert 'total_revenue' in report or 'revenue' in report


# ==============================================================================
# InvoiceService
# ==============================================================================

@pytest.mark.django_db
class TestInvoiceService:

    def test_check_payout_eligibility_returns_dict(self):
        pub    = PublisherFactory(status='active')
        result = InvoiceService.check_payout_eligibility(pub)
        assert isinstance(result, dict)

    def test_check_payout_eligibility_has_eligible_key(self):
        pub    = PublisherFactory(status='active')
        result = InvoiceService.check_payout_eligibility(pub)
        assert 'eligible' in result

    def test_generate_monthly_invoice_returns_invoice(self):
        pub     = PublisherFactory(status='active')
        invoice = InvoiceService.generate_monthly_invoice(pub, 2025, 1)
        from publisher_tools.models import PublisherInvoice
        assert isinstance(invoice, PublisherInvoice)

    def test_generate_monthly_invoice_status_is_draft(self):
        pub     = PublisherFactory(status='active')
        invoice = InvoiceService.generate_monthly_invoice(pub, 2025, 1)
        assert invoice.status == 'draft'

    def test_issue_invoice_changes_status_to_issued(self):
        admin   = UserFactory(is_staff=True)
        invoice = PublisherInvoiceFactory(status='draft')
        result  = InvoiceService.issue_invoice(invoice, issued_by=admin)
        assert result.status == 'issued'

    def test_mark_as_paid_changes_status_to_paid(self):
        admin   = UserFactory(is_staff=True)
        invoice = PublisherInvoiceFactory(status='issued')
        result  = InvoiceService.mark_as_paid(invoice, 'TXN-001', processed_by=admin)
        assert result.status == 'paid'

    def test_mark_as_paid_stores_reference(self):
        admin   = UserFactory(is_staff=True)
        invoice = PublisherInvoiceFactory(status='issued')
        result  = InvoiceService.mark_as_paid(invoice, 'TXN-UNIQUE-REF', processed_by=admin)
        assert 'TXN-UNIQUE-REF' in (result.payment_reference or '')


# ==============================================================================
# FraudDetectionService
# ==============================================================================

@pytest.mark.django_db
class TestFraudDetectionService:

    def test_take_action_updates_action_taken_field(self):
        admin = UserFactory(is_staff=True)
        log   = TrafficSafetyLogFactory(action_taken='flagged')
        result = FraudDetectionService.take_action(
            log, 'block_ip', taken_by=admin, notes='Confirmed bot traffic.'
        )
        assert result.action_taken == 'block_ip'

    def test_take_action_sets_action_taken_by(self):
        admin = UserFactory(is_staff=True)
        log   = TrafficSafetyLogFactory()
        result = FraudDetectionService.take_action(log, 'deduct_revenue', taken_by=admin)
        assert result.action_taken_by == admin

    def test_take_action_stores_notes(self):
        admin = UserFactory(is_staff=True)
        log   = TrafficSafetyLogFactory()
        result = FraudDetectionService.take_action(
            log, 'block_ip', taken_by=admin, notes='Automated detection.'
        )
        assert 'Automated detection.' in (result.notes or '')


# ==============================================================================
# QualityMetricService
# ==============================================================================

@pytest.mark.django_db
class TestQualityMetricService:

    def test_get_quality_trend_returns_list(self):
        site = SiteFactory(status='active')
        for i in range(5):
            SiteQualityMetricFactory(
                site=site,
                date=date.today() - timedelta(days=i),
                overall_quality_score=80 - i,
            )
        trend = QualityMetricService.get_quality_trend(site, days=30)
        assert isinstance(trend, list)

    def test_get_quality_trend_empty_for_new_site(self):
        site  = SiteFactory(status='active')
        trend = QualityMetricService.get_quality_trend(site, days=30)
        assert isinstance(trend, list)
        assert len(trend) == 0

    def test_get_quality_trend_respects_days_param(self):
        site = SiteFactory(status='active')
        # Create one inside range, one outside
        SiteQualityMetricFactory(
            site=site, date=date.today() - timedelta(days=5)
        )
        SiteQualityMetricFactory(
            site=site, date=date.today() - timedelta(days=60)
        )
        trend = QualityMetricService.get_quality_trend(site, days=30)
        assert len(trend) == 1

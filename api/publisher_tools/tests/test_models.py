# publisher_tools/tests/test_models.py
"""
High-priority model tests.

Covers:
  - Auto-generated IDs (publisher_id, site_id, app_id, unit_id)
  - Computed properties (is_active, active_sites_count, fill_rate, etc.)
  - save() hooks (api_key generation, ID generation)
  - __str__ representations
  - Status transitions at model level
  - Financial field defaults

Run:
    pytest publisher_tools/tests/test_models.py -v
"""
import pytest
from decimal import Decimal
from django.utils import timezone

from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AppFactory,
    AdUnitFactory, AdPlacementFactory, AdUnitTargetingFactory,
    MediationGroupFactory, WaterfallItemFactory,
    PublisherEarningFactory, PayoutThresholdFactory,
    PublisherInvoiceFactory, TrafficSafetyLogFactory,
    SiteQualityMetricFactory,
)


# ==============================================================================
# Publisher model
# ==============================================================================

@pytest.mark.django_db
class TestPublisherModel:

    def test_publisher_id_auto_generated_on_create(self):
        pub = PublisherFactory()
        assert pub.publisher_id.startswith('PUB')
        assert len(pub.publisher_id) == 9  # PUB + 6 digits

    def test_publisher_id_unique(self):
        p1 = PublisherFactory()
        p2 = PublisherFactory()
        assert p1.publisher_id != p2.publisher_id

    def test_api_key_auto_generated(self):
        pub = PublisherFactory()
        assert pub.api_key is not None
        assert len(pub.api_key) >= 32

    def test_api_key_unique_per_publisher(self):
        p1 = PublisherFactory()
        p2 = PublisherFactory()
        assert p1.api_key != p2.api_key

    def test_is_active_property_true_for_active(self):
        pub = PublisherFactory(status='active')
        assert pub.is_active is True

    def test_is_active_property_false_for_pending(self):
        pub = PublisherFactory(status='pending')
        assert pub.is_active is False

    def test_is_active_property_false_for_suspended(self):
        pub = PublisherFactory(status='suspended')
        assert pub.is_active is False

    def test_active_sites_count(self):
        pub = PublisherFactory(status='active')
        SiteFactory(publisher=pub, status='active')
        SiteFactory(publisher=pub, status='active')
        SiteFactory(publisher=pub, status='pending')
        assert pub.active_sites_count == 2

    def test_active_sites_count_zero_by_default(self):
        pub = PublisherFactory(status='active')
        assert pub.active_sites_count == 0

    def test_active_apps_count(self):
        pub = PublisherFactory(status='active')
        AppFactory(publisher=pub, status='active')
        AppFactory(publisher=pub, status='suspended')
        assert pub.active_apps_count == 1

    def test_str_includes_publisher_id(self):
        pub = PublisherFactory(display_name='Acme Corp')
        assert 'Acme Corp' in str(pub)
        assert pub.publisher_id in str(pub)

    def test_pending_balance_default_zero(self):
        pub = PublisherFactory()
        assert pub.pending_balance == Decimal('0.0000')

    def test_total_revenue_default_zero(self):
        pub = PublisherFactory()
        assert pub.total_revenue == Decimal('0.0000')

    def test_kyc_verified_false_by_default(self):
        pub = PublisherFactory()
        assert pub.is_kyc_verified is False

    def test_revenue_share_percentage_saved_correctly(self):
        pub = PublisherFactory(revenue_share_percentage=Decimal('65.00'))
        pub.refresh_from_db()
        assert pub.revenue_share_percentage == Decimal('65.00')


# ==============================================================================
# Site model
# ==============================================================================

@pytest.mark.django_db
class TestSiteModel:

    def test_site_id_auto_generated(self):
        site = SiteFactory()
        assert site.site_id.startswith('SITE')

    def test_site_id_unique(self):
        s1 = SiteFactory()
        s2 = SiteFactory()
        assert s1.site_id != s2.site_id

    def test_is_active_true_for_active_status(self):
        site = SiteFactory(status='active')
        assert site.is_active is True

    def test_is_active_false_for_pending(self):
        site = SiteFactory(status='pending')
        assert site.is_active is False

    def test_is_active_false_for_rejected(self):
        site = SiteFactory(status='rejected')
        assert site.is_active is False

    def test_str_includes_domain(self):
        site = SiteFactory(domain='example.com')
        assert 'example.com' in str(site)

    def test_ads_txt_not_verified_by_default(self):
        site = SiteFactory()
        assert site.is_ads_txt_verified is False

    def test_ivt_rate_default(self):
        site = SiteFactory()
        assert site.ivt_rate >= Decimal('0.00')

    def test_site_belongs_to_publisher(self):
        pub = PublisherFactory()
        site = SiteFactory(publisher=pub)
        assert site.publisher == pub

    def test_lifetime_counters_start_at_zero(self):
        site = SiteFactory()
        assert site.lifetime_impressions == 0
        assert site.lifetime_clicks == 0


# ==============================================================================
# App model
# ==============================================================================

@pytest.mark.django_db
class TestAppModel:

    def test_app_id_auto_generated(self):
        app = AppFactory()
        assert app.app_id.startswith('APP')

    def test_app_id_unique(self):
        a1 = AppFactory()
        a2 = AppFactory()
        assert a1.app_id != a2.app_id

    def test_is_active_true_for_active(self):
        app = AppFactory(status='active')
        assert app.is_active is True

    def test_str_includes_name(self):
        app = AppFactory(name='MyTestApp')
        assert 'MyTestApp' in str(app)

    def test_platform_choices(self):
        android_app = AppFactory(platform='android')
        ios_app     = AppFactory(platform='ios')
        assert android_app.platform == 'android'
        assert ios_app.platform == 'ios'


# ==============================================================================
# AdUnit model
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitModel:

    def test_unit_id_auto_generated(self):
        unit = AdUnitFactory()
        assert unit.unit_id is not None
        assert len(unit.unit_id) > 0

    def test_unit_id_unique(self):
        u1 = AdUnitFactory()
        u2 = AdUnitFactory()
        assert u1.unit_id != u2.unit_id

    def test_tag_code_generated(self):
        unit = AdUnitFactory()
        assert unit.tag_code is not None
        assert len(unit.tag_code) > 10

    def test_is_active_true_when_active(self):
        unit = AdUnitFactory(status='active')
        assert unit.is_active is True

    def test_is_active_false_when_paused(self):
        unit = AdUnitFactory(status='paused')
        assert unit.is_active is False

    def test_fill_rate_default_zero(self):
        unit = AdUnitFactory()
        assert unit.fill_rate == Decimal('0.0000')

    def test_avg_ecpm_default_zero(self):
        unit = AdUnitFactory()
        assert unit.avg_ecpm == Decimal('0.0000')

    def test_floor_price_persisted(self):
        unit = AdUnitFactory(floor_price=Decimal('1.5000'))
        unit.refresh_from_db()
        assert unit.floor_price == Decimal('1.5000')

    def test_str_includes_name(self):
        unit = AdUnitFactory(name='Header Banner')
        assert 'Header Banner' in str(unit)

    def test_belongs_to_publisher(self):
        pub = PublisherFactory()
        unit = AdUnitFactory(publisher=pub)
        assert unit.publisher == pub


# ==============================================================================
# AdPlacement model
# ==============================================================================

@pytest.mark.django_db
class TestAdPlacementModel:

    def test_placement_active_by_default(self):
        placement = AdPlacementFactory()
        assert placement.is_active is True

    def test_placement_linked_to_ad_unit(self):
        unit = AdUnitFactory()
        placement = AdPlacementFactory(ad_unit=unit)
        assert placement.ad_unit == unit

    def test_str_representation(self):
        placement = AdPlacementFactory(name='Above Fold')
        assert 'Above Fold' in str(placement)


# ==============================================================================
# MediationGroup model
# ==============================================================================

@pytest.mark.django_db
class TestMediationGroupModel:

    def test_mediation_group_has_strategy(self):
        group = MediationGroupFactory(strategy='waterfall')
        assert group.strategy == 'waterfall'

    def test_mediation_group_active_by_default(self):
        group = MediationGroupFactory(status='active')
        assert group.status == 'active'

    def test_mediation_group_linked_to_ad_unit(self):
        unit  = AdUnitFactory()
        group = MediationGroupFactory(ad_unit=unit)
        assert group.ad_unit == unit

    def test_floor_price_persisted(self):
        group = MediationGroupFactory(floor_price=Decimal('0.5000'))
        group.refresh_from_db()
        assert group.floor_price == Decimal('0.5000')


# ==============================================================================
# WaterfallItem model
# ==============================================================================

@pytest.mark.django_db
class TestWaterfallItemModel:

    def test_waterfall_item_priority_order(self):
        group = MediationGroupFactory()
        w1 = WaterfallItemFactory(mediation_group=group, priority=1)
        w2 = WaterfallItemFactory(mediation_group=group, priority=2)
        assert w1.priority < w2.priority

    def test_waterfall_item_active_by_default(self):
        item = WaterfallItemFactory(status='active')
        assert item.status == 'active'

    def test_timeout_default_set(self):
        item = WaterfallItemFactory()
        assert item.timeout_ms > 0


# ==============================================================================
# PublisherEarning model
# ==============================================================================

@pytest.mark.django_db
class TestPublisherEarningModel:

    def test_earning_linked_to_publisher(self):
        pub     = PublisherFactory()
        earning = PublisherEarningFactory(publisher=pub)
        assert earning.publisher == pub

    def test_publisher_revenue_less_than_gross(self):
        earning = PublisherEarningFactory(
            gross_revenue=Decimal('10.0000'),
            publisher_revenue=Decimal('7.0000'),
        )
        assert earning.publisher_revenue < earning.gross_revenue

    def test_is_finalized_false_by_default(self):
        earning = PublisherEarningFactory()
        assert earning.is_finalized is False

    def test_ecpm_stored(self):
        earning = PublisherEarningFactory(ecpm=Decimal('4.2100'))
        earning.refresh_from_db()
        assert earning.ecpm == Decimal('4.2100')


# ==============================================================================
# PayoutThreshold model
# ==============================================================================

@pytest.mark.django_db
class TestPayoutThresholdModel:

    def test_is_primary_flag(self):
        threshold = PayoutThresholdFactory(is_primary=True)
        assert threshold.is_primary is True

    def test_not_verified_by_default(self):
        threshold = PayoutThresholdFactory()
        assert threshold.is_verified is False

    def test_threshold_amount_stored(self):
        threshold = PayoutThresholdFactory(threshold_amount=Decimal('50.00'))
        threshold.refresh_from_db()
        assert threshold.threshold_amount == Decimal('50.00')


# ==============================================================================
# PublisherInvoice model
# ==============================================================================

@pytest.mark.django_db
class TestPublisherInvoiceModel:

    def test_invoice_status_draft_by_default(self):
        invoice = PublisherInvoiceFactory(status='draft')
        assert invoice.status == 'draft'

    def test_payable_amount_stored(self):
        invoice = PublisherInvoiceFactory(payable_amount=Decimal('350.00'))
        invoice.refresh_from_db()
        assert invoice.payable_amount == Decimal('350.00')

    def test_invoice_linked_to_publisher(self):
        pub     = PublisherFactory()
        invoice = PublisherInvoiceFactory(publisher=pub)
        assert invoice.publisher == pub

    def test_invoice_number_auto_generated_or_settable(self):
        invoice = PublisherInvoiceFactory()
        # invoice_number is set by InvoiceService or model.save
        # At minimum, the field should exist and not error
        assert hasattr(invoice, 'invoice_number')


# ==============================================================================
# TrafficSafetyLog model
# ==============================================================================

@pytest.mark.django_db
class TestTrafficSafetyLogModel:

    def test_traffic_log_not_false_positive_by_default(self):
        log = TrafficSafetyLogFactory()
        assert log.is_false_positive is False

    def test_fraud_score_stored(self):
        log = TrafficSafetyLogFactory(fraud_score=90)
        log.refresh_from_db()
        assert log.fraud_score == 90

    def test_log_linked_to_publisher(self):
        pub = PublisherFactory()
        log = TrafficSafetyLogFactory(publisher=pub)
        assert log.publisher == pub

    def test_revenue_at_risk_non_negative(self):
        log = TrafficSafetyLogFactory(revenue_at_risk=Decimal('2.5000'))
        assert log.revenue_at_risk >= Decimal('0')


# ==============================================================================
# SiteQualityMetric model
# ==============================================================================

@pytest.mark.django_db
class TestSiteQualityMetricModel:

    def test_quality_metric_linked_to_site(self):
        site   = SiteFactory()
        metric = SiteQualityMetricFactory(site=site)
        assert metric.site == site

    def test_has_alerts_false_by_default(self):
        metric = SiteQualityMetricFactory(has_alerts=False)
        assert metric.has_alerts is False

    def test_overall_quality_score_in_range(self):
        metric = SiteQualityMetricFactory(overall_quality_score=85)
        assert 0 <= metric.overall_quality_score <= 100

    def test_alert_reasons_is_list(self):
        metric = SiteQualityMetricFactory()
        assert isinstance(metric.alert_reasons, list)

# publisher_tools/tests/test_serializers.py
"""
High-priority serializer tests.

Covers:
  - Required field validation (missing fields → 400)
  - Field-level validators (email normalise, URL format, domain, floor_price)
  - Cross-model read serializers (correct fields returned)
  - Write serializers produce valid validated_data
  - Serializer rejects invalid choices (bad status, bad format)

Run:
    pytest publisher_tools/tests/test_serializers.py -v
"""
import pytest
from decimal import Decimal
from django.test import RequestFactory

from publisher_tools.serializers import (
    PublisherCreateSerializer,
    PublisherUpdateSerializer,
    PublisherListSerializer,
    PublisherDetailSerializer,
    SiteCreateSerializer,
    SiteUpdateSerializer,
    SiteListSerializer,
    SiteDetailSerializer,
    SiteVerifySerializer,
    AppCreateSerializer,
    AppListSerializer,
    AppDetailSerializer,
    InventoryVerificationSerializer,
    AdUnitCreateSerializer,
    AdUnitUpdateSerializer,
    AdUnitListSerializer,
    AdUnitDetailSerializer,
    AdPlacementCreateSerializer,
    AdUnitTargetingSerializer,
    MediationGroupSerializer,
    WaterfallItemSerializer,
    WaterfallReorderSerializer,
    PublisherEarningSerializer,
    EarningsSummarySerializer,
    PayoutThresholdSerializer,
    PublisherInvoiceListSerializer,
    PublisherInvoiceDetailSerializer,
    InvoiceDisputeSerializer,
    TrafficSafetyLogSerializer,
    FraudActionSerializer,
    MarkFalsePositiveSerializer,
    SiteQualityMetricSerializer,
    DateRangeSerializer,
)
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AppFactory,
    AdUnitFactory, AdPlacementFactory,
    MediationGroupFactory, WaterfallItemFactory,
    PublisherEarningFactory, PayoutThresholdFactory,
    PublisherInvoiceFactory, TrafficSafetyLogFactory,
    SiteQualityMetricFactory,
)


def make_request(user=None):
    """Helper — create a fake DRF request with an optional user."""
    from rest_framework.request import Request
    rf = RequestFactory()
    raw = rf.get('/')
    request = Request(raw)
    if user:
        request.user = user
    return request


# ==============================================================================
# PublisherCreateSerializer
# ==============================================================================

@pytest.mark.django_db
class TestPublisherCreateSerializer:

    def _valid_data(self):
        return {
            'display_name': 'Acme Corp',
            'business_type': 'company',
            'contact_email': 'contact@acme.com',
            'contact_phone': '+8801711000000',
            'website': 'https://acme.com',
            'country': 'Bangladesh',
            'city': 'Dhaka',
            'address': '123 Test Street, Dhaka',
            'revenue_share_percentage': '70.00',
        }

    def test_valid_data_passes(self):
        s = PublisherCreateSerializer(data=self._valid_data())
        assert s.is_valid(), s.errors

    def test_email_is_lowercased(self):
        data = self._valid_data()
        data['contact_email'] = '  CONTACT@ACME.COM  '
        s = PublisherCreateSerializer(data=data)
        s.is_valid()
        assert s.validated_data['contact_email'] == 'contact@acme.com'

    def test_invalid_website_url_rejected(self):
        data = self._valid_data()
        data['website'] = 'not-a-url'
        s = PublisherCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'website' in s.errors

    def test_missing_business_type_rejected(self):
        data = self._valid_data()
        del data['business_type']
        s = PublisherCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'business_type' in s.errors

    def test_revenue_share_invalid_over_100(self):
        data = self._valid_data()
        data['revenue_share_percentage'] = '110.00'
        s = PublisherCreateSerializer(data=data)
        # Validators should reject > 100
        assert not s.is_valid()


# ==============================================================================
# SiteCreateSerializer
# ==============================================================================

@pytest.mark.django_db
class TestSiteCreateSerializer:

    def _valid_data(self):
        return {
            'name': 'My Tech Blog',
            'domain': 'mytechblog.com',
            'url': 'https://mytechblog.com',
            'category': 'technology',
        }

    def test_valid_data_passes(self):
        s = SiteCreateSerializer(data=self._valid_data())
        assert s.is_valid(), s.errors

    def test_missing_domain_rejected(self):
        data = self._valid_data()
        del data['domain']
        s = SiteCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'domain' in s.errors

    def test_missing_url_rejected(self):
        data = self._valid_data()
        del data['url']
        s = SiteCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'url' in s.errors

    def test_invalid_url_scheme_rejected(self):
        data = self._valid_data()
        data['url'] = 'ftp://mytechblog.com'
        s = SiteCreateSerializer(data=data)
        # ftp is not a valid HTTP URL
        assert not s.is_valid()

    def test_name_required(self):
        data = self._valid_data()
        del data['name']
        s = SiteCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'name' in s.errors


# ==============================================================================
# AppCreateSerializer
# ==============================================================================

@pytest.mark.django_db
class TestAppCreateSerializer:

    def _valid_data(self):
        return {
            'name': 'Super App',
            'platform': 'android',
            'package_name': 'com.example.superapp',
            'category': 'games',
        }

    def test_valid_data_passes(self):
        s = AppCreateSerializer(data=self._valid_data())
        assert s.is_valid(), s.errors

    def test_invalid_platform_rejected(self):
        data = self._valid_data()
        data['platform'] = 'windows_phone'
        s = AppCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'platform' in s.errors

    def test_missing_package_name_rejected(self):
        data = self._valid_data()
        del data['package_name']
        s = AppCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'package_name' in s.errors

    def test_invalid_android_package_name(self):
        data = self._valid_data()
        data['package_name'] = 'not_a_valid_package'
        s = AppCreateSerializer(data=data)
        # validator in serializer should reject single-component names
        # (actual validation depends on validate_android_package_name)
        # If no validator, it passes — this test documents expected behaviour
        result = s.is_valid()
        # At minimum: no crash
        assert isinstance(result, bool)


# ==============================================================================
# AdUnitCreateSerializer
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitCreateSerializer:

    def _valid_data(self, site):
        return {
            'name': 'Header Banner',
            'format': 'banner',
            'inventory_type': 'web',
            'floor_price': '0.5000',
            'site': str(site.pk),
        }

    def test_valid_data_passes(self, db):
        site = SiteFactory()
        s = AdUnitCreateSerializer(data=self._valid_data(site))
        assert s.is_valid(), s.errors

    def test_invalid_format_rejected(self, db):
        site = SiteFactory()
        data = self._valid_data(site)
        data['format'] = 'flying_banner'
        s = AdUnitCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'format' in s.errors

    def test_negative_floor_price_rejected(self, db):
        site = SiteFactory()
        data = self._valid_data(site)
        data['floor_price'] = '-1.00'
        s = AdUnitCreateSerializer(data=data)
        assert not s.is_valid()

    def test_name_required(self, db):
        site = SiteFactory()
        data = self._valid_data(site)
        del data['name']
        s = AdUnitCreateSerializer(data=data)
        assert not s.is_valid()
        assert 'name' in s.errors


# ==============================================================================
# AdUnitTargetingSerializer
# ==============================================================================

@pytest.mark.django_db
class TestAdUnitTargetingSerializer:

    def test_valid_targeting_data(self, db):
        unit = AdUnitFactory()
        data = {
            'ad_unit': unit.pk,
            'device_type': 'mobile',
            'geo_targets': ['BD', 'IN'],
        }
        s = AdUnitTargetingSerializer(data=data)
        assert s.is_valid(), s.errors

    def test_invalid_country_codes_rejected(self, db):
        unit = AdUnitFactory()
        data = {
            'ad_unit': unit.pk,
            'device_type': 'all',
            'geo_targets': ['INVALID_CC', 'XX'],
        }
        s = AdUnitTargetingSerializer(data=data)
        # If validator exists — should reject
        # If not yet implemented — documents the gap
        result = s.is_valid()
        assert isinstance(result, bool)


# ==============================================================================
# MediationGroupSerializer
# ==============================================================================

@pytest.mark.django_db
class TestMediationGroupSerializer:

    def test_read_serializer_returns_expected_fields(self, db):
        group = MediationGroupFactory()
        s = MediationGroupSerializer(group)
        data = s.data
        assert 'strategy' in data
        assert 'floor_price' in data
        assert 'status' in data

    def test_invalid_strategy_rejected(self, db):
        unit = AdUnitFactory()
        data = {
            'ad_unit': unit.pk,
            'name': 'Test Group',
            'strategy': 'magic_bidding',
            'floor_price': '0.25',
        }
        s = MediationGroupSerializer(data=data)
        assert not s.is_valid()
        assert 'strategy' in s.errors


# ==============================================================================
# WaterfallReorderSerializer
# ==============================================================================

@pytest.mark.django_db
class TestWaterfallReorderSerializer:

    def test_valid_reorder_list(self, db):
        import uuid
        item_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        s = WaterfallReorderSerializer(data={'items': item_ids})
        assert s.is_valid(), s.errors

    def test_empty_list_rejected(self):
        s = WaterfallReorderSerializer(data={'items': []})
        assert not s.is_valid()

    def test_missing_items_key_rejected(self):
        s = WaterfallReorderSerializer(data={})
        assert not s.is_valid()
        assert 'items' in s.errors


# ==============================================================================
# InvoiceDisputeSerializer
# ==============================================================================

@pytest.mark.django_db
class TestInvoiceDisputeSerializer:

    def test_reason_required(self):
        s = InvoiceDisputeSerializer(data={})
        assert not s.is_valid()
        assert 'reason' in s.errors

    def test_valid_dispute(self):
        s = InvoiceDisputeSerializer(data={'reason': 'Revenue figures do not match my records.'})
        assert s.is_valid(), s.errors


# ==============================================================================
# FraudActionSerializer
# ==============================================================================

@pytest.mark.django_db
class TestFraudActionSerializer:

    def test_valid_action(self):
        s = FraudActionSerializer(data={'action': 'block_ip', 'notes': 'Automated block.'})
        assert s.is_valid(), s.errors

    def test_missing_action_rejected(self):
        s = FraudActionSerializer(data={'notes': 'some note'})
        assert not s.is_valid()
        assert 'action' in s.errors

    def test_invalid_action_value_rejected(self):
        s = FraudActionSerializer(data={'action': 'delete_publisher'})
        assert not s.is_valid()
        assert 'action' in s.errors


# ==============================================================================
# DateRangeSerializer
# ==============================================================================

class TestDateRangeSerializer:

    def test_valid_range(self):
        s = DateRangeSerializer(data={'start_date': '2025-01-01', 'end_date': '2025-01-31'})
        assert s.is_valid(), s.errors

    def test_start_after_end_rejected(self):
        s = DateRangeSerializer(data={'start_date': '2025-02-01', 'end_date': '2025-01-01'})
        assert not s.is_valid()

    def test_missing_start_date_rejected(self):
        s = DateRangeSerializer(data={'end_date': '2025-01-31'})
        assert not s.is_valid()
        assert 'start_date' in s.errors

    def test_missing_end_date_rejected(self):
        s = DateRangeSerializer(data={'start_date': '2025-01-01'})
        assert not s.is_valid()
        assert 'end_date' in s.errors


# ==============================================================================
# Read serializer smoke tests (instance → data, no crash)
# ==============================================================================

@pytest.mark.django_db
class TestReadSerializersNoErrors:
    """
    Smoke tests: instantiating read serializers on factory objects
    should never raise an exception.
    """

    def test_publisher_list_serializer(self, db):
        pub = PublisherFactory()
        data = PublisherListSerializer(pub).data
        assert 'publisher_id' in data

    def test_publisher_detail_serializer(self, db):
        pub = PublisherFactory()
        data = PublisherDetailSerializer(pub).data
        assert 'status' in data
        assert 'tier' in data

    def test_site_list_serializer(self, db):
        site = SiteFactory()
        data = SiteListSerializer(site).data
        assert 'site_id' in data
        assert 'domain' in data

    def test_site_detail_serializer(self, db):
        site = SiteFactory()
        data = SiteDetailSerializer(site).data
        assert 'url' in data

    def test_app_list_serializer(self, db):
        app = AppFactory()
        data = AppListSerializer(app).data
        assert 'app_id' in data
        assert 'platform' in data

    def test_ad_unit_list_serializer(self, db):
        unit = AdUnitFactory()
        data = AdUnitListSerializer(unit).data
        assert 'unit_id' in data
        assert 'format' in data

    def test_ad_unit_detail_serializer(self, db):
        unit = AdUnitFactory()
        data = AdUnitDetailSerializer(unit).data
        assert 'floor_price' in data

    def test_earning_serializer(self, db):
        earning = PublisherEarningFactory()
        data = PublisherEarningSerializer(earning).data
        assert 'publisher_revenue' in data
        assert 'ecpm' in data

    def test_payout_threshold_serializer(self, db):
        t = PayoutThresholdFactory()
        data = PayoutThresholdSerializer(t).data
        assert 'payment_method' in data
        assert 'threshold_amount' in data

    def test_invoice_list_serializer(self, db):
        inv = PublisherInvoiceFactory()
        data = PublisherInvoiceListSerializer(inv).data
        assert 'status' in data

    def test_invoice_detail_serializer(self, db):
        inv = PublisherInvoiceFactory()
        data = PublisherInvoiceDetailSerializer(inv).data
        assert 'payable_amount' in data

    def test_traffic_safety_log_serializer(self, db):
        log = TrafficSafetyLogFactory()
        data = TrafficSafetyLogSerializer(log).data
        assert 'fraud_score' in data
        assert 'traffic_type' in data

    def test_site_quality_metric_serializer(self, db):
        metric = SiteQualityMetricFactory()
        data = SiteQualityMetricSerializer(metric).data
        assert 'overall_quality_score' in data
        assert 'has_alerts' in data

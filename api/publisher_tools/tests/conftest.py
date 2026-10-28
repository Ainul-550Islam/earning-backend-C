# publisher_tools/tests/conftest.py
"""
Shared pytest fixtures for publisher_tools test suite.

Usage:
    pytest publisher_tools/tests/ -v
    pytest publisher_tools/tests/ -v -k "test_publisher"
    pytest publisher_tools/tests/ --cov=publisher_tools --cov-report=term-missing
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


# ─── User fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    """Staff/admin user — bypasses all publisher permission checks."""
    return User.objects.create_user(
        username='admin_test',
        email='admin@test.com',
        password='adminpass123',
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def regular_user(db):
    """Plain authenticated user — no publisher profile attached."""
    return User.objects.create_user(
        username='user_test',
        email='user@test.com',
        password='userpass123',
    )


@pytest.fixture
def publisher_user(db):
    """User with an active Publisher profile (standard tier)."""
    user = User.objects.create_user(
        username='publisher_test',
        email='publisher@test.com',
        password='pubpass123',
    )
    return user


@pytest.fixture
def publisher_user_2(db):
    """Second publisher user — used for ownership isolation tests."""
    return User.objects.create_user(
        username='publisher_test_2',
        email='publisher2@test.com',
        password='pubpass456',
    )


# ─── Publisher model fixtures ─────────────────────────────────────────────────

@pytest.fixture
def publisher(db, publisher_user):
    """Active Publisher linked to publisher_user."""
    from publisher_tools.tests.factories import PublisherFactory
    return PublisherFactory(user=publisher_user, status='active')


@pytest.fixture
def pending_publisher(db, regular_user):
    """Pending (unapproved) Publisher."""
    from publisher_tools.tests.factories import PublisherFactory
    return PublisherFactory(user=regular_user, status='pending')


@pytest.fixture
def suspended_publisher(db, publisher_user):
    """Suspended publisher."""
    from publisher_tools.tests.factories import PublisherFactory
    return PublisherFactory(user=publisher_user, status='suspended')


@pytest.fixture
def premium_publisher(db, publisher_user):
    """Premium-tier active publisher."""
    from publisher_tools.tests.factories import PublisherFactory
    return PublisherFactory(user=publisher_user, status='active', tier='premium')


# ─── Inventory fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def site(db, publisher):
    """Active verified site for publisher."""
    from publisher_tools.tests.factories import SiteFactory
    return SiteFactory(publisher=publisher, status='active')


@pytest.fixture
def pending_site(db, publisher):
    """Pending (unverified) site."""
    from publisher_tools.tests.factories import SiteFactory
    return SiteFactory(publisher=publisher, status='pending')


@pytest.fixture
def app(db, publisher):
    """Active App for publisher."""
    from publisher_tools.tests.factories import AppFactory
    return AppFactory(publisher=publisher, status='active')


@pytest.fixture
def ad_unit(db, publisher, site):
    """Active AdUnit for publisher/site."""
    from publisher_tools.tests.factories import AdUnitFactory
    return AdUnitFactory(publisher=publisher, site=site, status='active')


@pytest.fixture
def paused_ad_unit(db, publisher, site):
    """Paused AdUnit."""
    from publisher_tools.tests.factories import AdUnitFactory
    return AdUnitFactory(publisher=publisher, site=site, status='paused')


@pytest.fixture
def ad_placement(db, ad_unit):
    from publisher_tools.tests.factories import AdPlacementFactory
    return AdPlacementFactory(ad_unit=ad_unit)


@pytest.fixture
def mediation_group(db, ad_unit):
    from publisher_tools.tests.factories import MediationGroupFactory
    return MediationGroupFactory(ad_unit=ad_unit)


@pytest.fixture
def waterfall_item(db, mediation_group):
    from publisher_tools.tests.factories import WaterfallItemFactory
    return WaterfallItemFactory(mediation_group=mediation_group, priority=1)


# ─── Financial fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def earning(db, publisher, ad_unit, site):
    from publisher_tools.tests.factories import PublisherEarningFactory
    return PublisherEarningFactory(publisher=publisher, ad_unit=ad_unit, site=site)


@pytest.fixture
def payout_threshold(db, publisher):
    from publisher_tools.tests.factories import PayoutThresholdFactory
    return PayoutThresholdFactory(publisher=publisher)


@pytest.fixture
def invoice(db, publisher):
    from publisher_tools.tests.factories import PublisherInvoiceFactory
    return PublisherInvoiceFactory(publisher=publisher, status='draft')


@pytest.fixture
def issued_invoice(db, publisher):
    from publisher_tools.tests.factories import PublisherInvoiceFactory
    return PublisherInvoiceFactory(publisher=publisher, status='issued')


# ─── Fraud/quality fixtures ───────────────────────────────────────────────────

@pytest.fixture
def traffic_log(db, publisher, site):
    from publisher_tools.tests.factories import TrafficSafetyLogFactory
    return TrafficSafetyLogFactory(publisher=publisher, site=site)


@pytest.fixture
def quality_metric(db, site):
    from publisher_tools.tests.factories import SiteQualityMetricFactory
    return SiteQualityMetricFactory(site=site)


# ─── API client fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    """Unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def admin_client(admin_user):
    """DRF client authenticated as admin."""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def publisher_client(publisher_user, publisher):
    """DRF client authenticated as active publisher."""
    client = APIClient()
    client.force_authenticate(user=publisher_user)
    return client


@pytest.fixture
def publisher_client_2(publisher_user_2):
    """DRF client for second publisher — used for ownership isolation."""
    from publisher_tools.tests.factories import PublisherFactory
    PublisherFactory(user=publisher_user_2, status='active')
    client = APIClient()
    client.force_authenticate(user=publisher_user_2)
    return client


@pytest.fixture
def unauthenticated_client():
    return APIClient()

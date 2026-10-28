"""
api/offerwall/conftest.py

Pytest configuration and fixtures for offerwall tests.
Provides reusable fixtures for:
  - Users (regular, admin, provider)
  - Offers (various types)
  - Providers (various networks)
  - Conversions (various statuses)
  - API client
  - Webhook payloads
"""

import pytest
import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from datetime import datetime, timedelta

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# USER FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    """DRF API test client"""
    return APIClient()


@pytest.fixture
def user(db):
    """Regular authenticated user"""
    return User.objects.create_user(
        username='testuser',
        email='testuser@example.com',
        password='testpass123'
    )


@pytest.fixture
def admin_user(db):
    """Admin/staff user"""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def provider_user(db):
    """User with provider role"""
    user = User.objects.create_user(
        username='provider_user',
        email='provider@example.com',
        password='providerpass123'
    )
    # Add to provider group if it exists
    try:
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name='offer_providers')
        user.groups.add(group)
    except:
        pass
    return user


@pytest.fixture
def approver_user(db):
    """User with conversion approver role"""
    user = User.objects.create_user(
        username='approver',
        email='approver@example.com',
        password='approverpass123'
    )
    # Add to approver group if it exists
    try:
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name='conversion_approvers')
        user.groups.add(group)
    except:
        pass
    return user


# ─────────────────────────────────────────────────────────────
# PROVIDER FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def tapjoy_provider(db):
    """Tapjoy provider instance"""
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name='Tapjoy',
        provider_type='tapjoy',
        status='active',
        api_key='test_tapjoy_key',
        api_secret='test_tapjoy_secret',
        app_id='test_app_id',
        publisher_id='test_pub_id',
        api_base_url='https://api.tapjoy.com',
        webhook_url='https://api.example.com/webhooks/tapjoy/',
        secret_key='tapjoy_secret_123',
        revenue_share=Decimal('70.00'),
        rate_limit_per_minute=60,
        rate_limit_per_hour=3600,
        auto_sync=True,
    )


@pytest.fixture
def adgate_provider(db):
    """AdGate Media provider instance"""
    from api.offerwall.models import OfferProvider
    return OfferProvider.objects.create(
        name='AdGate Media',
        provider_type='adgate',
        status='active',
        api_key='test_adgate_key',
        app_id='test_adgate_app',
        publisher_id='test_adgate_pub',
        api_base_url='https://api.adgate.com',
        webhook_url='https://api.example.com/webhooks/adgate/',
        secret_key='adgate_secret_123',
        revenue_share=Decimal('75.00'),
    )


@pytest.fixture
def provider(db, tapjoy_provider):
    """Default provider fixture (Tapjoy)"""
    return tapjoy_provider


# ─────────────────────────────────────────────────────────────
# OFFER FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def offer_category(db):
    """Sample offer category"""
    from api.offerwall.models import OfferCategory
    return OfferCategory.objects.create(
        name='Games',
        slug='games',
        description='Mobile game offers',
        is_active=True,
        display_order=1
    )


@pytest.fixture
def offer(db, provider, offer_category):
    """Sample active offer"""
    from api.offerwall.models import Offer
    return Offer.objects.create(
        provider=provider,
        category=offer_category,
        external_offer_id=uuid.uuid4().hex[:12],
        title='Download Game XYZ',
        description='Download and play Game XYZ to earn points',
        short_description='Game offer',
        offer_type='app_install',
        platform='android',
        click_url='https://play.google.com/store/apps/details?id=com.game.xyz',
        tracking_url='https://tracking.example.com/tap?oid=123',
        countries=['US', 'GB', 'CA'],
        payout=Decimal('1.50'),
        reward_amount=Decimal('1.05'),
        conversion_count=100,
        view_count=5000,
        quality_score=85,
        status='active',
        max_completions=1000,
        current_completions=250,
    )


@pytest.fixture
def survey_offer(db, provider, offer_category):
    """Sample survey offer"""
    from api.offerwall.models import Offer
    return Offer.objects.create(
        provider=provider,
        external_offer_id=uuid.uuid4().hex[:12],
        title='Consumer Survey - Quick 5 min',
        description='Help us understand consumer behavior',
        offer_type='survey',
        platform='all',
        click_url='https://surveys.example.com/s/12345',
        countries=['US', 'UK'],
        payout=Decimal('0.75'),
        reward_amount=Decimal('0.50'),
        conversion_count=500,
        view_count=8000,
        quality_score=78,
        status='active',
    )


@pytest.fixture
def expired_offer(db, provider):
    """Sample expired offer"""
    from api.offerwall.models import Offer
    from django.utils import timezone
    return Offer.objects.create(
        provider=provider,
        external_offer_id=uuid.uuid4().hex[:12],
        title='Old Offer',
        description='This offer has expired',
        offer_type='signup',
        status='expired',
        expiry_date=timezone.now() - timedelta(days=1),
        payout=Decimal('0.50'),
    )


# ─────────────────────────────────────────────────────────────
# CONVERSION FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def offer_click(db, user, offer):
    """Sample offer click"""
    from api.offerwall.models import OfferClick
    return OfferClick.objects.create(
        user=user,
        offer=offer,
        ip_address='192.168.1.1',
        user_agent='Mozilla/5.0...',
        country_code='US',
        device_type='mobile',
        os='android',
        is_converted=False,
    )


@pytest.fixture
def conversion_pending(db, user, offer, offer_click):
    """Sample pending conversion"""
    from api.offerwall.models import OfferConversion
    return OfferConversion.objects.create(
        user=user,
        offer=offer,
        click=offer_click,
        conversion_id=uuid.uuid4().hex[:12],
        external_WalletTransaction_id=uuid.uuid4().hex[:10],
        payout_amount=Decimal('1.50'),
        reward_amount=Decimal('1.05'),
        bonus_amount=Decimal('0'),
        status='pending',
        is_verified=False,
    )


@pytest.fixture
def conversion_approved(db, user, offer):
    """Sample approved conversion"""
    from api.offerwall.models import OfferConversion
    return OfferConversion.objects.create(
        user=user,
        offer=offer,
        conversion_id=uuid.uuid4().hex[:12],
        external_WalletTransaction_id=uuid.uuid4().hex[:10],
        payout_amount=Decimal('1.50'),
        reward_amount=Decimal('1.05'),
        bonus_amount=Decimal('0'),
        status='approved',
        is_verified=True,
        verified_at=datetime.now(),
    )


@pytest.fixture
def conversion_rejected(db, user, offer):
    """Sample rejected conversion"""
    from api.offerwall.models import OfferConversion
    return OfferConversion.objects.create(
        user=user,
        offer=offer,
        conversion_id=uuid.uuid4().hex[:12],
        payout_amount=Decimal('1.50'),
        reward_amount=Decimal('1.05'),
        status='rejected',
        rejection_reason='Fraudulent activity detected',
    )


# ─────────────────────────────────────────────────────────────
# WEBHOOK FIXTURES (Raw payload data)
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def tapjoy_webhook_payload():
    """Sample Tapjoy conversion webhook payload"""
    return {
        'event': 'conversion',
        'conversion_id': uuid.uuid4().hex[:12],
        'user_id': 'tap_user_123',
        'offer_id': 'tap_offer_456',
        'payout': 1.50,
        'currency': 'USD',
        'timestamp': int(datetime.now().timestamp()),
        'signature': 'test_signature_hash',
    }


@pytest.fixture
def adgate_webhook_payload():
    """Sample AdGate conversion webhook payload"""
    return {
        'event_type': 'conversion',
        'transaction_id': uuid.uuid4().hex[:12],
        'user_id': 'adg_user_789',
        'offer_id': 'adg_offer_012',
        'status': 'approved',
        'reward': 1.05,
        'currency': 'USD',
        'timestamp': datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# AUTHENTICATED CLIENT FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def authenticated_client(api_client, user):
    """API client authenticated as regular user"""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """API client authenticated as admin"""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def provider_client(api_client, provider_user):
    """API client authenticated as provider"""
    api_client.force_authenticate(user=provider_user)
    return api_client


@pytest.fixture
def approver_client(api_client, approver_user):
    """API client authenticated as conversion approver"""
    api_client.force_authenticate(user=approver_user)
    return api_client

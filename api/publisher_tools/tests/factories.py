# publisher_tools/tests/factories.py
"""
factory_boy factories for all publisher_tools models.

Install:  pip install factory-boy faker
Usage:
    from publisher_tools.tests.factories import PublisherFactory, SiteFactory
    pub = PublisherFactory(status='active')
    site = SiteFactory(publisher=pub)
"""
import uuid
from decimal import Decimal
from datetime import date, timedelta

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ─── Auth ─────────────────────────────────────────────────────────────────────

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'user_{n}')
    email    = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_staff = False


class AdminUserFactory(UserFactory):
    is_staff      = True
    is_superuser  = True
    username      = factory.Sequence(lambda n: f'admin_{n}')


# ─── Publisher ────────────────────────────────────────────────────────────────

class PublisherFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.Publisher'

    user             = factory.SubFactory(UserFactory)
    display_name     = factory.Faker('company')
    business_type    = 'company'
    contact_email    = factory.Faker('email')
    contact_phone    = factory.Faker('phone_number')
    website          = factory.Faker('url')
    country          = 'Bangladesh'
    city             = 'Dhaka'
    address          = factory.Faker('address')
    status           = 'active'
    tier             = 'standard'
    is_kyc_verified  = False
    is_email_verified = True
    total_revenue    = Decimal('0.0000')
    total_paid_out   = Decimal('0.0000')
    pending_balance  = Decimal('0.0000')
    revenue_share_percentage = Decimal('70.00')

    # publisher_id and api_key are auto-generated in model.save()


# ─── Site ─────────────────────────────────────────────────────────────────────

class SiteFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.Site'

    publisher        = factory.SubFactory(PublisherFactory)
    name             = factory.Faker('domain_word')
    domain           = factory.LazyAttribute(lambda obj: f'{obj.name}.com')
    url              = factory.LazyAttribute(lambda obj: f'https://{obj.domain}')
    category         = 'news'
    subcategory      = factory.Faker('word')
    language         = 'en'
    status           = 'active'
    quality_score    = 80
    monthly_unique_visitors = 10_000
    avg_session_duration    = 120
    bounce_rate             = Decimal('0.4500')
    is_ads_txt_verified     = False
    sellers_json_verified   = False
    ivt_rate                = Decimal('0.0100')
    lifetime_impressions    = 0
    lifetime_clicks         = 0


# ─── App ──────────────────────────────────────────────────────────────────────

class AppFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.App'

    publisher    = factory.SubFactory(PublisherFactory)
    name         = factory.Faker('app_name', locale='en_US')
    platform     = 'android'
    package_name = factory.LazyAttribute(lambda obj: f'com.test.{obj.name.lower().replace(" ", "")}')
    category     = 'games'
    status       = 'active'
    quality_score = 75

    class Params:
        # factory.Faker('app_name') may not exist in all faker versions; fallback:
        name = factory.Sequence(lambda n: f'TestApp{n}')


# ─── InventoryVerification ────────────────────────────────────────────────────

class InventoryVerificationFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.InventoryVerification'

    publisher        = factory.SubFactory(PublisherFactory)
    site             = factory.SubFactory(SiteFactory)
    app              = None
    method           = 'ads_txt'
    status           = 'pending'
    verification_token = factory.LazyFunction(lambda: uuid.uuid4().hex)
    attempts         = 0


# ─── AdUnit ───────────────────────────────────────────────────────────────────

class AdUnitFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.AdUnit'

    publisher       = factory.SubFactory(PublisherFactory)
    site            = factory.SubFactory(SiteFactory)
    app             = None
    name            = factory.Sequence(lambda n: f'Test Ad Unit {n}')
    format          = 'banner'
    inventory_type  = 'web'
    status          = 'active'
    floor_price     = Decimal('0.5000')
    total_revenue   = Decimal('0.0000')
    total_impressions = 0
    total_clicks    = 0
    avg_ecpm        = Decimal('0.0000')
    fill_rate       = Decimal('0.0000')
    refresh_interval = 30
    is_responsive   = True
    is_lazy_load    = False

    # unit_id and tag_code are auto-generated in model.save()


# ─── AdPlacement ──────────────────────────────────────────────────────────────

class AdPlacementFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.AdPlacement'

    ad_unit    = factory.SubFactory(AdUnitFactory)
    name       = factory.Sequence(lambda n: f'Placement {n}')
    position   = 'above_fold'
    is_active  = True
    priority   = 1


# ─── AdUnitTargeting ─────────────────────────────────────────────────────────

class AdUnitTargetingFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.AdUnitTargeting'

    ad_unit     = factory.SubFactory(AdUnitFactory)
    device_type = 'all'
    os_targets  = factory.LazyFunction(list)
    geo_targets = factory.LazyFunction(lambda: ['ALL'])
    language_targets = factory.LazyFunction(list)
    excluded_categories = factory.LazyFunction(list)


# ─── MediationGroup ───────────────────────────────────────────────────────────

class MediationGroupFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.MediationGroup'

    ad_unit    = factory.SubFactory(AdUnitFactory)
    name       = factory.Sequence(lambda n: f'Mediation Group {n}')
    strategy   = 'waterfall'
    status     = 'active'
    floor_price = Decimal('0.2500')
    is_auto_optimize = False


# ─── WaterfallItem ────────────────────────────────────────────────────────────

class WaterfallItemFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.WaterfallItem'

    mediation_group = factory.SubFactory(MediationGroupFactory)
    # network is a FK to ad_networks.AdNetwork — use None or create a stub
    network         = None
    network_name    = factory.Sequence(lambda n: f'Network {n}')
    priority        = factory.Sequence(lambda n: n + 1)
    floor_price     = Decimal('0.1000')
    status          = 'active'
    timeout_ms      = 3000
    fill_rate       = Decimal('0.0000')
    avg_ecpm        = Decimal('0.0000')


# ─── HeaderBiddingConfig ──────────────────────────────────────────────────────

class HeaderBiddingConfigFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.HeaderBiddingConfig'

    mediation_group = factory.SubFactory(MediationGroupFactory)
    bidder_name     = factory.Sequence(lambda n: f'bidder_{n}')
    bidder_code     = factory.LazyAttribute(lambda obj: obj.bidder_name)
    params          = factory.LazyFunction(dict)
    floor_price     = Decimal('0.1000')
    timeout_ms      = 2000
    status          = 'active'


# ─── PublisherEarning ─────────────────────────────────────────────────────────

class PublisherEarningFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.PublisherEarning'

    publisher          = factory.SubFactory(PublisherFactory)
    site               = factory.SubFactory(SiteFactory)
    app                = None
    ad_unit            = factory.SubFactory(AdUnitFactory)
    network            = None
    date               = factory.LazyFunction(date.today)
    granularity        = 'daily'
    earning_type       = 'display'
    country            = 'BD'
    country_name       = 'Bangladesh'
    ad_requests        = 1000
    impressions        = 950
    clicks             = 45
    gross_revenue      = Decimal('5.0000')
    publisher_revenue  = Decimal('3.5000')
    platform_fee       = Decimal('1.5000')
    ecpm               = Decimal('3.6842')
    ctr                = Decimal('0.0473')
    fill_rate          = Decimal('0.9500')
    is_finalized       = False


# ─── PayoutThreshold ─────────────────────────────────────────────────────────

class PayoutThresholdFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.PayoutThreshold'

    publisher        = factory.SubFactory(PublisherFactory)
    payment_method   = 'bank_transfer'
    threshold_amount = Decimal('100.00')
    currency         = 'USD'
    is_primary       = True
    is_verified      = False
    account_name     = factory.Faker('name')
    account_details  = factory.LazyFunction(dict)


# ─── PublisherInvoice ─────────────────────────────────────────────────────────

class PublisherInvoiceFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.PublisherInvoice'

    publisher        = factory.SubFactory(PublisherFactory)
    payout_threshold = None
    period_start     = factory.LazyFunction(
        lambda: date.today().replace(day=1) - timedelta(days=1)
    )
    period_end       = factory.LazyFunction(
        lambda: date.today().replace(day=1) - timedelta(days=1)
    )
    gross_amount     = Decimal('500.0000')
    platform_fee     = Decimal('150.0000')
    net_amount       = Decimal('350.0000')
    withholding_tax  = Decimal('0.0000')
    payable_amount   = Decimal('350.0000')
    status           = 'draft'
    currency         = 'USD'


# ─── TrafficSafetyLog ─────────────────────────────────────────────────────────

class TrafficSafetyLogFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.TrafficSafetyLog'

    publisher      = factory.SubFactory(PublisherFactory)
    site           = factory.SubFactory(SiteFactory)
    app            = None
    ad_unit        = None
    traffic_type   = 'bot_traffic'
    severity       = 'medium'
    fraud_score    = 75
    ip_address     = factory.Faker('ipv4')
    user_agent     = 'Mozilla/5.0 (compatible; TestBot/1.0)'
    country        = 'BD'
    detected_at    = factory.LazyFunction(timezone.now)
    action_taken   = 'flagged'
    revenue_at_risk = Decimal('1.0000')
    revenue_deducted = Decimal('0.0000')
    is_false_positive = False


# ─── SiteQualityMetric ────────────────────────────────────────────────────────

class SiteQualityMetricFactory(DjangoModelFactory):
    class Meta:
        model = 'publisher_tools.SiteQualityMetric'

    site                  = factory.SubFactory(SiteFactory)
    date                  = factory.LazyFunction(date.today)
    overall_quality_score = 80
    content_score         = 75
    traffic_score         = 85
    technical_score       = 80
    ads_txt_score         = 90
    viewability_score     = Decimal('0.7000')
    ivt_rate              = Decimal('0.0100')
    bounce_rate           = Decimal('0.4500')
    has_alerts            = False
    alert_reasons         = factory.LazyFunction(list)
    recommendations       = factory.LazyFunction(list)


# ─── PublisherWebhook ─────────────────────────────────────────────────────────

class PublisherWebhookFactory(DjangoModelFactory):
    """Factory for PublisherWebhook model (migration 0006)."""

    class Meta:
        model = 'publisher_tools.PublisherWebhook'

    publisher         = factory.SubFactory(PublisherFactory)
    name              = factory.Sequence(lambda n: f'Webhook #{n}')
    endpoint_url      = factory.Sequence(lambda n: f'https://hooks.example.com/endpoint/{n}')
    secret_key        = factory.LazyFunction(lambda: 'wh_secret_' + uuid.uuid4().hex[:16])
    subscribed_events = factory.LazyFunction(lambda: ['earning.paid', 'invoice.issued'])
    subscribe_all     = False
    status            = 'active'
    is_active         = True
    timeout_seconds   = 10
    max_retries       = 3
    retry_backoff     = True
    custom_headers    = factory.LazyFunction(dict)
    description       = factory.Faker('sentence')

    # Stats start at zero
    total_deliveries      = 0
    successful_deliveries = 0
    failed_deliveries     = 0
    consecutive_failures  = 0


# ─── WebhookDeliveryLog ───────────────────────────────────────────────────────

class WebhookDeliveryLogFactory(DjangoModelFactory):
    """Factory for WebhookDeliveryLog model (migration 0006)."""

    class Meta:
        model = 'publisher_tools.WebhookDeliveryLog'

    webhook          = factory.SubFactory(PublisherWebhookFactory)
    event_type       = 'earning.paid'
    event_id         = factory.LazyFunction(lambda: uuid.uuid4().hex[:16])
    payload          = factory.LazyFunction(lambda: {'amount': '100.00', 'currency': 'USD'})
    status           = 'success'
    attempt          = 1
    response_code    = 200
    response_body    = '{"ok": true}'
    error_message    = ''
    delivery_time_ms = 145
    delivered_at     = factory.LazyFunction(timezone.now)


# ─── BlockedIP ────────────────────────────────────────────────────────────────

class BlockedIPFactory(DjangoModelFactory):
    """Factory for BlockedIP model (migration 0006)."""

    class Meta:
        model = 'publisher_tools.BlockedIP'

    ip_address      = factory.Faker('ipv4_public')
    reason          = factory.Faker('sentence', nb_words=5)
    fraud_score     = 85
    is_auto_blocked = True
    expires_at      = factory.LazyFunction(
        lambda: timezone.now() + __import__('datetime').timedelta(days=30)
    )
    is_permanent    = False
    unblocked_at    = None
    notes           = ''
    publisher       = factory.SubFactory(PublisherFactory)
    blocked_by      = None


# ─── ABTest ───────────────────────────────────────────────────────────────────

class ABTestFactory(DjangoModelFactory):
    """Factory for ABTest model (migration 0007)."""

    class Meta:
        model = 'publisher_tools.ABTest'

    publisher         = factory.SubFactory(PublisherFactory)
    ad_unit           = factory.SubFactory(AdUnitFactory)
    name              = factory.Sequence(lambda n: f'A/B Test #{n}')
    hypothesis        = factory.Faker('sentence')
    test_type         = 'floor_price'
    status            = 'draft'
    min_duration_days = 7
    confidence_level  = Decimal('95.00')
    min_sample_size   = 1000
    description       = ''
    metadata          = factory.LazyFunction(dict)
    # test_id is auto-generated by model.save()
    winner_variant    = None
    concluded_at      = None


# ─── ABTestVariant ────────────────────────────────────────────────────────────

class ABTestVariantFactory(DjangoModelFactory):
    """Factory for ABTestVariant model (migration 0007)."""

    class Meta:
        model = 'publisher_tools.ABTestVariant'

    test          = factory.SubFactory(ABTestFactory)
    name          = factory.Sequence(lambda n: f'Variant {n}')
    is_control    = False
    traffic_split = Decimal('50.00')
    config        = factory.LazyFunction(dict)

    # Stats default to zero
    total_impressions = 0
    total_clicks      = 0
    total_revenue     = Decimal('0.000000')
    total_ad_requests = 0
    ecpm              = Decimal('0.0000')
    ctr               = Decimal('0.0000')
    fill_rate         = Decimal('0.0000')

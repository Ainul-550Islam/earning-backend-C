"""Webhooks Test Factories

This module contains factory classes for creating test data
for the webhooks system using factory_boy.
"""

import factory
from factory import fuzzy, post_generation
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookBatchItem, WebhookTemplate, WebhookSecret,
    InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit,
    WebhookRetryAnalysis, WebhookReplay, WebhookReplayBatch, WebhookReplayItem
)
from ..constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus, InboundSource, ErrorType
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False


class WebhookEndpointFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookEndpoint instances."""
    
    class Meta:
        model = WebhookEndpoint
    
    url = factory.Faker('url')
    secret = factory.Faker('password', length=32)
    status = WebhookStatus.ACTIVE
    http_method = HttpMethod.POST
    timeout_seconds = 30
    max_retries = 3
    verify_ssl = True
    ip_whitelist = factory.LazyFunction(lambda: ['192.168.1.1', '10.0.0.1'])
    headers = factory.LazyFunction(lambda: {'Content-Type': 'application/json'})
    rate_limit_per_min = 1000
    payload_template = None
    created_by = factory.SubFactory(UserFactory)
    tenant = None
    label = factory.Faker('sentence', nb_words=3)
    description = factory.Faker('text', max_nb_chars=200)
    version = 1
    total_deliveries = 0
    success_deliveries = 0
    failed_deliveries = 0
    last_triggered_at = None


class WebhookSubscriptionFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookSubscription instances."""
    
    class Meta:
        model = WebhookSubscription
    
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    event_type = factory.Iterator([
        'user.created', 'user.updated', 'wallet.transaction.created',
        'withdrawal.requested', 'offer.credited', 'payment.succeeded'
    ])
    filter_config = factory.LazyFunction(lambda: {'user_id': 12345})
    is_active = True
    created_by = factory.SubFactory(UserFactory)


class WebhookDeliveryLogFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookDeliveryLog instances."""
    
    class Meta:
        model = WebhookDeliveryLog
    
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    event_type = factory.Iterator([
        'user.created', 'user.updated', 'wallet.transaction.created',
        'withdrawal.requested', 'offer.credited', 'payment.succeeded'
    ])
    payload = factory.LazyFunction(lambda: {
        'user_id': 12345,
        'email': 'test@example.com',
        'created_at': '2024-01-01T00:00:00Z'
    })
    status = factory.Iterator([
        DeliveryStatus.PENDING, DeliveryStatus.SUCCESS,
        DeliveryStatus.FAILED, DeliveryStatus.RETRYING
    ])
    response_code = factory.Iterator([200, 400, 500])
    response_body = factory.Faker('text', max_nb_chars=500)
    duration_ms = fuzzy.FuzzyInteger(100, 5000)
    attempt_number = fuzzy.FuzzyInteger(1, 5)
    max_attempts = 5
    next_retry_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=5))
    dispatched_at = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=10))
    completed_at = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=5))
    created_by = factory.SubFactory(UserFactory)


class WebhookFilterFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookFilter instances."""
    
    class Meta:
        model = WebhookFilter
    
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    field_path = factory.Iterator([
        'user.email', 'transaction.amount', 'user.status',
        'profile.settings.notifications.email'
    ])
    operator = factory.Iterator([
        FilterOperator.EQUALS, FilterOperator.CONTAINS,
        FilterOperator.GREATER_THAN, FilterOperator.LESS_THAN
    ])
    value = factory.Iterator([
        '@example.com', 100, 'active', 'marketing'
    ])
    is_active = True
    created_by = factory.SubFactory(UserFactory)


class WebhookBatchFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookBatch instances."""
    
    class Meta:
        model = WebhookBatch
    
    batch_id = factory.Sequence(lambda n: f'BATCH-{n:06d}')
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    event_count = fuzzy.FuzzyInteger(10, 1000)
    status = factory.Iterator([
        BatchStatus.PENDING, BatchStatus.PROCESSING,
        BatchStatus.COMPLETED, BatchStatus.CANCELLED
    ])
    completed_at = factory.LazyAttribute(lambda obj: (
        timezone.now() if obj.status == BatchStatus.COMPLETED else None
    ))
    created_by = factory.SubFactory(UserFactory)


class WebhookBatchItemFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookBatchItem instances."""
    
    class Meta:
        model = WebhookBatchItem
    
    batch = factory.SubFactory(WebhookBatchFactory)
    delivery_log = factory.SubFactory(WebhookDeliveryLogFactory)
    position = factory.Sequence(lambda n: n)
    status = factory.Iterator([
        BatchStatus.PENDING, BatchStatus.PROCESSING,
        BatchStatus.COMPLETED, BatchStatus.FAILED
    ])


class WebhookTemplateFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookTemplate instances."""
    
    class Meta:
        model = WebhookTemplate
    
    name = factory.Faker('sentence', nb_words=3)
    event_type = factory.Iterator([
        'user.created', 'user.updated', 'wallet.transaction.created',
        'withdrawal.requested', 'offer.credited'
    ])
    payload_template = factory.LazyFunction(lambda: '''
        {
            "user_id": {{user_id}},
            "email": {{user_email}},
            "message": "Welcome {{user_email}}!"
        }
    ''')
    transform_rules = factory.LazyFunction(lambda: {
        'format_email': {
            'type': 'map_value',
            'path': 'user_email',
            'mappings': {
                'user@example.com': 'USER@EXAMPLE.COM'
            }
        }
    })
    is_active = True
    created_by = factory.SubFactory(UserFactory)


class WebhookSecretFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookSecret instances."""
    
    class Meta:
        model = WebhookSecret
    
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    secret_hash = factory.Faker('sha256')
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=365))
    is_active = True
    created_by = factory.SubFactory(UserFactory)


class InboundWebhookFactory(factory.django.DjangoModelFactory):
    """Factory for creating InboundWebhook instances."""
    
    class Meta:
        model = InboundWebhook
    
    source = factory.Iterator([
        InboundSource.BKASH, InboundSource.NAGAD,
        InboundSource.STRIPE, InboundSource.PAYPAL
    ])
    url_token = factory.Sequence(lambda n: f'{n}-webhook-token')
    secret = factory.Faker('password', length=32)
    is_active = True
    created_by = factory.SubFactory(UserFactory)


class InboundWebhookLogFactory(factory.django.DjangoModelFactory):
    """Factory for creating InboundWebhookLog instances."""
    
    class Meta:
        model = InboundWebhookLog
    
    inbound = factory.SubFactory(InboundWebhookFactory)
    raw_payload = factory.LazyFunction(lambda: {
        'event': {
            'type': 'payment_intent.succeeded',
            'data': {
                'payment_id': 'pay_123456789',
                'amount': 100.00,
                'currency': 'USD'
            }
        }
    })
    headers = factory.LazyFunction(lambda: {
        'Content-Type': 'application/json',
        'X-Stripe-Signature': 'sha256=abc123...'
    })
    ip_address = factory.Faker('ipv4')
    signature_valid = True
    processed = factory.Iterator([True, False])
    processed_at = factory.LazyAttribute(lambda obj: (
        timezone.now() if obj.processed else None
    ))


class InboundWebhookRouteFactory(factory.django.DjangoModelFactory):
    """Factory for creating InboundWebhookRoute instances."""
    
    class Meta:
        model = InboundWebhookRoute
    
    inbound = factory.SubFactory(InboundWebhookFactory)
    event_pattern = factory.Iterator([
        'payment_intent.*', 'charge.succeeded', 'invoice.*'
    ])
    handler_function = factory.Iterator([
        'handle_payment_intent', 'handle_charge', 'handle_invoice'
    ])
    is_active = True


class InboundWebhookErrorFactory(factory.django.DjangoModelFactory):
    """Factory for creating InboundWebhookError instances."""
    
    class Meta:
        model = InboundWebhookError
    
    log = factory.SubFactory(InboundWebhookLogFactory)
    error_type = factory.Iterator([
        ErrorType.VALIDATION_ERROR, ErrorType.NETWORK_ERROR,
        ErrorType.TIMEOUT_ERROR, ErrorType.AUTHENTICATION_ERROR
    ])
    error_message = factory.Faker('text', max_nb_chars=500)


class WebhookAnalyticsFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookAnalytics instances."""
    
    class Meta:
        model = WebhookAnalytics
    
    date = factory.Faker('date_this_year')
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    total_sent = fuzzy.FuzzyInteger(100, 10000)
    success_count = fuzzy.FuzzyInteger(80, 9500)
    failed_count = fuzzy.FuzzyInteger(5, 500)
    avg_latency_ms = fuzzy.FuzzyFloat(50.0, 1000.0)
    success_rate = factory.LazyAttribute(lambda obj: (
        (obj.success_count / obj.total_sent * 100) if obj.total_sent > 0 else 0
    ))
    created_by = factory.SubFactory(UserFactory)


class WebhookHealthLogFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookHealthLog instances."""
    
    class Meta:
        model = WebhookHealthLog
    
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    checked_at = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=5))
    is_healthy = factory.Iterator([True, False])
    response_time_ms = fuzzy.FuzzyInteger(50, 5000)
    status_code = factory.Iterator([200, 500, 503])
    error = factory.Faker('text', max_nb_chars=200)
    created_by = factory.SubFactory(UserFactory)


class WebhookEventStatFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookEventStat instances."""
    
    class Meta:
        model = WebhookEventStat
    
    date = factory.Faker('date_this_year')
    event_type = factory.Iterator([
        'user.created', 'user.updated', 'wallet.transaction.created',
        'withdrawal.requested', 'offer.credited', 'payment.succeeded'
    ])
    fired_count = fuzzy.FuzzyInteger(100, 5000)
    delivered_count = fuzzy.FuzzyInteger(80, 4800)
    failed_count = fuzzy.FuzzyInteger(5, 200)
    created_by = factory.SubFactory(UserFactory)


class WebhookRateLimitFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookRateLimit instances."""
    
    class Meta:
        model = WebhookRateLimit
    
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    window_seconds = fuzzy.FuzzyInteger(60, 3600)
    max_requests = fuzzy.FuzzyInteger(100, 10000)
    current_count = fuzzy.FuzzyInteger(0, 1000)
    reset_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=1))
    created_by = factory.SubFactory(UserFactory)


class WebhookRetryAnalysisFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookRetryAnalysis instances."""
    
    class Meta:
        model = WebhookRetryAnalysis
    
    endpoint = factory.SubFactory(WebhookEndpointFactory)
    period = factory.Iterator(['hourly', 'daily', 'weekly', 'monthly'])
    avg_attempts_before_success = fuzzy.FuzzyFloat(1.0, 5.0)
    exhausted_count = fuzzy.FuzzyInteger(0, 100)
    created_by = factory.SubFactory(UserFactory)


class WebhookReplayFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookReplay instances."""
    
    class Meta:
        model = WebhookReplay
    
    original_log = factory.SubFactory(WebhookDeliveryLogFactory)
    replayed_by = factory.SubFactory(UserFactory)
    reason = factory.Faker('text', max_nb_chars=200)
    status = factory.Iterator([
        ReplayStatus.PENDING, ReplayStatus.PROCESSING,
        ReplayStatus.COMPLETED, ReplayStatus.FAILED
    ])
    replayed_at = factory.LazyAttribute(lambda obj: (
        timezone.now() if obj.status == ReplayStatus.COMPLETED else None
    ))
    new_log = factory.LazyAttribute(lambda obj: (
        WebhookDeliveryLogFactory() if obj.status == ReplayStatus.COMPLETED else None
    ))
    created_by = factory.SubFactory(UserFactory)


class WebhookReplayBatchFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookReplayBatch instances."""
    
    class Meta:
        model = WebhookReplayBatch
    
    batch_id = factory.Sequence(lambda n: f'REPLAY-BATCH-{n:06d}')
    created_by = factory.SubFactory(UserFactory)
    event_type = factory.Iterator([
        'user.created', 'user.updated', 'wallet.transaction.created',
        'withdrawal.requested', 'offer.credited'
    ])
    date_from = factory.Faker('date_this_month')
    date_to = factory.Faker('date_this_month')
    count = fuzzy.FuzzyInteger(10, 1000)
    status = factory.Iterator([
        ReplayStatus.PENDING, ReplayStatus.PROCESSING,
        ReplayStatus.COMPLETED, ReplayStatus.FAILED
    ])
    completed_at = factory.LazyAttribute(lambda obj: (
        timezone.now() if obj.status == ReplayStatus.COMPLETED else None
    ))


class WebhookReplayItemFactory(factory.django.DjangoModelFactory):
    """Factory for creating WebhookReplayItem instances."""
    
    class Meta:
        model = WebhookReplayItem
    
    batch = factory.SubFactory(WebhookReplayBatchFactory)
    original_log = factory.SubFactory(WebhookDeliveryLogFactory)
    status = factory.Iterator([
        ReplayStatus.PENDING, ReplayStatus.PROCESSING,
        ReplayStatus.COMPLETED, ReplayStatus.FAILED
    ])
    new_log = factory.LazyAttribute(lambda obj: (
        WebhookDeliveryLogFactory() if obj.status == ReplayStatus.COMPLETED else None
    ))
    replay = factory.LazyAttribute(lambda obj: (
        WebhookReplayFactory() if obj.status == ReplayStatus.COMPLETED else None
    ))


# Complex factories for creating related objects
class WebhookEndpointWithSubscriptionsFactory(WebhookEndpointFactory):
    """Factory for creating WebhookEndpoint with subscriptions."""
    
    @post_generation
    def subscriptions(self, create, extracted, **kwargs):
        if extracted:
            # Use provided subscriptions
            for subscription in extracted:
                self.subscriptions.add(subscription)
        else:
            # Create default subscriptions
            WebhookSubscriptionFactory.create_batch(
                size=3,
                endpoint=self
            )


class WebhookBatchWithItemsFactory(WebhookBatchFactory):
    """Factory for creating WebhookBatch with items."""
    
    @post_generation
    def items(self, create, extracted, **kwargs):
        if extracted:
            # Use provided items
            for item in extracted:
                self.items.add(item)
        else:
            # Create default items
            WebhookBatchItemFactory.create_batch(
                size=self.event_count,
                batch=self
            )


class WebhookReplayBatchWithItemsFactory(WebhookReplayBatchFactory):
    """Factory for creating WebhookReplayBatch with items."""
    
    @post_generation
    def items(self, create, extracted, **kwargs):
        if extracted:
            # Use provided items
            for item in extracted:
                self.items.add(item)
        else:
            # Create default items
            WebhookReplayItemFactory.create_batch(
                size=self.count,
                batch=self
            )


# Utility functions for test data
def create_test_endpoint_with_data():
    """Create a complete test endpoint with related data."""
    user = UserFactory()
    endpoint = WebhookEndpointWithSubscriptionsFactory(created_by=user)
    
    # Create delivery logs
    WebhookDeliveryLogFactory.create_batch(
        size=10,
        endpoint=endpoint,
        created_by=user
    )
    
    # Create filters
    WebhookFilterFactory.create_batch(
        size=3,
        endpoint=endpoint,
        created_by=user
    )
    
    # Create analytics
    WebhookAnalyticsFactory.create_batch(
        size=5,
        endpoint=endpoint,
        created_by=user
    )
    
    return endpoint


def create_test_inbound_webhook_with_data():
    """Create a complete test inbound webhook with related data."""
    user = UserFactory()
    inbound = InboundWebhookFactory(created_by=user)
    
    # Create logs
    InboundWebhookLogFactory.create_batch(
        size=10,
        inbound=inbound
    )
    
    # Create routes
    InboundWebhookRouteFactory.create_batch(
        size=3,
        inbound=inbound
    )
    
    return inbound


def create_test_replay_batch():
    """Create a complete test replay batch with items."""
    user = UserFactory()
    batch = WebhookReplayBatchWithItemsFactory(created_by=user)
    return batch

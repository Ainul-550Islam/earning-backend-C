"""factories.py – Factory Boy factories for postback tests."""
import uuid
import factory
import factory.fuzzy
from django.contrib.auth import get_user_model
from django.utils import timezone

from api.postback.choices import (
    ConversionEventType,
    DeduplicationWindow,
    NetworkType,
    PostbackConversionStatus,
    PostbackStatus,
    RejectionReason,
    SignatureAlgorithm,
    ValidatorStatus,
)
from api.postback.models import (
    DuplicateLeadCheck,
    LeadValidator,
    NetworkPostbackConfig,
    PostbackLog,
    PostbackS2SLog,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    username = factory.Sequence(lambda n: f"postback_user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "pass1234")
    is_active = True


class NetworkPostbackConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NetworkPostbackConfig

    name = factory.Sequence(lambda n: f"Test Network {n}")
    network_key = factory.Sequence(lambda n: f"test-network-{n:04d}")
    network_type = NetworkType.CPA
    status = ValidatorStatus.ACTIVE
    secret_key = factory.Faker("sha256")
    signature_algorithm = SignatureAlgorithm.HMAC_SHA256
    ip_whitelist = []
    trust_forwarded_for = False
    require_nonce = True
    field_mapping = {}
    required_fields = ["lead_id", "offer_id"]
    dedup_window = DeduplicationWindow.FOREVER
    reward_rules = {}
    default_reward_points = 100
    rate_limit_per_minute = 1000
    contact_email = factory.Faker("email")
    # S2S callback fields
    callback_url = ""
    callback_method = "GET"
    callback_secret = ""
    metadata = {}


class CPALeadNetworkFactory(NetworkPostbackConfigFactory):
    """Factory for CPAlead-specific network config."""
    name = "CPAlead"
    network_key = factory.Sequence(lambda n: f"cpalead-{n:04d}")
    network_type = NetworkType.CPA
    field_mapping = {
        "lead_id": "lead_id",
        "offer_id": "offer_id",
        "payout": "payout",
        "goal_id": "goal_id",
        "sub_id1": "sub_id",
    }
    callback_url = "https://tracker.example.com/cb?lead={lead_id}&payout={payout}&ip={ip_address}"
    callback_method = "GET"


class S2SNetworkFactory(NetworkPostbackConfigFactory):
    """Factory for a network with S2S callback configured."""
    callback_url = "https://adv.example.com/postback?txn={transaction_id}&rev={payout}"
    callback_method = "GET"
    callback_secret = "s2s-test-secret-key"


class InactiveNetworkFactory(NetworkPostbackConfigFactory):
    status = ValidatorStatus.INACTIVE


class TestingNetworkFactory(NetworkPostbackConfigFactory):
    status = ValidatorStatus.TESTING


class IPWhitelistedNetworkFactory(NetworkPostbackConfigFactory):
    ip_whitelist = ["127.0.0.1", "192.168.1.0/24"]


class NoSignatureNetworkFactory(NetworkPostbackConfigFactory):
    signature_algorithm = SignatureAlgorithm.NONE
    require_nonce = False


class PostbackLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PostbackLog

    network = factory.SubFactory(NetworkPostbackConfigFactory)
    status = PostbackStatus.RECEIVED
    raw_payload = factory.LazyFunction(lambda: {
        "lead_id": "LEAD123",
        "offer_id": "OFFER456",
        "payout": "2.50",
        "currency": "USD",
    })
    method = "POST"
    query_string = ""
    request_headers = {}
    lead_id = "LEAD123"
    offer_id = "OFFER456"
    payout = "2.50"
    currency = "USD"
    source_ip = "1.2.3.4"
    signature_verified = True
    ip_whitelisted = True
    received_at = factory.LazyFunction(timezone.now)
    # New fields
    event_type = ConversionEventType.UNKNOWN
    conversion_status = PostbackConversionStatus.APPROVED
    is_reversal = False
    click_id = ""
    fire_delay_ms = 0


class CPALeadPostbackLogFactory(PostbackLogFactory):
    """Factory for a CPAlead postback log with full fields."""
    network = factory.SubFactory(CPALeadNetworkFactory)
    raw_payload = factory.LazyFunction(lambda: {
        "lead_id": "CPA_LEAD_001",
        "offer_id": "OFFER_789",
        "payout": "5.00",
        "currency": "USD",
        "goal_id": "sale",
        "sub_id": "SUB_001",
        "sub_id2": "SUB_002",
        "sub_id3": "SUB_003",
        "country": "US",
        "device": "mobile",
        "os": "ios",
        "browser": "safari",
        "status": "approved",
    })
    lead_id = "CPA_LEAD_001"
    offer_id = "OFFER_789"
    event_type = ConversionEventType.SALE
    conversion_status = PostbackConversionStatus.APPROVED


class RewardedPostbackLogFactory(PostbackLogFactory):
    status = PostbackStatus.REWARDED
    points_awarded = 100
    processed_at = factory.LazyFunction(timezone.now)
    resolved_user = factory.SubFactory(UserFactory)
    event_type = ConversionEventType.LEAD
    conversion_status = PostbackConversionStatus.APPROVED


class RejectedPostbackLogFactory(PostbackLogFactory):
    status = PostbackStatus.REJECTED
    rejection_reason = RejectionReason.INVALID_SIGNATURE
    rejection_detail = "HMAC mismatch."
    signature_verified = False
    processed_at = factory.LazyFunction(timezone.now)


class DuplicatePostbackLogFactory(PostbackLogFactory):
    status = PostbackStatus.DUPLICATE
    rejection_reason = RejectionReason.DUPLICATE_LEAD


class FailedPostbackLogFactory(PostbackLogFactory):
    status = PostbackStatus.FAILED
    processing_error = "Database connection error."
    retry_count = 1
    next_retry_at = factory.LazyFunction(
        lambda: timezone.now() - timezone.timedelta(minutes=5)
    )


class ReversalPostbackLogFactory(PostbackLogFactory):
    """Factory for a reversal/chargeback postback log."""
    is_reversal = True
    conversion_status = PostbackConversionStatus.REVERSED
    payout = "-2.50"
    event_type = ConversionEventType.UNKNOWN


class DuplicateLeadCheckFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DuplicateLeadCheck

    network = factory.SubFactory(NetworkPostbackConfigFactory)
    lead_id = factory.Sequence(lambda n: f"LEAD_{n:010d}")
    first_seen_at = factory.LazyFunction(timezone.now)
    postback_log = factory.SubFactory(RewardedPostbackLogFactory)


class LeadValidatorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LeadValidator

    network = factory.SubFactory(NetworkPostbackConfigFactory)
    name = factory.Sequence(lambda n: f"Validator {n}")
    validator_type = "field_present"
    params = factory.LazyFunction(lambda: {"field": "lead_id"})
    is_blocking = True
    sort_order = factory.Sequence(lambda n: n)
    is_active = True


class FieldRegexValidatorFactory(LeadValidatorFactory):
    validator_type = "field_regex"
    params = {"field": "lead_id", "pattern": r"^[A-Z0-9]{6,20}$"}


class PayoutRangeValidatorFactory(LeadValidatorFactory):
    validator_type = "payout_range"
    params = {"min": 0.5, "max": 50.0}


class OfferWhitelistValidatorFactory(LeadValidatorFactory):
    validator_type = "offer_whitelist"
    params = {"allowed_offers": ["OFFER_A", "OFFER_B"]}


class PostbackS2SLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PostbackS2SLog

    postback_log = factory.SubFactory(RewardedPostbackLogFactory)
    callback_url = "https://adv.example.com/postback?lead=LEAD123&payout=2.50"
    http_status = 200
    response_body = "OK"
    success = True
    attempt_number = 1
    error_message = ""
    fired_at = factory.LazyFunction(timezone.now)

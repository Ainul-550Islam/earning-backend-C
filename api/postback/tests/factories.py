"""factories.py – Factory Boy factories for postback tests."""
import factory
import factory.fuzzy
from django.contrib.auth import get_user_model
from django.utils import timezone

from postback.choices import (
    DeduplicationWindow,
    NetworkType,
    PostbackStatus,
    RejectionReason,
    SignatureAlgorithm,
    ValidatorStatus,
)
from postback.models import (
    DuplicateLeadCheck,
    LeadValidator,
    NetworkPostbackConfig,
    PostbackLog,
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


class RewardedPostbackLogFactory(PostbackLogFactory):
    status = PostbackStatus.REWARDED
    points_awarded = 100
    processed_at = factory.LazyFunction(timezone.now)
    resolved_user = factory.SubFactory(UserFactory)


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

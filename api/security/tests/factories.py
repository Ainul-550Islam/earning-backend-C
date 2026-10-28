"""
Security Test Factories
Factory classes for generating test data for security models
Author: System Security Team
Version: 2.0.0
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from factory import Factory, SubFactory, LazyAttribute, Sequence
from factory.django import DjangoModelFactory
from faker import Faker

User = get_user_model()
fake = Faker()


class UserFactory(DjangoModelFactory):
    """Factory for User model"""
    
    class Meta:
        model = User
        django_get_or_create = ('username',)
    
    username = Sequence(lambda n: f"user_{n}")
    email = LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = LazyAttribute(lambda obj: fake.first_name())
    last_name = LazyAttribute(lambda obj: fake.last_name())
    is_active = True
    is_staff = False
    is_superuser = False


class StaffUserFactory(UserFactory):
    """Factory for Staff User"""
    
    is_staff = True


class SuperUserFactory(UserFactory):
    """Factory for Super User"""
    
    is_staff = True
    is_superuser = True


class DeviceInfoFactory(DjangoModelFactory):
    """Factory for DeviceInfo model"""
    
    class Meta:
        model = 'api.security.DeviceInfo'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    device_fingerprint = LazyAttribute(lambda _: fake.sha256())
    device_type = LazyAttribute(lambda _: fake.random_element(['desktop', 'mobile', 'tablet']))
    device_name = LazyAttribute(lambda _: f"{fake.company()} {fake.random_element(['Phone', 'Laptop', 'Tablet'])}")
    operating_system = LazyAttribute(lambda _: fake.random_element(['Windows', 'macOS', 'Linux', 'iOS', 'Android']))
    browser = LazyAttribute(lambda _: fake.random_element(['Chrome', 'Firefox', 'Safari', 'Edge']))
    browser_version = LazyAttribute(lambda _: fake.numerify('##.#'))
    screen_resolution = LazyAttribute(lambda _: f"{fake.random_int(1024, 2560)}x{fake.random_int(768, 1440)}")
    ip_address = LazyAttribute(lambda _: fake.ipv4())
    user_agent = LazyAttribute(lambda _: fake.user_agent())
    is_trusted = False
    trust_score = LazyAttribute(lambda _: fake.random_int(0, 100))
    risk_score = LazyAttribute(lambda _: fake.random_int(0, 100))
    is_suspicious = False
    usage_count = LazyAttribute(lambda _: fake.random_int(1, 1000))
    last_seen_at = LazyAttribute(lambda _: timezone.now() - timedelta(hours=fake.random_int(1, 24)))
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 365)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class TrustedDeviceFactory(DeviceInfoFactory):
    """Factory for TrustedDevice model"""
    
    class Meta:
        model = 'api.security.TrustedDevice'
    
    is_trusted = True
    trust_score = LazyAttribute(lambda _: fake.random_int(70, 100))
    device_name = LazyAttribute(lambda _: f"Trusted {fake.company()} Device")
    expires_at = LazyAttribute(lambda _: timezone.now() + timedelta(days=fake.random_int(30, 365)))


class SecurityLogFactory(DjangoModelFactory):
    """Factory for SecurityLog model"""
    
    class Meta:
        model = 'api.security.SecurityLog'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    event_type = LazyAttribute(lambda _: fake.random_element([
        'login_success', 'login_failed', 'logout', 'password_change',
        'account_locked', 'suspicious_activity', 'vpn_detected', 'proxy_detected'
    ]))
    severity = LazyAttribute(lambda _: fake.random_element(['debug', 'info', 'warning', 'error', 'critical']))
    ip_address = LazyAttribute(lambda _: fake.ipv4())
    user_agent = LazyAttribute(lambda _: fake.user_agent())
    device_info = LazyAttribute(lambda _: fake.company())
    metadata = LazyAttribute(lambda _: {
        'timestamp': fake.iso8601(),
        'session_id': fake.sha256(),
        'additional_info': fake.sentence()
    })
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(hours=fake.random_int(1, 168)))


class UserBanFactory(DjangoModelFactory):
    """Factory for UserBan model"""
    
    class Meta:
        model = 'api.security.UserBan'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    reason = LazyAttribute(lambda _: fake.sentence())
    ban_type = LazyAttribute(lambda _: fake.random_element(['temporary', 'permanent', 'suspension']))
    is_active = True
    created_by = SubFactory(StaffUserFactory)
    expires_at = LazyAttribute(lambda _: timezone.now() + timedelta(days=fake.random_int(1, 365)))
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class IPBlacklistFactory(DjangoModelFactory):
    """Factory for IPBlacklist model"""
    
    class Meta:
        model = 'api.security.IPBlacklist'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    ip_address = LazyAttribute(lambda _: fake.ipv4())
    reason = LazyAttribute(lambda _: fake.sentence())
    blacklist_type = LazyAttribute(lambda _: fake.random_element(['manual', 'automatic', 'vpn_detected', 'threat_intelligence']))
    is_active = True
    created_by = SubFactory(StaffUserFactory)
    expires_at = LazyAttribute(lambda _: timezone.now() + timedelta(days=fake.random_int(1, 365)))
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class ThreatIntelligenceFactory(DjangoModelFactory):
    """Factory for ThreatIntelligence model"""
    
    class Meta:
        model = 'api.security.ThreatIntelligence'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    threat_type = LazyAttribute(lambda _: fake.random_element(['malware', 'phishing', 'botnet', 'vpn', 'proxy']))
    indicator_type = LazyAttribute(lambda _: fake.random_element(['ip', 'domain', 'url', 'hash', 'email']))
    indicators = LazyAttribute(lambda _: [fake.ipv4() for _ in range(fake.random_int(1, 5))])
    severity = LazyAttribute(lambda _: fake.random_element(['low', 'medium', 'high', 'critical']))
    confidence = LazyAttribute(lambda _: fake.random.uniform(0.1, 1.0))
    source = LazyAttribute(lambda _: fake.company())
    description = LazyAttribute(lambda _: fake.text(max_nb_chars=200))
    is_active = True
    expires_at = LazyAttribute(lambda _: timezone.now() + timedelta(days=fake.random_int(1, 365)))
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class SecurityIncidentFactory(DjangoModelFactory):
    """Factory for SecurityIncident model"""
    
    class Meta:
        model = 'api.security.SecurityIncident'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    incident_id = LazyAttribute(lambda _: f"INC-{fake.random_int(10000, 99999)}")
    user = SubFactory(UserFactory)
    incident_type = LazyAttribute(lambda _: fake.random_element(['fraud_detection', 'security_breach', 'suspicious_activity', 'data_leak']))
    severity = LazyAttribute(lambda _: fake.random_element(['low', 'medium', 'high', 'critical']))
    status = LazyAttribute(lambda _: fake.random_element(['open', 'investigating', 'resolved', 'closed']))
    title = LazyAttribute(lambda _: fake.sentence())
    description = LazyAttribute(lambda _: fake.text(max_nb_chars=500))
    evidence = LazyAttribute(lambda _: {
        'ip_addresses': [fake.ipv4() for _ in range(fake.random_int(1, 3))],
        'user_agents': [fake.user_agent() for _ in range(fake.random_int(1, 2))],
        'timestamps': [fake.iso8601() for _ in range(fake.random_int(1, 5))]
    })
    assigned_to = SubFactory(StaffUserFactory)
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))
    updated_at = LazyAttribute(lambda _: timezone.now())
    resolved_at = LazyAttribute(lambda _: None)


class PasswordHistoryFactory(DjangoModelFactory):
    """Factory for PasswordHistory model"""
    
    class Meta:
        model = 'api.security.PasswordHistory'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    password_hash = LazyAttribute(lambda _: fake.sha256())
    password_algorithm = LazyAttribute(lambda _: fake.random_element(['bcrypt', 'pbkdf2', 'argon2']))
    salt = LazyAttribute(lambda _: fake.sha256())
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 365)))
    is_active = False
    expires_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))


class SecurityPolicyFactory(DjangoModelFactory):
    """Factory for SecurityPolicy model"""
    
    class Meta:
        model = 'api.security.SecurityPolicy'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    policy_key = LazyAttribute(lambda _: fake.random_element(['password_policy', 'session_policy', 'access_policy']))
    policy_value = LazyAttribute(lambda _: fake.json())
    is_active = True
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 365)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class SecurityInsightFactory(DjangoModelFactory):
    """Factory for SecurityInsight model"""
    
    class Meta:
        model = 'api.security.SecurityInsight'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    insight_date = LazyAttribute(lambda _: fake.date_between(start_date='-30d', end_date='today'))
    total_security_events = LazyAttribute(lambda _: fake.random_int(100, 10000))
    high_risk_events = LazyAttribute(lambda _: fake.random_int(1, 100))
    vpn_detections = LazyAttribute(lambda _: fake.random_int(1, 50))
    proxy_detections = LazyAttribute(lambda _: fake.random_int(1, 30))
    failed_logins = LazyAttribute(lambda _: fake.random_int(10, 500))
    successful_logins = LazyAttribute(lambda _: fake.random_int(100, 1000))
    unique_ips = LazyAttribute(lambda _: fake.random_int(50, 500))
    top_threat_types = LazyAttribute(lambda _: {
        'malware': fake.random_int(1, 20),
        'phishing': fake.random_int(1, 15),
        'botnet': fake.random_int(1, 10)
    })
    risk_distribution = LazyAttribute(lambda _: {
        'low': fake.random_int(60, 80),
        'medium': fake.random_int(15, 30),
        'high': fake.random_int(5, 15),
        'critical': fake.random_int(1, 5)
    })
    created_at = LazyAttribute(lambda _: timezone.now())
    updated_at = LazyAttribute(lambda _: timezone.now())


class RiskScoreFactory(DjangoModelFactory):
    """Factory for RiskScore model"""
    
    class Meta:
        model = 'api.security.RiskScore'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    current_score = LazyAttribute(lambda _: Decimal(str(fake.random.uniform(0, 100))))
    previous_score = LazyAttribute(lambda _: Decimal(str(fake.random.uniform(0, 100))))
    risk_factors = LazyAttribute(lambda _: fake.random_elements([
        'multiple_ips', 'suspicious_location', 'vpn_usage', 'failed_attempts',
        'unusual_device', 'high_frequency', 'off_hours_access'
    ], unique=True))
    calculated_at = LazyAttribute(lambda _: timezone.now())
    expires_at = LazyAttribute(lambda _: timezone.now() + timedelta(hours=fake.random_int(1, 24)))
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class GeolocationLogFactory(DjangoModelFactory):
    """Factory for GeolocationLog model"""
    
    class Meta:
        model = 'api.security.GeolocationLog'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    ip_address = LazyAttribute(lambda _: fake.ipv4())
    country = LazyAttribute(lambda _: fake.country_code())
    country_name = LazyAttribute(lambda _: fake.country())
    city = LazyAttribute(lambda _: fake.city())
    latitude = LazyAttribute(lambda _: fake.latitude())
    longitude = LazyAttribute(lambda _: fake.longitude())
    timezone = LazyAttribute(lambda _: fake.timezone())
    asn = LazyAttribute(lambda _: fake.random_int(1, 99999))
    organization = LazyAttribute(lambda _: fake.company())
    is_proxy = LazyAttribute(lambda _: fake.boolean())
    is_vpn = LazyAttribute(lambda _: fake.boolean())
    queried_at = LazyAttribute(lambda _: timezone.now() - timedelta(hours=fake.random_int(1, 168)))
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))


class UserSessionFactory(DjangoModelFactory):
    """Factory for UserSession model"""
    
    class Meta:
        model = 'api.security.UserSession'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    session_key = LazyAttribute(lambda _: fake.sha256())
    ip_address = LazyAttribute(lambda _: fake.ipv4())
    user_agent = LazyAttribute(lambda _: fake.user_agent())
    device_info = SubFactory(DeviceInfoFactory)
    is_active = LazyAttribute(lambda _: fake.boolean())
    last_activity = LazyAttribute(lambda _: timezone.now() - timedelta(minutes=fake.random_int(1, 1440)))
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(hours=fake.random_int(1, 24)))
    expires_at = LazyAttribute(lambda _: timezone.now() + timedelta(hours=fake.random_int(1, 24)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class SessionActivityFactory(DjangoModelFactory):
    """Factory for SessionActivity model"""
    
    class Meta:
        model = 'api.security.SessionActivity'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    session = SubFactory(UserSessionFactory)
    activity_type = LazyAttribute(lambda _: fake.random_element(['login', 'logout', 'page_view', 'api_call', 'form_submit']))
    ip_address = LazyAttribute(lambda _: fake.ipv4())
    user_agent = LazyAttribute(lambda _: fake.user_agent())
    metadata = LazyAttribute(lambda _: {
        'timestamp': fake.iso8601(),
        'endpoint': fake.uri(),
        'response_time': fake.random_int(50, 500)
    })
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(minutes=fake.random_int(1, 1440)))


class TwoFactorMethodFactory(DjangoModelFactory):
    """Factory for TwoFactorMethod model"""
    
    class Meta:
        model = 'api.security.TwoFactorMethod'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    method_type = LazyAttribute(lambda _: fake.random_element(['totp', 'sms', 'email', 'backup_codes']))
    is_active = True
    is_primary = False
    secret_key = LazyAttribute(lambda _: fake.sha256())
    phone_number = LazyAttribute(lambda _: fake.phone_number())
    email_address = LazyAttribute(lambda _: fake.email())
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 365)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class TwoFactorAttemptFactory(DjangoModelFactory):
    """Factory for TwoFactorAttempt model"""
    
    class Meta:
        model = 'api.security.TwoFactorAttempt'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    method = SubFactory(TwoFactorMethodFactory)
    attempt_type = LazyAttribute(lambda _: fake.random_element(['login', 'setup', 'verify', 'disable']))
    is_successful = LazyAttribute(lambda _: fake.boolean())
    ip_address = LazyAttribute(lambda _: fake.ipv4())
    user_agent = LazyAttribute(lambda _: fake.user_agent())
    failure_reason = LazyAttribute(lambda _: fake.sentence() if fake.boolean() else None)
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(hours=fake.random_int(1, 168)))


class TwoFactorRecoveryCodeFactory(DjangoModelFactory):
    """Factory for TwoFactorRecoveryCode model"""
    
    class Meta:
        model = 'api.security.TwoFactorRecoveryCode'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    code = LazyAttribute(lambda _: fake.numerify('########'))
    is_used = False
    used_at = LazyAttribute(lambda _: None)
    expires_at = LazyAttribute(lambda _: timezone.now() + timedelta(days=fake.random_int(30, 365)))
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))


class CountryFactory(DjangoModelFactory):
    """Factory for Country model"""
    
    class Meta:
        model = 'api.security.Country'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    country_code = LazyAttribute(lambda _: fake.country_code())
    country_name = LazyAttribute(lambda _: fake.country())
    is_active = True
    risk_level = LazyAttribute(lambda _: fake.random_element(['low', 'medium', 'high']))
    created_at = LazyAttribute(lambda _: timezone.now())
    updated_at = LazyAttribute(lambda _: timezone.now())


class CountryBlockRuleFactory(DjangoModelFactory):
    """Factory for CountryBlockRule model"""
    
    class Meta:
        model = 'api.security.CountryBlockRule'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    country = SubFactory(CountryFactory)
    block_type = LazyAttribute(lambda _: fake.random_element(['complete', 'partial', 'monitor']))
    is_active = True
    reason = LazyAttribute(lambda _: fake.sentence())
    created_by = SubFactory(StaffUserFactory)
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class APIRateLimitFactory(DjangoModelFactory):
    """Factory for APIRateLimit model"""
    
    class Meta:
        model = 'api.security.APIRateLimit'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    endpoint = LazyAttribute(lambda _: f"/api/{fake.random_element(['users', 'security', 'admin'])}/{fake.word()}")
    method = LazyAttribute(lambda _: fake.random_element(['GET', 'POST', 'PUT', 'DELETE']))
    requests_per_minute = LazyAttribute(lambda _: fake.random_int(10, 1000))
    requests_per_hour = LazyAttribute(lambda _: fake.random_int(100, 10000))
    requests_per_day = LazyAttribute(lambda _: fake.random_int(1000, 100000))
    is_active = True
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(days=fake.random_int(1, 30)))
    updated_at = LazyAttribute(lambda _: timezone.now())


class RateLimitLogFactory(DjangoModelFactory):
    """Factory for RateLimitLog model"""
    
    class Meta:
        model = 'api.security.RateLimitLog'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    ip_address = LazyAttribute(lambda _: fake.ipv4())
    endpoint = LazyAttribute(lambda _: f"/api/{fake.random_element(['users', 'security', 'admin'])}/{fake.word()}")
    method = LazyAttribute(lambda _: fake.random_element(['GET', 'POST', 'PUT', 'DELETE']))
    user = SubFactory(UserFactory)
    is_blocked = LazyAttribute(lambda _: fake.boolean())
    block_reason = LazyAttribute(lambda _: fake.sentence() if fake.boolean() else None)
    created_at = LazyAttribute(lambda _: timezone.now() - timedelta(hours=fake.random_int(1, 168)))


class ClickTrackerFactory(DjangoModelFactory):
    """Factory for ClickTracker model"""
    
    class Meta:
        model = 'api.security.ClickTracker'
    
    id = LazyAttribute(lambda _: uuid.uuid4())
    user = SubFactory(UserFactory)
    session_key = LazyAttribute(lambda _: fake.sha256())
    page_url = LazyAttribute(lambda _: fake.uri())
    element_selector = LazyAttribute(lambda _: fake.css_selector())
    element_text = LazyAttribute(lambda _: fake.sentence(nb_words=3))
    click_category = LazyAttribute(lambda _: fake.random_element(['navigation', 'form', 'button', 'link', 'image']))
    position_x = LazyAttribute(lambda _: fake.random_int(0, 1920))
    position_y = LazyAttribute(lambda _: fake.random_int(0, 1080))
    viewport_width = LazyAttribute(lambda _: fake.random_int(1024, 1920))
    viewport_height = LazyAttribute(lambda _: fake.random_int(768, 1080))
    clicked_at = LazyAttribute(lambda _: timezone.now() - timedelta(minutes=fake.random_int(1, 1440)))
    created_at = LazyAttribute(lambda _: timezone.now())


class EnhancedClickTrackerFactory(ClickTrackerFactory):
    """Factory for EnhancedClickTracker model"""
    
    class Meta:
        model = 'api.security.EnhancedClickTracker'
    
    heat_score = LazyAttribute(lambda _: fake.random_int(1, 100))
    engagement_value = LazyAttribute(lambda _: fake.random_int(1, 10))
    conversion_value = LazyAttribute(lambda _: fake.random_int(0, 100))
    metadata = LazyAttribute(lambda _: {
        'scroll_depth': fake.random_int(0, 100),
        'dwell_time': fake.random_int(100, 10000),
        'device_type': fake.random_element(['desktop', 'mobile', 'tablet'])
    })
"""Test Factories for Rate Limit Module"""

import factory
from factory import fuzzy
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import random

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile,
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ('username',)
    username = factory.Sequence(lambda n: f'testuser{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return cls._get_manager(model_class).create_user(*args, **kwargs)


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'tenants.Tenant'
        django_get_or_create = ('name',)
    name = factory.Sequence(lambda n: f'tenant_{n}')
    domain = factory.LazyAttribute(lambda o: f'{o.name}.example.com')
    is_active = True
    tier = 'free'
    daily_limit = None
    hourly_limit = None


class RateLimitConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RateLimitConfig
        django_get_or_create = ('name',)
    name = factory.Sequence(lambda n: f'config_{n}')
    rate_limit_type = fuzzy.FuzzyChoice(['user','ip','endpoint','global','referral','task'])
    requests_per_unit = fuzzy.FuzzyInteger(10, 1000)
    requests_per_minute = None
    burst_size = None
    burst_multiplier = 1.0
    time_unit = fuzzy.FuzzyChoice(['second','minute','hour','day'])
    time_value = fuzzy.FuzzyInteger(1, 24)
    is_active = True
    whitelist = factory.LazyFunction(list)
    blacklist = factory.LazyFunction(list)
    bypass_keys = factory.LazyFunction(list)
    hit_count = fuzzy.FuzzyInteger(0, 1000)
    block_count = fuzzy.FuzzyInteger(0, 100)
    tenant = factory.SubFactory(TenantFactory)

    @factory.lazy_attribute
    def ip_address(self):
        return f'192.168.1.{random.randint(1,254)}' if self.rate_limit_type == 'ip' else None

    @factory.lazy_attribute
    def endpoint(self):
        return f'/api/ep_{random.randint(1,100)}/' if self.rate_limit_type == 'endpoint' else None

    @factory.lazy_attribute
    def task_type(self):
        return random.choice(['survey','video','offer']) if self.rate_limit_type == 'task' else None

    @factory.lazy_attribute
    def offer_wall(self):
        return 'wall_1' if self.rate_limit_type == 'referral' else None


class RateLimitLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RateLimitLog
    user = factory.SubFactory(UserFactory)
    ip_address = factory.LazyFunction(lambda: f'192.168.1.{random.randint(1,254)}')
    endpoint = factory.LazyFunction(lambda: f'/api/ep_{random.randint(1,100)}/')
    request_method = fuzzy.FuzzyChoice(['GET','POST','PUT','DELETE'])
    user_agent = factory.Faker('user_agent')
    config = factory.SubFactory(RateLimitConfigFactory)
    status = fuzzy.FuzzyChoice(['allowed','blocked','exceeded'])
    requests_count = fuzzy.FuzzyInteger(1, 100)
    task_id = factory.LazyFunction(lambda: f'task_{random.randint(1000,9999)}')
    offer_id = factory.LazyFunction(lambda: f'offer_{random.randint(1000,9999)}')
    referral_code = factory.LazyFunction(lambda: f'ref_{random.randint(100,999)}')
    suspicion_score = fuzzy.FuzzyInteger(0, 100)
    timestamp = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=random.randint(1,1440)))
    tenant = factory.SubFactory(TenantFactory)


class UserRateLimitProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserRateLimitProfile
        django_get_or_create = ('user',)
    user = factory.SubFactory(UserFactory)
    is_premium = fuzzy.FuzzyChoice([True, False])
    premium_until = factory.LazyAttribute(lambda o: timezone.now() + timedelta(days=30) if o.is_premium else None)
    custom_daily_limit = fuzzy.FuzzyInteger(500, 5000)
    custom_hourly_limit = fuzzy.FuzzyInteger(50, 500)
    current_usage = fuzzy.FuzzyInteger(0, 1000)
    daily_usage = fuzzy.FuzzyInteger(0, 5000)
    hourly_usage = fuzzy.FuzzyInteger(0, 500)
    total_requests = fuzzy.FuzzyInteger(0, 10000)
    blocked_requests = fuzzy.FuzzyInteger(0, 1000)
    last_request_at = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=random.randint(1,60)))
    api_health_score = fuzzy.FuzzyInteger(60, 100)
    suspicion_score = fuzzy.FuzzyInteger(0, 100)
    tenant = factory.SubFactory(TenantFactory)
    daily_limit = None
    hourly_limit = None
    tier = 'free'
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        manager = cls._get_manager(model_class)
        user = kwargs.get('user')
        if user is None:
            return manager.create(**kwargs)
        obj, created = manager.get_or_create(user=user, defaults=kwargs)
        if not created:
            try:
                valid = {f.name for f in obj._meta.concrete_fields}
                for k, v in kwargs.items():
                    if k != 'user' and k in valid:
                        setattr(obj, k, v)
                obj.save()
            except Exception:
                pass
        return obj


class IPBlockListFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IPBlockList
    block_type = fuzzy.FuzzyChoice(['single','range','subnet'])
    reason = fuzzy.FuzzyChoice(['abuse','fraud','spam','malicious','manual'])
    blocked_by = factory.SubFactory(UserFactory)
    description = factory.Faker('text', max_nb_chars=200)
    is_active = True
    permanent = False
    block_count = fuzzy.FuzzyInteger(0, 1000)
    tenant = factory.SubFactory(TenantFactory)

    @factory.lazy_attribute
    def ip_address(self):
        return f'192.168.{random.randint(1,254)}.{random.randint(1,254)}' if self.block_type == 'single' else None

    @factory.lazy_attribute
    def ip_range_start(self):
        return f'192.168.{random.randint(1,254)}.1' if self.block_type == 'range' else None

    @factory.lazy_attribute
    def ip_range_end(self):
        if self.block_type == 'range' and self.ip_range_start:
            return self.ip_range_start.rsplit('.', 1)[0] + '.254'
        return None

    @factory.lazy_attribute
    def subnet(self):
        return f'192.168.{random.randint(1,254)}.0/24' if self.block_type == 'subnet' else None

    @factory.lazy_attribute
    def expires_at(self):
        return timezone.now() + timedelta(days=random.randint(1,30)) if not self.permanent else None


class AbuseReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AbuseReport
    ip_address = factory.LazyFunction(lambda: f'192.168.1.{random.randint(1,254)}')
    user = factory.SubFactory(UserFactory)
    user_agent = factory.Faker('user_agent')
    abuse_type = fuzzy.FuzzyChoice(['rate_limit','spam','fraud','malicious','bot','other'])
    endpoint = factory.LazyFunction(lambda: f'/api/ep_{random.randint(1,100)}/')
    pattern = fuzzy.FuzzyChoice(['rapid_requests','high_volume','suspicious_pattern','bot_activity'])
    count_24h = fuzzy.FuzzyInteger(0, 100)
    count_7d = fuzzy.FuzzyInteger(0, 500)
    count_total = fuzzy.FuzzyInteger(0, 1000)
    first_seen = factory.LazyFunction(lambda: timezone.now() - timedelta(days=random.randint(1,30)))
    last_seen = factory.LazyFunction(lambda: timezone.now() - timedelta(hours=random.randint(1,24)))
    is_blocked = fuzzy.FuzzyChoice([True, False])
    is_investigated = fuzzy.FuzzyChoice([True, False])
    severity = fuzzy.FuzzyInteger(1, 5)
    metadata = factory.LazyFunction(lambda: {'request_count': random.randint(1,100)})
    tenant = factory.SubFactory(TenantFactory)


class RateLimitExceptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RateLimitException
    user = factory.SubFactory(UserFactory)
    ip_address = None
    endpoint_pattern = None
    exception_type = fuzzy.FuzzyChoice(['whitelist','premium','emergency','maintenance','custom'])
    reason = factory.Faker('text', max_nb_chars=200)
    granted_by = factory.SubFactory(UserFactory)
    multiplier = fuzzy.FuzzyFloat(1.0, 10.0)
    max_requests = fuzzy.FuzzyInteger(100, 10000)
    is_active = True
    permanent = False
    usage_count = fuzzy.FuzzyInteger(0, 1000)
    tenant = factory.SubFactory(TenantFactory)

    @factory.lazy_attribute
    def expires_at(self):
        return timezone.now() + timedelta(days=random.randint(1,30)) if not self.permanent else None


class RateLimitInsightFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RateLimitInsight
        django_get_or_create = ('date', 'hour')
    date = factory.LazyFunction(lambda: (timezone.now() - timedelta(days=random.randint(0,30))).date())
    hour = None
    total_requests = fuzzy.FuzzyInteger(1000, 100000)
    allowed_requests = fuzzy.FuzzyInteger(800, 90000)
    blocked_requests = fuzzy.FuzzyInteger(100, 20000)
    top_abusers = factory.LazyFunction(lambda: [{'user_id': i, 'count': random.randint(50,500)} for i in range(3)])
    top_endpoints = factory.LazyFunction(lambda: [{'endpoint': f'/ep_{i}/', 'count': random.randint(100,1000)} for i in range(3)])
    top_ips = factory.LazyFunction(lambda: [{'ip': f'192.168.1.{i}', 'count': random.randint(50,500)} for i in range(3)])
    abuse_reports_count = fuzzy.FuzzyInteger(0, 100)
    auto_blocks_count = fuzzy.FuzzyInteger(0, 50)
    manual_blocks_count = fuzzy.FuzzyInteger(0, 20)
    avg_response_time = fuzzy.FuzzyFloat(100.0, 1000.0)
    peak_requests_per_minute = fuzzy.FuzzyInteger(100, 5000)
    peak_hour = fuzzy.FuzzyInteger(0, 23)
    unique_users = fuzzy.FuzzyInteger(100, 10000)
    unique_ips = fuzzy.FuzzyInteger(50, 5000)
    error_rate = fuzzy.FuzzyFloat(0.0, 10.0)
    tenant = factory.SubFactory(TenantFactory)


# Specialised factories
class PremiumUserRateLimitProfileFactory(UserRateLimitProfileFactory):
    is_premium = True
    premium_until = factory.LazyFunction(lambda: timezone.now() + timedelta(days=365))
    custom_daily_limit = fuzzy.FuzzyInteger(2000, 10000)
    api_health_score = fuzzy.FuzzyInteger(90, 100)


class SuspiciousUserRateLimitProfileFactory(UserRateLimitProfileFactory):
    suspicion_score = fuzzy.FuzzyInteger(70, 100)
    api_health_score = fuzzy.FuzzyInteger(20, 60)


class PermanentIPBlockFactory(IPBlockListFactory):
    permanent = True
    expires_at = None
    is_active = True


class TemporaryIPBlockFactory(IPBlockListFactory):
    permanent = False
    is_active = True
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=random.randint(1,7)))


class HighVolumeAbuseReportFactory(AbuseReportFactory):
    abuse_type = 'rate_limit'
    pattern = 'high_volume'
    severity = fuzzy.FuzzyInteger(4, 5)
    count_24h = fuzzy.FuzzyInteger(50, 200)
    is_blocked = True


class BotAbuseReportFactory(AbuseReportFactory):
    abuse_type = 'bot'
    pattern = 'bot_activity'
    user_agent = factory.LazyFunction(lambda: 'Python-urllib/3.8')


class BulkDataFactory:
    @staticmethod
    def create_complete_scenario():
        users = UserFactory.create_batch(5)
        configs = RateLimitConfigFactory.create_batch(3)
        profiles = [UserRateLimitProfileFactory.create(user=u) for u in users]
        logs = [RateLimitLogFactory.create(user=random.choice(users), config=random.choice(configs)) for _ in range(10)]
        reports = [AbuseReportFactory.create(user=random.choice(users)) for _ in range(5)]
        blocks = IPBlockListFactory.create_batch(3)
        return {'users': users, 'configs': configs, 'profiles': profiles, 'logs': logs, 'reports': reports, 'blocks': blocks}


class TestDataGenerator:
    @staticmethod
    def generate_ip_addresses(count=10):
        return [f'192.168.{random.randint(1,254)}.{random.randint(1,254)}' for _ in range(count)]

    @staticmethod
    def generate_endpoints(count=10):
        return [f'/api/endpoint_{i}/' for i in range(1, count + 1)]

    @staticmethod
    def generate_user_agents(count=5):
        return ['Mozilla/5.0'] * count

    @staticmethod
    def generate_abuse_patterns():
        return ['rapid_requests','high_volume','suspicious_pattern','bot_activity']

    @staticmethod
    def generate_time_series_data(days=30, base_value=1000):
        data = []
        for i in range(days):
            date = timezone.now().date() - timedelta(days=i)
            data.append({'date': date, 'value': base_value + random.randint(-200,200)})
        return data

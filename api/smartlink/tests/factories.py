import factory
import factory.fuzzy
from django.contrib.auth import get_user_model
from ..models import (
    SmartLink, SmartLinkGroup, SmartLinkTag, SmartLinkFallback,
    SmartLinkRotation, TargetingRule, GeoTargeting, DeviceTargeting,
    OfferPool, OfferPoolEntry, Click, ClickMetadata, UniqueClick,
    SmartLinkDailyStat, SmartLinkStat, ABTestResult, SmartLinkVersion,
)
from ..choices import SmartLinkType, DeviceType, RotationMethod

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'publisher_{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active = True


class SmartLinkGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SmartLinkGroup

    publisher = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f'Group {n}')
    is_active = True


class SmartLinkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SmartLink

    publisher = factory.SubFactory(UserFactory)
    slug = factory.Sequence(lambda n: f'testslug{n:04d}')
    name = factory.Sequence(lambda n: f'Test SmartLink {n}')
    type = SmartLinkType.GENERAL
    rotation_method = RotationMethod.WEIGHTED
    is_active = True
    is_archived = False
    enable_fraud_filter = True
    enable_bot_filter = True
    enable_unique_click = True


class SmartLinkFallbackFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SmartLinkFallback

    smartlink = factory.SubFactory(SmartLinkFactory)
    url = 'https://fallback.example.com'
    is_active = True


class SmartLinkRotationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SmartLinkRotation

    smartlink = factory.SubFactory(SmartLinkFactory)
    method = RotationMethod.WEIGHTED
    auto_optimize_epc = False


class TargetingRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TargetingRule

    smartlink = factory.SubFactory(SmartLinkFactory)
    logic = 'AND'
    is_active = True


class GeoTargetingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GeoTargeting

    rule = factory.SubFactory(TargetingRuleFactory)
    mode = 'whitelist'
    countries = ['US', 'GB', 'BD']


class DeviceTargetingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeviceTargeting

    rule = factory.SubFactory(TargetingRuleFactory)
    mode = 'whitelist'
    device_types = ['mobile', 'tablet']


class OfferPoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OfferPool

    smartlink = factory.SubFactory(SmartLinkFactory)
    is_active = True


class ClickFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Click

    smartlink = factory.SubFactory(SmartLinkFactory)
    ip = factory.fuzzy.FuzzyChoice(['1.2.3.4', '5.6.7.8', '192.168.1.1'])
    country = factory.fuzzy.FuzzyChoice(['US', 'GB', 'BD', 'IN', 'DE'])
    device_type = factory.fuzzy.FuzzyChoice(['mobile', 'desktop', 'tablet'])
    os = factory.fuzzy.FuzzyChoice(['android', 'ios', 'windows'])
    browser = factory.fuzzy.FuzzyChoice(['chrome', 'safari', 'firefox'])
    user_agent = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36'
    is_unique = True
    is_fraud = False
    is_bot = False
    is_converted = False
    fraud_score = 0
    payout = 0


class ClickMetadataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClickMetadata

    click = factory.SubFactory(ClickFactory)
    sub1 = factory.Sequence(lambda n: f'campaign_{n}')
    sub2 = factory.Sequence(lambda n: f'adset_{n}')
    sub3 = ''
    sub4 = ''
    sub5 = ''
    custom_params = {}


class SmartLinkDailyStatFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SmartLinkDailyStat

    smartlink = factory.SubFactory(SmartLinkFactory)
    date = factory.LazyFunction(lambda: __import__('django.utils.timezone', fromlist=['now']).now().date())
    clicks = 1000
    unique_clicks = 800
    conversions = 50
    revenue = 250.00
    epc = 0.25
    conversion_rate = 0.05
